"""API layer tests against the real FastAPI app (fresh process)."""
import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    import app.flood_engine as fe

    # Seed deterministic state: run a heavy scenario so flood/forecast, roads,
    # drainage and alerts return meaningful data. (Lifespan is NOT started to
    # avoid the background pipeline worker interfering with tests.)
    fe.engine.run(override_rainfall=60.0)
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_system_status(client):
    r = client.get("/api/system/status")
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "Chennai"
    assert body["version"]
    assert len(body["providers"]) >= 3


def test_flood_forecast_endpoint(client):
    r = client.get("/api/flood/forecast")
    assert r.status_code == 200
    preds = r.json()
    assert len(preds) > 20000
    p = preds[0]
    for key in ("road_id", "road_name", "lat", "lon", "risk", "max_depth_cm", "depth_curve"):
        assert key in p


def test_flood_grid_full_domain(client):
    r = client.get("/api/flood/grid?minutes=60")
    assert r.status_code == 200
    cells = r.json()
    # full domain returned (no >0.5cm filter), all with risk labels
    assert len(cells) > 1000
    assert all("risk" in c and "depth_cm" in c for c in cells)


def test_roads_geojson_major(client):
    r = client.get("/api/roads/geojson?major=true")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) > 1000
    f = fc["features"][0]
    assert f["geometry"]["type"] == "LineString"
    assert "risk" in f["properties"]


def test_hotspots_seeded(client):
    r = client.get("/api/flood/hotspots?minutes=180")
    assert r.status_code == 200
    hs = r.json()
    assert len(hs) > 0
    assert all("rank" in h and "area_name" in h for h in hs)


def test_drainage_status(client):
    r = client.get("/api/drainage/status")
    assert r.status_code == 200
    body = r.json()
    assert body["total_nodes"] == 444
    assert body["total_edges"] == 278
    assert 0 <= body["average_utilization"] <= 100


def test_alerts_generated_by_pipeline_seed(client):
    r = client.get("/api/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_safe_route_default_engine(client):
    r = client.get("/api/route/safe",
                   params={"origin_lat": 13.0819, "origin_lon": 80.2705,
                           "dest_lat": 12.9941, "dest_lon": 80.1709,
                           "mode": "NORMAL", "forecast_minutes": 60})
    assert r.status_code == 200
    body = r.json()
    assert body["distance_km"] > 0
    assert body["estimated_minutes"] > 0


def test_street_endpoint(client):
    preds = client.get("/api/flood/forecast").json()
    road_id = preds[0]["road_id"]
    r = client.get(f"/api/flood/street/{road_id}")
    assert r.status_code == 200
    assert r.json()["road_id"] == road_id


def test_rainfall_forecast(client):
    r = client.get("/api/rainfall/forecast")
    assert r.status_code == 200
    assert "timesteps" in r.json()


def test_rainfall_nowcast(client):
    r = client.get("/api/rainfall/nowcast")
    assert r.status_code == 200
    body = r.json()
    assert len(body["rainfall_mm_hr"]) == 9
    assert body["confidence"] in ("HIGH", "MEDIUM", "LOW")


def test_providers_status_endpoint(client):
    r = client.get("/api/providers/status")
    assert r.status_code == 200
    body = r.json()
    assert "providers" in body
    names = {p["name"] for p in body["providers"]}
    assert "nasa_gpm" in names
    assert "google_flood" in names
    assert "open_meteo" in names
    assert body["nasa"]["configured"] is False
    assert body["nasa"]["status"] == "config-missing"
    assert body["google_flood"]["configured"] is False
    assert body["google_flood"]["status"] == "config-missing"


def test_nasa_rainfall_endpoint_config_missing_without_token(client):
    r = client.get("/api/flood/nasa-rainfall")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "config-missing"
    assert "message" in body
    assert body["cells"] == []


def test_google_flood_context_endpoint_config_missing_without_key(client):
    r = client.get("/api/flood/google-context")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "config-missing"
    assert "message" in body
    assert body["context"] is None


def test_provider_status_never_exposes_secrets(client):
    r = client.get("/api/providers/status")
    body = r.json()
    raw = str(body)
    assert "Bearer" not in raw
    for secret in ("nasa_earthdata_token", "google_flood_api_key", "open_meteo_api_key"):
        assert secret not in raw


def test_simulation_scenario_overrides(client):
    r = client.post("/api/simulation/start", json={
        "name": "TEST_SCENARIO", "rainfall_mm_hr": 60.0, "duration_min": 60, "blockage_percent": 15,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["scenario"]["name"] == "TEST_SCENARIO"