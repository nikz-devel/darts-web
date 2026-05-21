"""
Tests for Django settings configuration.
"""

import os
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings


class TestSettings(TestCase):
    """Unit tests for application configuration."""

    def test_database_configured(self) -> None:
        """DATABASES should be configured."""
        assert "default" in settings.DATABASES

    def test_celery_broker_url(self) -> None:
        """Celery broker URL should be set."""
        assert hasattr(settings, "CELERY_BROKER_URL")

    def test_logging_configured(self) -> None:
        """LOGGING dict should be configured with console handler."""
        assert "handlers" in settings.LOGGING
        assert "console" in settings.LOGGING["handlers"]

    def test_auth_user_model_is_custom(self) -> None:
        """AUTH_USER_MODEL should point to our custom User model."""
        assert settings.AUTH_USER_MODEL == "accounts.User"

    @override_settings(DEBUG=True)
    def test_debug_can_be_enabled(self) -> None:
        """DEBUG should be overridable to True."""
        assert settings.DEBUG is True
