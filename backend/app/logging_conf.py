import logging
import json
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def setup_logging(log_level: str = "INFO"):
    logger = logging.getLogger("floodguard")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    if not logger.handlers:
        logger.addHandler(handler)
    return logger


log = setup_logging()
