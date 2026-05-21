"""Django apps package — contains all bounded context modules."""

from django.apps import AppConfig


class AppsConfig(AppConfig):
    """Main app configuration for the backend apps package."""

    name = "backend.apps"
    label = "apps"
    verbose_name = "Darts Tournament Apps"

