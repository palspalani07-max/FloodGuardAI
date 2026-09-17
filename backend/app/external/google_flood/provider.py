"""Google Flood Forecasting provider (real API, river/stream flood context).

This provider supplies supplementary flood *context* from Google's riverine
flood forecasts (Flood Hub / Flood Forecasting API). It does NOT perform
street-level urban drainage simulation - that is FloodGuard's own coupled
surface/drainage model.

Documented API used (https://developers.google.com/flood-forecasting/rest):
  - POST /v1/floodStatus:searchLatestFloodStatusByArea
        body {"regionCode": "IN"}  -> {"floodStatuses": [FloodStatus]}
  - GET  /v1/gauges:queryGaugeForecasts?gaugeIds=... -> gauge forecasts

Each FloodStatus carries riverine ``severity`` (NO_FLOODING, ABOVE_NORMAL,
SEVERE, EXTREME, ...), gauge location, issued time and forecast trend.

Auth is the API key query param (GOOGLE_FLOOD_API_KEY from .env). When the key
is absent the provider reports ``config-missing`` and the pipeline simply skips
it. Google data is never fabricated - errors degrade to no-context, and
FloodGuard street-level predictions remain authoritative.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from ..base import BaseProvider
from ...logging_conf import log

_BASE_URL = "https://floodforecasting.googleapis.com"
_DEFAULT_REGION = "IN"


def _haversine_km(la1: float, lo1: float, la2: float, lo2: float) -> float:
    from math import asin, cos, radians, sin, sqrt
    R = 6371.0
    p1, p2 = radians(la1), radians(la2)
    dp = radians(la2 - la1)
    dl = radians(lo2 - lo1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * R * asin(sqrt(a))


class GoogleFloodProvider(BaseProvider):
    name = "google_flood"
    requires_auth = True
    base_url = _BASE_URL

    def __init__(self, settings):
        super().__init__(settings)
        self.available = bool(settings.google_flood_api_key)
        self._client = httpx.Client(timeout=15.0)
        self._last_context: Optional[dict] = None
        if not self.available:
            log.warning("Google Flood provider config-missing: GOOGLE_FLOOD_API_KEY not configured")

    def config_missing(self) -> bool:
        return not bool(self.settings.google_flood_api_key)

    def _key_params(self) -> dict:
        return {"key": self.settings.google_flood_api_key}

    # ------------------------------------------------------------------
    # Official endpoints
    # ------------------------------------------------------------------
    def search_flood_statuses(self, region_code: str = _DEFAULT_REGION,
                              loop: Optional[List[dict]] = None,
                              page_size: int = 50) -> List[dict]:
        """POST /v1/floodStatus:searchLatestFloodStatusByArea.

        Returns the latest riverine flood statuses for a region (default India).
        """
        if not self.available:
            return []
        body: dict = {"pageSize": page_size}
        if loop:
            body["loop"] = {"points": loop}
        else:
            body["regionCode"] = region_code
        try:
            r = self._client.post(
                f"{self.base_url}/v1/floodStatus:searchLatestFloodStatusByArea",
                params=self._key_params(),
                json=body,
            )
            if r.status_code == 200:
                self._record_success()
                statuses = (r.json().get("floodStatuses", []) or [])
                log.info(f"Google Flood Forecasting returned {len(statuses)} flood statuses ({region_code})")
                return statuses
            self._record_error(f"floodStatus HTTP {r.status_code}")
            return []
        except Exception as e:
            self._record_error(f"search_flood_statuses: {e}")
            return []

    def query_gauge_forecasts(self, gauge_ids: List[str],
                              issued_time_start: Optional[str] = None) -> Dict[str, dict]:
        """GET /v1/gauges:queryGaugeForecasts -> {gaugeId: ForecastSet}."""
        if not self.available or not gauge_ids:
            return {}
        params = {"gaugeIds": gauge_ids[:500], **self._key_params()}
        if issued_time_start:
            params["issuedTimeStart"] = issued_time_start
        try:
            r = self._client.get(f"{self.base_url}/v1/gauges:queryGaugeForecasts", params=params)
            if r.status_code == 200:
                self._record_success()
                return (r.json().get("forecasts", {}) or {})
            self._record_error(f"gauges HTTP {r.status_code}")
            return {}
        except Exception as e:
            self._record_error(f"query_gauge_forecasts: {e}")
            return {}

    # ------------------------------------------------------------------
    # Back-compatible helpers
    # ------------------------------------------------------------------
    def get_available_locations(self) -> List[dict]:
        """Available flood gauges (latest status per gauge) in the region."""
        return self.search_flood_statuses()

    def get_floods(self, limit: int = 10) -> List[dict]:
        """Latest active riverine flood statuses (severity != NO_FLOODING/UNKNOWN)."""
        statuses = self.search_flood_statuses()
        active = [
            s for s in statuses
            if str(s.get("severity", "")).upper() not in ("NO_FLOODING", "UNKNOWN", "SEVERITY_UNSPECIFIED")
        ]
        return active[:limit]

    def get_forecast(self, lat: float, lon: float,
                     max_distance_km: float = 100.0) -> Optional[dict]:
        """Nearest flood status (context) to a lat/lon that is non-null."""
        if not self.available:
            return None
        statuses = self.search_flood_statuses()
        if not statuses:
            return None
        nearest = None
        best = None
        for s in statuses:
            loc = s.get("gaugeLocation") or {}
            la = loc.get("latitude")
            lo = loc.get("longitude")
            if la is None or lo is None:
                continue
            d = _haversine_km(lat, lon, float(la), float(lo))
            if d > max_distance_km:
                continue
            if best is None or d < best:
                best, nearest = d, s
        if nearest is None:
            self._record_error(f"No Google flood gauge within {max_distance_km}km of ({lat},{lon})")
            return None
        self._record_success()
        return nearest

    # ------------------------------------------------------------------
    # Normalized context + risk mapping
    # ------------------------------------------------------------------
    def get_flood_context(self, lat: float, lon: float,
                          region_code: str = _DEFAULT_REGION) -> Optional[dict]:
        """Aggregate Google's riverine flood status into a normalized context."""
        if not self.available:
            return None
        statuses = self.search_flood_statuses(region_code=region_code)
        if not statuses:
            return None
        near = []
        for s in statuses:
            loc = s.get("gaugeLocation") or {}
            la, lo = loc.get("latitude"), loc.get("longitude")
            if la is None or lo is None:
                continue
            near.append((_haversine_km(lat, lon, float(la), float(lo)), s))
        near.sort(key=lambda t: t[0])
        closest = near[0][1] if near else None

        risks = [self._classify_risk(s.get("severity", "")) for _, s in near]
        risk_rank = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "SEVERE": 3, "EXTREME": 4}
        top_risk = max(
            (r for r in risks),
            key=lambda r: risk_rank.get(r, 0),
            default="LOW",
        )
        top_status = max(near, key=lambda t: risk_rank.get(
            self._classify_risk(t[1].get("severity", "")), 0))[1] if near else None

        context = {
            "source": "GOOGLE_FLOOD_HUB",
            "note": "Google flood context is river/stream-scale and supplementary. "
                    "FloodGuard's street-level prediction is produced by its own "
                    "surface/drainage coupled model.",
            "region_code": region_code,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "radius_km": 200.0,
            "gauge_count_checked": len(near),
            "risk_level": top_risk,
            "closest_gauge": {
                "gauge_id": (closest or {}).get("gaugeId"),
                "distance_km": round(near[0][0], 1) if near else None,
                "severity": str((closest or {}).get("severity", "UNKNOWN")).upper(),
                "issued_time": (closest or {}).get("issuedTime"),
                "forecast_trend": (closest or {}).get("forecastTrend"),
                "quality_verified": bool((closest or {}).get("qualityVerified", False)),
            } if closest else None,
            "top_gauge": {
                "gauge_id": (top_status or {}).get("gaugeId"),
                "severity": str((top_status or {}).get("severity", "UNKNOWN")).upper(),
                "issued_time": (top_status or {}).get("issuedTime"),
                "map_inference_type": (top_status or {}).get("mapInferenceType"),
            } if top_status else None,
            "gauge_count_high_risk": len([r for r in risks if r in ("HIGH", "SEVERE", "EXTREME")]),
        }
        self._last_context = context
        return context

    def _classify_risk(self, flood_severity) -> str:
        """Map a Google riverine severity to a FloodGuard-style risk label."""
        if not flood_severity:
            return "UNKNOWN"
        s = str(flood_severity).strip().upper()
        map = {
            "NO_FLOODING": "LOW",
            "UNKNOWN": "LOW",
            "SEVERITY_UNSPECIFIED": "UNKNOWN",
            "ABOVE_NORMAL": "HIGH",
            "SEVERE": "SEVERE",
            "EXTREME": "EXTREME",
        }
        return map.get(s, "UNKNOWN")

    def get_key_info(self) -> Optional[dict]:
        """Return metadata about the configured key (without exposing it)."""
        if not self.available:
            return {"configured": False, "status": "config-missing"}
        return {
            "configured": True,
            "status": self.status,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_error": self.last_error,
            "context_available_at": (
                (self._last_context or {}).get("generated_at") if self._last_context else None
            ),
        }