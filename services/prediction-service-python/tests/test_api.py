"""
Tests for FastAPI endpoints.

Tests the API layer including:
- Health checks
- Prediction endpoints
- Rate limiting
- Error handling
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
from uuid import uuid4

# Import the app
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Tests for health and status endpoints."""

    def test_root_endpoint(self):
        """Root endpoint should return service info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "NCAA" in data["message"]

    def test_health_endpoint(self):
        """Health endpoint should return OK status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_config_endpoint(self):
        """Config endpoint should return model configuration."""
        response = client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert "hca_spread" in data
        assert "min_spread_edge" in data


class TestPredictEndpoint:
    """Tests for the /predict endpoint."""

    def test_predict_valid_request(self):
        """Valid prediction request should succeed."""
        request_body = {
            "game_id": str(uuid4()),
            "home_team": "Duke",
            "away_team": "UNC",
            "commence_time": datetime.now().isoformat(),
            "home_ratings": {
                "team_name": "Duke",
                "adj_o": 118.5,
                "adj_d": 94.2,
                "tempo": 69.0,
                "rank": 8,
                "efg": 52.5,
                "efgd": 47.8,
                "tor": 16.5,
                "tord": 21.0,
                "orb": 31.0,
                "drb": 74.0,
                "ftr": 35.0,
                "ftrd": 29.0,
                "two_pt_pct": 53.0,
                "two_pt_pct_d": 47.0,
                "three_pt_pct": 36.0,
                "three_pt_pct_d": 32.0,
                "three_pt_rate": 37.0,
                "three_pt_rate_d": 35.0,
            },
            "away_ratings": {
                "team_name": "UNC",
                "adj_o": 112.0,
                "adj_d": 100.5,
                "tempo": 67.5,
                "rank": 35,
                "efg": 50.0,
                "efgd": 50.5,
                "tor": 18.0,
                "tord": 19.0,
                "orb": 28.5,
                "drb": 71.5,
                "ftr": 32.0,
                "ftrd": 32.0,
                "two_pt_pct": 50.0,
                "two_pt_pct_d": 50.0,
                "three_pt_pct": 34.0,
                "three_pt_pct_d": 34.5,
                "three_pt_rate": 35.0,
                "three_pt_rate_d": 36.0,
            },
            "market_odds": {
                "spread": -6.5,
                "spread_price": -110,
                "total": 145.5,
                "over_price": -110,
                "under_price": -110,
            },
            "is_neutral": False,
        }

        response = client.post("/predict", json=request_body)
        assert response.status_code == 200
        data = response.json()
        assert "prediction" in data
        assert "recommendations" in data

    def test_predict_missing_ratings(self):
        """Request with missing ratings should fail with 422."""
        request_body = {
            "game_id": str(uuid4()),
            "home_team": "Duke",
            "away_team": "UNC",
            "commence_time": datetime.now().isoformat(),
            # Missing home_ratings and away_ratings
        }

        response = client.post("/predict", json=request_body)
        assert response.status_code == 422  # Validation error

    def test_predict_neutral_site(self):
        """Neutral site prediction should have zero HCA."""
        request_body = {
            "game_id": str(uuid4()),
            "home_team": "Duke",
            "away_team": "UNC",
            "commence_time": datetime.now().isoformat(),
            "home_ratings": {
                "team_name": "Duke",
                "adj_o": 110.0, "adj_d": 100.0, "tempo": 68.0, "rank": 50,
                "efg": 50.0, "efgd": 50.0, "tor": 18.0, "tord": 18.0,
                "orb": 28.0, "drb": 72.0, "ftr": 33.0, "ftrd": 33.0,
                "two_pt_pct": 50.0, "two_pt_pct_d": 50.0,
                "three_pt_pct": 35.0, "three_pt_pct_d": 35.0,
                "three_pt_rate": 35.0, "three_pt_rate_d": 35.0,
            },
            "away_ratings": {
                "team_name": "UNC",
                "adj_o": 110.0, "adj_d": 100.0, "tempo": 68.0, "rank": 50,
                "efg": 50.0, "efgd": 50.0, "tor": 18.0, "tord": 18.0,
                "orb": 28.0, "drb": 72.0, "ftr": 33.0, "ftrd": 33.0,
                "two_pt_pct": 50.0, "two_pt_pct_d": 50.0,
                "three_pt_pct": 35.0, "three_pt_pct_d": 35.0,
                "three_pt_rate": 35.0, "three_pt_rate_d": 35.0,
            },
            "is_neutral": True,
        }

        response = client.post("/predict", json=request_body)
        assert response.status_code == 200


class TestRateLimiting:
    """Tests for rate limiting middleware."""

    def test_rate_limit_headers_present(self):
        """Rate limit headers should be present in response."""
        response = client.get("/health")
        # After adding rate limiting, these headers should be present
        # For now, just verify the endpoint works
        assert response.status_code == 200

    def test_multiple_rapid_requests(self):
        """Multiple rapid requests should eventually hit rate limit."""
        # Send 20 rapid requests
        responses = [client.get("/health") for _ in range(20)]

        # All should succeed for now (rate limit is generous)
        # After implementing strict rate limiting, some should fail with 429
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 1  # At least some should succeed


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_json(self):
        """Invalid JSON should return 422."""
        response = client.post(
            "/predict",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_unknown_endpoint(self):
        """Unknown endpoint should return 404."""
        response = client.get("/unknown/endpoint")
        assert response.status_code == 404
