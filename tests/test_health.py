def test_health_check_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["service"] == "sparkdraw-ai"
    assert data["version"] == "1.0"
    assert "provider" in data
