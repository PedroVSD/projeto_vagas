import json
import logging
import sys

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # inclui extras sem expor secrets
        if hasattr(record, "metrics"):
            payload["metrics"] = getattr(record, "metrics")
        if record.exc_info and record.exc_info[0]:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    # LOG_FORMAT=json para estruturado (Fase 7), default text
    log_format = getattr(settings, "log_format", "text")

    if log_format == "json":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logging.basicConfig(level=level, handlers=[handler])
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
    # Silencia logs verbosos de libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # nunca logar secrets (mascarar em extra)
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
