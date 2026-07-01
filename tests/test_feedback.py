"""
Tests for C1 NLP Feedback Translator endpoint (/analyze-feedback).
Mocks the OpenAI call via AIService — never hits the real API in tests.
"""
from unittest.mock import AsyncMock, patch

VALID_PAYLOAD = {
    "feedback_text": "Make the homepage feel more premium and modern.",
    "project_type": "web_development",
    "project_id": 1,
}


def test_analyze_feedback_returns_structured_ticket(client):
    mocked_response = {
        "title": "Homepage premium upgrade",
        "category": "ui",
        "priority": "medium",
        "subtasks": ["Typography scale audit", "Spacing review", "Button refinement"],
        "assigned_role": "designer",
        "estimated_hours": 6,
    }

    with patch("routes.feedback.ai_service.analyze_feedback", new=AsyncMock(return_value=mocked_response)):
        r = client.post("/analyze-feedback", json=VALID_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["title"] == "Homepage premium upgrade"
    assert body["data"]["category"] == "ui"
    assert body["data"]["subtasks"] == ["Typography scale audit", "Spacing review", "Button refinement"]
    assert body["data"]["estimated_hours"] == 6


def test_analyze_feedback_falls_back_when_response_missing_fields(client):
    # Malformed AI response — missing required fields — must return safe fallback, never crash
    mocked_response = {"title": "Incomplete ticket"}

    with patch("routes.feedback.ai_service.analyze_feedback", new=AsyncMock(return_value=mocked_response)):
        r = client.post("/analyze-feedback", json=VALID_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["category"] in {"ui", "backend", "content", "design", "bug"}
    assert isinstance(body["data"]["subtasks"], list)


def test_analyze_feedback_handles_openai_failure_gracefully(client):
    with patch(
        "routes.feedback.ai_service.analyze_feedback",
        new=AsyncMock(side_effect=RuntimeError("OpenAI API error: rate limit exceeded")),
    ):
        r = client.post("/analyze-feedback", json=VALID_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert "rate limit" in body["message"].lower()


def test_feedback_text_too_short_returns_422(client):
    payload = {**VALID_PAYLOAD, "feedback_text": "too short"}
    r = client.post("/analyze-feedback", json=payload)
    assert r.status_code == 422
