from fastapi import APIRouter
from pydantic import BaseModel

from services.ai_service import AIService

router = APIRouter()
ai_service = AIService()

FALLBACK_DIGEST = {"summary": "This week the team made steady progress on your project. We will share a detailed update once more activity is logged."}


class DigestRequest(BaseModel):
    project_name: str
    client_name: str
    events_summary: str


def _validate_digest(data: dict) -> dict:
    if not isinstance(data, dict):
        return dict(FALLBACK_DIGEST)

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return dict(FALLBACK_DIGEST)

    return {"summary": summary.strip()}


@router.post("")
async def generate_digest(req: DigestRequest):
    try:
        raw = await ai_service.generate_digest(
            req.project_name,
            req.client_name,
            req.events_summary,
        )
    except Exception:
        return {"success": True, "data": dict(FALLBACK_DIGEST)}

    return {"success": True, "data": _validate_digest(raw)}
