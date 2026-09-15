"""Pipeline worker — fetches data, runs flood model, generates alerts, updates cache."""
import threading
import time
from datetime import datetime, timezone

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
        self.flood_engine.storage.save_alerts(alerts)
        for alert in alerts[:5]:
            notification_service.notify(alert)
        self.last_run = datetime.now(timezone.utc)
        self.data_freshness_seconds = (datetime.now(timezone.utc) - t0).total_seconds()
        log.info(f"Pipeline run complete in {self.data_freshness_seconds:.1f}s, "
                 f"{len(predictions)} predictions, {len(alerts)} alerts")


pipeline: PipelineWorker | None = None


def get_pipeline(flood_engine) -> PipelineWorker:
    global pipeline
    if pipeline is None:
        pipeline = PipelineWorker(flood_engine)
    return pipeline