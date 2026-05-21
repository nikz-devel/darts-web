"""Token generation and validation service."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, TypedDict

import jwt
from django.conf import settings

if TYPE_CHECKING:
    from backend.apps.accounts.models import User


class TokenPayload(TypedDict):
    """JWT payload structure."""

    user_id: str
    email: str
    exp: datetime
    iat: datetime


class TokenPairDTO(TypedDict):
    """Token pair returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


# Token TTLs
ACCESS_TOKEN_TTL_MINUTES = 15
REFRESH_TOKEN_TTL_DAYS = 7


class TokenService:
    """Service for JWT and refresh token operations."""

    def __init__(self) -> None:
        self._secret_key = settings.SECRET_KEY
        self._algorithm = "HS256"

    def generate_access_token(self, user: "User") -> str:
        """Generate a JWT access token.

        Args:
            user: The authenticated user.

        Returns:
            A signed JWT string with 15-minute TTL.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": str(user.id),
            "email": user.email,
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def generate_refresh_token(self) -> str:
        """Generate a cryptographically secure refresh token (UUID).

        Returns:
            A UUID4 string to be stored hashed in the database.
        """
        return str(uuid.uuid4())

    def decode_access_token(self, token: str) -> TokenPayload:
        """Decode and validate a JWT access token.

        Args:
            token: The JWT string.

        Returns:
            The decoded payload dict.

        Raises:
            jwt.ExpiredSignatureError: If the token has expired.
            jwt.InvalidTokenError: If the token is invalid.
        """
        payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        return payload  # type: ignore[return-value]

    def hash_token(self, token: str) -> str:
        """Hash a token using SHA-256 for secure storage.

        Args:
            token: The raw token string.

        Returns:
            A hex-encoded SHA-256 hash.
        """
        return hashlib.sha256(token.encode()).hexdigest()

    def get_access_token_ttl(self) -> int:
        """Return the access token TTL in seconds."""
        return ACCESS_TOKEN_TTL_MINUTES * 60

    def get_refresh_token_ttl(self) -> timedelta:
        """Return the refresh token TTL as a timedelta."""
        return timedelta(days=REFRESH_TOKEN_TTL_DAYS)