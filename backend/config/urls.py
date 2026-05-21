"""URL Configuration for the Darts Tournament Platform."""

from django.contrib import admin
from django.urls import include, path

from backend.config.health import health_check, readiness_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health_check, name="health-check"),
    path("ready/", readiness_check, name="readiness-check"),
    path("api/v1/auth/", include("backend.apps.accounts.urls")),
]
