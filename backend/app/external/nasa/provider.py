"""NASA GPM IMERG precipitation provider.

Real near-real-time rainfall from the GPM IMERG half-hourly product (Level 3).

Flow (all official NASA services, server-side only):
  1. CMR (Common Metadata Repository) granule search by ``short_name`` —
     tries the near-real-time product ``GPM_3IMERGHHE`` first, then the
     final ``GPM_3IMERGHH`` — intersecting the Chennai bbox, sorted newest first.
  2. GES DISC OPeNDAP (DAP2 ``.ascii``) constrained request: resolve the
     nearest lat/lon grid indices once, then extract ``precipitation`` over
     that single 0.1deg cell (falling back to ``precipitationCal``).

IMERG precipitation is reported in mm/hr. If no token is configured the
provider reports ``config-missing`` and the system falls back to
Open-Meteo / simulation data.

Auth is the Earthdata Login bearer token (NASA_EARTHDATA_TOKEN, .env, never
exposed to the browser). Timeouts and per-stage error handling keep a broken or
unreachable NASA service from ever failing the flood pipeline.
"""
from bisect import bisect_left
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from ..base import BaseProvider
from ...models import RainfallCell
from ...logging_conf import log

# NASA CMR base URL for granule search
_CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
# NASA Earthdata token verification endpoint (best-effort)
_USERINFO_URL = "https://urs.earthdata.nasa.gov/api/users/verified"
# IMERG product short names in order of preference (NRT/Early then Final).
_IMERG_SHORT_NAMES = ["GPM_3IMERGHHE", "GPM_3IMERGHH", "GPM_3IMERGE"]
# Fallback collection concept id used only if no short_name matches.
_IMERG_FALLBACK_COLLECTION = "C1235612873-GES_DISC"
# GPM IMERG 0.1 degree global grid dims (used for the coordinate lookup).
_IMERG_LAT_N = 1800
_IMERG_LON_N = 3600
# IMERG "no precipitation / fill" sentinel codepoint.
_IMERG_FILL = -9999.0


class NASAProvider(BaseProvider):
    name = "nasa_gpm"
    requires_auth = True
    base_url = _CMR_URL

    def __init__(self, settings):
        super().__init__(settings)
        self.available = bool(settings.nasa_earthdata_token)
        self._client = httpx.Client(timeout=20.0)
        self._token_verified = False
        self._idx_cache: Dict[str, dict] = {}
        if not self.available:
            log.warning("NASA GPM provider config-missing: NASA_EARTHDATA_TOKEN not configured")

    def config_missing(self) -> bool:
        return not bool(self.settings.nasa_earthdata_token)

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.settings.nasa_earthdata_token}"}

    def verify_token(self) -> bool:
        """Best-effort Earthdata token check via the URS user info endpoint."""
        if not self.available:
            return False
        try:
            r = self._client.get(_USERINFO_URL, headers=self._auth_headers())
            if r.status_code == 200:
                self._record_success()
                self._token_verified = True
                log.info("NASA Earthdata token verified successfully")
                return True
            self._record_error(f"Token verification failed: HTTP {r.status_code}")
            return False
        except Exception as e:
            self._record_error(f"Token verification error: {e}")
            return False

    def search_granules(self, bbox: tuple = None, start_time: datetime = None,
                        end_time: datetime = None, limit: int = 5) -> List[dict]:
        """Search CMR for the most recent GPM IMERG granules over ``bbox``.

        ``bbox`` is (south, north, west, east). Products are tried in
        near-real-time order (Early/NRT before Final), with a hardcoded
        collection concept id as a last resort.
        """
        if not self.available:
            return []
        common: Dict[str, str] = {
            "page_size": str(limit),
            "sort_key": "-start_date",
        }
        if bbox:
            s, n, w, e = bbox
            common["bounding_box"] = f"{w},{s},{e},{n}"
        if start_time:
            common["start_date"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if end_time:
            common["end_date"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        for short_name in _IMERG_SHORT_NAMES:
            params = dict(common, short_name=short_name)
            try:
                r = self._client.get(_CMR_URL, params=params, headers=self._auth_headers())
                if r.status_code == 200:
                    entries = (r.json().get("feed", {}) or {}).get("entry", [])
                    if entries:
                        self._record_success()
                        log.info(f"CMR returned {len(entries)} IMERG granules ({short_name})")
                        return entries
                    self._record_error(f"CMR search ({short_name}) returned no granules")
                else:
                    self._record_error(f"CMR search ({short_name}) HTTP {r.status_code}")
            except Exception as e:
                self._record_error(f"CMR search ({short_name}) error: {e}")
        # Last resort: legacy concept id for the Late/Final product.
        try:
            params = dict(common, collection_concept_id=_IMERG_FALLBACK_COLLECTION)
            r = self._client.get(_CMR_URL, params=params, headers=self._auth_headers())
            if r.status_code == 200:
                entries = (r.json().get("feed", {}) or {}).get("entry", [])
                if entries:
                    self._record_success()
                    return entries
                self._record_error("CMR fallback search returned no granules")
            else:
                self._record_error(f"CMR fallback search HTTP {r.status_code}")
        except Exception as e:
            self._record_error(f"CMR fallback search error: {e}")
        return []

    def get_latest_granule(self, bbox: tuple = None) -> Optional[dict]:
        """Get the most recent GPM IMERG granule metadata for ``bbox``."""
        granules = self.search_granules(bbox=bbox, limit=1)
        return granules[0] if granules else None

    def get_latest_rainfall(self, lat: float, lon: float) -> Optional[RainfallCell]:
        """Fetch a single grid point from the latest available IMERG granule."""
        if not self.available:
            return None
        granule = self.get_latest_granule(bbox=(lat - 0.1, lat + 0.1, lon - 0.1, lon + 0.1))
        if not granule:
            return None
        return self._parse_granule_to_cell(granule, lat, lon)

    def get_rainfall_grid(self, bbox: tuple, resolution_deg: float = 0.1) -> List[RainfallCell]:
        """Return per-cell IMERG rainfall (mm/hr) over ``bbox`` (s,n,w,e).

        The OPeNDAP lat/lon index lookup is cached so the whole grid costs
        one coordinate fetch plus one value fetch per cell.
        """
        if not self.available:
            return []
        granule = self.get_latest_granule(bbox=bbox)
        if not granule:
            return []
        cells = []
        s, n, w, e = bbox
        lat = s
        while lat <= n:
            lon = w
            while lon <= e:
                cell = self._parse_granule_to_cell(granule, lat, lon)
                if cell:
                    cells.append(cell)
                lon += resolution_deg
            lat += resolution_deg
        return cells

    def _parse_granule_to_cell(self, granule: dict, lat: float, lon: float) -> Optional[RainfallCell]:
        try:
            time_start = granule.get("time_start")
            if time_start:
                ts = datetime.fromisoformat(str(time_start).replace("Z", "+00:00"))
            else:
                ts = datetime.now(timezone.utc)
            now = datetime.now(timezone.utc)
            lag_min = max(0, int((now - ts).total_seconds() / 60))
            opendap_url = None
            for link in granule.get("links", []) or []:
                href = str(link.get("href", ""))
                if "opendap" in href.lower() or ".nc4" in href.lower() or ".hdf5" in href.lower():
                    opendap_url = href
                    break
            confidence = "MEDIUM"
            if granule.get("granule_size"):
                try:
                    size_mb = float(granule["granule_size"]) / (1024 * 1024)
                    if size_mb > 10:
                        confidence = "HIGH"
                except (ValueError, TypeError):
                    pass
            rainfall = self._fetch_opendap_precipitation(opendap_url, lat, lon)
            return RainfallCell(
                cell_id=f"NASA_{lat:.4f}_{lon:.4f}",
                lat=round(lat, 4),
                lon=round(lon, 4),
                rainfall_mm_hr=rainfall,
                timestamp=ts,
                source="NASA_GPM_IMERG",
                confidence=confidence,
                forecast_minutes=0,
            )
        except Exception as e:
            log.debug(f"NASA granule parse error: {e}")
            self._record_error(f"granule parse: {e}")
            return None

    # ------------------------------------------------------------------
    # OPeNDAP (DAP2 ASCII) helpers
    # ------------------------------------------------------------------
    def _ascii_base(self, opendap_url: Optional[str]) -> Optional[str]:
        """Turn a granule OPeNDAP href into the DAP2 ASCII endpoint."""
        if not opendap_url:
            return None
        u = opendap_url.split("?")[0]
        if u.endswith("/contents.html"):
            u = u[: -len("/contents.html")]
        return u + ".ascii"

    @staticmethod
    def _parse_ascii_floats(text: str) -> List[float]:
        """Extract numeric values from a DAP2 ASCII response.

        Data lines are comma-separated and carry array indices first and the
        value last (e.g. ``0, 1031, 2603, 12.5``), so we read the final token.
        Attribute/header lines begin with '#' or '_', or are the variable-name
        header row, and are skipped.
        """
        out: List[float] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("_"):
                continue
            tokens = line.split(",")
            if len(tokens) < 2:
                continue
            try:
                value = float(tokens[-1])
            except (ValueError, TypeError):
                continue
            out.append(value)
        return out

    def _grid_indices(self, ascii_base: str) -> Optional[Dict[str, object]]:
        """Fetch and cache the IMERG lat/lon coordinate arrays via OPeNDAP."""
        if ascii_base in self._idx_cache:
            return self._idx_cache[ascii_base]
        for lat_var, lon_var in (("lat", "lon"), ("Latitude", "Longitude")):
            try:
                lat_resp = self._client.get(
                    f"{ascii_base}?{lat_var}[0:1:{_IMERG_LAT_N - 1}]",
                    headers=self._auth_headers(), timeout=10.0)
                lon_resp = self._client.get(
                    f"{ascii_base}?{lon_var}[0:1:{_IMERG_LON_N - 1}]",
                    headers=self._auth_headers(), timeout=10.0)
                if lat_resp.status_code != 200 or lon_resp.status_code != 200:
                    continue
                lats = self._parse_ascii_floats(lat_resp.text)
                lons = self._parse_ascii_floats(lon_resp.text)
                if len(lats) < 2 or len(lons) < 2:
                    continue
                cache = {"lat": lats, "lon": lons}
                self._idx_cache[ascii_base] = cache
                return cache
            except Exception as e:
                log.debug(f"OPeNDAP coord fetch failed ({lat_var}): {e}")
        return None

    @staticmethod
    def _nearest_index(values: List[float], target: float) -> int:
        pos = bisect_left(values, target)
        if pos == 0:
            return 0
        if pos >= len(values):
            return len(values) - 1
        return pos - 1 if abs(values[pos - 1] - target) <= abs(values[pos] - target) else pos

    @staticmethod
    def _sanitize(value: float) -> float:
        if value is None or value < 0 or value > 500:
            return 0.0
        return round(value, 4)

    def _fetch_opendap_precipitation(self, opendap_url: Optional[str],
                                     lat: float, lon: float) -> float:
        """Fetch IMERG precipitation (mm/hr) at (lat, lon) via OPeNDAP.

        Returns 0.0 on failure/missing so the caller never crashes. Real
        request errors are recorded so the provider status reflects them.
        """
        ascii_base = self._ascii_base(opendap_url)
        if not ascii_base:
            return 0.0
        try:
            coords = self._grid_indices(ascii_base)
            if not coords:
                self._record_error(f"OPeNDAP coord arrays unavailable for {ascii_base}")
                return 0.0
            i = self._nearest_index(coords["lat"], lat)
            j = self._nearest_index(coords["lon"], lon)
            for var in ("precipitation", "precipitationCal"):
                r = self._client.get(
                    f"{ascii_base}?{var}[0][{i}][{j}]",
                    headers=self._auth_headers(), timeout=10.0)
                if r.status_code != 200:
                    continue
                vals = self._parse_ascii_floats(r.text)
                if vals:
                    return self._sanitize(vals[-1])
            self._record_error(f"OPeNDAP precipitation missing at ({lat:.2f},{lon:.2f})")
        except Exception as e:
            self._record_error(f"OPeNDAP fetch failed for ({lat:.2f},{lon:.2f}): {e}")
        return 0.0

    def get_token_info(self) -> Optional[dict]:
        """Return metadata about the current token (without exposing it)."""
        if not self.available:
            return {"configured": False, "verified": False, "status": "config-missing"}
        return {
            "configured": True,
            "verified": self._token_verified,
            "status": self.status,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_error": self.last_error,
        }