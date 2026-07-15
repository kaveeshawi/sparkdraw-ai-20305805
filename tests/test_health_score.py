"""
Tests for C3 Health Score algorithm.
Validates deduction rules match CLAUDE.md Section 7 spec.
"""

PERFECT_PAYLOAD = {
    "project_id": 1,
    "revision_count": 1,
    "avg_revision_rate": 2.0,
    "hours_burn_ratio": 0.50,
    "approval_lag_avg_hours": 24.0,
    "deadline_slips": 0,
    "message_velocity_change": 0.0,
    "sentiment_trend": 0.0,
    "completion_pct": 0.75,
    "client_at_risk": False,
}


def _post(client, payload: dict):
    return client.post("/health-score", json=payload)


def test_perfect_project_scores_100(client):
    r = _post(client, PERFECT_PAYLOAD)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["score"] == 100
    assert data["flag"] == "green"
    assert data["reasons"] == []


def test_high_burn_with_low_completion_deducts_20_points(client):
    payload = {
        **PERFECT_PAYLOAD,
        "hours_burn_ratio": 0.90,
        "completion_pct": 0.40,
    }
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] == 80
    assert any("hours" in reason.lower() for reason in data["reasons"])


def test_high_burn_alone_does_not_deduct(client):
    payload = {**PERFECT_PAYLOAD, "hours_burn_ratio": 0.90, "completion_pct": 0.80}
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] == 100


def test_revision_risk_deducts_15_points(client):
    payload = {**PERFECT_PAYLOAD, "revision_count": 3, "avg_revision_rate": 1.0}
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] == 85
    assert any("revision" in reason.lower() for reason in data["reasons"])


def test_critical_client_sentiment_deducts_20_points(client):
    payload = {**PERFECT_PAYLOAD, "sentiment_trend": -0.85}
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] == 80
    assert any("critically" in reason.lower() for reason in data["reasons"])


def test_client_at_risk_deducts_15_points(client):
    payload = {**PERFECT_PAYLOAD, "client_at_risk": True}
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] == 85


def test_approval_lag_deducts_10_points(client):
    payload = {**PERFECT_PAYLOAD, "approval_lag_avg_hours": 72.0}
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] == 90
    assert any("approval" in reason.lower() for reason in data["reasons"])


def test_score_below_40_is_red(client):
    payload = {
        "project_id": 99,
        "revision_count": 4,
        "avg_revision_rate": 2.0,
        "hours_burn_ratio": 0.92,
        "approval_lag_avg_hours": 96.0,
        "deadline_slips": 1,
        "message_velocity_change": -0.8,
        "sentiment_trend": -0.85,
        "completion_pct": 0.30,
        "client_at_risk": True,
    }
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] < 40
    assert data["flag"] == "red"


def test_score_40_to_69_is_amber(client):
    payload = {
        **PERFECT_PAYLOAD,
        "revision_count": 6,
        "avg_revision_rate": 2.0,
        "hours_burn_ratio": 0.90,
        "completion_pct": 0.40,
    }
    r = _post(client, payload)
    data = r.json()["data"]
    assert 40 <= data["score"] <= 69
    assert data["flag"] == "amber"


def test_score_70_plus_is_green(client):
    payload = {
        **PERFECT_PAYLOAD,
        "hours_burn_ratio": 0.90,
        "completion_pct": 0.80,
    }
    r = _post(client, payload)
    data = r.json()["data"]
    assert data["score"] >= 70
    assert data["flag"] == "green"
