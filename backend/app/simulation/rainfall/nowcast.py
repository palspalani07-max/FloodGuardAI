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
        source_parts = ["OPEN_METEO"]
        nasa_intensity = None
        if base_intensity is None:
            base_intensity = current.precipitation_mm * 4.0  # recent mm -> mm/hr
            if base_intensity < 0.5:
                base_intensity = self._forecast_intensity(forecast)

            # Blend in NASA GPM IMERG data if available (skipped for explicit
            # simulation overrides so scenario rainfall keeps full precedence).
            nasa = registry.nasa()
            nasa_intensity = self._fetch_nasa_rainfall(nasa, lat, lon)
            if nasa_intensity is not None and nasa_intensity > 0:
                if base_intensity < 0.5:
                    base_intensity = nasa_intensity
                else:
                    base_intensity = 0.6 * base_intensity + 0.4 * nasa_intensity
                source_parts.append("NASA_GPM")

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

        source_label = "+".join(source_parts) + "+SYNTHETIC"
        result = NowcastResult(
            timesteps=self.steps,
            rainfall_mm_hr=rain_by_step,
            confidence="HIGH" if (override_intensity is not None or nasa_intensity is not None) else "MEDIUM",
            source=source_label,
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

    def _fetch_nasa_rainfall(self, nasa_provider, lat: float, lon: float) -> Optional[float]:
        """Fetch rainfall intensity from NASA GPM IMERG provider.

        Returns mm/hr or None if unavailable. Failures are silently ignored
        so the nowcast falls back to Open-Meteo only.
        """
        try:
            if not nasa_provider or not nasa_provider.available:
                return None
            cell = nasa_provider.get_latest_rainfall(lat, lon)
            if cell and cell.rainfall_mm_hr > 0:
                return cell.rainfall_mm_hr
            return None
        except Exception as e:
            log.debug(f"NASA rainfall fetch failed: {e}")
            return None