"""Google Flood Forecasting provider (integration when access is available).

This provider supplies additional flood *context* (Google's river/stream flood
forecasts). It does NOT perform street-level urban drainage simulation - that is
FloodGuard's own coupled surface/drainage model.
"""
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from ..base import BaseProvider
from ...logging_conf import log


class GoogleFloodProvider(BaseProvider):
    name = "google_flood"
    requires_auth = True
    base_url = "https://floodforecasting.googleapis.com"

    def __init__(self, settings):
        super().__init__(settings)
        self.available = bool(settings.google_flood_api_key)
        self._client = httpx.Client(timeout=15.0)
        if not self.available:
            log.warning("Google Flood provider unavailable: no GOOGLE_FLOOD_API_KEY configured")

    def get_available_locations(self) -> List[dict]:
        if not self.available:
            return []
        try:
            r = self._client.get(
                f"{self.base_url}/v1/locations",
                params={"key": self.settings.google_flood_api_key},
            )
            if r.status_code == 200:
                self._record_success()
                return r.json().get("locations", [])
            self._record_error(f"locations HTTP {r.status_code}")
            return []
        except Exception as e:
            self._record_error(str(e))
            return []

    def get_forecast(self, location_latlng: str = "13.0827,80.2707") -> Optional[dict]:
        if not self.available:
            return None
        try:
            r = self._client.get(
                f"{self.base_url}/v1/forecasts",
                params={"location": location_latlng, "key": self.settings.google_flood_api_key},
            )
            if r.status_code == 200:
                self._record_success()
                return r.json()
            self._record_error(f"forecast HTTP {r.status_code}")
            return None
        except Exception as e:
            self._record_error(str(e))
            return None

    def get_flood_context(self, lat: float, lon: float) -> Optional[dict]:
        """Semantic wrapper around get_forecast."""
        data = self.get_forecast(f"{lat},{lon}")
        if not data:
            return None
        return {
            "source": "GOOGLE_FLOOD",
            "note": "Google flood context is supplementary. FloodGuard's street-level "
                    "prediction is produced by its own surface/drainage coupled model.",
            "payload": data,
        }