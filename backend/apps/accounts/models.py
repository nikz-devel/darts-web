"""Domain models for the Authentication bounded context.

Contains:
- User (Aggregate Root)
- EmailConfirmationToken
- RefreshToken
"""

from __future__ import annotations

import uuid

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin

from .managers import UserManager


# ---------------------------------------------------------------------------
# Constants / Choices
# ---------------------------------------------------------------------------

USER_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("active", "Active"),
    ("blocked", "Blocked"),
]

TOKEN_TYPE_CHOICES = [
    ("email_confirmation", "Email Confirmation"),
    ("password_reset", "Password Reset"),
]


# ---------------------------------------------------------------------------
# User — Aggregate Root
# ---------------------------------------------------------------------------

class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model using email as the unique identifier."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True, max_length=254)
    status = models.CharField(
        max_length=20,
        choices=USER_STATUS_CHOICES,
        default="pending",
    )
    email_verified = models.BooleanField(default=False)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.email

    def mark_email_verified(self) -> None:
        """Mark the user's email as verified and set status to active."""
        self.email_verified = True
        if self.status == "pending":
            self.status = "active"
        self.save(update_fields=["email_verified", "status", "updated_at"])

    def increment_failed_login(self) -> None:
        """Increment failed login counter. Caller decides when to lock."""
        self.failed_login_attempts = models.F("failed_login_attempts") + 1
        self.save(update_fields=["failed_login_attempts", "updated_at"])
        self.refresh_from_db()

    def reset_failed_login(self) -> None:
        """Reset failed login counter after a successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until", "updated_at"])

    @property
    def is_locked(self) -> bool:
        """Check if the account is currently locked."""
        if self.locked_until is None:
            return False
        from django.utils import timezone
        return timezone.now() < self.locked_until


# ---------------------------------------------------------------------------
# EmailConfirmationToken
# ---------------------------------------------------------------------------

class EmailConfirmationToken(models.Model):
    """Token for email confirmation and password reset flows."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="confirmation_tokens",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    token_type = models.CharField(
        max_length=30,
        choices=TOKEN_TYPE_CHOICES,
    )
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_confirmation_tokens"
        indexes = [
            models.Index(fields=["token", "token_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.token_type} token for {self.user.email}"

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if the token has already been used."""
        return self.used_at is not None

    def mark_used(self) -> None:
        """Mark the token as used."""
        from django.utils import timezone
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])


# ---------------------------------------------------------------------------
# RefreshToken
# ---------------------------------------------------------------------------

class RefreshToken(models.Model):
    """Stored refresh token for JWT rotation and revocation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="refresh_tokens",
    )
    token_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    device_info = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refresh_tokens"

    def __str__(self) -> str:
        return f"Refresh token for {self.user.email}"

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_revoked(self) -> bool:
        """Check if the token has been revoked."""
        return self.revoked_at is not None

    def revoke(self) -> None:
        """Revoke this refresh token."""
        from django.utils import timezone
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])
