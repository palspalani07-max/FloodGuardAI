from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime, timezone


class BaseProvider(ABC):
    name = "base"
    requires_auth = False
    available = True

    def __init__(self, settings):
        self.settings = settings
        self.last_success: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def config_missing(self) -> bool:
        """True when the provider needs credentials that are not configured."""
        return False

    @property
    def status(self) -> str:
        if not self.available:
            if self.config_missing():
                return "config-missing"
            return "unavailable"
        if self.last_error and (self.last_success is None or self.last_error_time > self.last_success):
            return "error"
        if self.last_success is None:
            return "idle"
        return "connected"

    @property
    def last_error_time(self) -> Optional[datetime]:
        return getattr(self, "_last_error_time", None)

    def _record_success(self):
        self.last_success = datetime.now(timezone.utc)
        self.last_error = None
        self._last_error_time = None

    def _record_error(self, error: str):
        self.last_error = str(error)[:300]
        self._last_error_time = datetime.now(timezone.utc)
        from ..logging_conf import log
        log.warning(f"provider {self.name} error: {error}")

    def status_info(self) -> dict:
        age = None
        if self.last_success:
            age = (datetime.now(timezone.utc) - self.last_success).total_seconds()
        return {
            "name": self.name,
            "status": self.status,
            "last_updated": self.last_success,
            "data_age_seconds": age,
            "data_type": "LIVE" if self.last_success else "UNAVAILABLE",
            "details": {
                "requires_auth": self.requires_auth,
                "config_missing": self.config_missing(),
                "last_error": self.last_error,
            },
        }