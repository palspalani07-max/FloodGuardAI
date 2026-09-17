"""Rainfall nowcast tests: NASA GPM preference with Open-Meteo fallback."""
import pytest
from datetime import datetime, timezone

from app.config import Settings
from app.external.provider_registry import registry
from app.models import RainfallCell, WeatherData, WeatherForecast
from app.simulation.rainfall.nowcast import RainfallNowcast


class _FakeOpenMeteo:
    available = True

    def get_current_weather(self, lat, lon):
        return WeatherData(
            temperature_c=30, precipitation_mm=0.0, humidity_percent=60,
            source="OPEN_METEO", timestamp=datetime.now(timezone.utc))

    def get_forecast(self, lat, lon):
        return WeatherForecast(hourly_precipitation=[], source="OPEN_METEO",
                               timestamp=datetime.now(timezone.utc))


class _FakeNASA:
    available = True

    def __init__(self, intensity=40.0):
        self.intensity = intensity

    def get_latest_rainfall(self, lat, lon):
        if self.intensity is not None:
            return RainfallCell(
                cell_id="NASA_test", lat=lat, lon=lon,
                rainfall_mm_hr=self.intensity,
                timestamp=datetime.now(timezone.utc),
                source="NASA_GPM_IMERG", confidence="HIGH")
        return None


@pytest.fixture(autouse=True)
def _isolate_providers(monkeypatch):
    """Swap registry providers for NASA-preference tests and restore after."""
    monkeypatch.setattr(registry, "open_meteo", lambda: _FakeOpenMeteo())
    monkeypatch.setattr(registry, "nasa", lambda: _FakeNASA())


def test_nowcast_prefers_nasa_when_available():
    nowcast = RainfallNowcast()
    result = nowcast.generate(13.08, 80.27)
    assert "NASA_GPM" in result.source
    assert result.rainfall_mm_hr[0] > 25
    assert result.confidence == "HIGH"


def test_nowcast_falls_back_to_open_meteo_when_nasa_unavailable(monkeypatch):
    nasa = _FakeNASA()
    nasa.available = False
    monkeypatch.setattr(registry, "nasa", lambda: nasa)
    nowcast = RainfallNowcast()
    result = nowcast.generate(13.08, 80.27)
    assert "NASA_GPM" not in result.source
    assert result.source.startswith("OPEN_METEO")
    assert result.rainfall_mm_hr[0] == 0.0


def test_nowcast_survives_nasa_failure(monkeypatch):
    class Boom:
        available = True

        def get_latest_rainfall(self, lat, lon):
            raise ConnectionError("NASA down")

    monkeypatch.setattr(registry, "nasa", lambda: Boom())
    nowcast = RainfallNowcast()
    result = nowcast.generate(13.08, 80.27)
    assert "NASA_GPM" not in result.source
    assert isinstance(result.rainfall_mm_hr[0], float)


def test_override_intensity_takes_precedence(monkeypatch):
    monkeypatch.setattr(registry, "nasa", lambda: _FakeNASA(intensity=99.0))
    nowcast = RainfallNowcast()
    result = nowcast.generate(13.08, 80.27, override_intensity=30.0)
    assert result.rainfall_mm_hr[0] == 30.0
    assert result.source == "OPEN_METEO+SYNTHETIC"