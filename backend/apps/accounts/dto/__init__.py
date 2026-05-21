"""Data Transfer Objects for the accounts bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UserDTO:
    """Read-only User representation for API responses."""

    id: UUID
    email: str
    status: str
    email_verified: bool
    created_at: datetime


@dataclass(frozen=True)
class TokenPairDTO:
    """Access + Refresh token pair returned after login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # seconds


@dataclass(frozen=True)
class AuthResultDTO:
    """Generic result of an auth operation that may return tokens or an error."""

    success: bool
    message: str
    user: UserDTO | None = None
    tokens: TokenPairDTO | None = None