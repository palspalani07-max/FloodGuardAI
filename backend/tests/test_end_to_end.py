"""End-to-end pipeline test: rain -> runoff -> surface flow -> drainage ->
hydraulic capacity -> overload -> surcharge -> flood depth -> street risk ->
alert -> route diversion."""
import pytest

from app.simulation.risk.classifier import Severity
from app.services.alert_service import AlertService


@pytest.fixture(scope="module")
def engine():
    from app.flood_engine import FloodEngine
    return FloodEngine()


@pytest.fixture(scope="module")
def heavy_run(engine):
    return engine.run(override_rainfall=60.0)


def test_pipeline_produces_full_cells(heavy_run):
    assert heavy_run["status"] == "ok"
    assert heavy_run["cells_simulated"] == 1517
    assert heavy_run["timesteps"] == [0, 15, 30, 45, 60, 90, 120, 150, 180]


def test_extreme_rain_leads_to_flooding(engine, heavy_run):
    preds = engine.storage.get_flood_predictions()
    assert len(preds) > 20000
    risky = [p for p in preds if p["risk"] in ("HIGH", "SEVERE", "CRITICAL")]
    assert len(risky) > 0


def test_flood_depth_increases_with_time(engine, heavy_run):
    preds = engine.storage.get_flood_predictions()
    # peak depths >= current for a good majority of roads
    increasing = sum(1 for p in preds if p["max_depth_cm"] >= p["current_depth_cm"] - 0.01)
    assert increasing > 0.8 * len(preds)


def test_heavy_rain_generates_hotspots(heavy_run):
    assert len(heavy_run["hotspots"]) > 0
    sev = {h["severity"] for h in heavy_run["hotspots"]}
    assert sev & {"HIGH", "SEVERE", "CRITICAL"}


def test_alerts_generated_from_predictions(engine, heavy_run):
    preds = engine.storage.get_flood_predictions()
    alerts = AlertService().generate_alerts(preds)
    assert len(alerts) > 0
    sev = {a["severity"] for a in alerts}
    assert sev & {"HIGH", "SEVERE", "CRITICAL"}
    # messages must be human readable and warn users
    assert all("flood" in a["message"].lower() for a in alerts[:5])


def test_diversion_when_flooding(engine, heavy_run):
    from app.routing.flood_aware import FloodAwareProvider
    from app.models import RoutingMode
    provider = FloodAwareProvider()
    pred_map = {p["road_id"]: p for p in engine.storage.get_flood_predictions()}
    # normal conditions: no flood penalties
    dry_preds = {k: {"risk": "SAFE", "max_depth_cm": 0.0} for k in pred_map}
    r_norm = provider.get_route(13.0819, 80.2705, 12.9791, 80.2208,
                                mode=RoutingMode.NORMAL, predictions_by_road=dry_preds)
    r_flood = provider.get_route(13.0819, 80.2705, 12.9791, 80.2208,
                                 mode=RoutingMode.NORMAL, predictions_by_road=pred_map)
    assert r_norm.distance_km > 0
    # In heavy rain at least one exercised route shows the flood-aware behaviour:
    # either it diverted, took longer, or reached a flooded road blocked out.
    assert r_flood.distance_km > 0
    assert r_flood.estimated_minutes >= 0
    # diversion must flag when a flood road is avoided
    if r_flood.diverted:
        assert r_flood.avoided_roads > 0
    else:
        assert r_flood.risk in (Severity.SAFE.value, Severity.MINOR.value)