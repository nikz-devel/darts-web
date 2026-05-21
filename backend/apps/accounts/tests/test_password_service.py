"""Unit tests for PasswordService."""

from __future__ import annotations

import pytest

from backend.apps.accounts.services.password_service import (
    PASSWORD_MIN_LENGTH,
    PasswordService,
    PasswordValidationResult,
)

pytestmark = pytest.mark.django_db


class TestPasswordService:
    """Test cases for PasswordService."""

    @pytest.fixture
    def service(self) -> PasswordService:
        return PasswordService()

    # ------------------------------------------------------------------
    # validate_password
    # ------------------------------------------------------------------

    def test_valid_password_passes(self, service: PasswordService) -> None:
        result = service.validate_password("SecurePass123")
        assert result.is_valid is True
        assert result.errors == []

    def test_too_short_password_fails(self, service: PasswordService) -> None:
        result = service.validate_password("Short1")
        assert result.is_valid is False
        assert any(f"минимум {PASSWORD_MIN_LENGTH}" in e for e in result.errors)

    def test_no_digits_fails(self, service: PasswordService) -> None:
        result = service.validate_password("AllLettersOnly")
        assert result.is_valid is False
        assert any("буквы и цифры" in e for e in result.errors)

    def test_no_letters_fails(self, service: PasswordService) -> None:
        result = service.validate_password("1234567890")
        assert result.is_valid is False
        assert any("буквы и цифры" in e for e in result.errors)

    def test_empty_password_fails(self, service: PasswordService) -> None:
        result = service.validate_password("")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_exactly_min_length_with_letters_and_digits_passes(
        self, service: PasswordService
    ) -> None:
        # min length is 8, must have letter + digit
        result = service.validate_password("Pass1234")
        assert result.is_valid is True

    def test_multiple_errors_reported(self, service: PasswordService) -> None:
        result = service.validate_password("weak")
        assert result.is_valid is False
        assert len(result.errors) == 2  # too short + no digits

    # ------------------------------------------------------------------
    # check_password_strength (alias)
    # ------------------------------------------------------------------

    def test_check_password_strength_returns_tuple(self, service: PasswordService) -> None:
        is_valid, errors = service.check_password_strength("SecurePass123")
        assert is_valid is True
        assert errors == []

    def test_check_password_strength_consistent_with_validate(
        self, service: PasswordService
    ) -> None:
        password = "Weak1"
        result = service.validate_password(password)
        is_valid, errors = service.check_password_strength(password)
        assert is_valid == result.is_valid
        assert errors == result.errors