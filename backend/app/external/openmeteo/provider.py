"""Open-Meteo weather/precipitation provider (real API)."""
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import httpx

from ..base import BaseProvider
from ...models import WeatherData, WeatherForecast, RainfallCell
from ...logging_conf import log


class OpenMeteoProvider(BaseProvider):
    name = "open_meteo"
    requires_auth = False
    base_url = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, settings):
        super().__init__(settings)
        self.available = True
        self._client = httpx.Client(timeout=15.0)

    def get_current_weather(self, lat: float, lon: float) -> WeatherData:
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_direction_10m,pressure_msl",
                "timezone": "auto",
            }
            if self.settings.open_meteo_api_key:
                params["apikey"] = self.settings.open_meteo_api_key
            r = self._client.get(self.base_url, params=params)
            r.raise_for_status()
            data = r.json()["current"]
            weather = WeatherData(
                temperature_c=data.get("temperature_2m", 0.0),
                wind_speed_kmh=data.get("wind_speed_10m", 0.0),
                wind_direction_deg=data.get("wind_direction_10m", 0.0),
                precipitation_mm=data.get("precipitation", 0.0),
                humidity_percent=data.get("relative_humidity_2m", 0.0),
                conditions=self._code_to_condition(data.get("weather_code", 0)),
                timestamp=datetime.now(timezone.utc),
                source="OPEN_METEO",
            )
            self._record_success()
            return weather
        except Exception as e:
            self._record_error(f"get_current_weather: {e}")
            return WeatherData(source="OPEN_METEO_SIMULATED")

    def get_forecast(self, lat: float, lon: float) -> WeatherForecast:
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,precipitation,precipitation_probability,wind_speed_10m,wind_direction_10m,weather_code",
                "forecast_days": 2,
                "timezone": "auto",
            }
            if self.settings.open_meteo_api_key:
                params["apikey"] = self.settings.open_meteo_api_key
            r = self._client.get(self.base_url, params=params)
            r.raise_for_status()
            data = r.json()["hourly"]
            forecast = WeatherForecast(
                hourly_times=data.get("time", []),
                hourly_precipitation=data.get("precipitation", []),
                hourly_temperature=data.get("temperature_2m", []),
                hourly_wind_speed=data.get("wind_speed_10m", []),
                hourly_wind_direction=data.get("wind_direction_10m", []),
                hourly_probability=data.get("precipitation_probability", []),
                source="OPEN_METEO",
                timestamp=datetime.now(timezone.utc),
            )
            self._record_success()
            return forecast
        except Exception as e:
            self._record_error(f"get_forecast: {e}")
            return WeatherForecast(source="OPEN_METEO_SIMULATED")

    def get_rainfall_nowcast(self, lat: float, lon: float) -> List[RainfallCell]:
        """0-180 min rainfall nowcast from Open-Meteo (15-minutely)."""
        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "minutely_15": "precipitation",
                "forecast_days": 1,
            }
            if self.settings.open_meteo_api_key:
                params["apikey"] = self.settings.open_meteo_api_key
            r = self._client.get(self.base_url, params=params)
            r.raise_for_status()
            data = r.json().get("minutely_15", {})
            times = data.get("time", [])
            precip = data.get("precipitation", [])
            cells = []
            for i, t in enumerate(times):
                try:
                    ts = datetime.fromisoformat(t)
                except (ValueError, TypeError):
                    ts = datetime.now(timezone.utc)
                now = datetime.now(timezone.utc)
                future_min = int((ts.replace(tzinfo=timezone.utc) - now).total_seconds() / 60) if ts.tzinfo else 0
                if 0 <= future_min <= 180 and i < len(precip):
                    mm = float(precip[i])
                    cells.append(RainfallCell(
                        cell_id=f"OM_{i}",
                        lat=lat, lon=lon,
                        rainfall_mm_hr=min(float(mm) * 4 if mm and mm > 0 else 0.0, 150.0),
                        timestamp=ts,
                        source="OPEN_METEO",
                        forecast_minutes=future_min // 15 * 15,
                        confidence="MEDIUM",
                    ))
            self._record_success()
            return cells
        except Exception as e:
            self._record_error(f"get_rainfall_nowcast: {e}")
            return []

    def _code_to_condition(self, code: int) -> str:
        table = {
            0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime fog",
            51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
            61: "Light rain", 63: "Rain", 65: "Heavy rain",
            80: "Light showers", 81: "Showers", 82: "Violent showers",
            95: "Thunderstorm", 96: "Thunderstorm hail", 99: "Severe thunderstorm hail",
        }
        return table.get(code, "Unknown")