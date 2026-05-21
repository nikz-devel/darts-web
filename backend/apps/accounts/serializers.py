"""API serializers for the accounts app."""

from __future__ import annotations

from rest_framework import serializers

from backend.apps.accounts.services.password_service import PasswordService


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration."""

    email = serializers.EmailField(
        max_length=254,
        help_text="Email address (RFC 5322 compliant, max 254 chars)",
    )
    password = serializers.CharField(
        write_only=True,
        help_text="Password (min 8 chars, letters and digits required)",
    )
    password_confirm = serializers.CharField(
        write_only=True,
        help_text="Password confirmation (must match password)",
    )

    def validate_email(self, value: str) -> str:
        """Normalize email to lowercase."""
        return value.lower().strip()

    def validate(self, attrs: dict) -> dict:
        """Validate password match."""
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({
                "password_confirm": "Пароли не совпадают",
            })
        # Validate password strength
        password_service = PasswordService()
        result = password_service.validate_password(attrs["password"])
        if not result.is_valid:
            raise serializers.ValidationError({
                "password": result.errors,
            })
        return attrs


class RegisterResponseSerializer(serializers.Serializer):
    """Response serializer for successful registration."""

    id = serializers.UUIDField(help_text="User UUID")
    email = serializers.EmailField(help_text="User email")
    status = serializers.CharField(help_text="Account status (pending/active)")
    message = serializers.CharField(
        required=False,
        default="Регистрация успешна.",
        help_text="Success message",
    )


class ConfirmEmailSerializer(serializers.Serializer):
    """Serializer for email confirmation."""

    token = serializers.CharField(
        help_text="Email confirmation token",
    )


class ConfirmEmailResponseSerializer(serializers.Serializer):
    """Response serializer for successful email confirmation."""

    user_id = serializers.UUIDField(help_text="User UUID")
    email = serializers.EmailField(help_text="User email")
    confirmed_at = serializers.DateTimeField(help_text="Confirmation timestamp")


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""

    email = serializers.EmailField(
        max_length=254,
        help_text="Email address",
    )
    password = serializers.CharField(
        write_only=True,
        help_text="Password",
    )

    def validate_email(self, value: str) -> str:
        """Normalize email to lowercase."""
        return value.lower().strip()


class TokenPairResponseSerializer(serializers.Serializer):
    """Response serializer for JWT token pair."""

    access_token = serializers.CharField(help_text="JWT access token")
    refresh_token = serializers.CharField(help_text="Refresh token (UUID)")
    token_type = serializers.CharField(help_text="Token type (Bearer)")
    expires_in = serializers.IntegerField(help_text="TTL in seconds")


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for token refresh."""

    refresh_token = serializers.CharField(
        help_text="Raw refresh token (UUID)",
    )


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout."""

    refresh_token = serializers.CharField(
        help_text="Raw refresh token to revoke",
    )


class UserSerializer(serializers.Serializer):
    """Serializer for current user profile."""

    id = serializers.UUIDField(help_text="User UUID")
    email = serializers.EmailField(help_text="User email")
    status = serializers.CharField(help_text="Account status")
    email_verified = serializers.BooleanField(help_text="Email verified flag")