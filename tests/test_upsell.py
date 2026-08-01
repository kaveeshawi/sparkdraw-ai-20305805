"""
Tests for C2 Upsell Engine — ensemble-v2-calibrated ML model.
Model is mocked — never loads real .pkl files in CI.
"""

from unittest.mock import patch

import numpy as np

from routes.upsell import DEFAULT_FEATURE_ORDER

BASE_PAYLOAD = {
    "completion_pct": 0.90,
    "health_score": 85.0,
    "revision_count": 2,
    "approval_lag_hrs": 24.0,
    "budget_used_pct": 0.65,
    "sentiment_avg": 0.5,
    "project_age_days": 45,
    "invoice_count": 2,
    "days_since_last_revision": 7.0,
}


def _mock_model(probability: float):
    mock = patch("routes.upsell.get_model")
    patched = mock.start()
    clf = type("Clf", (), {})()
    clf.predict_proba = lambda X: np.array([[1 - probability, probability]])
    patched.return_value = (clf, DEFAULT_FEATURE_ORDER)
    return mock


def _post(client, payload: dict):
    return client.post("/upsell", json=payload)


def test_high_confidence_returns_upsell_ready(client):
    mock = _mock_model(0.82)
    try:
        r = _post(client, BASE_PAYLOAD)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["upsell_ready"] is True
        assert data["tier"] == "high"
        assert data["confidence"] == 0.82
        assert data["model_version"] == "ensemble-v2-calibrated"
        assert data["service"] == "upsell_recommended"
        assert len(data["signals"]) >= 1
    finally:
        mock.stop()


def test_medium_confidence_tier(client):
    mock = _mock_model(0.60)
    try:
        r = _post(client, BASE_PAYLOAD)
        data = r.json()["data"]
        assert data["tier"] == "medium"
        assert data["upsell_ready"] is True
    finally:
        mock.stop()


def test_low_confidence_not_upsell_ready(client):
    mock = _mock_model(0.40)
    try:
        r = _post(client, BASE_PAYLOAD)
        data = r.json()["data"]
        assert data["upsell_ready"] is False
        assert data["tier"] == "low"
        assert data["service"] is None
        assert data["reason"] == "timing_not_right"
    finally:
        mock.stop()


def test_missing_model_returns_503(client):
    with patch("routes.upsell.get_model", side_effect=FileNotFoundError("model missing")):
        r = _post(client, BASE_PAYLOAD)
        assert r.status_code == 503
