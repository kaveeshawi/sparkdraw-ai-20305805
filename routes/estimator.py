from fastapi import APIRouter
from pydantic import BaseModel

from services.ai_service import AIService

router = APIRouter()
ai_service = AIService()

FALLBACK_ESTIMATE = {"hours": 4, "reasoning": "Default estimate"}


class EstimateHoursRequest(BaseModel):
    task_title: str
    task_description: str
    project_type: str


def _validate_estimate(data: dict) -> dict:
    if not isinstance(data, dict):
        return dict(FALLBACK_ESTIMATE)

    hours = data.get("hours")
    reasoning = data.get("reasoning")

    if not isinstance(hours, (int, float)) or isinstance(hours, bool):
        return dict(FALLBACK_ESTIMATE)

    hours = max(1, min(40, int(hours)))

    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = FALLBACK_ESTIMATE["reasoning"]

    return {"hours": hours, "reasoning": reasoning.strip()}


@router.post("")
async def estimate_hours(req: EstimateHoursRequest):
    try:
        raw = await ai_service.estimate_hours(
            req.task_title,
            req.task_description or "",
            req.project_type,
        )
    except Exception:
        return {"success": True, "data": dict(FALLBACK_ESTIMATE)}

    return {"success": True, "data": _validate_estimate(raw)}
