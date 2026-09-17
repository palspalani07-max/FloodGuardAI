"""Pipeline worker — fetches data, runs flood model, generates alerts, updates cache."""
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from ..config import settings
from ..logging_conf import log
from ..external.provider_registry import registry
from ..services.alert_service import alert_service
from ..services.notification import notification_service

RUN_INTERVAL_S = 240  # seconds between pipeline runs


class PipelineWorker:
    def __init__(self, flood_engine):
        self.flood_engine = flood_engine
        self._running = False
        self._thread: threading.Thread | None = None
        self.last_run: datetime | None = None
        self.data_freshness_seconds: float | None = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="flood-pipeline")
        self._thread.start()
        log.info("PipelineWorker started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        log.info("PipelineWorker stopped")

    def _loop(self):
        while self._running:
            try:
                self._run_once()
            except Exception as e:
                log.error(f"PipelineWorker error: {e}")
            time.sleep(RUN_INTERVAL_S)

    def _run_once(self):
        t0 = datetime.now(timezone.utc)
        om = registry.open_meteo()
        weather = om.get_current_weather(settings.city_lat, settings.city_lon)
        self.flood_engine.storage.save_weather(weather.model_dump())
        result = self.flood_engine.run()
        predictions = self.flood_engine.storage.get_flood_predictions()
        alerts = alert_service.generate_alerts(predictions)
        # Fetch Google Flood Hub supplementary context (non-blocking) and enrich
        # the alert set with honest, source-tagged river/stream context alerts.
        google_context = self._fetch_google_flood_context()
        context_alerts = self._google_context_alerts(google_context)
        alerts.extend(context_alerts)
        self.flood_engine.storage.save_alerts(alerts)
        for alert in alerts[:5]:
            notification_service.notify(alert)
        self.flood_engine.google_flood_context = google_context
        self.last_run = datetime.now(timezone.utc)
        self.data_freshness_seconds = (datetime.now(timezone.utc) - t0).total_seconds()
        log.info(f"Pipeline run complete in {self.data_freshness_seconds:.1f}s, "
                 f"{len(predictions)} predictions, {len(alerts)} alerts"
                 + (f", Google Flood context: {google_context['risk_level']}" if google_context else ""))

    def _fetch_google_flood_context(self) -> Optional[dict]:
        """Fetch supplementary flood context from Google Flood Forecasting.

        Returns the context dict if available, None otherwise. Errors are
        logged but never propagate to fail the pipeline run.
        """
        try:
            gf = registry.google_flood()
            if not gf or not gf.available:
                return None
            context = gf.get_flood_context(settings.city_lat, settings.city_lon)
            return context
        except Exception as e:
            log.debug(f"Google Flood context fetch failed: {e}")
            return None

    def _google_context_alerts(self, context: Optional[dict]) -> list:
        """Build a source-tagged context alert for HIGH/SEVERE/EXTREME Google risk.

        Wording is honest: Google supplies river/stream-scale context only;
        street-level prediction comes from FloodGuard's own model.
        """
        if not context:
            return []
        risk = (context.get("risk_level") or "").upper()
        severity = {"EXTREME": "CRITICAL", "SEVERE": "SEVERE", "HIGH": "HIGH"}.get(risk)
        if not severity:
            return []
        closest = context.get("closest_gauge") or {}
        now = datetime.now(timezone.utc)
        detail = (
            f" (nearest gauge {closest.get('gauge_id')}, "
            f"{closest.get('distance_km')} km, status {closest.get('severity')})"
            if closest.get("gauge_id") else ""
        )
        message = (
            f"Google Flood Hub: {risk} river/stream flood risk for the Chennai region{detail}. "
            "This is regional context; use FloodGuard's street-level predictions for local decisions."
        )
        return [{
            "alert_id": str(uuid4())[:8],
            "lat": settings.city_lat,
            "lon": settings.city_lon,
            "severity": severity,
            "message": message,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=3)).isoformat(),
            "status": "active",
            "road_id": None,
            "road_name": None,
            "source": "GOOGLE_FLOOD_HUB",
        }]


pipeline: PipelineWorker | None = None


def get_pipeline(flood_engine) -> PipelineWorker:
    global pipeline
    if pipeline is None:
        pipeline = PipelineWorker(flood_engine)
    return pipeline