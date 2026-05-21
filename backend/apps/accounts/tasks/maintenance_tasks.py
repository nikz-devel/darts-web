"""Celery tasks for maintenance operations."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from celery import shared_task
from django.utils import timezone

if TYPE_CHECKING:
    from backend.apps.accounts.models import EmailConfirmationToken, User


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="maintenance",
    name="accounts.tasks.cleanup_expired_tokens",
)
def cleanup_expired_tokens(self) -> dict:
    """Delete expired and unused email confirmation tokens.

    This task runs hourly to clean up old tokens that are:
    - Expired (expires_at < now)
    - Never used (used_at is None)

    Returns:
        A dict with cleanup statistics.
    """
    from backend.apps.accounts.models import EmailConfirmationToken

    # Find expired and unused tokens
    expired_tokens = EmailConfirmationToken.objects.filter(
        expires_at__lt=timezone.now(),
        used_at__isnull=True,
    )

    count = expired_tokens.count()
    if count > 0:
        expired_tokens.delete()
        logger.info(
            "Cleaned up %d expired/unused tokens",
            count,
            extra={"task": "cleanup_expired_tokens", "deleted_count": count},
        )

    return {
        "status": "completed",
        "deleted_count": count,
    }


@shared_task(
    bind=True,
    queue="maintenance",
    name="accounts.tasks.unlock_user_accounts",
)
def unlock_user_accounts(self) -> dict:
    """Unlock user accounts whose lock period has passed.

    This task runs every 5 minutes to find users who:
    - Have locked_until set
    - Whose lock period has expired (locked_until < now)

    Returns:
        A dict with unlock statistics.
    """
    from backend.apps.accounts.models import User

    # Find locked users whose lock period has passed
    locked_users = User.objects.filter(
        locked_until__isnull=False,
        locked_until__lt=timezone.now(),
    )

    count = locked_users.count()
    if count > 0:
        locked_users.update(locked_until=None, failed_login_attempts=0)
        logger.info(
            "Unlocked %d user accounts",
            count,
            extra={"task": "unlock_user_accounts", "unlocked_count": count},
        )

    return {
        "status": "completed",
        "unlocked_count": count,
    }