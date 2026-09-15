import pytest

from app.simulation.drainage.engine import ManningCalculator, DrainageEngine


def test_pipe_capacity_positive():
    c = ManningCalculator.pipe_capacity(1.2, 0.01)
    assert c > 0.0


def test_pipe_capacity_direction():
    bigger = ManningCalculator.pipe_capacity(1.5, 0.01)
    smaller = ManningCalculator.pipe_capacity(1.0, 0.01)
    assert bigger > smaller


def test_pipe_capacity_zero_inputs():
    assert ManningCalculator.pipe_capacity(0, 0.01) == 0.0
    assert ManningCalculator.pipe_capacity(1.0, 0) == 0.0


def test_effective_capacity_blockage():
    base = 5.0
    assert ManningCalculator.effective_capacity(base, 0.0) == pytest.approx(base)
    assert ManningCalculator.effective_capacity(base, 50.0) == pytest.approx(base * 0.5)
    assert ManningCalculator.effective_capacity(base, 100.0) == pytest.approx(0.0)
    # out-of-range clamps
    assert ManningCalculator.effective_capacity(base, -20.0) == pytest.approx(base)
    assert ManningCalculator.effective_capacity(base, 130.0) == pytest.approx(0.0)


def _make_engine():
    nodes = [
        {"node_id": "N1", "elevation_m": 10.0, "inlet_capacity": 2.0},
        {"node_id": "N2", "elevation_m": 8.0, "inlet_capacity": 2.0},
        {"node_id": "N3", "elevation_m": 5.0, "inlet_capacity": 2.0},
    ]
    edges = [
        {"edge_id": "E1", "from_node": "N1", "to_node": "N2", "capacity_m3s": 1.0, "blockage_percent": 0.0},
        {"edge_id": "E2", "from_node": "N2", "to_node": "N3", "capacity_m3s": 1.0, "blockage_percent": 60.0},
    ]
    eng = DrainageEngine()
    eng.load(nodes, edges)
    return eng


def test_drainage_flows_and_overload():
    eng = _make_engine()
    monkey = None
    snap = eng.push_flow({"N1": 100.0}, dt_min=15.0)  # 100 m3 in to N1 over 15 min
    assert snap["node_flow_m3s"]["N1"] == pytest.approx(100.0 / (15 * 60), abs=1e-3)
    # N1 inlet capacity is 2.0 m3/s -> 100/(900)=0.111 flows free, no overload
    assert "N1" not in snap["overloaded_nodes"]


def test_drainage_surcharge_when_over_capacity():
    eng = _make_engine()
    snap = eng.push_flow({"N1": 2000.0}, dt_min=15.0)
    assert "N1" in snap["overloaded_nodes"]
    assert snap["surcharge_m3"]["N1"] > 0.0


def test_blocked_pipe_reduces_effective_capacity():
    eng = _make_engine()
    base = eng.graph.edges["E1"]["effective_capacity_m3s"]
    blocked = eng.graph.edges["E2"]["effective_capacity_m3s"]
    assert blocked == pytest.approx(base * 0.4)