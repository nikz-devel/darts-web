"""API views for the accounts app."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView, exception_handler

from backend.apps.accounts.authentication import JWTAuthentication
from backend.apps.accounts.models import EmailConfirmationToken, User
from backend.apps.accounts.serializers import (
    ConfirmEmailSerializer,
    ConfirmEmailResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    RefreshTokenSerializer,
    RegisterSerializer,
    RegisterResponseSerializer,
    TokenPairResponseSerializer,
    UserSerializer,
)
from backend.apps.accounts.services.authentication_service import (
    AuthenticationService,
    ServiceResult,
)
from backend.apps.accounts.services.token_service import TokenService
from backend.config.celery import app as celery_app

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """Custom REST framework exception handler.

    Ensures all errors return consistent JSON format:
    {"detail": "error message"}
    """
    response = exception_handler(exc, context)

    if response is not None:
        # DRF already formats ValidationError and other DRF exceptions
        return response

    # Handle non-DRF exceptions (should rarely happen)
    if isinstance(exc, ValidationError):
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    logger.exception("Unhandled exception in API: %s", exc)
    return Response(
        {"detail": "Внутренняя ошибка сервера"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


class RegisterView(APIView):
    """Handle user registration.

    POST /api/v1/auth/register/

    Creates a new user account with status=pending and sends
    a confirmation email asynchronously via Celery.
    """

    permission_classes = []  # Public endpoint
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Register a new user.

        Args:
            request: DRF request with body:
                {
                    "email": "user@example.com",
                    "password": "SecurePass123",
                    "password_confirm": "SecurePass123"
                }

        Returns:
            201: Registration successful, email sent
            400: Validation error (bad email, weak password, mismatch)
            409: Email already exists
        """
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors

            # Check if email already exists (from unique constraint)
            if "email" in errors and "already exists" in str(errors["email"]).lower():
                return Response(
                    {"detail": "Пользователь с таким email уже существует"},
                    status=status.HTTP_409_CONFLICT,
                )

            # Flatten errors to a single detail message
            flat_errors: list[str] = []
            for field, messages in errors.items():
                if isinstance(messages, list):
                    flat_errors.extend(str(m) for m in messages)
                else:
                    flat_errors.append(str(messages))

            return Response(
                {"detail": flat_errors[0] if flat_errors else "Ошибка валидации"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get client IP for rate limiting
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.META.get("REMOTE_ADDR", "")

        service = AuthenticationService()
        result = service.register_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            password_confirm=serializer.validated_data["password_confirm"],
            client_ip=client_ip,
        )

        if not result.success:
            error = result.error or "Ошибка регистрации"
            # Map to HTTP status
            if "IP" in error:
                return Response(
                    {"detail": error},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            if "уже существует" in error:
                return Response(
                    {"detail": result.error},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                {"detail": result.error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Queue async email confirmation
        user_id = result.data["id"]
        email = result.data["email"]
        token_record = EmailConfirmationToken.objects.filter(
            user_id=user_id,
            token_type="email_confirmation",
        ).first()

        if token_record:
            celery_app.send_task(
                "accounts.tasks.send_confirmation_email",
                kwargs={
                    "user_id": str(user_id),
                    "email": email,
                    "token": token_record.token,
                    "confirmation_url": None,
                },
            )
            logger.info(
                "Queued confirmation email task for user %s",
                user_id,
            )

        response_data = {
            "id": result.data["id"],
            "email": result.data["email"],
            "status": result.data["status"],
            "message": "Регистрация успешна. На email отправлено письмо для подтверждения.",
        }
        return Response(
            RegisterResponseSerializer(response_data).data,
            status=status.HTTP_201_CREATED,
        )


class ConfirmEmailView(APIView):
    """Handle email confirmation.

    POST /api/v1/auth/confirm-email/

    Validates the confirmation token and activates the user account.
    """

    permission_classes = []
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Confirm a user's email address.

        Args:
            request: DRF request with body:
                {"token": "confirmation_token_string"}

        Returns:
            200: Email confirmed successfully
            400: Invalid token, expired token, or token already used
        """
        serializer = ConfirmEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Неверный токен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = AuthenticationService()
        result = service.confirm_email(serializer.validated_data["token"])

        if not result.success:
            # Map service errors to HTTP status
            error = result.error or "Ошибка подтверждения"
            if "устарела" in error or "использован" in error:
                return Response(
                    {"detail": error},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {"detail": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ConfirmEmailResponseSerializer(result.data).data,
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    """Handle user authentication.

    POST /api/v1/auth/login/

    Authenticates a user with email and password, issues JWT tokens.
    Rate limited: after 3 failed attempts, account is locked for 15 minutes.
    """

    permission_classes = []  # Public endpoint
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Authenticate user and return JWT tokens.

        Args:
            request: DRF request with body:
                {
                    "email": "user@example.com",
                    "password": "SecurePass123"
                }

        Returns:
            200: Authentication successful, JWT tokens returned
            400: Validation error (bad email/password format)
            401: Invalid credentials
            429: Too many attempts, account locked
        """
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Неверные учетные данные"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = AuthenticationService()
        result = service.login(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )

        if not result.success:
            error = result.error or "Ошибка входа"
            # Map to HTTP status
            if "заблокирован" in error or "15 минут" in error:
                return Response(
                    {"detail": error},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {"detail": error},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            TokenPairResponseSerializer(result.data).data,
            status=status.HTTP_200_OK,
        )


class RefreshTokenView(APIView):
    """Handle JWT token refresh.

    POST /api/v1/auth/refresh/

    Accepts a valid refresh token, validates it, rotates the token pair,
    and returns new JWT access + refresh tokens.
    """

    permission_classes = []
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Refresh JWT tokens using rotation.

        Args:
            request: DRF request with body:
                {"refresh_token": "uuid..."}

        Returns:
            200: New token pair issued
            400: Invalid refresh token format
            401: Token expired, revoked, or invalid
        """
        serializer = RefreshTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Неверный refresh токен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = AuthenticationService()
        result = service.refresh_token(
            serializer.validated_data["refresh_token"],
        )

        if not result.success:
            error = result.error or "Ошибка обновления токена"
            if "устарел" in error:
                return Response(
                    {"detail": error},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(
                {"detail": error},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response(
            TokenPairResponseSerializer(result.data).data,
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """Handle user logout.

    POST /api/v1/auth/logout/

    Requires Bearer JWT token in Authorization header.
    Revokes the provided refresh token.
    """

    permission_classes = []
    authentication_classes = []

    def post(self, request: Request) -> Response:
        """Revoke refresh token and log out user.

        Args:
            request: DRF request with body:
                {"refresh_token": "uuid..."}
            Authorization: Bearer <access_token>

        Returns:
            200: Logout successful
            401: Missing or invalid access token
            400: Invalid refresh token
        """
        # Verify JWT access token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                {"detail": "Требуется авторизация"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access_token = auth_header[7:]  # Strip "Bearer "
        token_service = TokenService()
        try:
            payload = token_service.decode_access_token(access_token)
        except Exception:  # noqa: BLE001
            return Response(
                {"detail": "Неверный токен"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Validate and revoke refresh token
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": "Неверный refresh токен"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = AuthenticationService()
        result = service.logout(serializer.validated_data["refresh_token"])

        if not result.success:
            return Response(
                {"detail": result.error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Выход выполнен"},
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """Return the current authenticated user profile.

    GET /api/v1/auth/me/

    Requires Bearer JWT token in Authorization header.
    """

    permission_classes = []
    authentication_classes = []

    def get(self, request: Request) -> Response:
        """Return the current user's profile.

        Args:
            request: DRF request with Authorization: Bearer <access_token>

        Returns:
            200: User profile data
            401: Missing or invalid access token
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                {"detail": "Требуется авторизация"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access_token = auth_header[7:]  # Strip "Bearer "
        token_service = TokenService()
        try:
            payload = token_service.decode_access_token(access_token)
        except Exception:  # noqa: BLE001
            return Response(
                {"detail": "Неверный токен"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = payload.get("user_id")
        if not user_id:
            return Response(
                {"detail": "Неверный токен"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"detail": "Пользователь не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            UserSerializer({
                "id": str(user.id),
                "email": user.email,
                "status": user.status,
                "email_verified": user.email_verified,
            }).data,
            status=status.HTTP_200_OK,
        )


