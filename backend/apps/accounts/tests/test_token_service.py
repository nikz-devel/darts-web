"""Unit tests for TokenService."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import jwt
import pytest
from django.test import override_settings

from backend.apps.accounts.services.token_service import (
    TokenService,
    ACCESS_TOKEN_TTL_MINUTES,
    REFRESH_TOKEN_TTL_DAYS,
)

pytestmark = pytest.mark.django_db


class MockUser:
    """Lightweight user mock for testing TokenService."""

    def __init__(self, user_id: str = "123e4567-e89b-12d3-a456-426614174000", email: str = "test@example.com"):
        self.id = user_id
        self.email = email


class TestTokenService:
    """Test cases for TokenService."""

    @pytest.fixture
    def service(self) -> TokenService:
        return TokenService()

    @pytest.fixture
    def user(self) -> MockUser:
        return MockUser()

    # ------------------------------------------------------------------
    # generate_access_token
    # ------------------------------------------------------------------

    def test_generate_access_token_returns_jwt_string(
        self, service: TokenService, user: MockUser
    ) -> None:
        token = service.generate_access_token(user)
        assert isinstance(token, str)
        assert token.startswith("ey")  # JWT format

    def test_generate_access_token_payload_contains_user_data(
        self, service: TokenService, user: MockUser
    ) -> None:
        token = service.generate_access_token(user)
        payload = jwt.decode(
            token,
            service._secret_key,
            algorithms=[service._algorithm],
        )
        assert payload["user_id"] == user.id
        assert payload["email"] == user.email

    def test_generate_access_token_has_15_minute_ttl(
        self, service: TokenService, user: MockUser
    ) -> None:
        token = service.generate_access_token(user)
        payload = jwt.decode(
            token,
            service._secret_key,
            algorithms=[service._algorithm],
        )
        exp = payload["exp"]
        iat = payload["iat"]
        assert exp - iat == ACCESS_TOKEN_TTL_MINUTES * 60

    # ------------------------------------------------------------------
    # generate_refresh_token
    # ------------------------------------------------------------------

    def test_generate_refresh_token_returns_uuid_string(self, service: TokenService) -> None:
        token = service.generate_refresh_token()
        assert isinstance(token, str)
        # UUID format: 8-4-4-4-12
        parts = token.split("-")
        assert len(parts) == 5

    def test_generate_refresh_token_produces_unique_tokens(
        self, service: TokenService
    ) -> None:
        tokens = {service.generate_refresh_token() for _ in range(100)}
        assert len(tokens) == 100

    # ------------------------------------------------------------------
    # decode_access_token
    # ------------------------------------------------------------------

    def test_decode_access_token_roundtrip(
        self, service: TokenService, user: MockUser
    ) -> None:
        token = service.generate_access_token(user)
        payload = service.decode_access_token(token)
        assert payload["user_id"] == user.id
        assert payload["email"] == user.email

    def test_decode_access_token_expired_raises(
        self, service: TokenService, user: MockUser
    ) -> None:
        # Manually create an expired token
        import time
        now = int(time.time())
        payload = {
            "user_id": user.id,
            "email": user.email,
            "iat": now - 1000,
            "exp": now - 100,  # Expired 900 seconds ago
        }
        expired_token = jwt.encode(payload, service._secret_key, algorithm=service._algorithm)
        with pytest.raises(jwt.ExpiredSignatureError):
            service.decode_access_token(expired_token)

    def test_decode_access_token_invalid_raises(
        self, service: TokenService
    ) -> None:
        with pytest.raises(jwt.InvalidTokenError):
            service.decode_access_token("invalid.token.here")

    # ------------------------------------------------------------------
    # hash_token
    # ------------------------------------------------------------------

    def test_hash_token_returns_hex_sha256(self, service: TokenService) -> None:
        result = service.hash_token("test_token")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_token_is_deterministic(self, service: TokenService) -> None:
        token = "my_secret_token"
        h1 = service.hash_token(token)
        h2 = service.hash_token(token)
        assert h1 == h2

    def test_hash_token_different_inputs_produce_different_hashes(
        self, service: TokenService
    ) -> None:
        h1 = service.hash_token("token1")
        h2 = service.hash_token("token2")
        assert h1 != h2

    # ------------------------------------------------------------------
    # TTL helpers
    # ------------------------------------------------------------------

    def test_get_access_token_ttl_returns_seconds(self, service: TokenService) -> None:
        ttl = service.get_access_token_ttl()
        assert ttl == ACCESS_TOKEN_TTL_MINUTES * 60

    def test_get_refresh_token_ttl_returns_timedelta(self, service: TokenService) -> None:
        ttl = service.get_refresh_token_ttl()
        assert ttl == timedelta(days=REFRESH_TOKEN_TTL_DAYS)