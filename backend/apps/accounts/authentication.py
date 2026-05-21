"""JWT Bearer token authentication for DRF."""

from __future__ import annotations

from typing import TYPE_CHECKING

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from backend.apps.accounts.models import User

if TYPE_CHECKING:
    from rest_framework.request import Request


class JWTAuthentication(authentication.BaseAuthentication):
    """DRF authentication class that reads and validates JWT Bearer tokens.

    Usage:
        class MyView(APIView):
            authentication_classes = [JWTAuthentication]

    The authenticated user is attached to request.user.
    """

    keyword = "Bearer"

    def authenticate(self, request: "Request") -> tuple[User, str] | None:
        """Validate the Authorization: Bearer <token> header.

        Args:
            request: DRF request object.

        Returns:
            A tuple (user, token) on success, None if no auth header.

        Raises:
            AuthenticationFailed: If the token is invalid or expired.
        """
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")

        if not auth_header:
            return None

        parts = auth_header.split()

        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Неверный формат заголовка авторизации")

        if parts[0] != self.keyword:
            return None  # Let other authenticators try

        token = parts[1]

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Токен устарел")
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed("Неверный токен")

        user_id = payload.get("user_id")
        if not user_id:
            raise exceptions.AuthenticationFailed("Неверный токен")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed("Пользователь не найден")

        if user.status == "blocked":
            raise exceptions.AuthenticationFailed("Аккаунт заблокирован")

        return (user, token)

    def authenticate_header(self, request: "Request") -> str:
        """Return the WWW-Authenticate header value for 401 responses."""
        return self.keyword