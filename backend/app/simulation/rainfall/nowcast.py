"""Rainfall nowcast generation (0-180 min).

Combines recent precipitation, precipitation trend, weather forecast, spatial
interpolation and temporal smoothing. This is NOT claimed to be a radar-grade
nowcasting system - the architecture allows a radar-based nowcast model to
replace this module later (see RadarProvider).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np

from ...external.provider_registry import registry
from ...logging_conf import log


@dataclass
class NowcastResult:
    timesteps: List[int] = field(default_factory=lambda: [0, 15, 30, 45, 60, 90, 120, 150, 180])
    rainfall_mm_hr: dict = field(default_factory=dict)  # minutes -> value
    confidence: str = "MEDIUM"
    source: str = "OPEN_METEO+SYNTHETIC"
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RainfallNowcast:
    def __init__(self):
        self.steps = [0, 15, 30, 45, 60, 90, 120, 150, 180]

    def generate(self, lat: float, lon: float, override_intensity: Optional[float] = None) -> NowcastResult:
        current = None
        forecast = None
        om = registry.open_meteo()
        current = om.get_current_weather(lat, lon)
        forecast = om.get_forecast(lat, lon)

        base_intensity = override_intensity
        if base_intensity is None:
            base_intensity = current.precipitation_mm * 4.0  # recent mm -> mm/hr
            if base_intensity < 0.5:
                base_intensity = self._forecast_intensity(forecast)

        # Build a smooth decay/advection curve from now toward forecast.
        rain_by_step = {}
        for i, step in enumerate(self.steps):
            t = step / 180.0
            # gentle temporal smoothing toward the 1-hr forecast value
            target = self._forecast_value(forecast, step)
            if base_intensity > 0.5:
                intensity = base_intensity * (1 - 0.25 * t) + target * (0.25 * t)
            else:
                intensity = target
            intensity = max(0.0, float(np.clip(intensity, 0, 200)))
            if base_intensity > 0.5:
                intensity = max(intensity, base_intensity * 0.3) if intensity > 0 else intensity
            rain_by_step[step] = round(intensity, 1)

        result = NowcastResult(
            timesteps=self.steps,
            rainfall_mm_hr=rain_by_step,
            confidence="MEDIUM" if not override_intensity else "HIGH",
            source="OPEN_METEO+SYNTHETIC",
        )
        return result

    def _forecast_intensity(self, forecast) -> float:
        if not forecast.hourly_precipitation:
            return 0.0
        vals = [v for v in forecast.hourly_precipitation[:6] if v is not None]
        if not vals:
            return 0.0
        return float(max(vals)) * 1.5

    def _forecast_value(self, forecast, minutes: int) -> float:
        if not forecast.hourly_precipitation:
            return 0.0
        idx = min(minutes // 60, len(forecast.hourly_precipitation) - 1)
        return float(forecast.hourly_precipitation[idx] or 0.0) * 1.5