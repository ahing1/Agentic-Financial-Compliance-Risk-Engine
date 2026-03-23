"""
tests/test_routes.py — API Endpoint Integration Tests

Tests the actual HTTP endpoints using FastAPI's TestClient.
TestClient simulates HTTP requests without starting a real server —
it's fast and doesn't need an open port.

These tests verify:
- Correct status codes (200, 404, 422)
- Response shape matches schemas
- Error handling works for bad input
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.middleware.auth import get_current_user


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI app.

    TestClient wraps the app and lets you make requests like:
        response = client.get("/health")
        response = client.post("/filings/analyze", json={...})

    No real HTTP server is started — requests go directly to the app.
    """
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """
    Test client with auth bypassed.

    Overrides the get_current_user dependency so filing endpoints
    can be tested without a real user/token in the database.
    """
    app.dependency_overrides[get_current_user] = lambda: "test-user-id"
    yield client
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    
    def test_health_returns_200(self, client):
        """Health check responds with 200 when services are up."""
        response = client.get("/health")
        # Health might return 503 if Redis isn't running in test env.
        # We just verify the endpoint exists and returns valid JSON.
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data


class TestRootEndpoint:
    
    def test_root_returns_api_info(self, client):
        """Root endpoint confirms the API is running."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestFilingEndpoints:

    def test_analyze_rejects_empty_ticker(self, auth_client):
        """POST /filings/analyze rejects empty ticker with 422."""
        response = auth_client.post(
            "/filings/analyze",
            json={"ticker": "", "filing_type": "10-K"},
        )
        assert response.status_code == 422

    def test_analyze_rejects_invalid_filing_type(self, auth_client):
        """POST /filings/analyze rejects invalid filing type."""
        response = auth_client.post(
            "/filings/analyze",
            json={"ticker": "AAPL", "filing_type": "8-K"},
        )
        assert response.status_code == 422

    def test_analyze_rejects_numeric_ticker(self, auth_client):
        """POST /filings/analyze rejects tickers with numbers."""
        response = auth_client.post(
            "/filings/analyze",
            json={"ticker": "ABC123", "filing_type": "10-K"},
        )
        assert response.status_code == 422

    def test_status_returns_404_for_unknown_filing(self, auth_client):
        """GET /filings/{id}/status returns 404 for non-existent filing."""
        response = auth_client.get("/filings/00000000-0000-0000-0000-000000000000/status")
        assert response.status_code == 404

    def test_report_returns_404_for_unknown_filing(self, auth_client):
        """GET /filings/{id}/report returns 404 for non-existent filing."""
        response = auth_client.get("/filings/00000000-0000-0000-0000-000000000000/report")
        assert response.status_code == 404

    def test_history_returns_paginated_response(self, auth_client):
        """GET /filings/history returns proper pagination structure."""
        response = auth_client.get("/filings/history")
        assert response.status_code == 200
        data = response.json()
        assert "filings" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["filings"], list)

    def test_history_accepts_pagination_params(self, auth_client):
        """GET /filings/history respects page and page_size params."""
        response = auth_client.get("/filings/history?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_history_rejects_invalid_page(self, auth_client):
        """GET /filings/history rejects page < 1."""
        response = auth_client.get("/filings/history?page=0")
        assert response.status_code == 422

    def test_history_rejects_oversized_page(self, auth_client):
        """GET /filings/history rejects page_size > 100."""
        response = auth_client.get("/filings/history?page_size=500")
        assert response.status_code == 422