"""OSRM routing provider (public demo server)."""
import httpx

from ..config import settings
from ..logging_conf import log
from ..models import RouteResult, RouteSegment
from ..simulation.risk.classifier import Severity
from .base import BaseRoutingProvider


class OSRMProvider(BaseRoutingProvider):
    name = "osrm"
    profile = "driving"

    def __init__(self):
        self.base = settings.osrm_url.rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    def get_route(self, origin_lat, origin_lon, dest_lat, dest_lon,
                  avoid_road_ids=None) -> RouteResult:
        coords = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        url = f"{self.base}/route/v1/{self.profile}/{coords}"
        params = {"overview": "full", "geometries": "geojson", "alternatives": "true"}
        try:
            r = self._client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "Ok" or not data.get("routes"):
                return RouteResult(mode="NORMAL", distance_km=0, estimated_minutes=0, max_depth_cm=0,
                                   risk=Severity.SAFE, avoided_roads=0, route=[])
            route = data["routes"][0]
            dist_m = route.get("distance", 0)
            dur_min = route.get("duration", 0) / 60.0
            geom = route.get("geometry", {}).get("coordinates", [])
            segments = []
            for c in geom:
                segments.append(RouteSegment(lat=c[1], lon=c[0], depth_cm=0.0, flood_risk=Severity.SAFE))
            return RouteResult(
                mode="NORMAL",
                distance_km=round(dist_m / 1000, 2),
                estimated_minutes=round(dur_min, 1),
                max_depth_cm=0.0,
                risk=Severity.SAFE,
                avoided_roads=0,
                route=segments,
                diverted=False,
            )
        except Exception as e:
            log.warning(f"OSRM route error: {e}")
            return RouteResult(mode="NORMAL", distance_km=0, estimated_minutes=0, max_depth_cm=0,
                               risk=Severity.SAFE, avoided_roads=0, route=[])

    def health(self) -> dict:
        return {"name": "osrm", "status": "ok", "url": self.base}


provider = OSRMProvider()