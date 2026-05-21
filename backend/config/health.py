"""
Health check and readiness endpoints.

/health/ — lightweight liveness probe (always returns 200 if Django is running)
/ready/ — readiness probe that checks database and redis connectivity
"""

import logging

from django.http import JsonResponse
from django.db import connections
from django.views.decorators.http import require_http_methods

import redis

from backend.config.settings import REDIS_URL

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def health_check(request) -> JsonResponse:
    """Liveness probe — confirms the application process is running."""
    return JsonResponse({"status": "healthy", "service": "darts-tournament-backend"})


@require_http_methods(["GET"])
def readiness_check(request) -> JsonResponse:
    """
    Readiness probe — verifies all critical dependencies are reachable.

    Checks:
    - PostgreSQL database connection
    - Redis connection
    """
    checks: dict[str, str] = {}
    all_healthy = True

    # Check database
    try:
        db_conn = connections["default"]
        db_conn.ensure_connection()
        with db_conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
        logger.info("Database health check passed")
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        all_healthy = False
        logger.error("Database health check failed: %s", exc)

    # Check Redis
    try:
        client = redis.from_url(REDIS_URL)
        client.ping()
        checks["redis"] = "ok"
        logger.info("Redis health check passed")
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        all_healthy = False
        logger.error("Redis health check failed: %s", exc)

    status_code = 200 if all_healthy else 503
    response_status = "ready" if all_healthy else "not_ready"

    return JsonResponse(
        {"status": response_status, "checks": checks},
        status=status_code,
    )
