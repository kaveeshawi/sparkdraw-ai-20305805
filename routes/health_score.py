from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthScoreRequest(BaseModel):
    project_id: int
    revision_count: int
    avg_revision_rate: float       # agency average revisions per project
    hours_burn_ratio: float        # actual_hours / estimated_hours
    approval_lag_avg_hours: float  # average hours between requested_at and responded_at
    deadline_slips: int            # number of missed milestone deadlines
    message_velocity_change: float # fractional change in client message frequency (negative = drop)
    sentiment_trend: float         # avg client sentiment over last 30 days (-1 to +1)
    completion_pct: float = 1.0    # fraction of tasks marked done (0–1)
    client_at_risk: bool = False   # 3+ consecutive negative client messages


def compute_health_score(req: HealthScoreRequest) -> dict:
    """
    C3 — Project Health Score (rule-based V1).
    Inputs are computed live from DB metrics in Laravel (getAIMetrics).
    """
    score = 100
    reasons: list[str] = []

    # Revision rate — scope creep (CLAUDE.md C3)
    if req.revision_count >= 4:
        score -= 25
        reasons.append("Revision rate critically high (R4+)")
    elif req.revision_count > req.avg_revision_rate * 1.5:
        score -= 15
        reasons.append("Revision rate above agency average")
    elif req.revision_count >= 3:
        score -= 10
        reasons.append("Multiple revision rounds (R3+)")

    # Hours burn only penalises when progress is also lagging (CLAUDE.md C3)
    if req.hours_burn_ratio > 0.85 and req.completion_pct < 0.5:
        burn_pct = round(req.hours_burn_ratio * 100, 1)
        done_pct = round(req.completion_pct * 100, 1)
        score -= 20
        reasons.append(
            f"Hours at {burn_pct}% with {done_pct}% of work remaining"
        )

    if req.approval_lag_avg_hours > 48:
        lag = round(req.approval_lag_avg_hours, 1)
        score -= 10
        reasons.append(f"Client approval averaging {lag} hours")

    if req.deadline_slips > 0:
        deduction = min(req.deadline_slips * 15, 30)
        score -= deduction
        reasons.append(f"Milestone deadline slipped {req.deadline_slips} time(s)")

    if req.message_velocity_change < -0.5:
        score -= 10
        reasons.append("Client communication frequency dropped")

    # Client sentiment — same signal as the sentiment timeline (tiered)
    if req.sentiment_trend < -0.7:
        score -= 20
        reasons.append("Client sentiment critically low")
    elif req.sentiment_trend < -0.5:
        score -= 15
        reasons.append("Client sentiment negative")
    elif req.sentiment_trend < -0.3:
        score -= 10
        reasons.append("Client sentiment declining")

    if req.client_at_risk:
        score -= 15
        reasons.append("Three consecutive negative client messages")

    score = max(0, score)

    if score >= 70:
        flag = "green"
    elif score >= 40:
        flag = "amber"
    else:
        flag = "red"

    return {
        "score": score,
        "flag": flag,
        "reasons": reasons,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("")
async def get_health_score(req: HealthScoreRequest):
    result = compute_health_score(req)
    return {"success": True, "data": result}
