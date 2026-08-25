"""Adapter Telegram (Bot API)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.notifications.base import NotificationProvider

logger = logging.getLogger(__name__)


class TelegramProvider(NotificationProvider):
    name = "telegram"

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        s = get_settings()
        self.bot_token = bot_token or s.telegram_bot_token
        self.chat_id = chat_id or s.telegram_chat_id

    def is_enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send(self, payload: dict[str, Any]) -> bool:
        if not self.is_enabled():
            logger.info("Telegram disabled (sem TELEGRAM_BOT_TOKEN/CHAT_ID)")
            return False

        from app.notifications.formatting import format_job_message

        subject, body = format_job_message(payload, payload.get("score"))
        # Telegram API: sendMessage
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        text = f"{subject}\n\n{body}"
        # corta em 4096 chars (limite Telegram)
        if len(text) > 4000:
            text = text[:4000] + "\n... [cortado]"

        try:
            with httpx.Client(timeout=10) as c:
                r = c.post(
                    url,
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                )
                r.raise_for_status()
                data = r.json()
                if not data.get("ok"):
                    logger.warning("Telegram api não ok: %s", data)
                    return False
                logger.info("Telegram enviado para chat %s", self.chat_id)
                return True
        except Exception as e:
            logger.warning("Telegram send falhou: %s", e)
            return False
