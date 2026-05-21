"""
Tests for health check and readiness endpoints.
"""

import json
from unittest.mock import MagicMock, patch

from django.http import JsonResponse
from django.test import RequestFactory, TestCase, override_settings

from backend.config.health import health_check, readiness_check


class TestHealthCheck(TestCase):
    """Unit tests for the liveness probe endpoint."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_health_check_returns_200(self) -> None:
        request = self.factory.get("/health/")
        response = health_check(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["status"] == "healthy"
        assert data["service"] == "darts-tournament-backend"

    def test_health_check_only_allows_get(self) -> None:
        request = self.factory.post("/health/")
        response = health_check(request)

        assert response.status_code == 405


@override_settings(REDIS_URL="redis://localhost:6379/0")
class TestReadinessCheck(TestCase):
    """Unit tests for the readiness probe endpoint."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    @patch("backend.config.health.connections")
    @patch("backend.config.health.redis")
    def test_readiness_all_healthy(
        self, mock_redis_module: MagicMock, mock_connections: MagicMock
    ) -> None:
        # Mock database connection
        mock_db_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_db_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connections.__getitem__ = MagicMock(return_value=mock_db_conn)

        # Mock Redis connection
        mock_redis_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis_client

        request = self.factory.get("/ready/")
        response = readiness_check(request)

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["status"] == "ready"
        assert data["checks"]["database"] == "ok"
        assert data["checks"]["redis"] == "ok"

    @patch("backend.config.health.connections")
    @patch("backend.config.health.redis")
    def test_readiness_database_down(
        self, mock_redis_module: MagicMock, mock_connections: MagicMock
    ) -> None:
        # Mock database failure
        mock_connections.__getitem__ = MagicMock(
            side_effect=Exception("Connection refused")
        )

        # Mock Redis works
        mock_redis_client = MagicMock()
        mock_redis_module.from_url.return_value = mock_redis_client

        request = self.factory.get("/ready/")
        response = readiness_check(request)

        assert response.status_code == 503
        data = json.loads(response.content)
        assert data["status"] == "not_ready"
        assert "error" in data["checks"]["database"]

    @patch("backend.config.health.connections")
    @patch("backend.config.health.redis")
    def test_readiness_redis_down(
        self, mock_redis_module: MagicMock, mock_connections: MagicMock
    ) -> None:
        # Mock database works
        mock_db_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_db_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connections.__getitem__ = MagicMock(return_value=mock_db_conn)

        # Mock Redis failure
        mock_redis_client = MagicMock()
        mock_redis_client.ping.side_effect = Exception("Connection refused")
        mock_redis_module.from_url.return_value = mock_redis_client

        request = self.factory.get("/ready/")
        response = readiness_check(request)

        assert response.status_code == 503
        data = json.loads(response.content)
        assert data["status"] == "not_ready"
        assert "error" in data["checks"]["redis"]
