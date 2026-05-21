"""
Celery application configuration.

Sets up Celery with Django settings and auto-discovers tasks.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

app = Celery("darts_tournament")

# Use Django settings for Celery configuration
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:
    """Simple task to verify Celery is working."""
    print(f"Request: {self.request!r}")
