# tests/test_chat_stateless_smoke.py
"""
Smoke tests for stateless chat API (2-step: initialize then message).
Uses TestClient; requires Redis for full flow.
"""

import sys
import os

# Add project root to path so "src" is importable (same as test_stateless_architecture.py)
_test_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.abspath(os.path.join(_test_dir, ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

# Valid user profile for /initialize (UserProfile requires user_id in nested object)
INIT_PAYLOAD = {
    "user_id": "smoke-test-user-001",
    "user_profile": {
        "user_id": "smoke-test-user-001",
        "name": "Smoke Test User",
        "date_of_birth": "1990-05-15",
        "time_of_birth": "14:30:00",
        "place_of_birth": "New Delhi, India",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "timezone": "Asia/Kolkata",
        "preferred_system": "vedic",
    },
    "conversation_history": [],
}


class TestStatelessChatSmoke:
    """Smoke tests for /api/v1/chat/initialize and /api/v1/chat/message."""

    def test_initialize_returns_200_or_500(self):
        """Initialize accepts valid payload; 500 if Redis down."""
        r = client.post("/api/v1/chat/initialize", json=INIT_PAYLOAD)
        assert r.status_code in (200, 500), f"Expected 200 or 500, got {r.status_code}"

    def test_message_without_initialize_gives_404(self):
        """Message with unknown user_id returns 404 (session not found)."""
        r = client.post(
            "/api/v1/chat/message",
            json={"user_id": "nonexistent-user-999", "question": "Hello"},
        )
        assert r.status_code == 404, f"Expected 404 (session not found), got {r.status_code}"

    def test_message_request_validation(self):
        """Missing question or user_id yields 422."""
        r = client.post("/api/v1/chat/message", json={"user_id": "u1"})
        assert r.status_code == 422
        r = client.post("/api/v1/chat/message", json={"question": "Hi"})
        assert r.status_code == 422

    def test_initialize_request_validation(self):
        """Missing required fields in initialize yields 422."""
        r = client.post("/api/v1/chat/initialize", json={"user_id": "u1"})
        assert r.status_code == 422
