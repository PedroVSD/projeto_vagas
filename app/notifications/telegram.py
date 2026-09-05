"""Adapter Telegram (Bot API)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.notifications.base import NotificationProvider

logger = logging.getLogger(__name__)

# Telegram throttling - 1 mensagem por minuto (configurável via LLM throttling + env)
_TELEGRAM_THROTTLE_SECONDS_DEFAULT = 60
_last_telegram_send: float = 0.0


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

        # throttling 1min entre mensagens - yaml throttling.telegram_throttle_seconds tem prioridade
        global _last_telegram_send
        from pathlib import Path

        import yaml

        from app.core.config import get_settings as _get_s

        try:
            throttle = _get_s().telegram_throttle_seconds
            yp = Path("config/search_queries.yaml")
            if yp.exists():
                ydata = yaml.safe_load(yp.read_text(encoding="utf-8")) or {}
                throttle = ydata.get("throttling", {}).get("telegram_throttle_seconds", throttle)
        except Exception:
            throttle = _TELEGRAM_THROTTLE_SECONDS_DEFAULT
        now = time.time()
        elapsed = now - _last_telegram_send
        if _last_telegram_send > 0 and elapsed < throttle:
            wait = throttle - elapsed
            logger.info("Telegram throttling: aguardando %.1fs para próxima mensagem (yaml %ss)", wait, throttle)
            time.sleep(wait)

        from app.notifications.formatting import format_job_message

        subject, body = format_job_message(payload, payload.get("score"))
        # Telegram API: sendMessage
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        text = f"{subject}\n\n{body}"
        # corta em 4096 chars (limite Telegram)
        if len(text) > 4000:
            text = text[:4000] + "\n... [cortado]"

        # Telegram parse_mode Markdown quebra com caracteres especiais (*_`[) - tenta Markdown, fallback plain
        def _post(parse_mode: str | None) -> httpx.Response:
            payload: dict[str, object] = {
                "chat_id": self.chat_id,
                "text": text,
                "disable_web_page_preview": True,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            with httpx.Client(timeout=10) as c:
                return c.post(url, json=payload)

        try:
            # 1ª tentativa: Markdown (formatação **)
            r = _post("Markdown")
            if r.status_code == 400:
                # log corpo do erro para diagnóstico (ex: can't parse entities)
                try:
                    err_data = r.json()
                    logger.warning("Telegram 400 Markdown: %s -> retry plain", err_data)
                except Exception:
                    logger.warning("Telegram 400 Markdown text: %s -> retry plain", r.text[:500])
                # 2ª tentativa: sem parse_mode (plain)
                r = _post(None)
            r.raise_for_status()
            data = r.json()
            if not data.get("ok"):
                logger.warning("Telegram api não ok: %s", data)
                return False
            logger.info("Telegram enviado para chat %s", self.chat_id)
            _last_telegram_send = time.time()
            return True
        except Exception as e:
            # httpx HTTPStatusError já inclui response body se raise_for_status
            logger.warning("Telegram send falhou: %s", e)
            return False
