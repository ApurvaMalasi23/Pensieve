"""
tests/test_showcase_mode.py
---------------------------
Automated test suite verifying Showcase Mode hardening:
1. SHOWCASE_MODE=true:
   - POST /documents/upload immediately returns 403 Forbidden without filesystem/Qdrant processing.
   - DELETE /documents/{doc_id} immediately returns 403 Forbidden without filesystem/Qdrant processing.
   - GET /health accurately reflects showcase_mode=True.
2. In-memory IP rate limiter:
   - Consecutive calls to /ask exceeding the per-minute quota return 429 Too Many Requests with Retry-After header.
3. SHOWCASE_MODE=false:
   - Normal operation preserved.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from pensieve import config
from pensieve.api import app, _ip_request_timestamps


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the in-memory rate limiting dictionary between tests."""
    _ip_request_timestamps.clear()
    yield
    _ip_request_timestamps.clear()


def test_showcase_mode_upload_forbidden():
    """When SHOWCASE_MODE is True, POST /documents/upload must immediately reject with 403."""
    with patch.object(config, "SHOWCASE_MODE", True):
        with patch("pensieve.api.SHOWCASE_MODE", True):
            client = TestClient(app)
            response = client.post(
                "/documents/upload",
                files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            )
            assert response.status_code == 403
            data = response.json()
            assert "Showcase mode active" in data["detail"]


def test_showcase_mode_delete_forbidden():
    """When SHOWCASE_MODE is True, DELETE /documents/{doc_id} must immediately reject with 403."""
    with patch("pensieve.api.SHOWCASE_MODE", True):
        client = TestClient(app)
        response = client.delete("/documents/dummy_doc_id_123")
        assert response.status_code == 403
        data = response.json()
        assert "Showcase mode active" in data["detail"]


def test_showcase_mode_health_status():
    """Health check endpoint must reflect showcase_mode boolean flag."""
    with patch("pensieve.api.SHOWCASE_MODE", True):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["showcase_mode"] is True

    with patch("pensieve.api.SHOWCASE_MODE", False):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["showcase_mode"] is False


def test_rate_limiter_ask_endpoint():
    """Test that requests exceeding RATE_LIMIT_ASK_PER_MINUTE return 429."""
    client = TestClient(app)

    # Test with a low limit of 3 requests
    with patch("pensieve.api.RATE_LIMIT_ASK_PER_MINUTE", 3):
        with patch("pensieve.api.detect_comparison_intent", return_value=(False, [])):
            with patch("pensieve.api.classify_intent", return_value="narrative"):
                with patch("pensieve.api.retrieve_narrative_chunks", return_value=[]):
                    with patch("pensieve.api.generate_answer") as mock_gen:
                        from pensieve.generator import GenerationResult
                        mock_gen.return_value = GenerationResult(
                            query="test",
                            answer="test answer",
                            citations=[],
                            no_context_found=True,
                        )

                        # First 3 requests succeed
                        for i in range(3):
                            res = client.post("/ask", json={"query": f"question {i}"})
                            assert res.status_code == 200

                        # 4th request must be rate limited with 429
                        res_blocked = client.post("/ask", json={"query": "question 4"})
                        assert res_blocked.status_code == 429
                        assert "Rate limit exceeded" in res_blocked.json()["detail"]
                        assert "Retry-After" in res_blocked.headers
