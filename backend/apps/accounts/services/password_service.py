"""Password validation and hashing service."""

from __future__ import annotations

import re
from dataclasses import dataclass


PASSWORD_MIN_LENGTH = 8
PASSWORD_REGEX = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


@dataclass
class PasswordValidationResult:
    """Result of password validation."""

    is_valid: bool
    errors: list[str]


class PasswordService:
    """Service for password validation and strength checks."""

    def validate_password(self, password: str) -> PasswordValidationResult:
        """Validate password strength.

        Args:
            password: The raw password string.

        Returns:
            PasswordValidationResult with is_valid flag and list of errors.
        """
        errors: list[str] = []

        if len(password) < PASSWORD_MIN_LENGTH:
            errors.append(
                f"Пароль должен содержать минимум {PASSWORD_MIN_LENGTH} символов"
            )
        if not PASSWORD_REGEX.match(password):
            errors.append(
                "Пароль должен содержать буквы и цифры"
            )

        return PasswordValidationResult(is_valid=len(errors) == 0, errors=errors)

    def check_password_strength(self, password: str) -> tuple[bool, list[str]]:
        """Alias for validate_password for backward compatibility.

        Args:
            password: The raw password string.

        Returns:
            A tuple of (is_valid, errors).
        """
        result = self.validate_password(password)
        return result.is_valid, result.errors