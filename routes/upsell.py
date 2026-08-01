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

    return {
        "upsell_ready": upsell_ready,
        "confidence": round(confidence, 4),
        "tier": tier,
        "signals": signals,
        "model_version": "ensemble-v2-calibrated",
        # Laravel AIBridgeController compatibility
        "service": "upsell_recommended" if upsell_ready else None,
        "reason": None if upsell_ready else "timing_not_right",
    }


@router.post("")
async def upsell_endpoint(req: UpsellRequest):
    try:
        result = predict_upsell(req)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"success": True, "data": result}
