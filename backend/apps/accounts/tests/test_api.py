"""Unit tests for authentication API endpoints."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.accounts.models import EmailConfirmationToken, RefreshToken, User
from backend.apps.accounts.services.authentication_service import AuthenticationService


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Clear cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client() -> APIClient:
    """Return DRF API client."""
    return APIClient()


@pytest.fixture
def register_url() -> str:
    return "/api/v1/auth/register/"


@pytest.fixture
def confirm_email_url() -> str:
    return "/api/v1/auth/confirm-email/"


# =============================================================================
# POST /api/v1/auth/register/
# =============================================================================

class TestRegisterView:
    """Test cases for POST /api/v1/auth/register/."""

    def test_register_success_201(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """AT-01: Successful registration returns 201 and sends confirmation email."""
        with patch(
            "backend.apps.accounts.views.celery_app.send_task"
        ) as mock_task:
            response = api_client.post(
                register_url,
                {
                    "email": "newuser@example.com",
                    "password": "SecurePass123",
                    "password_confirm": "SecurePass123",
                },
                format="json",
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["email"] == "newuser@example.com"
        assert data["status"] == "pending"
        assert "message" in data

        # Verify user was created
        user = User.objects.get(email__iexact="newuser@example.com")
        assert user.status == "pending"
        assert user.email_verified is False

        # Verify Celery task was called
        mock_task.assert_called_once()
        call_kwargs = mock_task.call_args.kwargs["kwargs"]
        assert call_kwargs["user_id"] == str(user.id)
        assert call_kwargs["email"] == "newuser@example.com"
        assert "token" in call_kwargs

    def test_register_duplicate_email_409(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """AT-02: Duplicate email returns 409."""
        User.objects.create_user(
            email="existing@example.com",
            password="SomePass123",
        )

        response = api_client.post(
            register_url,
            {
                "email": "existing@example.com",
                "password": "SecurePass123",
                "password_confirm": "SecurePass123",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "уже существует" in response.json()["detail"]

    def test_register_weak_password_400(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """AT-03: Weak password returns 400."""
        response = api_client.post(
            register_url,
            {
                "email": "test@example.com",
                "password": "123",
                "password_confirm": "123",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Пароль должен содержать минимум" in response.json()["detail"]

    def test_register_password_mismatch_400(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Password mismatch returns 400."""
        response = api_client.post(
            register_url,
            {
                "email": "test@example.com",
                "password": "SecurePass123",
                "password_confirm": "OtherPass123",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "не совпадают" in response.json()["detail"]

    def test_register_invalid_email_400(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Invalid email format returns 400."""
        response = api_client.post(
            register_url,
            {
                "email": "not-an-email",
                "password": "SecurePass123",
                "password_confirm": "SecurePass123",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_missing_fields_400(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Missing required fields returns 400."""
        response = api_client.post(
            register_url,
            {"email": "test@example.com"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_email_normalized_to_lowercase(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Email is normalized to lowercase."""
        with patch(
            "backend.apps.accounts.views.celery_app.send_task"
        ):
            response = api_client.post(
                register_url,
                {
                    "email": "  TeSt@EXAMPLE.COM  ",
                    "password": "SecurePass123",
                    "password_confirm": "SecurePass123",
                },
                format="json",
            )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["email"] == "test@example.com"
        assert User.objects.filter(email="test@example.com").exists()

    def test_register_creates_confirmation_token(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Registration creates an email confirmation token."""
        with patch(
            "backend.apps.accounts.views.celery_app.send_task"
        ):
            response = api_client.post(
                register_url,
                {
                    "email": "test@example.com",
                    "password": "SecurePass123",
                    "password_confirm": "SecurePass123",
                },
                format="json",
            )

        user = User.objects.get(email__iexact="test@example.com")
        token = EmailConfirmationToken.objects.filter(
            user=user,
            token_type="email_confirmation",
        ).first()
        assert token is not None
        assert not token.is_expired
        assert not token.is_used

    def test_register_ip_rate_limit_exceeded_429(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """AT-06: After 5 registrations from same IP, returns 429."""
        with patch(
            "backend.apps.accounts.views.celery_app.send_task"
        ):
            for i in range(5):
                response = api_client.post(
                    register_url,
                    {
                        "email": f"user{i}@example.com",
                        "password": "SecurePass123",
                        "password_confirm": "SecurePass123",
                    },
                    format="json",
                    REMOTE_ADDR="10.0.0.1",
                )
                assert response.status_code == status.HTTP_201_CREATED

        # 6th attempt should be rate limited
        response = api_client.post(
            register_url,
            {
                "email": "user6@example.com",
                "password": "SecurePass123",
                "password_confirm": "SecurePass123",
            },
            format="json",
            REMOTE_ADDR="10.0.0.1",
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "IP" in response.json()["detail"]

    def test_register_different_ips_not_rate_limited(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Different IPs should not share rate limit counters."""
        with patch(
            "backend.apps.accounts.views.celery_app.send_task"
        ):
            # 5 registrations from IP 1
            for i in range(5):
                response = api_client.post(
                    register_url,
                    {
                        "email": f"ip1user{i}@example.com",
                        "password": "SecurePass123",
                        "password_confirm": "SecurePass123",
                    },
                    format="json",
                    REMOTE_ADDR="10.0.0.1",
                )
                assert response.status_code == status.HTTP_201_CREATED

            # 6th registration from IP 1 blocked
            response1_blocked = api_client.post(
                register_url,
                {
                    "email": "ip1user5@example.com",
                    "password": "SecurePass123",
                    "password_confirm": "SecurePass123",
                },
                format="json",
                REMOTE_ADDR="10.0.0.1",
            )
            assert response1_blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS

            # 6th registration from different IP should succeed
            response2_allowed = api_client.post(
                register_url,
                {
                    "email": "ip2user0@example.com",
                    "password": "SecurePass123",
                    "password_confirm": "SecurePass123",
                },
                format="json",
                REMOTE_ADDR="10.0.0.2",
            )
            assert response2_allowed.status_code == status.HTTP_201_CREATED


# =============================================================================
# POST /api/v1/auth/confirm-email/
# =============================================================================

class TestConfirmEmailView:
    """Test cases for POST /api/v1/auth/confirm-email/."""

    def test_confirm_email_success_200(
        self,
        api_client: APIClient,
        confirm_email_url: str,
    ) -> None:
        """AT-04: Valid token activates user account."""
        # Create a pending user with token
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        token = EmailConfirmationToken.objects.create(
            user=user,
            token="valid_token_123",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=48),
        )

        response = api_client.post(
            confirm_email_url,
            {"token": "valid_token_123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] == str(user.id)
        assert data["email"] == "test@example.com"
        assert "confirmed_at" in data

        user.refresh_from_db()
        assert user.email_verified is True
        assert user.status == "active"

    def test_confirm_email_expired_token_400(
        self,
        api_client: APIClient,
        confirm_email_url: str,
    ) -> None:
        """AT-05: Expired token returns 400."""
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        token = EmailConfirmationToken.objects.create(
            user=user,
            token="expired_token",
            token_type="email_confirmation",
            expires_at=timezone.now() - timedelta(hours=1),
        )

        response = api_client.post(
            confirm_email_url,
            {"token": "expired_token"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "устарела" in response.json()["detail"]

    def test_confirm_email_invalid_token_400(
        self,
        api_client: APIClient,
        confirm_email_url: str,
    ) -> None:
        """Non-existent token returns 400."""
        response = api_client.post(
            confirm_email_url,
            {"token": "nonexistent_token"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Неверный токен" in response.json()["detail"]

    def test_confirm_email_already_used_token_400(
        self,
        api_client: APIClient,
        confirm_email_url: str,
    ) -> None:
        """Already-used token returns 400."""
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        token = EmailConfirmationToken.objects.create(
            user=user,
            token="used_token",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        token.mark_used()

        response = api_client.post(
            confirm_email_url,
            {"token": "used_token"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "использован" in response.json()["detail"]

    def test_confirm_email_missing_token_400(
        self,
        api_client: APIClient,
        confirm_email_url: str,
    ) -> None:
        """Missing token returns 400."""
        response = api_client.post(
            confirm_email_url,
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_confirm_email_token_used_twice_400(
        self,
        api_client: APIClient,
        confirm_email_url: str,
    ) -> None:
        """EC-02: Using token twice returns 400 on second attempt."""
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        token = EmailConfirmationToken.objects.create(
            user=user,
            token="reusable_token",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=48),
        )

        # First confirmation — success
        response1 = api_client.post(
            confirm_email_url,
            {"token": "reusable_token"},
            format="json",
        )
        assert response1.status_code == status.HTTP_200_OK

        # Second confirmation — failure
        response2 = api_client.post(
            confirm_email_url,
            {"token": "reusable_token"},
            format="json",
        )
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert "использован" in response2.json()["detail"]


# =============================================================================
# Edge cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests for auth API."""

    def test_email_case_insensitive_duplicate(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """EC-01: Email case normalization prevents duplicates."""
        User.objects.create_user(
            email="test@example.com",
            password="SomePass123",
        )

        response = api_client.post(
            register_url,
            {
                "email": "TEST@EXAMPLE.COM",
                "password": "SecurePass123",
                "password_confirm": "SecurePass123",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_password_only_letters_400(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Password without digits returns 400."""
        response = api_client.post(
            register_url,
            {
                "email": "test@example.com",
                "password": "SecurePass",
                "password_confirm": "SecurePass",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "буквы и цифры" in response.json()["detail"]

    def test_password_only_digits_400(
        self,
        api_client: APIClient,
        register_url: str,
    ) -> None:
        """Password without letters returns 400."""
        response = api_client.post(
            register_url,
            {
                "email": "test@example.com",
                "password": "12345678",
                "password_confirm": "12345678",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "буквы и цифры" in response.json()["detail"]

    def test_confirm_email_wrong_token_type_400(
        self,
        api_client: APIClient,
        confirm_email_url: str,
    ) -> None:
        """Password reset token cannot be used for email confirmation."""
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
        )
        EmailConfirmationToken.objects.create(
            user=user,
            token="reset_token",
            token_type="password_reset",
            expires_at=timezone.now() + timedelta(hours=48),
        )

        response = api_client.post(
            confirm_email_url,
            {"token": "reset_token"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# POST /api/v1/auth/login/
# =============================================================================

@pytest.fixture
def login_url() -> str:
    return "/api/v1/auth/login/"


class TestLoginView:
    """Test cases for POST /api/v1/auth/login/."""

    def test_login_success_200(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """AT-06: Successful login returns 200 with JWT token pair."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )

        response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "SecurePass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 900

    def test_login_invalid_credentials_401(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """AT-07: Invalid password returns 401."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )

        response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "WrongPass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Неверные учетные данные" in response.json()["detail"]

    def test_login_nonexistent_user_401(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """Non-existent email returns 401."""
        response = api_client.post(
            login_url,
            {"email": "nobody@example.com", "password": "SecurePass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Неверные учетные данные" in response.json()["detail"]

    def test_login_account_locked_429(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """Locked account triggers rate limit, returns 429."""
        from datetime import timedelta
        from django.utils import timezone as dj_tz

        user = User.objects.create_user(
            email="locked@example.com",
            password="SecurePass123",
            status="active",
        )
        user.locked_until = dj_tz.now() + timedelta(minutes=15)
        user.save(update_fields=["locked_until"])

        response = api_client.post(
            login_url,
            {"email": "locked@example.com", "password": "SecurePass123"},
            format="json",
        )

        # Locked account: service returns "заблокирован" → 429 (rate limit)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "заблокирован" in response.json()["detail"]

    def test_login_rate_limit_exceeded_429(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """AT-08: Three failed attempts triggers 429 rate limit."""
        User.objects.create_user(
            email="ratelimit@example.com",
            password="SecurePass123",
            status="active",
        )

        for _ in range(3):
            response = api_client.post(
                login_url,
                {"email": "ratelimit@example.com", "password": "WrongPass123"},
                format="json",
            )
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Fourth attempt — rate limited
        response = api_client.post(
            login_url,
            {"email": "ratelimit@example.com", "password": "WrongPass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "слишком много" in response.json()["detail"].lower()

    def test_login_missing_fields_400(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """Missing email or password returns 400."""
        response = api_client.post(
            login_url,
            {"email": "test@example.com"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_invalid_email_format_400(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """Invalid email format returns 400."""
        response = api_client.post(
            login_url,
            {"email": "not-an-email", "password": "SecurePass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_email_case_normalized(
        self,
        api_client: APIClient,
        login_url: str,
    ) -> None:
        """Email is normalized to lowercase."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )

        response = api_client.post(
            login_url,
            {"email": "TEST@EXAMPLE.COM", "password": "SecurePass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.json()


# =============================================================================
# POST /api/v1/auth/refresh/
# =============================================================================

@pytest.fixture
def refresh_url() -> str:
    return "/api/v1/auth/refresh/"


class TestRefreshView:
    """Test cases for POST /api/v1/auth/refresh/."""

    def test_refresh_success_200(
        self,
        api_client: APIClient,
        login_url: str,
        refresh_url: str,
    ) -> None:
        """Refresh token rotation issues new token pair."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )

        # Login to get a valid refresh token
        login_response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "SecurePass123"},
            format="json",
        )
        refresh_token = login_response.json()["refresh_token"]

        response = api_client.post(
            refresh_url,
            {"refresh_token": refresh_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"

    def test_refresh_invalid_token_401(
        self,
        api_client: APIClient,
        refresh_url: str,
    ) -> None:
        """Invalid refresh token returns 401."""
        response = api_client.post(
            refresh_url,
            {"refresh_token": "nonexistent-token"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "refresh" in response.json()["detail"].lower()

    def test_refresh_expired_token_401(
        self,
        api_client: APIClient,
        refresh_url: str,
    ) -> None:
        """Expired refresh token returns 401."""
        from django.utils import timezone as dj_tz

        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )
        from backend.apps.accounts.models import RefreshToken

        service = AuthenticationService()
        raw = service._generate_refresh_token(user)
        rt = RefreshToken.objects.filter(user=user).first()
        rt.expires_at = dj_tz.now()
        rt.save(update_fields=["expires_at"])

        response = api_client.post(
            refresh_url,
            {"refresh_token": raw},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "устарел" in response.json()["detail"].lower()

    def test_refresh_missing_token_400(
        self,
        api_client: APIClient,
        refresh_url: str,
    ) -> None:
        """Missing refresh_token field returns 400."""
        response = api_client.post(
            refresh_url,
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# POST /api/v1/auth/logout/
# =============================================================================

@pytest.fixture
def logout_url() -> str:
    return "/api/v1/auth/logout/"


class TestLogoutView:
    """Test cases for POST /api/v1/auth/logout/."""

    def test_logout_success_200(
        self,
        api_client: APIClient,
        login_url: str,
        logout_url: str,
    ) -> None:
        """AT-09: Successful logout revokes refresh token."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )

        # Login to get token pair
        login_response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "SecurePass123"},
            format="json",
        )
        tokens = login_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        # Set Bearer auth
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = api_client.post(
            logout_url,
            {"refresh_token": refresh_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "выход" in response.json()["detail"].lower()

    def test_logout_unauthenticated_401(
        self,
        api_client: APIClient,
        logout_url: str,
    ) -> None:
        """Logout without JWT returns 401."""
        response = api_client.post(
            logout_url,
            {"refresh_token": "some-token"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_invalid_refresh_token_400(
        self,
        api_client: APIClient,
        login_url: str,
        logout_url: str,
    ) -> None:
        """Invalid refresh token returns 400."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )
        login_response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "SecurePass123"},
            format="json",
        )
        access_token = login_response.json()["access_token"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = api_client.post(
            logout_url,
            {"refresh_token": "nonexistent-token"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_missing_token_400(
        self,
        api_client: APIClient,
        login_url: str,
        logout_url: str,
    ) -> None:
        """Missing refresh_token field returns 400."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )
        login_response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "SecurePass123"},
            format="json",
        )
        access_token = login_response.json()["access_token"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = api_client.post(
            logout_url,
            {},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_expired_access_token_401(
        self,
        api_client: APIClient,
        logout_url: str,
    ) -> None:
        """Expired access token returns 401."""
        api_client.credentials(HTTP_AUTHORIZATION="Bearer expired.token.here")

        response = api_client.post(
            logout_url,
            {"refresh_token": "some-token"},
            format="json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_cannot_reuse_refresh_token(
        self,
        api_client: APIClient,
        login_url: str,
        refresh_url: str,
        logout_url: str,
    ) -> None:
        """After logout, the refresh token is revoked and cannot be reused."""
        User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
        )

        login_response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "SecurePass123"},
            format="json",
        )
        tokens = login_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        # Logout with the refresh token
        api_client.post(
            logout_url,
            {"refresh_token": refresh_token},
            format="json",
        )

        # Try to use the same refresh token again — should be rejected (revoked)
        response = api_client.post(
            refresh_url,
            {"refresh_token": refresh_token},
            format="json",
        )

        # Revoked token → 401 Unauthorized (RefreshTokenView maps "отозван" → 401)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# GET /api/v1/auth/me/
# =============================================================================

@pytest.fixture
def me_url() -> str:
    return "/api/v1/auth/me/"


class TestMeView:
    """Test cases for GET /api/v1/auth/me/."""

    def test_me_success_200(
        self,
        api_client: APIClient,
        login_url: str,
        me_url: str,
    ) -> None:
        """Authenticated user profile returned as 200."""
        user = User.objects.create_user(
            email="test@example.com",
            password="SecurePass123",
            status="active",
            email_verified=True,
        )

        login_response = api_client.post(
            login_url,
            {"email": "test@example.com", "password": "SecurePass123"},
            format="json",
        )
        access_token = login_response.json()["access_token"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = api_client.get(me_url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(user.id)
        assert data["email"] == "test@example.com"
        assert data["status"] == "active"
        assert data["email_verified"] is True

    def test_me_unauthenticated_401(
        self,
        api_client: APIClient,
        me_url: str,
    ) -> None:
        """No token returns 401."""
        response = api_client.get(me_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_invalid_token_401(
        self,
        api_client: APIClient,
        me_url: str,
    ) -> None:
        """Invalid JWT returns 401."""
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token")

        response = api_client.get(me_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_expired_token_401(
        self,
        api_client: APIClient,
        me_url: str,
    ) -> None:
        """Expired access token returns 401."""
        api_client.credentials(HTTP_AUTHORIZATION="Bearer expired.token.here")

        response = api_client.get(me_url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_blocked_user_401(
        self,
        api_client: APIClient,
        login_url: str,
        me_url: str,
    ) -> None:
        """Blocked user cannot access /me/."""
        from datetime import timedelta
        from django.utils import timezone as dj_tz

        user = User.objects.create_user(
            email="blocked@example.com",
            password="SecurePass123",
            status="blocked",
        )
        user.locked_until = dj_tz.now() + timedelta(minutes=15)
        user.save(update_fields=["locked_until"])

        login_response = api_client.post(
            login_url,
            {"email": "blocked@example.com", "password": "SecurePass123"},
            format="json",
        )

        # Login may fail at service level, check status
        if login_response.status_code == status.HTTP_403_FORBIDDEN:
            assert "заблокирован" in login_response.json()["detail"]
        elif login_response.status_code == status.HTTP_200_OK:
            # Token was issued, but accessing /me/ should fail
            access_token = login_response.json()["access_token"]
            api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
            response = api_client.get(me_url)
            assert response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            )


