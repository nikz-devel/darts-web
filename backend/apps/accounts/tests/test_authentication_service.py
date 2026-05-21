"""Unit tests for AuthenticationService."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.utils import timezone

from backend.apps.accounts.models import EmailConfirmationToken, RefreshToken, User
from backend.apps.accounts.services.authentication_service import (
    AuthenticationService,
    EMAIL_CONFIRMATION_TTL_HOURS,
    ServiceResult,
)
from backend.apps.accounts.services.rate_limit_service import (
    MAX_LOGIN_ATTEMPTS,
    LOGIN_LOCKOUT_MINUTES,
)
from backend.apps.accounts.services.token_service import TokenService

pytestmark = pytest.mark.django_db


class TestAuthenticationService:
    """Test cases for AuthenticationService."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        """Clear Django cache before and after each test."""
        cache.clear()
        yield
        cache.clear()

    @pytest.fixture
    def service(self) -> AuthenticationService:
        return AuthenticationService()

    @pytest.fixture
    def token_service(self) -> TokenService:
        return TokenService()

    # ------------------------------------------------------------------
    # register_user
    # ------------------------------------------------------------------

    def test_register_user_creates_pending_user(
        self, service: AuthenticationService
    ) -> None:
        result = service.register_user(
            email="new@example.com",
            password="SecurePass123",
            password_confirm="SecurePass123",
        )
        assert result.success is True
        assert result.data is not None
        assert result.data["email"] == "new@example.com"
        assert result.data["status"] == "pending"
        user = User.objects.get(email__iexact="new@example.com")
        assert user.status == "pending"
        assert user.email_verified is False

    def test_register_user_normalizes_email(
        self, service: AuthenticationService
    ) -> None:
        result = service.register_user(
            email="  TeSt@EXAMPLE.COM  ",
            password="SecurePass123",
            password_confirm="SecurePass123",
        )
        assert result.success is True
        assert User.objects.filter(email__iexact="test@example.com").exists()

    def test_register_user_password_mismatch(
        self, service: AuthenticationService
    ) -> None:
        result = service.register_user(
            email="test@example.com",
            password="SecurePass123",
            password_confirm="DifferentPass",
        )
        assert result.success is False
        assert "не совпадают" in result.error

    def test_register_user_duplicate_email(
        self, service: AuthenticationService
    ) -> None:
        User.objects.create_user(email="test@example.com", password="pass123456")
        result = service.register_user(
            email="test@example.com",
            password="SecurePass123",
            password_confirm="SecurePass123",
        )
        assert result.success is False
        assert "уже существует" in result.error

    def test_register_user_creates_confirmation_token(
        self, service: AuthenticationService
    ) -> None:
        result = service.register_user(
            email="test@example.com",
            password="SecurePass123",
            password_confirm="SecurePass123",
        )
        user_id = result.data["id"]
        user = User.objects.get(id=user_id)
        token = EmailConfirmationToken.objects.filter(user=user).first()
        assert token is not None
        assert token.token_type == "email_confirmation"
        assert token.is_expired is False
        assert token.is_used is False

    # ------------------------------------------------------------------
    # confirm_email
    # ------------------------------------------------------------------

    def test_confirm_email_activates_user(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        # Register to get a token
        service.register_user(
            email="test@example.com",
            password="SecurePass123",
            password_confirm="SecurePass123",
        )
        user = User.objects.get(email__iexact="test@example.com")
        token = EmailConfirmationToken.objects.get(user=user)

        result = service.confirm_email(token.token)
        assert result.success is True
        user.refresh_from_db()
        assert user.email_verified is True
        assert user.status == "active"

    def test_confirm_email_marks_token_used(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        service.register_user(
            email="test@example.com",
            password="SecurePass123",
            password_confirm="SecurePass123",
        )
        user = User.objects.get(email__iexact="test@example.com")
        token = EmailConfirmationToken.objects.get(user=user)

        service.confirm_email(token.token)
        token.refresh_from_db()
        assert token.is_used is True

    def test_confirm_email_invalid_token(self, service: AuthenticationService) -> None:
        result = service.confirm_email("nonexistent_token")
        assert result.success is False
        assert "Неверный токен" in result.error

    def test_confirm_email_expired_token(self, service: AuthenticationService) -> None:
        user = User.objects.create_user(email="test@example.com", password="pass123456")
        expired_token = EmailConfirmationToken.objects.create(
            user=user,
            token="expired_token",
            token_type="email_confirmation",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        result = service.confirm_email(expired_token.token)
        assert result.success is False
        assert "устарела" in result.error

    def test_confirm_email_already_used_token(
        self, service: AuthenticationService
    ) -> None:
        user = User.objects.create_user(email="test@example.com", password="pass123456")
        token = EmailConfirmationToken.objects.create(
            user=user,
            token="used_token",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        token.mark_used()
        result = service.confirm_email(token.token)
        assert result.success is False
        assert "уже использован" in result.error

    # ------------------------------------------------------------------
    # login
    # ------------------------------------------------------------------

    def test_login_success_returns_tokens(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        result = service.login("test@example.com", "SecurePass123")
        assert result.success is True
        assert "access_token" in result.data
        assert "refresh_token" in result.data
        assert result.data["token_type"] == "Bearer"

        # Verify refresh token was stored
        user = User.objects.get(email__iexact="test@example.com")
        stored_token = RefreshToken.objects.filter(user=user).first()
        assert stored_token is not None

    def test_login_case_insensitive_email(
        self, service: AuthenticationService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        result = service.login("TEST@EXAMPLE.COM", "SecurePass123")
        assert result.success is True

    def test_login_invalid_password(
        self, service: AuthenticationService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        result = service.login("test@example.com", "WrongPassword")
        assert result.success is False
        assert "Неверные учетные данные" in result.error

    def test_login_nonexistent_user(
        self, service: AuthenticationService
    ) -> None:
        result = service.login("nobody@example.com", "AnyPassword")
        assert result.success is False
        assert "Неверные учетные данные" in result.error

    def test_login_account_locked(self, service: AuthenticationService) -> None:
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        user.locked_until = timezone.now() + timedelta(minutes=15)
        user.save()
        result = service.login("test@example.com", "SecurePass123")
        assert result.success is False
        assert "заблокирован" in result.error

    def test_login_rate_limit_after_three_attempts(
        self, service: AuthenticationService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        lock_key = f"rate_limit:login:test@example.com"

        # First 3 failures
        for i in range(3):
            result = service.login("test@example.com", "WrongPassword")
            assert result.success is False

        # 4th attempt triggers rate limit
        result = service.login("test@example.com", "SecurePass123")
        assert result.success is False
        assert "Слишком много попыток" in result.error

    def test_login_resets_failed_attempts_on_success(
        self, service: AuthenticationService
    ) -> None:
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        # First fail
        service.login("test@example.com", "WrongPassword")
        user.refresh_from_db()
        assert user.failed_login_attempts >= 1

        # Then succeed
        result = service.login("test@example.com", "SecurePass123")
        assert result.success is True
        user.refresh_from_db()
        assert user.failed_login_attempts == 0

    # ------------------------------------------------------------------
    # refresh_token
    # ------------------------------------------------------------------

    def test_refresh_token_returns_new_pair(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        login_result = service.login("test@example.com", "SecurePass123")
        old_refresh = login_result.data["refresh_token"]

        result = service.refresh_token(old_refresh)
        assert result.success is True
        assert result.data["access_token"] != old_refresh
        assert result.data["refresh_token"] != old_refresh

    def test_refresh_token_revokes_old_and_creates_new(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        login_result = service.login("test@example.com", "SecurePass123")
        old_refresh = login_result.data["refresh_token"]

        service.refresh_token(old_refresh)

        old_token_hash = token_service.hash_token(old_refresh)
        old_record = RefreshToken.objects.get(token_hash=old_token_hash)
        assert old_record.is_revoked is True

    def test_refresh_token_invalid(self, service: AuthenticationService) -> None:
        result = service.refresh_token("invalid_token_string")
        assert result.success is False
        assert "Неверный" in result.error

    def test_refresh_token_revoked(self, service: AuthenticationService) -> None:
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        token = RefreshToken.objects.create(
            user=user,
            token_hash="some_hash",
            expires_at=timezone.now() + timedelta(days=7),
            revoked_at=timezone.now(),
        )
        result = service.refresh_token("not_the_real_token")
        assert result.success is False

    def test_refresh_token_expired(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        raw_token = token_service.generate_refresh_token()
        RefreshToken.objects.create(
            user=user,
            token_hash=token_service.hash_token(raw_token),
            expires_at=timezone.now() - timedelta(days=1),
        )
        result = service.refresh_token(raw_token)
        assert result.success is False
        assert "устарел" in result.error

    # ------------------------------------------------------------------
    # request_password_reset
    # ------------------------------------------------------------------

    def test_request_password_reset_creates_token_for_existing_user(
        self, service: AuthenticationService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        result = service.request_password_reset("test@example.com")
        assert result.success is True

        user = User.objects.get(email__iexact="test@example.com")
        token = EmailConfirmationToken.objects.filter(
            user=user, token_type="password_reset"
        ).exists()
        assert token is True

    def test_request_password_reset_returns_success_for_nonexistent(
        self, service: AuthenticationService
    ) -> None:
        # Must not reveal that email doesn't exist
        result = service.request_password_reset("nobody@example.com")
        assert result.success is True

    # ------------------------------------------------------------------
    # reset_password
    # ------------------------------------------------------------------

    def test_reset_password_updates_password_and_revokes_sessions(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="OldPass123",
        )
        login_result = service.login("test@example.com", "OldPass123")
        refresh_token = login_result.data["refresh_token"]

        # Create a password reset token
        user = User.objects.get(email__iexact="test@example.com")
        reset_token = EmailConfirmationToken.objects.create(
            user=user,
            token="reset_token_123",
            token_type="password_reset",
            expires_at=timezone.now() + timedelta(hours=48),
        )

        result = service.reset_password(
            token=reset_token.token,
            new_password="NewPass456",
            password_confirm="NewPass456",
        )
        assert result.success is True

        user.refresh_from_db()
        assert user.check_password("NewPass456") is True

        # Old refresh token should be revoked
        old_hash = token_service.hash_token(refresh_token)
        old_token = RefreshToken.objects.get(token_hash=old_hash)
        assert old_token.is_revoked is True

    def test_reset_password_mismatch(self, service: AuthenticationService) -> None:
        result = service.reset_password(
            token="any_token",
            new_password="NewPass123",
            password_confirm="DifferentPass",
        )
        assert result.success is False
        assert "не совпадают" in result.error

    def test_reset_password_invalid_token(self, service: AuthenticationService) -> None:
        result = service.reset_password(
            token="nonexistent",
            new_password="NewPass123",
            password_confirm="NewPass123",
        )
        assert result.success is False
        assert "Неверный токен" in result.error

    def test_reset_password_expired_token(self, service: AuthenticationService) -> None:
        user = User.objects.create_user(
            email="test@example.com",
            password="OldPass123",
        )
        expired_token = EmailConfirmationToken.objects.create(
            user=user,
            token="expired_reset",
            token_type="password_reset",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        result = service.reset_password(
            token=expired_token.token,
            new_password="NewPass123",
            password_confirm="NewPass123",
        )
        assert result.success is False
        assert "устарела" in result.error

    # ------------------------------------------------------------------
    # logout
    # ------------------------------------------------------------------

    def test_logout_revokes_refresh_token(
        self, service: AuthenticationService, token_service: TokenService
    ) -> None:
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        login_result = service.login("test@example.com", "SecurePass123")
        refresh_token = login_result.data["refresh_token"]

        result = service.logout(refresh_token)
        assert result.success is True

        token_hash = token_service.hash_token(refresh_token)
        token_record = RefreshToken.objects.get(token_hash=token_hash)
        assert token_record.is_revoked is True

    def test_logout_invalid_token(self, service: AuthenticationService) -> None:
        result = service.logout("nonexistent_token")
        assert result.success is False
        assert "не найден" in result.error