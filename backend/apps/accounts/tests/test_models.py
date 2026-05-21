"""Unit tests for accounts domain models."""

from datetime import timedelta
from uuid import UUID

import pytest
from django.utils import timezone

from backend.apps.accounts.models import (
    EmailConfirmationToken,
    RefreshToken,
    User,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pending_user(db) -> User:
    """A freshly created pending user."""
    return User.objects.create_user(
        email="test@example.com",
        password="SecurePass123",
    )


@pytest.fixture
def active_user(db) -> User:
    """An active user with verified email."""
    user = User.objects.create_user(
        email="active@example.com",
        password="SecurePass123",
    )
    user.mark_email_verified()
    return user


@pytest.fixture
def superuser(db) -> User:
    """A superuser."""
    return User.objects.create_superuser(
        email="admin@example.com",
        password="AdminPass123",
    )


# ---------------------------------------------------------------------------
# User model tests
# ---------------------------------------------------------------------------

class TestUserCreation:
    def test_create_user_has_uuid_pk(self, pending_user: User) -> None:
        assert isinstance(pending_user.id, UUID)

    def test_create_user_email_domain_is_normalized(self, db) -> None:
        user = User.objects.create_user(
            email="user@Example.COM",
            password="pass",
        )
        # Django's normalize_email lowercases only the domain part
        assert user.email == "user@example.com"

    def test_create_user_status_is_pending_by_default(self, pending_user: User) -> None:
        assert pending_user.status == "pending"

    def test_create_user_email_not_verified_by_default(self, pending_user: User) -> None:
        assert pending_user.email_verified is False

    def test_create_user_without_email_raises(self, db) -> None:
        with pytest.raises(ValueError, match="Email must be set"):
            User.objects.create_user(email="", password="pass")

    def test_create_superuser_is_active_and_verified(self, superuser: User) -> None:
        assert superuser.status == "active"
        assert superuser.email_verified is True
        assert superuser.is_staff is True
        assert superuser.is_superuser is True

    def test_create_superuser_requires_is_staff(self, db) -> None:
        with pytest.raises(ValueError, match="is_staff"):
            User.objects.create_superuser(
                email="x@example.com",
                password="pass",
                is_staff=False,
            )

    def test_create_superuser_requires_is_superuser(self, db) -> None:
        with pytest.raises(ValueError, match="is_superuser"):
            User.objects.create_superuser(
                email="x@example.com",
                password="pass",
                is_superuser=False,
            )

    def test_user_str_representation(self, pending_user: User) -> None:
        assert str(pending_user) == "test@example.com"

    def test_email_unique_constraint(self, db, pending_user: User) -> None:
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="test@example.com",
                password="another",
            )


class TestUserAccountMethods:
    def test_mark_email_verified_sets_active(self, pending_user: User) -> None:
        pending_user.mark_email_verified()
        assert pending_user.email_verified is True
        assert pending_user.status == "active"

    def test_mark_email_verified_already_active(self, active_user: User) -> None:
        active_user.mark_email_verified()
        assert active_user.status == "active"

    def test_increment_failed_login(self, pending_user: User) -> None:
        pending_user.increment_failed_login()
        assert pending_user.failed_login_attempts == 1

    def test_reset_failed_login(self, pending_user: User) -> None:
        pending_user.failed_login_attempts = 3
        pending_user.save()
        pending_user.reset_failed_login()
        assert pending_user.failed_login_attempts == 0
        assert pending_user.locked_until is None

    def test_is_locked_when_locked_until_in_future(self, pending_user: User) -> None:
        pending_user.locked_until = timezone.now() + timedelta(minutes=10)
        pending_user.save()
        assert pending_user.is_locked is True

    def test_is_locked_when_locked_until_in_past(self, pending_user: User) -> None:
        pending_user.locked_until = timezone.now() - timedelta(minutes=10)
        pending_user.save()
        assert pending_user.is_locked is False

    def test_is_locked_when_no_locked_until(self, pending_user: User) -> None:
        assert pending_user.is_locked is False


# ---------------------------------------------------------------------------
# EmailConfirmationToken tests
# ---------------------------------------------------------------------------

class TestEmailConfirmationToken:
    def test_create_token(self, pending_user: User, db) -> None:
        token = EmailConfirmationToken.objects.create(
            user=pending_user,
            token="abc123hashed",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        assert isinstance(token.id, UUID)
        assert token.is_used is False
        assert token.is_expired is False

    def test_token_expired(self, pending_user: User, db) -> None:
        token = EmailConfirmationToken.objects.create(
            user=pending_user,
            token="expired-token",
            token_type="email_confirmation",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert token.is_expired is True

    def test_token_mark_used(self, pending_user: User, db) -> None:
        token = EmailConfirmationToken.objects.create(
            user=pending_user,
            token="use-me",
            token_type="email_confirmation",
            expires_at=timezone.now() + timedelta(hours=48),
        )
        token.mark_used()
        assert token.is_used is True
        assert token.used_at is not None

    def test_token_str(self, pending_user: User, db) -> None:
        token = EmailConfirmationToken.objects.create(
            user=pending_user,
            token="str-test",
            token_type="password_reset",
            expires_at=timezone.now() + timedelta(hours=1),
        )
        assert "password_reset" in str(token)
        assert pending_user.email in str(token)


# ---------------------------------------------------------------------------
# RefreshToken tests
# ---------------------------------------------------------------------------

class TestRefreshToken:
    def test_create_refresh_token(self, pending_user: User, db) -> None:
        rt = RefreshToken.objects.create(
            user=pending_user,
            token_hash="hashed-value",
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert isinstance(rt.id, UUID)
        assert rt.is_expired is False
        assert rt.is_revoked is False

    def test_refresh_token_expired(self, pending_user: User, db) -> None:
        rt = RefreshToken.objects.create(
            user=pending_user,
            token_hash="old-hash",
            expires_at=timezone.now() - timedelta(days=1),
        )
        assert rt.is_expired is True

    def test_refresh_token_revoke(self, pending_user: User, db) -> None:
        rt = RefreshToken.objects.create(
            user=pending_user,
            token_hash="revoke-me",
            expires_at=timezone.now() + timedelta(days=7),
        )
        rt.revoke()
        assert rt.is_revoked is True
        assert rt.revoked_at is not None

    def test_refresh_token_str(self, pending_user: User, db) -> None:
        rt = RefreshToken.objects.create(
            user=pending_user,
            token_hash="str-hash",
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert pending_user.email in str(rt)

    def test_device_info_optional(self, pending_user: User, db) -> None:
        rt = RefreshToken.objects.create(
            user=pending_user,
            token_hash="no-device",
            expires_at=timezone.now() + timedelta(days=7),
        )
        assert rt.device_info is None
