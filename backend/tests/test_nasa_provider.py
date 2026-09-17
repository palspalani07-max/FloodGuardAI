"""Tests for NASA GPM IMERG provider (mocked HTTP — no real API calls)."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.config import Settings
from app.external.nasa.provider import NASAProvider


def _make_settings(token="test-token-abc"):
    return Settings(
        nasa_earthdata_token=token,
        google_flood_api_key="",
        open_meteo_api_key="",
    )


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def _entry(title="GPM_3IMERGHHE_07_20240101_000000"):
    return {
        "title": title,
        "time_start": datetime.now(timezone.utc).isoformat(),
        "time_end": datetime.now(timezone.utc).isoformat(),
        "granule_size": "52428800",
        "links": [
            {"href": "https://disc2.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/test.nc4/contents.html"}
        ],
    }


class TestNASAProviderConfigMissing:
    def test_config_missing_without_token(self):
        settings = _make_settings(token="")
        provider = NASAProvider(settings)
        assert not provider.available
        assert provider.status == "config-missing"
        assert provider.config_missing() is True

    def test_available_with_token(self):
        settings = _make_settings()
        provider = NASAProvider(settings)
        assert provider.available
        assert provider.config_missing() is False

    def test_get_latest_rainfall_returns_none_when_unconfigured(self):
        provider = NASAProvider(_make_settings(token=""))
        assert provider.get_latest_rainfall(13.08, 80.27) is None

    def test_get_rainfall_grid_returns_empty_when_unconfigured(self):
        provider = NASAProvider(_make_settings(token=""))
        assert provider.get_rainfall_grid((12.99, 13.17, 80.15, 80.32)) == []

    def test_verify_token_returns_false_when_unconfigured(self):
        provider = NASAProvider(_make_settings(token=""))
        assert not provider.verify_token()

    def test_search_granules_returns_empty_when_unconfigured(self):
        provider = NASAProvider(_make_settings(token=""))
        assert provider.search_granules() == []

    def test_token_info_when_unconfigured(self):
        provider = NASAProvider(_make_settings(token=""))
        info = provider.get_token_info()
        assert info["configured"] is False
        assert info["status"] == "config-missing"


class TestNASAProviderTokenVerification:
    def test_token_verify_success(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider._client, "get", return_value=FakeResponse(200, json_data={"user": {"id": "u1"}})):
            assert provider.verify_token() is True
        assert provider._token_verified is True
        assert provider.status == "connected"

    def test_token_verify_failure_401(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider._client, "get", return_value=FakeResponse(401)):
            assert provider.verify_token() is False
        assert provider.status == "error"

    def test_token_verify_network_error(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider._client, "get", side_effect=ConnectionError("timeout")):
            assert provider.verify_token() is False
        assert provider.status == "error"
        assert "timeout" in provider.last_error


class TestNASACMRSearch:
    def test_search_granules_uses_nrt_short_name(self):
        provider = NASAProvider(_make_settings())
        seen = []
        cmr = {"feed": {"entry": [_entry()]}}

        def fake_get(url, params=None, headers=None, timeout=None):
            seen.append(params)
            return FakeResponse(200, json_data=cmr)

        with patch.object(provider._client, "get", side_effect=fake_get):
            granules = provider.search_granules(bbox=(12.99, 13.17, 80.15, 80.32))
        assert len(granules) == 1
        assert seen[0]["short_name"] == "GPM_3IMERGHHE"
        assert seen[0]["bounding_box"] == "80.15,12.99,80.32,13.17"
        assert provider.status == "connected"

    def test_search_granules_falls_back_to_concept_id(self):
        provider = NASAProvider(_make_settings())
        seen = []

        def fake_get(url, params=None, headers=None, timeout=None):
            seen.append(params)
            if params.get("collection_concept_id"):
                return FakeResponse(200, json_data={"feed": {"entry": [_entry()]}})
            return FakeResponse(200, json_data={"feed": {"entry": []}})

        with patch.object(provider._client, "get", side_effect=fake_get):
            granules = provider.search_granules()
        assert len(granules) == 1
        assert seen[-1]["collection_concept_id"] == "C1235612873-GES_DISC"

    def test_search_granules_http_error(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider._client, "get", return_value=FakeResponse(500)):
            assert provider.search_granules() == []
        assert provider.status == "error"

    def test_search_granules_network_error(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider._client, "get", side_effect=Exception("DNS failure")):
            assert provider.search_granules() == []
        assert provider.status == "error"


class TestNASAOpendapHelpers:
    def test_ascii_base_from_contents_html(self):
        provider = NASAProvider(_make_settings())
        base = provider._ascii_base(
            "https://disc2.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/test.nc4/contents.html")
        assert base.endswith("/opendap/GPM_L3/test.nc4.ascii")

    def test_ascii_base_none(self):
        provider = NASAProvider(_make_settings())
        assert provider._ascii_base(None) is None

    def test_parse_ascii_floats_takes_last_token(self):
        provider = NASAProvider(_make_settings())
        text = "# NetCDF file: test\n"
        text += "1, 2, 3, 12.5\n"
        text += "lat,lat\n"
        text += "0, -90.0\n"
        vals = provider._parse_ascii_floats(text)
        assert vals == [12.5, -90.0]

    def test_nearest_index(self):
        provider = NASAProvider(_make_settings())
        arr = [-90.0, -89.9, 12.9, 13.0, 13.1]
        assert provider._nearest_index(arr, 13.0) == 3
        assert provider._nearest_index(arr, -100.0) == 0
        assert provider._nearest_index(arr, 99.0) == 4

    def test_sanitize(self):
        provider = NASAProvider(_make_settings())
        assert provider._sanitize(-9999.0) == 0.0
        assert provider._sanitize(600.0) == 0.0
        assert provider._sanitize(4.56789) == 4.5679

    def test_grid_indices_fetches_and_caches(self):
        provider = NASAProvider(_make_settings())
        lat_ascii = "lat,lat\n0, -90.0\n1, -89.9\n2, 42.5\n"
        lon_ascii = "lon,lon\n0, -180.0\n1, 80.27\n"

        def fake_get(url, headers=None, timeout=None, **kw):
            if "?lat[" in url:
                return FakeResponse(200, text=lat_ascii)
            if "?lon[" in url:
                return FakeResponse(200, text=lon_ascii)
            return FakeResponse(404)

        with patch.object(provider._client, "get", side_effect=fake_get):
            coords = provider._grid_indices("https://x/opendap/test.nc4.ascii")
        assert coords["lat"] == [-90.0, -89.9, 42.5]
        assert coords["lon"] == [-180.0, 80.27]
        assert "https://x/opendap/test.nc4.ascii" in provider._idx_cache


class TestNASAOpendapPrecipitation:
    def test_fetch_precipitation_success(self):
        provider = NASAProvider(_make_settings())

        def fake_get(url, headers=None, timeout=None, **kw):
            return FakeResponse(200, text="# header\n0, 48, 875, 8.5\n")

        with patch.object(provider, "_grid_indices", return_value={"lat": [-90, 13.1], "lon": [-180, 80.3]}):
            with patch.object(provider._client, "get", side_effect=fake_get):
                value = provider._fetch_opendap_precipitation(
                    "https://x/opendap/test.nc4/contents.html", 13.08, 80.27)
        assert value == 8.5
        assert provider.last_error is None

    def test_fetch_precipitation_falls_back_to_precipitation_cal(self):
        provider = NASAProvider(_make_settings())

        def fake_get(url, headers=None, timeout=None, **kw):
            if "precipitationCal[" in url:
                return FakeResponse(200, text="0, 48, 875, 3.25\n")
            return FakeResponse(404, text="not found")

        with patch.object(provider, "_grid_indices", return_value={"lat": [-90, 13.1], "lon": [-180, 80.3]}):
            with patch.object(provider._client, "get", side_effect=fake_get):
                value = provider._fetch_opendap_precipitation("https://x/test.nc4", 13.08, 80.27)
        assert value == 3.25

    def test_fetch_precipitation_empty_url(self):
        provider = NASAProvider(_make_settings())
        assert provider._fetch_opendap_precipitation(None, 13.08, 80.27) == 0.0

    def test_fetch_precipitation_missing_coords_sets_error(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider, "_grid_indices", return_value=None):
            value = provider._fetch_opendap_precipitation("https://x/test.nc4", 13.08, 80.27)
        assert value == 0.0
        assert provider.status == "error"

    def test_fetch_precipitation_network_error(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider, "_grid_indices", return_value={"lat": [-90, 13.1], "lon": [-180, 80.3]}):
            with patch.object(provider._client, "get", side_effect=ConnectionError("boom")):
                value = provider._fetch_opendap_precipitation("https://x/test.nc4", 13.08, 80.27)
        assert value == 0.0
        assert provider.status == "error"


class TestNASARainfallCell:
    def test_get_latest_rainfall_from_granule(self):
        provider = NASAProvider(_make_settings())
        granule = _entry()
        with patch.object(provider, "get_latest_granule", return_value=granule):
            with patch.object(provider, "_fetch_opendap_precipitation", return_value=3.5):
                cell = provider.get_latest_rainfall(13.08, 80.27)
        assert cell is not None
        assert cell.lat == 13.08
        assert cell.lon == 80.27
        assert cell.source == "NASA_GPM_IMERG"
        assert cell.rainfall_mm_hr == 3.5

    def test_get_latest_rainfall_no_granule(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider, "search_granules", return_value=[]):
            assert provider.get_latest_rainfall(13.08, 80.27) is None

    def test_get_rainfall_grid_multiple_cells(self):
        provider = NASAProvider(_make_settings())
        with patch.object(provider, "get_latest_granule", return_value=_entry()):
            with patch.object(provider, "_fetch_opendap_precipitation", return_value=1.2):
                cells = provider.get_rainfall_grid((12.99, 13.03, 80.15, 80.19), resolution_deg=0.02)
        assert len(cells) > 0
        for c in cells:
            assert c.source == "NASA_GPM_IMERG"
            assert c.rainfall_mm_hr == 1.2

    def test_granule_parsing_confidence_high_for_large_granule(self):
        provider = NASAProvider(_make_settings())
        granule = _entry()
        granule["granule_size"] = str(50 * 1024 * 1024)
        cell = provider._parse_granule_to_cell(granule, 13.08, 80.27)
        assert cell is not None
        assert cell.confidence.value == "HIGH"


class TestNASATokenInfo:
    def test_token_info_available(self):
        provider = NASAProvider(_make_settings())
        info = provider.get_token_info()
        assert info["configured"] is True
        assert info["verified"] is False