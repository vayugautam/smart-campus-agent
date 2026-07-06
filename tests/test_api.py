"""
test_api.py – Tests for the FastAPI endpoints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.data.seed import seed


client = TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_ok(self):
        """GET /health should return {"status": "ok"}."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestChatEndpoint:
    """Tests for POST /chat."""

    def test_chat_returns_reply(self):
        """POST /chat should return a ChatResponse with reply and thread_id."""
        response = client.post("/chat", json={"message": "When is the next hackathon?"})
        payload = response.json()

        assert response.status_code == 200
        assert payload["reply"]
        assert payload["thread_id"]

    def test_chat_creates_thread(self):
        """POST /chat without thread_id should create a new thread."""
        response = client.post("/chat", json={"message": "Tell me about the library."})
        payload = response.json()

        assert response.status_code == 200
        assert payload["thread_id"]

    def test_chat_continues_thread(self):
        """POST /chat with existing thread_id should continue the conversation."""
        seed()

        first = client.post("/chat", json={"message": "Book the lab for tomorrow at 8 AM."})
        first_payload = first.json()
        thread_id = first_payload["thread_id"]

        assert first.status_code == 200
        assert "facility name" in first_payload["reply"].lower()
        assert first_payload["waiting_on_confirmation"] is False

        second = client.post("/chat", json={"message": "Computer Lab 1", "thread_id": thread_id})
        second_payload = second.json()

        assert second.status_code == 200
        assert second_payload["thread_id"] == thread_id
        assert "facility name" not in second_payload["reply"].lower()
