"""Redis-backed rate limiting service for brute-force protection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.core.cache import cache

if TYPE_CHECKING:
    pass


# Rate limiting constants
MAX_LOGIN_ATTEMPTS = 3
LOGIN_LOCKOUT_MINUTES = 15
MAX_REGISTRATION_PER_IP = 5
REGISTRATION_LOCKOUT_MINUTES = 60


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    remaining: int
    limit: int
    reset_in_seconds: int


class RateLimitService:
    """Redis-backed rate limiter using Django cache (Redis backend).

    Key patterns:
        - rate_limit:login:{email}     — login attempt counter per email (TTL 15 min)
        - rate_limit:register:{ip}    — registration counter per IP (TTL 60 min)
    """

    LOGIN_PREFIX = "rate_limit:login:"
    REGISTER_PREFIX = "rate_limit:register:"

    def __init__(self) -> None:
        pass

    def check_login(self, email: str) -> RateLimitResult:
        """Check if login is allowed for the given email.

        Args:
            email: The email address to check.

        Returns:
            RateLimitResult indicating if the request is allowed.
        """
        key = f"{self.LOGIN_PREFIX}{email}"
        attempts = cache.get(key, 0)

        if attempts >= MAX_LOGIN_ATTEMPTS:
            ttl = self._get_ttl(key, LOGIN_LOCKOUT_MINUTES * 60)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=MAX_LOGIN_ATTEMPTS,
                reset_in_seconds=ttl,
            )

        return RateLimitResult(
            allowed=True,
            remaining=MAX_LOGIN_ATTEMPTS - int(attempts),
            limit=MAX_LOGIN_ATTEMPTS,
            reset_in_seconds=LOGIN_LOCKOUT_MINUTES * 60,
        )

    def record_failed_login(self, email: str) -> RateLimitResult:
        """Record a failed login attempt.

        Increments the counter and returns the updated rate limit status.

        Args:
            email: The email address of the failed attempt.

        Returns:
            Updated RateLimitResult.
        """
        key = f"{self.LOGIN_PREFIX}{email}"
        attempts = cache.get(key, 0) + 1
        timeout = LOGIN_LOCKOUT_MINUTES * 60
        cache.set(key, attempts, timeout=timeout)

        if attempts >= MAX_LOGIN_ATTEMPTS:
            ttl = self._get_ttl(key, timeout)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=MAX_LOGIN_ATTEMPTS,
                reset_in_seconds=ttl,
            )

        return RateLimitResult(
            allowed=True,
            remaining=MAX_LOGIN_ATTEMPTS - attempts,
            limit=MAX_LOGIN_ATTEMPTS,
            reset_in_seconds=timeout,
        )

    def reset_login(self, email: str) -> None:
        """Reset login rate limit counter for the email.

        Called on successful login.

        Args:
            email: The email address to reset.
        """
        key = f"{self.LOGIN_PREFIX}{email}"
        cache.delete(key)

    def check_registration(self, ip: str) -> RateLimitResult:
        """Check if registration is allowed from the given IP.

        Args:
            ip: The client's IP address.

        Returns:
            RateLimitResult indicating if the request is allowed.
        """
        key = f"{self.REGISTER_PREFIX}{ip}"
        count = cache.get(key, 0)

        if count >= MAX_REGISTRATION_PER_IP:
            ttl = self._get_ttl(key, REGISTRATION_LOCKOUT_MINUTES * 60)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=MAX_REGISTRATION_PER_IP,
                reset_in_seconds=ttl,
            )

        return RateLimitResult(
            allowed=True,
            remaining=MAX_REGISTRATION_PER_IP - int(count),
            limit=MAX_REGISTRATION_PER_IP,
            reset_in_seconds=REGISTRATION_LOCKOUT_MINUTES * 60,
        )

    def record_registration(self, ip: str) -> RateLimitResult:
        """Record a registration attempt from the given IP.

        Args:
            ip: The client's IP address.

        Returns:
            Updated RateLimitResult.
        """
        key = f"{self.REGISTER_PREFIX}{ip}"
        count = cache.get(key, 0) + 1
        timeout = REGISTRATION_LOCKOUT_MINUTES * 60
        cache.set(key, count, timeout=timeout)

        if count >= MAX_REGISTRATION_PER_IP:
            ttl = self._get_ttl(key, timeout)
            return RateLimitResult(
                allowed=False,
                remaining=0,
                limit=MAX_REGISTRATION_PER_IP,
                reset_in_seconds=ttl,
            )

        return RateLimitResult(
            allowed=True,
            remaining=MAX_REGISTRATION_PER_IP - count,
            limit=MAX_REGISTRATION_PER_IP,
            reset_in_seconds=timeout,
        )

    def _get_ttl(self, key: str, default_seconds: int) -> int:
        """Get TTL for a cache key, returning default if unavailable.

        Works with both Redis (has .ttl) and LocMemCache (no .ttl).
        """
        try:
            return max(cache.ttl(key), 0)
        except (AttributeError, TypeError):
            return default_seconds