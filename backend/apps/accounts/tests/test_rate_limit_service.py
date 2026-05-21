"""Unit tests for RateLimitService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache

from backend.apps.accounts.services.rate_limit_service import (
    MAX_LOGIN_ATTEMPTS,
    MAX_REGISTRATION_PER_IP,
    LOGIN_LOCKOUT_MINUTES,
    REGISTRATION_LOCKOUT_MINUTES,
    RateLimitResult,
    RateLimitService,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Clear cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def service() -> RateLimitService:
    return RateLimitService()


class TestRateLimitServiceLogin:
    """Test cases for login rate limiting."""

    def test_check_login_first_attempt_allowed(
        self, service: RateLimitService
    ) -> None:
        """First login attempt should be allowed."""
        result = service.check_login("test@example.com")
        assert result.allowed is True
        assert result.remaining == MAX_LOGIN_ATTEMPTS
        assert result.limit == MAX_LOGIN_ATTEMPTS

    def test_check_login_after_failures(
        self, service: RateLimitService
    ) -> None:
        """After failures, remaining attempts should decrease."""
        for _ in range(2):
            service.record_failed_login("test@example.com")
        result = service.check_login("test@example.com")
        assert result.allowed is True
        assert result.remaining == MAX_LOGIN_ATTEMPTS - 2

    def test_check_login_blocked_after_max_attempts(
        self, service: RateLimitService
    ) -> None:
        """After MAX_LOGIN_ATTEMPTS, login should be blocked."""
        for _ in range(MAX_LOGIN_ATTEMPTS):
            service.record_failed_login("test@example.com")
        result = service.check_login("test@example.com")
        assert result.allowed is False
        assert result.remaining == 0

    def test_record_failed_login_increments_counter(
        self, service: RateLimitService
    ) -> None:
        """Each failed login should increment the counter."""
        result1 = service.record_failed_login("test@example.com")
        assert result1.remaining == MAX_LOGIN_ATTEMPTS - 1

        result2 = service.record_failed_login("test@example.com")
        assert result2.remaining == MAX_LOGIN_ATTEMPTS - 2

    def test_record_failed_login_blocks_at_max(
        self, service: RateLimitService
    ) -> None:
        """After MAX_LOGIN_ATTEMPTS failures, result should show blocked."""
        for _ in range(MAX_LOGIN_ATTEMPTS - 1):
            service.record_failed_login("test@example.com")
        result = service.record_failed_login("test@example.com")
        assert result.allowed is False
        assert result.remaining == 0

    def test_reset_login_clears_counter(self, service: RateLimitService) -> None:
        """reset_login should clear the rate limit counter."""
        service.record_failed_login("test@example.com")
        service.reset_login("test@example.com")
        result = service.check_login("test@example.com")
        assert result.allowed is True
        assert result.remaining == MAX_LOGIN_ATTEMPTS

    def test_different_emails_have_separate_counters(
        self, service: RateLimitService
    ) -> None:
        """Each email should have its own rate limit counter."""
        service.record_failed_login("user1@example.com")
        service.record_failed_login("user1@example.com")
        result1 = service.check_login("user1@example.com")
        result2 = service.check_login("user2@example.com")
        assert result1.remaining == MAX_LOGIN_ATTEMPTS - 2
        assert result2.remaining == MAX_LOGIN_ATTEMPTS

    def test_check_login_ttl_is_correct(
        self, service: RateLimitService
    ) -> None:
        """Check should return correct TTL in seconds."""
        result = service.check_login("test@example.com")
        assert result.reset_in_seconds == LOGIN_LOCKOUT_MINUTES * 60


class TestRateLimitServiceRegistration:
    """Test cases for registration rate limiting."""

    def test_check_registration_first_attempt_allowed(
        self, service: RateLimitService
    ) -> None:
        """First registration from IP should be allowed."""
        result = service.check_registration("192.168.1.1")
        assert result.allowed is True
        assert result.remaining == MAX_REGISTRATION_PER_IP

    def test_check_registration_decreases_remaining(
        self, service: RateLimitService
    ) -> None:
        """After each registration attempt, remaining should decrease."""
        for _ in range(4):
            service.record_registration("192.168.1.1")
        result = service.check_registration("192.168.1.1")
        assert result.remaining == MAX_REGISTRATION_PER_IP - 4

    def test_check_registration_blocked_at_max(
        self, service: RateLimitService
    ) -> None:
        """After MAX_REGISTRATION_PER_IP attempts, should be blocked."""
        for _ in range(MAX_REGISTRATION_PER_IP):
            service.record_registration("192.168.1.1")
        result = service.check_registration("192.168.1.1")
        assert result.allowed is False
        assert result.remaining == 0

    def test_record_registration_blocks_at_max(
        self, service: RateLimitService
    ) -> None:
        """After MAX attempts, record should return blocked."""
        for _ in range(MAX_REGISTRATION_PER_IP - 1):
            service.record_registration("192.168.1.1")
        result = service.record_registration("192.168.1.1")
        assert result.allowed is False

    def test_different_ips_have_separate_counters(
        self, service: RateLimitService
    ) -> None:
        """Different IPs should have independent counters."""
        for _ in range(5):
            service.record_registration("192.168.1.1")
        result1 = service.check_registration("192.168.1.1")
        result2 = service.check_registration("192.168.1.2")
        assert result1.allowed is False
        assert result2.allowed is True

    def test_check_registration_ttl_is_correct(
        self, service: RateLimitService
    ) -> None:
        """Check should return correct TTL for registration."""
        result = service.check_registration("192.168.1.1")
        assert result.reset_in_seconds == REGISTRATION_LOCKOUT_MINUTES * 60


class TestRateLimitResult:
    """Test cases for RateLimitResult dataclass."""

    def test_rate_limit_result_allowed(self) -> None:
        """RateLimitResult should store correct allowed state."""
        result = RateLimitResult(
            allowed=True,
            remaining=2,
            limit=5,
            reset_in_seconds=300,
        )
        assert result.allowed is True
        assert result.remaining == 2
        assert result.limit == 5
        assert result.reset_in_seconds == 300

    def test_rate_limit_result_denied(self) -> None:
        """RateLimitResult should show denied state with zero remaining."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            limit=5,
            reset_in_seconds=600,
        )
        assert result.allowed is False
        assert result.remaining == 0