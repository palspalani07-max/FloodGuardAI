import pytest

from app.simulation.coupling.engine import SurfaceDrainageCoupling


@pytest.fixture(scope="module")
def coupling() -> SurfaceDrainageCoupling:
    return SurfaceDrainageCoupling(capture_rate=0.4, inlet_capacity_m3s=2.0)


def test_inlet_mapping_assigns_nearest_node(coupling):
    cells = [
        {"cell_id": "A", "lat": 13.0, "lon": 80.2},
        {"cell_id": "B", "lat": 13.01, "lon": 80.21},
        {"cell_id": "C", "lat": 13.5, "lon": 81.0},  # far away
    ]
    nodes = [
        {"node_id": "N1", "lat": 13.005, "lon": 80.205},
        {"node_id": "N2", "lat": 13.5, "lon": 81.0},
    ]
    mapping = coupling.build_inlet_mapping(cells, nodes)
    assert mapping.get("A") == "N1"
    assert mapping.get("B") == "N1"
    assert mapping.get("C") == "N2"


def test_couple_captures_surface_water(coupling):
    surface = {
        "A": {"depth_cm": 10.0},
        "B": {"depth_cm": 10.0},
    }
    inlet_map = {"A": "N1", "B": "N1"}
    result = coupling.couple(surface, {"surcharge_m3": {}, "edge_flow_m3s": {}}, 15.0, inlet_map)
    # capture is capacity-limited and shared across the 2 cells
    total = sum(result.inlet_capture_m3.values())
    assert 0 < total <= 2.0 * 15 * 60


def test_surcharge_returns_to_surface(coupling):
    surface = {"A": {"depth_cm": 0.0}}
    inlet_map = {"A": "N1"}
    drainage = {"surcharge_m3": {"N1": 500.0}, "edge_flow_m3s": {}}
    result = coupling.couple(surface, drainage, 15.0, inlet_map)
    assert result.surcharge_volume_m3.get("A") == pytest.approx(500.0)