"""Celery tasks for email sending."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from celery import shared_task

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)

# Email validation regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    """Check if email address is valid."""
    return bool(EMAIL_REGEX.match(email))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3, "countdown": 60},
    queue="emails",
    name="accounts.tasks.send_confirmation_email",
)
def send_confirmation_email(
    self,
    user_id: str,
    email: str,
    token: str,
    confirmation_url: str | None = None,
) -> dict:
    """Send email confirmation email to a newly registered user.

    This task is queued asynchronously via Celery.

    Args:
        user_id: UUID of the user.
        email: User's email address.
        token: Email confirmation token.
        confirmation_url: Optional base URL for the confirmation link.
            If not provided, the link will be constructed using a default.

    Returns:
        A dict with task result info.
    """
    if not is_valid_email(email):
        logger.error("Invalid email address: %s", email)
        raise ValueError(f"Invalid email address: {email}")

    # Build confirmation link
    if confirmation_url:
        link = f"{confirmation_url.rstrip('/')}/?token={token}"
    else:
        # Default frontend URL pattern (can be overridden via settings)
        frontend_base = "http://localhost:3000/confirm-email"
        link = f"{frontend_base}?token={token}"

    # Compose email content
    subject = "Подтверждение регистрации"
    body = f"""
Здравствуйте!

Для подтверждения email адреса перейдите по ссылке:
{link}

Ссылка действительна в течение 48 часов.

Если вы не регистрировались на нашем сайте, просто игнорируйте это письмо.
"""

    # In production, this would send via SMTP/SendGrid/SES.
    # For now, we log the email content and simulate sending.
    logger.info(
        "Sending confirmation email to %s for user %s",
        email,
        user_id,
        extra={
            "task": "send_confirmation_email",
            "user_id": user_id,
            "email": email,
            "subject": subject,
            "confirmation_link": link,
        },
    )

    # Simulate email sending (replace with real email backend in production)
    _send_email_sync(subject, body, email)

    return {
        "status": "sent",
        "user_id": user_id,
        "email": email,
    }


def _send_email_sync(subject: str, body: str, to_email: str) -> None:
    """Send email synchronously.

    This is a placeholder for a real email backend (SMTP, SendGrid, SES, etc.).
    In production, replace with your preferred email service.
    """
    logger.info(
        "EMAIL SENT\n  To: %s\n  Subject: %s\n  Body:\n%s",
        to_email,
        subject,
        body,
    )