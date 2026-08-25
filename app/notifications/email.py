"""Adapter Email via SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import get_settings
from app.notifications.base import NotificationProvider

logger = logging.getLogger(__name__)


class EmailProvider(NotificationProvider):
    name = "email"

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        smtp_from: str | None = None,
        smtp_to: str | None = None,
    ):
        s = get_settings()
        self.smtp_host = smtp_host or s.smtp_host
        self.smtp_port = smtp_port or s.smtp_port
        self.smtp_username = smtp_username or s.smtp_username
        self.smtp_password = smtp_password or s.smtp_password
        self.smtp_from = smtp_from or s.smtp_from
        self.smtp_to = smtp_to or s.smtp_to

    def is_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_to and self.smtp_from)

    def send(self, payload: dict[str, Any]) -> bool:
        if not self.is_enabled():
            logger.info("Email disabled (sem SMTP_HOST/TO/FROM)")
            return False

        from app.notifications.formatting import format_job_message

        subject, body = format_job_message(payload, payload.get("score"))

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.smtp_from
        msg["To"] = self.smtp_to
        msg.set_content(body)

        try:
            # usa STARTTLS se porta 587
            with smtplib.SMTP(self.smtp_host, self.smtp_port or 587, timeout=10) as server:
                if self.smtp_port in (587, 2587):
                    server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            logger.info("Email enviado para %s", self.smtp_to)
            return True
        except Exception as e:
            logger.warning("Email send falhou: %s", e)
            return False
