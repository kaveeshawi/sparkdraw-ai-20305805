from pathlib import Path

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

_MODEL = None
_FEATURE_NAMES = None

DEFAULT_FEATURE_ORDER = [
    "completion_pct",
    "health_score",
    "revision_count",
    "approval_lag_hrs",
    "budget_used_pct",
    "sentiment_avg",
    "project_age_days",
    "invoice_count",
    "days_since_last_revision",
]

# Ranked service catalog — model confidence ranks these; UI lets admin pick & send.
SERVICE_POOL = [
    "premium_retainer",
    "seo_package",
    "monthly_maintenance",
    "performance_audit",
    "content_retainer",
    "brand_extension",
    "nurture_followup",
]


class UpsellRequest(BaseModel):
    completion_pct: float
    health_score: float
    revision_count: int
    approval_lag_hrs: float
    budget_used_pct: float
    sentiment_avg: float
    project_age_days: int
    invoice_count: int = 1
    days_since_last_revision: float = 14.0


def get_model():
    """Lazy-load ML model + feature names once per process."""
    global _MODEL, _FEATURE_NAMES

    if _MODEL is not None:
        return _MODEL, _FEATURE_NAMES

    model_path = MODELS_DIR / "upsell_model_v2.pkl"
    features_path = MODELS_DIR / "feature_names.pkl"

    if not model_path.exists():
        raise FileNotFoundError(f"Upsell model not found at {model_path}")

    _MODEL = joblib.load(model_path)
    _FEATURE_NAMES = joblib.load(features_path) if features_path.exists() else DEFAULT_FEATURE_ORDER

    return _MODEL, _FEATURE_NAMES


def _build_feature_vector(req: UpsellRequest, feature_names: list[str]):
    values = {
        "completion_pct": req.completion_pct,
        "health_score": req.health_score,
        "revision_count": req.revision_count,
        "approval_lag_hrs": req.approval_lag_hrs,
        "budget_used_pct": req.budget_used_pct,
        "sentiment_avg": req.sentiment_avg,
        "project_age_days": req.project_age_days,
        "invoice_count": req.invoice_count,
        "days_since_last_revision": req.days_since_last_revision,
    }
    row = {name: values[name] for name in feature_names}
    return pd.DataFrame([row])


def _rank_services(req: UpsellRequest, tier: str) -> list[str]:
    """Pick 2–3 distinct services ordered by fit for this project."""
    scored: list[tuple[float, str]] = []

    for svc in SERVICE_POOL:
        score = 0.0
        if svc == "premium_retainer":
            score = req.completion_pct * 40 + (req.health_score / 100) * 30 + max(req.sentiment_avg, 0) * 20
            if tier == "high":
                score += 25
        elif svc == "seo_package":
            score = req.completion_pct * 25 + (1 - min(req.budget_used_pct, 1)) * 20 + 15
        elif svc == "monthly_maintenance":
            score = req.completion_pct * 35 + (req.project_age_days / 90) * 15 + 10
        elif svc == "performance_audit":
            score = (1 - min(req.health_score / 100, 1)) * 25 + req.revision_count * 4 + 12
        elif svc == "content_retainer":
            score = max(req.sentiment_avg, 0) * 30 + req.invoice_count * 5 + 10
        elif svc == "brand_extension":
            score = (req.health_score / 100) * 20 + req.completion_pct * 15 + 8
        elif svc == "nurture_followup":
            score = 18
            if tier == "low" or req.sentiment_avg < 0:
                score += 30
            if req.completion_pct < 0.55:
                score += 15

        scored.append((score, svc))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Always surface primary tier label first when high/medium
    primary = {
        "high": "premium_retainer",
        "medium": "upsell_recommended",
        "low": "nurture_followup",
    }.get(tier, "upsell_recommended")

    ordered: list[str] = []
    if primary not in ordered:
        ordered.append(primary)
    for _, svc in scored:
        if svc not in ordered:
            ordered.append(svc)
        if len(ordered) >= 3:
            break

    return ordered[:3]


def predict_upsell(req: UpsellRequest) -> dict:
    model, feature_names = get_model()
    names = list(feature_names or DEFAULT_FEATURE_ORDER)
    X = _build_feature_vector(req, names)

    confidence = float(model.predict_proba(X)[0][1])

    if confidence >= 0.75:
        tier = "high"
    elif confidence >= 0.55:
        tier = "medium"
    else:
        tier = "low"

    signals = []
    if req.completion_pct >= 0.70:
        signals.append(f"project {req.completion_pct * 100:.0f}% complete")
    if req.health_score >= 65:
        signals.append(f"health score {req.health_score:.0f}")
    if req.sentiment_avg >= 0.1:
        signals.append("positive client sentiment")
    if req.revision_count <= 3:
        signals.append("low revision pressure")

    upsell_ready = confidence >= 0.55
    ranked = _rank_services(req, tier)

    # Decaying confidence so options are distinguishable in the UI
    decays = [1.0, 0.88, 0.76]
    options = []
    for i, svc in enumerate(ranked):
        options.append({
            "service": svc,
            "confidence": round(max(0.05, min(0.99, confidence * decays[i])), 4),
            "rank": i + 1,
        })

    service = options[0]["service"] if options else "upsell_recommended"

    return {
        "upsell_ready": upsell_ready,
        "confidence": round(confidence, 4),
        "tier": tier,
        "signals": signals,
        "model_version": "ensemble-v2-calibrated",
        "service": service,
        "options": options,
        "reason": None if upsell_ready else "timing_not_right",
    }


@router.post("")
async def upsell_endpoint(req: UpsellRequest):
    try:
        result = predict_upsell(req)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"success": True, "data": result}
