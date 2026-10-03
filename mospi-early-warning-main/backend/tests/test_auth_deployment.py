"""Deployment readiness and safe authentication fallback coverage."""

from fastapi.testclient import TestClient

from app.main import app
from app.routers import auth


client = TestClient(app)


def test_auth_status_reports_provider_readiness(monkeypatch):
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(auth, "AUTH_DEMO_MODE", False)

    response = client.get("/auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "google_login_enabled": True,
        "demo_login_enabled": False,
    }


def test_google_login_fails_clearly_when_oauth_not_configured(monkeypatch):
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_SECRET", "")

    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code == 503
    assert "GOOGLE_CLIENT_ID" in response.json()["detail"]


def test_demo_role_login_is_closed_unless_explicitly_enabled(monkeypatch):
    monkeypatch.setattr(auth, "AUTH_DEMO_MODE", False)

    response = client.post("/auth/demo-login", json={"role": "admin"})

    assert response.status_code == 404


def test_google_login_uses_configured_callback(monkeypatch):
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(auth, "GOOGLE_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(auth, "GOOGLE_REDIRECT_URI", "https://api.example.test/auth/google/callback")

    response = client.get("/auth/google/login", follow_redirects=False)

    assert response.status_code == 302
    assert "client_id=client-id" in response.headers["location"]
    assert "redirect_uri=https%3A%2F%2Fapi.example.test%2Fauth%2Fgoogle%2Fcallback" in response.headers["location"]
