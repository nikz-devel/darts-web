"""Token generation, validation and hashing service.

Pure business-logic service with no Django ORM dependencies.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCESS_TOKEN_TTL_MINUTES: int = 15
REFRESH_TOKEN_TTL_DAYS: int = 7
EMAIL_CONFIRM_TOKEN_TTL_HOURS: int = 48
PASSWORD_RESET_TOKEN_TTL_HOURS: int = 48

# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------


class TokenError(Exception):
    """Base exception for token operations."""


class InvalidTokenError(TokenError):
    """Raised when a token is malformed or has been tampered with."""


class ExpiredTokenError(TokenError):
    """Raised when a token has expired."""


# ---------------------------------------------------------------------------
# TokenService — Pure Functions
# ---------------------------------------------------------------------------


def generate_uuid_token() -> str:
    """Generate a secure random UUID-based token (for refresh/email tokens)."""
    return uuid.uuid4().hex + uuid.uuid4().hex


def generate_access_token(
    *,
    user_id: str,
    email: str,
    secret_key: str,
    algorithm: str = "HS256",
    issued_at: datetime | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        user_id: UUID of the user as string.
        email: User email for embedding in token payload.
        secret_key: Application secret (from settings).
        algorithm: JWT signing algorithm.
        issued_at: Optional explicit issue time (useful for testing).

    Returns:
        Signed JWT string.
    """
    now = issued_at or datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def generate_refresh_token() -> str:
    """Generate a secure random token for refresh flow.

    Returns a random hex string suitable for use as a refresh token.
    """
    return secrets.token_urlsafe(32)


def generate_confirmation_token() -> str:
    """Generate a secure token for email confirmation or password reset."""
    return secrets.token_urlsafe(48)


def decode_access_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
) -> dict[str, Any]:
    """Validate and decode a JWT access token.

    Args:
        token: The JWT string.
        secret_key: Application secret.
        algorithm: JWT signing algorithm.

    Returns:
        The decoded payload dictionary.

    Raises:
        ExpiredTokenError: If the token has expired.
        InvalidTokenError: If the token is malformed or invalid.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError("Access token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid access token") from exc
    return payload


def hash_token(token: str) -> str:
    """Create a deterministic SHA-256 hash of a token for storage.

    Never stores the raw token in the database.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, token_hash: str) -> bool:
    """Verify a raw token against its stored hash."""
    return secrets.compare_digest(hash_token(token), token_hash)


def get_token_expiry(
    ttl_seconds: int,
    base_time: datetime | None = None,
) -> datetime:
    """Calculate expiry datetime for a token with the given TTL."""
    return (base_time or datetime.now(timezone.utc)) + timedelta(seconds=ttl_seconds)


def calculate_access_expiry(
    base_time: datetime | None = None,
) -> datetime:
    """Expiry for an access token (15 minutes by default)."""
    return get_token_expiry(ACCESS_TOKEN_TTL_MINUTES * 60, base_time)


def calculate_refresh_expiry(
    base_time: datetime | None = None,
) -> datetime:
    """Expiry for a refresh token (7 days by default)."""
    return get_token_expiry(REFRESH_TOKEN_TTL_DAYS * 24 * 3600, base_time)


def calculate_email_confirmation_expiry(
    base_time: datetime | None = None,
) -> datetime:
    """Expiry for an email confirmation token (48 hours by default)."""
    return get_token_expiry(EMAIL_CONFIRM_TOKEN_TTL_HOURS * 3600, base_time)


def calculate_password_reset_expiry(
    base_time: datetime | None = None,
) -> datetime:
    """Expiry for a password reset token (48 hours by default)."""
    return get_token_expiry(PASSWORD_RESET_TOKEN_TTL_HOURS * 3600, base_time)