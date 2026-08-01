from fastapi import APIRouter
from pydantic import BaseModel, field_validator

router = APIRouter()


class SentimentRequest(BaseModel):
    text: str
    project_id: int
    message_id: int

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("text must not be empty")
        return v


@router.post("")
async def analyze_sentiment(req: SentimentRequest):
    # TODO Session 4.2 — replace with real OpenAI call
    return {
        "success": True,
        "data": {
            "score": 0.0,
            "label": "neutral",
        },
    }
