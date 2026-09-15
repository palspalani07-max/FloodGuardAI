"""Alert service: generates alerts from flood predictions using severity + proximity thresholds."""
from datetime import datetime, timedelta, timezone
from typing import List
from uuid import uuid4

from ..models import Alert, Severity
from ..simulation.risk.classifier import FloodClassifier
from ..config import settings
from ..logging_conf import log


class AlertService:
    def __init__(self):
        self.classifier = FloodClassifier()

    def generate_alerts(self, predictions: List[dict]) -> List[dict]:
        now = datetime.now(timezone.utc)
        alerts = []
        for pred in predictions:
            risk = Severity(pred.get("risk", "SAFE"))
            if risk in (Severity.SAFE, Severity.MINOR):
                continue
            arrive = pred.get("arrival_time_min")
            if arrive is None or arrive > 120:
                continue
            alert_id = str(uuid4())[:8]
            if risk == Severity.CRITICAL:
                msg = f"CRITICAL FLOOD ALERT: Severe flooding predicted near {pred['road_name']} within {arrive:.0f} minutes. Avoid low-lying roads."
            elif risk == Severity.SEVERE:
                msg = f"High flood alert: {pred['road_name']} may see {pred['max_depth_cm']:.0f} cm flooding within {arrive:.0f} minutes."
            else:
                msg = f"Heavy rainfall detected. Flood risk increasing near {pred['road_name']} (predicted {pred['max_depth_cm']:.0f} cm)."
            alerts.append({
                "alert_id": alert_id,
                "lat": pred["lat"],
                "lon": pred["lon"],
                "severity": risk.value,
                "message": msg,
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=2)).isoformat(),
                "status": "active",
                "road_id": pred.get("road_id"),
                "road_name": pred.get("road_name"),
                "max_depth_cm": pred.get("max_depth_cm", 0),
                "arrival_time_min": arrive,
            })
        alerts.sort(key=lambda a: {"CRITICAL": 4, "SEVERE": 3, "HIGH": 2, "MINOR": 1}.get(a["severity"], 0), reverse=True)
        log.info(f"Generated {len(alerts)} alerts from {len(predictions)} predictions")
        return alerts

    def check_user_location(self, user_lat: float, user_lon: float, predictions: List[dict]) -> List[dict]:
        """Check if a user is inside or approaching a dangerous area."""
        from ..geospatial.earth import haversine_m
        nearby = []
        for pred in predictions:
            risk = Severity(pred.get("risk", "SAFE"))
            if risk in (Severity.SAFE, Severity.MINOR):
                continue
            d = haversine_m(user_lat, user_lon, pred["lat"], pred["lon"])
            if d < 1500:
                arrive = pred.get("arrival_time_min", 999) or 999
                if arrive < 90:
                    nearby.append({
                        "alert_id": str(uuid4())[:8],
                        "severity": risk.value,
                        "message": f"Flood predicted within {arrive:.0f} min near you ({pred['road_name']}, {pred['max_depth_cm']:.0f} cm)",
                        "road_name": pred.get("road_name"),
                        "arrival_minutes": arrive,
                        "max_depth_cm": pred.get("max_depth_cm", 0),
                        "distance_m": round(d),
                    })
        return sorted(nearby, key=lambda a: a["arrival_minutes"])


alert_service = AlertService()