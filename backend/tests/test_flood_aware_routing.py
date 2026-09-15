"""Flood-aware routing tests.

These focus on the penalty/penalisation logic and diversion behaviour.
Building the provider loads the real OSM road network (~34k ways) once per module.
"""
import pytest

from app.routing.flood_aware import _SEV_PENALTY, FloodAwareProvider
from app.models import RoutingMode, Severity


@pytest.fixture(scope="module")
def provider():
    return FloodAwareProvider()


def test_provider_builds_graph(provider):
    assert len(provider.graph.nodes) > 1000
    assert len(provider.graph.edges) > 1000


def test_severity_penalty_monotonic():
    assert _SEV_PENALTY["SAFE"] < _SEV_PENALTY["MINOR"] < _SEV_PENALTY["HIGH"] < \
        _SEV_PENALTY["SEVERE"] < _SEV_PENALTY["CRITICAL"]


def _synthetic_predictions(provider):
    """Assign each road a deterministic risk from its id hash."""
    preds = {}
    levels = ["SAFE", "MINOR", "HIGH", "SEVERE", "CRITICAL"]
    for i, edge in enumerate(provider.graph.edges(data=True)):
        road_id = edge[2].get("road_id", f"r{i}")
        preds[road_id] = {"road_id": road_id, "risk": levels[i % 5], "max_depth_cm": float((i % 5) * 10)}
    return preds


def test_flood_penalty_increases_weight(provider):
    preds = _synthetic_predictions(provider)
    provider._set_flood_penalties(RoutingMode.NORMAL, preds)
    max_w, min_w = 0.0, 1e18
    max_sev = min_sev = ""
    for u, v, d in provider.graph.edges(data=True):
        p = preds.get(d["road_id"], {})
        if d["adjusted_weight"] > max_w:
            max_w, max_sev = d["adjusted_weight"], p.get("risk", "SAFE")
        if 0 < d["adjusted_weight"] < min_w:
            min_w, min_sev = d["adjusted_weight"], p.get("risk", "SAFE")
    assert max_sev in ("SEVERE", "CRITICAL")
    assert min_sev in ("SAFE", "MINOR")


def test_emergency_mode_weights_higher_penalty(provider):
    preds = _synthetic_predictions(provider)
    provider._set_flood_penalties(RoutingMode.NORMAL, preds)
    normal = sum(d["adjusted_weight"] for _, _, d in provider.graph.edges(data=True))
    provider._set_flood_penalties(RoutingMode.EMERGENCY, preds)
    emergency = sum(d["adjusted_weight"] for _, _, d in provider.graph.edges(data=True))
    assert emergency > normal


def test_route_is_produced_with_valid_result(provider):
    # Central (13.0819, 80.2705) -> Velachery (12.9791, 80.2208)
    r = provider.get_route(13.0819, 80.2705, 12.9791, 80.2208,
                           mode=RoutingMode.NORMAL,
                           predictions_by_road=_synthetic_predictions(provider))
    assert r is not None
    assert r.distance_km > 0
    assert r.route or r.distance_km > 0
    # Route uses sensible minutes for ~15 km
    assert r.estimated_minutes > 0