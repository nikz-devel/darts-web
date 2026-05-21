"""Core authentication service handling registration, login, and related flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from django.utils import timezone as dj_timezone

from backend.apps.accounts.models import EmailConfirmationToken, RefreshToken, User
from backend.apps.accounts.services.rate_limit_service import (
    RateLimitService,
)
from backend.apps.accounts.services.token_service import (
    TokenPairDTO,
    TokenService,
)

if TYPE_CHECKING:
    pass


EMAIL_CONFIRMATION_TTL_HOURS = 48
PASSWORD_RESET_TTL_HOURS = 48


@dataclass
class UserDTO:
    """Public user data transfer object."""

    id: str
    email: str
    status: str


@dataclass
class ServiceResult:
    """Generic service operation result."""

    success: bool
    data: dict | None = None
    error: str | None = None


class AuthenticationService:
    """Service encapsulating authentication use cases.

    Handles:
    - User registration with email confirmation
    - Email confirmation
    - Login with rate limiting
    - JWT token generation and refresh
    - Password reset
    - Logout (token revocation)
    """

    def __init__(self) -> None:
        self._token_service = TokenService()
        self._rate_limiter = RateLimitService()

    def register_user(
        self,
        email: str,
        password: str,
        password_confirm: str,
        client_ip: str | None = None,
    ) -> ServiceResult:
        """Register a new user and send email confirmation.

        Args:
            email: User's email address.
            password: Plain text password.
            password_confirm: Password confirmation.
            client_ip: Client's IP address for rate limiting.

        Returns:
            ServiceResult with UserDTO on success, error message otherwise.
        """
        # Normalize email
        email = email.lower().strip()

        # IP-based rate limiting (5 per IP per hour)
        if client_ip:
            reg_check = self._rate_limiter.check_registration(client_ip)
            if not reg_check.allowed:
                return ServiceResult(
                    success=False,
                    error="Слишком много попыток регистрации с этого IP. Попробуйте через час",
                )

        # Validate password match
        if password != password_confirm:
            return ServiceResult(
                success=False,
                error="Пароли не совпадают",
            )

        # Check email uniqueness
        if User.objects.filter(email__iexact=email).exists():
            return ServiceResult(
                success=False,
                error="Пользователь с таким email уже существует",
            )

        # Create user (status=pending by default)
        user = User.objects.create_user(
            email=email,
            password=password,
        )

        # Record registration attempt for IP rate limiting
        if client_ip:
            self._rate_limiter.record_registration(client_ip)

        # Generate email confirmation token
        self._create_confirmation_token(user, "email_confirmation")

        return ServiceResult(
            success=True,
            data={
                "id": str(user.id),
                "email": user.email,
                "status": user.status,
            },
        )

    def confirm_email(self, token: str) -> ServiceResult:
        """Confirm a user's email address using a token.

        Args:
            token: The raw confirmation token string.

        Returns:
            ServiceResult indicating success or failure.
        """
        try:
            token_record = EmailConfirmationToken.objects.select_related("user").get(
                token=token,
                token_type="email_confirmation",
            )
        except EmailConfirmationToken.DoesNotExist:
            return ServiceResult(
                success=False,
                error="Неверный токен",
            )

        if token_record.is_used:
            return ServiceResult(
                success=False,
                error="Токен уже использован",
            )

        if token_record.is_expired:
            return ServiceResult(
                success=False,
                error="Ссылка устарела",
            )

        user = token_record.user
        user.mark_email_verified()
        token_record.mark_used()

        return ServiceResult(
            success=True,
            data={
                "user_id": str(user.id),
                "email": user.email,
                "confirmed_at": dj_timezone.now().isoformat(),
            },
        )

    def login(self, email: str, password: str) -> ServiceResult:
        """Authenticate a user and issue JWT tokens.

        Implements rate limiting: after 3 failed attempts, the account
        is locked for 15 minutes.

        Args:
            email: User's email address.
            password: Plain text password.

        Returns:
            ServiceResult with TokenPairDTO on success, error otherwise.
        """
        email = email.lower().strip()

        # Rate limiting check
        check = self._rate_limiter.check_login(email)
        if not check.allowed:
            return ServiceResult(
                success=False,
                error="Слишком много попыток. Попробуйте через 15 минут",
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return ServiceResult(
                success=False,
                error="Неверные учетные данные",
            )

        # Check if account is locked
        if user.is_locked:
            return ServiceResult(
                success=False,
                error="Аккаунт заблокирован",
            )

        # Verify password
        if not user.check_password(password):
            self._handle_failed_login(user, email)
            return ServiceResult(
                success=False,
                error="Неверные учетные данные",
            )

        # Successful login — reset counters and issue tokens
        user.reset_failed_login()
        self._rate_limiter.reset_login(email)

        access_token = self._token_service.generate_access_token(user)
        refresh_token = self._generate_refresh_token(user)

        return ServiceResult(
            success=True,
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": self._token_service.get_access_token_ttl(),
            },
        )

    def refresh_token(self, refresh_token: str) -> ServiceResult:
        """Refresh JWT tokens using a valid refresh token.

        Implements token rotation: a used refresh token is revoked
        and a new pair is issued.

        Args:
            refresh_token: The raw refresh token string.

        Returns:
            ServiceResult with new TokenPairDTO on success.
        """
        token_hash = self._token_service.hash_token(refresh_token)

        try:
            token_record = RefreshToken.objects.select_related("user").get(
                token_hash=token_hash,
            )
        except RefreshToken.DoesNotExist:
            return ServiceResult(
                success=False,
                error="Неверный refresh токен",
            )

        if token_record.is_revoked:
            return ServiceResult(
                success=False,
                error="Токен отозван",
            )

        if token_record.is_expired:
            return ServiceResult(
                success=False,
                error="Refresh токен устарел",
            )

        user = token_record.user

        # Rotate: revoke old token and issue new pair
        token_record.revoke()
        new_access_token = self._token_service.generate_access_token(user)
        new_refresh_token = self._generate_refresh_token(user)

        return ServiceResult(
            success=True,
            data={
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "Bearer",
                "expires_in": self._token_service.get_access_token_ttl(),
            },
        )

    def request_password_reset(self, email: str) -> ServiceResult:
        """Initiate password reset flow for a user.

        Always returns success to prevent email enumeration attacks.

        Args:
            email: User's email address.

        Returns:
            ServiceResult with success=True regardless of whether
            the email exists.
        """
        email = email.lower().strip()

        try:
            user = User.objects.get(email__iexact=email)
            self._create_confirmation_token(user, "password_reset")
        except User.DoesNotExist:
            pass  # Silently ignore to prevent enumeration

        return ServiceResult(
            success=True,
            data={"message": "Если email существует, письмо отправлено"},
        )

    def reset_password(
        self,
        token: str,
        new_password: str,
        password_confirm: str,
    ) -> ServiceResult:
        """Reset user's password using a valid reset token.

        After reset, all active sessions (refresh tokens) are revoked.

        Args:
            token: The raw password reset token.
            new_password: The new password.
            password_confirm: Password confirmation.

        Returns:
            ServiceResult indicating success or failure.
        """
        if new_password != password_confirm:
            return ServiceResult(
                success=False,
                error="Пароли не совпадают",
            )

        try:
            token_record = EmailConfirmationToken.objects.select_related("user").get(
                token=token,
                token_type="password_reset",
            )
        except EmailConfirmationToken.DoesNotExist:
            return ServiceResult(
                success=False,
                error="Неверный токен",
            )

        if token_record.is_used:
            return ServiceResult(
                success=False,
                error="Токен уже использован",
            )

        if token_record.is_expired:
            return ServiceResult(
                success=False,
                error="Ссылка устарела",
            )

        user = token_record.user
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])

        token_record.mark_used()

        # Revoke all active sessions
        RefreshToken.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=dj_timezone.now()
        )

        return ServiceResult(
            success=True,
            data={
                "user_id": str(user.id),
                "changed_at": dj_timezone.now().isoformat(),
            },
        )

    def logout(self, refresh_token: str) -> ServiceResult:
        """Log out a user by revoking their refresh token.

        Args:
            refresh_token: The raw refresh token to revoke.

        Returns:
            ServiceResult indicating success or failure.
        """
        token_hash = self._token_service.hash_token(refresh_token)

        try:
            token_record = RefreshToken.objects.get(token_hash=token_hash)
            token_record.revoke()
            return ServiceResult(success=True, data={"message": "Выход выполнен"})
        except RefreshToken.DoesNotExist:
            return ServiceResult(success=False, error="Токен не найден")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_confirmation_token(
        self,
        user: User,
        token_type: str,
    ) -> EmailConfirmationToken:
        """Create a time-limited email confirmation or password reset token."""
        # Generate a secure random token
        import secrets
        raw_token = secrets.token_urlsafe(32)

        expires_at = dj_timezone.now() + timedelta(
            hours=EMAIL_CONFIRMATION_TTL_HOURS
            if token_type == "email_confirmation"
            else PASSWORD_RESET_TTL_HOURS
        )

        return EmailConfirmationToken.objects.create(
            user=user,
            token=raw_token,
            token_type=token_type,
            expires_at=expires_at,
        )

    def _generate_refresh_token(self, user: User) -> str:
        """Create and store a refresh token for a user."""
        raw_token = self._token_service.generate_refresh_token()
        expires_at = dj_timezone.now() + self._token_service.get_refresh_token_ttl()

        RefreshToken.objects.create(
            user=user,
            token_hash=self._token_service.hash_token(raw_token),
            expires_at=expires_at,
        )

        return raw_token

    def _handle_failed_login(self, user: User, email: str) -> None:
        """Increment failed login counter and apply lockout if needed."""
        user.increment_failed_login()
        user.refresh_from_db()

        rate_check = self._rate_limiter.record_failed_login(email)

        if not rate_check.allowed:
            # Lock the account when rate limit is exceeded
            user.locked_until = dj_timezone.now() + timedelta(
                minutes=15
            )
            user.save(update_fields=["locked_until"])