"""Fase 4 - Interface NotificationProvider (adapter)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NotificationProvider(ABC):
    name: str  # ex: "email", "telegram"

    @abstractmethod
    def is_enabled(self) -> bool:
        """Retorna True se credenciais configuradas."""
        ...

    @abstractmethod
    def send(self, payload: dict[str, Any]) -> bool:
        """Envia notificação. Retorna True se sucesso.

        payload contém: title, company, url, score, classification, etc.
        Não deve levantar exceção para falha recuperável — retorna False e loga.
        """
        ...
