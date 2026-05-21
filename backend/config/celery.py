"""
Celery application configuration.

Sets up Celery with Django settings and auto-discovers tasks.
"""

import os
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

app = Celery("darts_tournament")

# Use Django settings for Celery configuration
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    "cleanup-expired-tokens-hourly": {
        "task": "accounts.tasks.cleanup_expired_tokens",
        "schedule": crontab(minute=0, hour="*"),  # Run every hour at minute 0
    },
    "unlock-user-accounts-every-5-min": {
        "task": "accounts.tasks.unlock_user_accounts",
        "schedule": timedelta(minutes=5),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:
    """Simple task to verify Celery is working."""
    print(f"Request: {self.request!r}")
