from fastapi import APIRouter
from pydantic import BaseModel

from services.ai_service import AIService

router = APIRouter()
ai_service = AIService()

FALLBACK_BRIEF = {
    "milestones": [
        {"title": "Discovery & Kickoff", "due_offset_days": 7, "description": "Align on goals and scope"},
        {"title": "Design Phase", "due_offset_days": 21, "description": "Wireframes and visual design"},
        {"title": "Development", "due_offset_days": 42, "description": "Build and integrate features"},
        {"title": "QA & Launch", "due_offset_days": 56, "description": "Testing and go-live"},
    ],
    "estimated_hours": 80,
    "suggested_phases": ["Discovery", "Design", "Development", "Launch"],
    "risks": ["Scope creep from unclear requirements", "Client approval delays"],
}


class BriefRequest(BaseModel):
    project_name: str
    project_type: str
    service_description: str = ""
    budget: float
    duration_weeks: int


def _validate_brief(data: dict) -> dict:
    if not isinstance(data, dict):
        return dict(FALLBACK_BRIEF)

    milestones = data.get("milestones")
    estimated_hours = data.get("estimated_hours")
    suggested_phases = data.get("suggested_phases")
    risks = data.get("risks")

    if not isinstance(milestones, list) or len(milestones) < 4:
        return dict(FALLBACK_BRIEF)

    clean_milestones = []
    for m in milestones[:6]:
        if not isinstance(m, dict) or not isinstance(m.get("title"), str):
            continue
        clean_milestones.append({
            "title": m["title"].strip(),
            "due_offset_days": int(m.get("due_offset_days", 7)) if isinstance(m.get("due_offset_days"), (int, float)) else 7,
            "description": str(m.get("description", "")).strip(),
        })

    if len(clean_milestones) < 4:
        return dict(FALLBACK_BRIEF)

    if not isinstance(estimated_hours, (int, float)) or isinstance(estimated_hours, bool):
        estimated_hours = FALLBACK_BRIEF["estimated_hours"]
    else:
        estimated_hours = max(1, int(estimated_hours))

    if not isinstance(suggested_phases, list) or not all(isinstance(p, str) for p in suggested_phases):
        suggested_phases = FALLBACK_BRIEF["suggested_phases"]
    else:
        suggested_phases = suggested_phases[:4]

    if not isinstance(risks, list) or not all(isinstance(r, str) for r in risks):
        risks = FALLBACK_BRIEF["risks"]
    else:
        risks = risks[:3]

    return {
        "milestones": clean_milestones,
        "estimated_hours": estimated_hours,
        "suggested_phases": suggested_phases,
        "risks": risks,
    }


@router.post("")
async def generate_brief(req: BriefRequest):
    try:
        raw = await ai_service.generate_brief(
            req.project_name,
            req.project_type,
            req.budget,
            req.duration_weeks,
            req.service_description,
        )
    except Exception:
        return {"success": True, "data": dict(FALLBACK_BRIEF)}

    return {"success": True, "data": _validate_brief(raw)}
