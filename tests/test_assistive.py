"""
Tests for A1 Task Hour Estimator and A3 Project Brief Generator.
Mocks OpenAI via AIService — never hits the real API in tests.
"""
from unittest.mock import AsyncMock, patch

ESTIMATE_PAYLOAD = {
    "task_title": "Design homepage wireframes",
    "task_description": "Create responsive wireframes for the marketing homepage",
    "project_type": "web_design",
}

BRIEF_PAYLOAD = {
    "project_name": "NovaTech Rebrand",
    "project_type": "branding",
    "budget": 8000,
    "duration_weeks": 8,
}


def test_estimate_hours_returns_integer_and_reasoning(client):
    mocked_response = {
        "hours": 6,
        "reasoning": "UI tasks of this type typically take 4-8 hours",
    }

    with patch("routes.estimator.ai_service.estimate_hours", new=AsyncMock(return_value=mocked_response)):
        r = client.post("/estimate-hours", json=ESTIMATE_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert isinstance(body["data"]["hours"], int)
    assert body["data"]["hours"] == 6
    assert "reasoning" in body["data"]
    assert len(body["data"]["reasoning"]) > 0


def test_estimate_hours_falls_back_on_openai_failure(client):
    with patch(
        "routes.estimator.ai_service.estimate_hours",
        new=AsyncMock(side_effect=RuntimeError("OpenAI API error")),
    ):
        r = client.post("/estimate-hours", json=ESTIMATE_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["hours"] == 4
    assert body["data"]["reasoning"] == "Default estimate"


def test_brief_generator_returns_4_to_6_milestones(client):
    mocked_response = {
        "milestones": [
            {"title": "Discovery", "due_offset_days": 7, "description": "Research and kickoff"},
            {"title": "Wireframes", "due_offset_days": 14, "description": "Low-fi layouts"},
            {"title": "Visual Design", "due_offset_days": 28, "description": "Brand application"},
            {"title": "Development", "due_offset_days": 42, "description": "Build and integrate"},
            {"title": "Launch", "due_offset_days": 56, "description": "QA and go-live"},
        ],
        "estimated_hours": 120,
        "suggested_phases": ["Discovery", "Design", "Build", "Launch"],
        "risks": ["Scope creep", "Approval delays"],
    }

    with patch("routes.brief.ai_service.generate_brief", new=AsyncMock(return_value=mocked_response)):
        r = client.post("/brief-generator", json=BRIEF_PAYLOAD)

    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert 4 <= len(body["data"]["milestones"]) <= 6
    assert body["data"]["estimated_hours"] == 120
    assert isinstance(body["data"]["suggested_phases"], list)
    assert isinstance(body["data"]["risks"], list)
