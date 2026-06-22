import json
import logging
from datetime import UTC, datetime
from typing import Literal


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def configure_logging(level: str, log_format: Literal["text", "json"] = "text") -> None:
    if log_format == "json":
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logging.basicConfig(
            level=level.upper(),
            handlers=[handler],
            force=True,
        )
        return

    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
