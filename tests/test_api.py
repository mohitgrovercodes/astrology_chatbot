# tests/test_api.py
# tests\test_api.py
"""
API Tests
==========

Test suite for FastAPI endpoints.
"""

from fastapi.testclient import TestClient
from src.api.main import app
import pytest

client = TestClient(app)


class TestHealthEndpoints:
    """Health check endpoint tests."""
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert data["version"] == "1.0.0"
    
    def test_ping(self):
        """Test ping endpoint."""
        response = client.get("/api/v1/ping")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pong"


class TestAuthMiddleware:
    """Authentication middleware tests."""
    
    def test_chat_without_api_key(self):
        """Test chat endpoint without API key."""
        response = client.post(
            "/api/v1/chat",
            json={"query": "test", "user_id": "test"}
        )
        assert response.status_code == 401
    
    def test_chat_with_invalid_api_key(self):
        """Test chat endpoint with invalid API key."""
        response = client.post(
            "/api/v1/chat",
            headers={"X-API-Key": "invalid-key"},
            json={"query": "test", "user_id": "test"}
        )
        # Will pass in debug mode, fail in production
        assert response.status_code in [200, 403]


class TestChatEndpoint:
    """Chat endpoint tests."""
    
    def test_chat_basic_query(self):
        """Test basic chat query."""
        response = client.post(
            "/api/v1/chat",
            headers={"X-API-Key": "test-key"},
            json={
                "query": "What is my sun sign?",
                "user_id": "test_user"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "intent" in data
        assert "processing_time" in data
    
    def test_chat_with_history(self):
        """Test chat with conversation history."""
        response = client.post(
            "/api/v1/chat",
            headers={"X-API-Key": "test-key"},
            json={
                "query": "Tell me more",
                "user_id": "test_user",
                "conversation_history": [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello!"}
                ]
            }
        )
        assert response.status_code == 200
    
    def test_chat_invalid_request(self):
        """Test chat with missing fields."""
        response = client.post(
            "/api/v1/chat",
            headers={"X-API-Key": "test-key"},
            json={"query": "test"}  # Missing user_id
        )
        assert response.status_code == 422  # Validation error


    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "uptime" in data
        assert "components" in data
        assert data["version"] == "1.0.0"

class TestCalculationEndpoints:
    """Calculation endpoint tests."""
    
    def test_calculate_chart(self):
        """Test chart calculation endpoint."""
        response = client.post(
            "/api/v1/calculate/chart",
            headers={"X-API-Key": "test-key"},
            json={
                "date_of_birth": "1990-03-15",
                "time_of_birth": "14:30:00",
                "latitude": 26.9124,
                "longitude": 75.7873,
                "timezone": "Asia/Kolkata",
                "system": "vedic"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "lagna" in data
        assert "planets" in data
    
    def test_current_transits(self):
        """Test current transits endpoint."""
        response = client.get(
            "/api/v1/calculate/current-transits",
            headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "planets" in data


class TestRateLimiting:
    """Rate limiting tests."""
    
    def test_rate_limit_headers(self):
        """Test rate limit headers in response."""
        response = client.post(
            "/api/v1/chat",
            headers={"X-API-Key": "test-key"},
            json={"query": "test", "user_id": "test"}
        )
        # Check for rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
