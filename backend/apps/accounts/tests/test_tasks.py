"""Unit tests for Celery tasks."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from backend.apps.accounts.models import EmailConfirmationToken, User
from backend.apps.accounts.tasks.email_tasks import (
    send_confirmation_email,
    send_password_reset_email,
)
from backend.apps.accounts.tasks.maintenance_tasks import (
    cleanup_expired_tokens,
    unlock_user_accounts,
)


class TestSendConfirmationEmailTask(TestCase):
    """Tests for send_confirmation_email Celery task."""

    @patch("backend.apps.accounts.tasks.email_tasks._send_email_sync")
    def test_send_confirmation_email_success(self, mock_send: MagicMock) -> None:
        """Test successful email confirmation sending."""
        result = send_confirmation_email(
            user_id="test-user-id",
            email="test@example.com",
            token="test-token-123",
            confirmation_url="https://example.com/confirm",
        )

        assert result["status"] == "sent"
        assert result["user_id"] == "test-user-id"
        assert result["email"] == "test@example.com"
        mock_send.assert_called_once()

    @patch("backend.apps.accounts.tasks.email_tasks._send_email_sync")
    def test_send_confirmation_email_without_url(self, mock_send: MagicMock) -> None:
        """Test email confirmation without custom URL uses default."""
        result = send_confirmation_email(
            user_id="test-user-id",
            email="test@example.com",
            token="test-token-123",
        )

        assert result["status"] == "sent"
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "?token=test-token-123" in call_args[1]  # Body should contain token

    def test_send_confirmation_email_invalid_email(self) -> None:
        """Test that invalid email raises ValueError."""
        with self.assertRaises(ValueError) as context:
            send_confirmation_email(
                user_id="test-user-id",
                email="invalid-email",
                token="test-token-123",
            )
        assert "Invalid email address" in str(context.exception)


class TestSendPasswordResetEmailTask(TestCase):
    """Tests for send_password_reset_email Celery task."""

    @patch("backend.apps.accounts.tasks.email_tasks._send_email_sync")
    def test_send_password_reset_email_success(self, mock_send: MagicMock) -> None:
        """Test successful password reset email sending."""
        result = send_password_reset_email(
            user_id="test-user-id",
            email="test@example.com",
            token="reset-token-123",
            reset_url="https://example.com/reset",
        )

        assert result["status"] == "sent"
        assert result["user_id"] == "test-user-id"
        assert result["email"] == "test@example.com"
        mock_send.assert_called_once()

    @patch("backend.apps.accounts.tasks.email_tasks._send_email_sync")
    def test_send_password_reset_email_without_url(self, mock_send: MagicMock) -> None:
        """Test password reset without custom URL uses default."""
        result = send_password_reset_email(
            user_id="test-user-id",
            email="test@example.com",
            token="reset-token-123",
        )

        assert result["status"] == "sent"
        mock_send.assert_called_once()
        call_args = mock_send.call_args[0]
        assert "?token=reset-token-123" in call_args[1]

    def test_send_password_reset_email_invalid_email(self) -> None:
        """Test that invalid email raises ValueError."""
        with self.assertRaises(ValueError) as context:
            send_password_reset_email(
                user_id="test-user-id",
                email="not-an-email",
                token="reset-token-123",
            )
        assert "Invalid email address" in str(context.exception)


class TestCleanupExpiredTokensTask(TestCase):
    """Tests for cleanup_expired_tokens Celery task."""

    def setUp(self) -> None:
        """Create test users and tokens."""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpassword123",
        )

    def test_cleanup_expired_tokens_deletes_expired(self) -> None:
        """Test that expired tokens are deleted."""
        # Create expired token
        expired_token = EmailConfirmationToken.objects.create(
            user=self.user,
            token="expired-token",
            token_type="email_confirmation",
            expires_at=timezone.now() - timedelta(hours=1),
        )

        # Create valid token
        valid_token = EmailConfirmationToken.objects.create(
            user=self.user,
            token="valid-token",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        result = cleanup_expired_tokens()

        assert result["status"] == "completed"
        assert result["deleted_count"] == 1
        assert EmailConfirmationToken.objects.filter(token="expired-token").count() == 0
        assert EmailConfirmationToken.objects.filter(token="valid-token").count() == 1

    def test_cleanup_expired_tokens_keeps_used_tokens(self) -> None:
        """Test that used tokens are not deleted even if expired."""
        # Create expired but used token
        used_token = EmailConfirmationToken.objects.create(
            user=self.user,
            token="used-expired-token",
            token_type="email_confirmation",
            expires_at=timezone.now() - timedelta(hours=1),
            used_at=timezone.now() - timedelta(minutes=30),
        )

        result = cleanup_expired_tokens()

        assert result["status"] == "completed"
        assert result["deleted_count"] == 0
        assert EmailConfirmationToken.objects.filter(token="used-expired-token").count() == 1

    def test_cleanup_expired_tokens_no_tokens(self) -> None:
        """Test cleanup when no expired tokens exist."""
        # Create only valid tokens
        EmailConfirmationToken.objects.create(
            user=self.user,
            token="valid-token",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        result = cleanup_expired_tokens()

        assert result["status"] == "completed"
        assert result["deleted_count"] == 0


class TestUnlockUserAccountsTask(TestCase):
    """Tests for unlock_user_accounts Celery task."""

    def test_unlock_user_accounts_unlocks_expired(self) -> None:
        """Test that users with expired locks are unlocked."""
        # Create user with expired lock
        user = User.objects.create_user(
            email="locked@example.com",
            password="testpassword123",
            locked_until=timezone.now() - timedelta(hours=1),
            failed_login_attempts=5,
        )

        result = unlock_user_accounts()

        assert result["status"] == "completed"
        assert result["unlocked_count"] == 1

        user.refresh_from_db()
        assert user.locked_until is None
        assert user.failed_login_attempts == 0

    def test_unlock_user_accounts_keeps_active_locks(self) -> None:
        """Test that users with active locks are not unlocked."""
        # Create user with active lock
        user = User.objects.create_user(
            email="active-locked@example.com",
            password="testpassword123",
            locked_until=timezone.now() + timedelta(hours=1),
            failed_login_attempts=5,
        )

        result = unlock_user_accounts()

        assert result["status"] == "completed"
        assert result["unlocked_count"] == 0

        user.refresh_from_db()
        assert user.locked_until is not None
        assert user.failed_login_attempts == 5

    def test_unlock_user_accounts_no_locked_users(self) -> None:
        """Test unlock when no users have expired locks."""
        # Create user with active lock (should not be unlocked)
        User.objects.create_user(
            email="still-locked@example.com",
            password="testpassword123",
            locked_until=timezone.now() + timedelta(hours=1),
            failed_login_attempts=5,
        )

        result = unlock_user_accounts()

        assert result["status"] == "completed"
        assert result["unlocked_count"] == 0

    def test_unlock_user_accounts_ignores_unlocked_users(self) -> None:
        """Test that users without locks are ignored."""
        # Create user without lock
        User.objects.create_user(
            email="unlocked@example.com",
            password="testpassword123",
            failed_login_attempts=0,
        )

        result = unlock_user_accounts()

        assert result["status"] == "completed"
        assert result["unlocked_count"] == 0