"""Production assistant provider status and safe outage behavior."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import groq_service
from app.main import app


def test_groq_health_reports_provider_status(monkeypatch):
    from app.routers import groq_chat

    monkeypatch.setattr(groq_chat, "is_healthy", lambda: False)
    response = TestClient(app).get("/groq-chat/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "offline",
        "model": groq_chat.GROQ_CHAT_MODEL,
        "project_context_loaded": True,
    }


def test_groq_outage_returns_friendly_message_and_preserves_authorized_sources(monkeypatch):
    doc = {
        "title": "Project PRJ-A-731001",
        "project_id": "PRJ-A-731001",
        "text": "Project PRJ-A-731001. Status: Ongoing.",
        "source_date": "2026-03-01",
        "score": 1.0,
    }
    monkeypatch.setattr(groq_service, "GROQ_API_KEY", "")
    monkeypatch.setattr(groq_service, "_route_query", lambda *_args: [doc])

    result = groq_service.production_chat.chat(
        db=None,
        question="What is the status of PRJ-A-731001?",
        user=SimpleNamespace(role="ministry", ministry="Ministry A"),
    )

    assert result["answer"] == groq_service._UNAVAILABLE
    assert [source["project_id"] for source in result["sources"]] == ["PRJ-A-731001"]


def test_groq_generation_error_is_handled_without_traceback(monkeypatch):
    monkeypatch.setattr(groq_service, "GROQ_API_KEY", "test-key")

    def unavailable(_request, timeout):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(groq_service.urllib.request, "urlopen", unavailable)
    assert groq_service._post_completion([]) is None
