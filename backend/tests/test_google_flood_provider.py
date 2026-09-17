"""Tests for Google Flood Forecasting provider (mocked HTTP — no real API calls)."""
import pytest
from unittest.mock import patch

from app.config import Settings
from app.external.google_flood.provider import GoogleFloodProvider


def _make_settings(key="test-google-key-xyz"):
    return Settings(
        google_flood_api_key=key,
        nasa_earthdata_token="",
        open_meteo_api_key="",
    )


class FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = ""

    def json(self):
        return self._json


def _status(gauge_id="ga1", severity="SEVERE", lat=13.08, lon=80.27):
    return {
        "gaugeId": gauge_id,
        "qualityVerified": True,
        "gaugeLocation": {"latitude": lat, "longitude": lon},
        "issuedTime": "2026-09-17T00:00:00Z",
        "forecastTrend": "RISING",
        "mapInferenceType": "SATELLITE",
        "severity": severity,
        "source": "GOOGLE",
    }


class TestGoogleFloodProviderConfigMissing:
    def test_config_missing_without_key(self):
        provider = GoogleFloodProvider(_make_settings(key=""))
        assert not provider.available
        assert provider.status == "config-missing"
        assert provider.config_missing() is True

    def test_available_with_key(self):
        provider = GoogleFloodProvider(_make_settings())
        assert provider.available
        assert provider.config_missing() is False

    def test_statuses_empty_when_unconfigured(self):
        provider = GoogleFloodProvider(_make_settings(key=""))
        assert provider.search_flood_statuses() == []
        assert provider.get_available_locations() == []
        assert provider.get_floods() == []

    def test_forecast_none_when_unconfigured(self):
        provider = GoogleFloodProvider(_make_settings(key=""))
        assert provider.get_forecast(13.08, 80.27) is None
        assert provider.get_flood_context(13.08, 80.27) is None
        assert provider.query_gauge_forecasts(["ga1"]) == {}

    def test_key_info_when_unconfigured(self):
        provider = GoogleFloodProvider(_make_settings(key=""))
        info = provider.get_key_info()
        assert info["configured"] is False
        assert info["status"] == "config-missing"


class TestGoogleFloodStatuses:
    def test_search_flood_statuses_success(self):
        provider = GoogleFloodProvider(_make_settings())
        seen = {}
        payload = {"floodStatuses": [_status(), _status(gauge_id="ga2", severity="NO_FLOODING")]}

        def fake_post(url, json=None, params=None, **kw):
            seen["json"] = json
            seen["params"] = params
            return FakeResponse(200, payload)

        with patch.object(provider._client, "post", side_effect=fake_post):
            statuses = provider.search_flood_statuses()
        assert len(statuses) == 2
        assert seen["json"]["regionCode"] == "IN"
        assert seen["params"]["key"] == "test-google-key-xyz"
        assert provider.status == "connected"

    def test_search_flood_statuses_http_error(self):
        provider = GoogleFloodProvider(_make_settings())
        with patch.object(provider._client, "post", return_value=FakeResponse(403)):
            assert provider.search_flood_statuses() == []
        assert provider.status == "error"

    def test_search_flood_statuses_network_error(self):
        provider = GoogleFloodProvider(_make_settings())
        with patch.object(provider._client, "post", side_effect=ConnectionError("refused")):
            assert provider.search_flood_statuses() == []
        assert provider.status == "error"


class TestGoogleGaugeForecasts:
    def test_query_gauge_forecasts_success(self):
        provider = GoogleFloodProvider(_make_settings())
        payload = {
            "forecasts": {
                "ga1": {"gaugeId": "ga1", "issuedTime": "2026-09-17T00:00:00Z",
                        "forecastRanges": [{"forecastStartTime": "2026-09-17T01:00:00Z", "value": 12.4}]}
            }
        }

        def fake_get(url, params=None, **kw):
            return FakeResponse(200, payload)

        with patch.object(provider._client, "get", side_effect=fake_get):
            forecasts = provider.query_gauge_forecasts(["ga1"])
        assert "ga1" in forecasts
        assert provider.status == "connected"

    def test_query_gauge_forecasts_http_error(self):
        provider = GoogleFloodProvider(_make_settings())
        with patch.object(provider._client, "get", return_value=FakeResponse(404)):
            assert provider.query_gauge_forecasts(["ga1"]) == {}
        assert provider.status == "error"


class TestGoogleFloods:
    def test_get_floods_filters_active(self):
        provider = GoogleFloodProvider(_make_settings())
        statuses = [
            _status(gauge_id="ga1", severity="SEVERE"),
            _status(gauge_id="ga2", severity="NO_FLOODING"),
            _status(gauge_id="ga3", severity="UNKNOWN"),
        ]
        with patch.object(provider, "search_flood_statuses", return_value=statuses):
            floods = provider.get_floods()
        assert [f["gaugeId"] for f in floods] == ["ga1"]


class TestGoogleForecast:
    def test_get_forecast_nearest_gauge(self):
        provider = GoogleFloodProvider(_make_settings())
        statuses = [
            _status(gauge_id="far", severity="NO_FLOODING", lat=28.6, lon=77.2),
            _status(gauge_id="near", severity="SEVERE", lat=13.08, lon=80.27),
        ]
        with patch.object(provider, "search_flood_statuses", return_value=statuses):
            forecast = provider.get_forecast(13.08, 80.27)
        assert forecast is not None
        assert forecast["gaugeId"] == "near"
        assert provider.status == "connected"

    def test_get_forecast_none_beyond_radius(self):
        provider = GoogleFloodProvider(_make_settings())
        statuses = [_status(gauge_id="far", severity="SEVERE", lat=28.6, lon=77.2)]
        with patch.object(provider, "search_flood_statuses", return_value=statuses):
            assert provider.get_forecast(13.08, 80.27, max_distance_km=100.0) is None
        assert provider.status == "error"


class TestGoogleContext:
    def test_get_flood_context_aggregates(self):
        provider = GoogleFloodProvider(_make_settings())
        statuses = [
            _status(gauge_id="near-severe", severity="SEVERE", lat=13.05, lon=80.25),
            _status(gauge_id="far-extreme", severity="EXTREME", lat=13.2, lon=80.4),
        ]
        with patch.object(provider, "search_flood_statuses", return_value=statuses):
            context = provider.get_flood_context(13.08, 80.27)
        assert context is not None
        assert context["source"] == "GOOGLE_FLOOD_HUB"
        assert context["region_code"] == "IN"
        assert context["risk_level"] == "EXTREME"
        assert context["gauge_count_high_risk"] == 2
        assert context["closest_gauge"]["gauge_id"] == "near-severe"
        assert context["closest_gauge"]["severity"] == "SEVERE"
        assert context["top_gauge"]["severity"] == "EXTREME"
        assert "supplementary" in context["note"]

    def test_get_flood_context_none_when_error(self):
        provider = GoogleFloodProvider(_make_settings())
        with patch.object(provider, "search_flood_statuses", return_value=[]):
            assert provider.get_flood_context(13.08, 80.27) is None

    def test_classify_risk_severity_enum(self):
        provider = GoogleFloodProvider(_make_settings())
        assert provider._classify_risk("NO_FLOODING") == "LOW"
        assert provider._classify_risk("UNKNOWN") == "LOW"
        assert provider._classify_risk("ABOVE_NORMAL") == "HIGH"
        assert provider._classify_risk("SEVERE") == "SEVERE"
        assert provider._classify_risk("EXTREME") == "EXTREME"
        assert provider._classify_risk(None) == "UNKNOWN"


class TestGoogleKeyInfo:
    def test_key_info_never_exposes_key(self):
        provider = GoogleFloodProvider(_make_settings(key="super-secret-key"))
        info = provider.get_key_info()
        assert info["configured"] is True
        raw = str(info)
        assert "super-secret-key" not in raw
        assert "google_flood_api_key" not in raw