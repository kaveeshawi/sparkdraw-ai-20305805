from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from services.ai_service import AIService

router = APIRouter()
ai_service = AIService()

ALLOWED_CATEGORIES = {"ui", "backend", "content", "design", "bug"}
ALLOWED_PRIORITIES = {"low", "medium", "high"}
ALLOWED_ROLES = {"developer", "designer", "both"}

FALLBACK_TICKET = {
    "title": "Review client feedback",
    "category": "ui",
    "priority": "medium",
    "subtasks": ["Review feedback with client", "Clarify requirements"],
    "assigned_role": "both",
    "estimated_hours": 2,
}


class FeedbackRequest(BaseModel):
    feedback_text: str
    project_type: str
    project_id: int

    @field_validator("feedback_text")
    @classmethod
    def validate_feedback_text(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("feedback_text must be at least 10 characters")
        if len(v) > 2000:
            raise ValueError("feedback_text must not exceed 2000 characters")
        return v


def _validate_ticket(data: dict) -> dict:
    """Validate the AI response against the C1 ticket schema — return a safe fallback if malformed."""
    if not isinstance(data, dict):
        return dict(FALLBACK_TICKET)

    title = data.get("title")
    category = data.get("category")
    priority = data.get("priority")
    subtasks = data.get("subtasks")
    assigned_role = data.get("assigned_role")
    estimated_hours = data.get("estimated_hours")

    if not isinstance(title, str) or not title.strip():
        return dict(FALLBACK_TICKET)
    if category not in ALLOWED_CATEGORIES:
        return dict(FALLBACK_TICKET)
    if priority not in ALLOWED_PRIORITIES:
        return dict(FALLBACK_TICKET)
    if not isinstance(subtasks, list) or not all(isinstance(s, str) for s in subtasks):
        return dict(FALLBACK_TICKET)
    if assigned_role not in ALLOWED_ROLES:
        return dict(FALLBACK_TICKET)
    if not isinstance(estimated_hours, int) or isinstance(estimated_hours, bool):
        return dict(FALLBACK_TICKET)

    return {
        "title": title.strip(),
        "category": category,
        "priority": priority,
        "subtasks": subtasks[:4],
        "assigned_role": assigned_role,
        "estimated_hours": estimated_hours,
    }


@router.post("")
async def analyze_feedback(req: FeedbackRequest):
    try:
        raw = await ai_service.analyze_feedback(req.feedback_text, req.project_type)
    except Exception as exc:
        return {"success": False, "message": str(exc)}

    ticket = _validate_ticket(raw)
    return {"success": True, "data": ticket}
