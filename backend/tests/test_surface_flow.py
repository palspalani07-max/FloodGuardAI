import pytest

from app.simulation.surface_flow.engine import SurfaceFlowEngine


def _cells():
    # 3x2 grid with a downhill gradient toward the south-west
    cells = []
    for i, lat in enumerate([13.100, 13.090, 13.080]):
        for j, lon in enumerate([80.150, 80.160]):
            elev = 12.0 - i * 2.0 - j  # lower south and west
            cells.append({
                "cell_id": f"T_{i}_{j}", "lat": lat, "lon": lon,
                "elevation_m": elev, "slope": 0.0,
            })
    eng = SurfaceFlowEngine(grid_side_m=1000.0)
    eng.setup_grid(cells)
    return eng


def test_neighbours_bounds():
    eng = _cells()
    n00 = eng.neighbours("T_0_0")
    # corner cell: only 2 neighbours
    assert len(n00) == 2
    n11 = eng.neighbours("T_1_1")
    # 3×2 grid: T_1_1 has neighbours north=(0,1), south=(2,1), west=(1,0); east=(1,2) is out-of-bounds
    assert len(n11) == 3


def test_water_moves_downhill():
    eng = _cells()
    # drop water in the top-right (highest elevation cell)
    eng.step({"T_0_1": 1000.0}, dt_min=15.0)
    snap = eng.snapshot()
    # water must have drained toward a lower neighbour
    assert snap["T_0_1"]["depth_cm"] < 100.0  # not all water held in place
    assert any(v["depth_cm"] > 0 for v in snap.values())


def test_inlet_removal_reduces_depth():
    eng = _cells()
    eng.step({"T_1_1": 1000.0}, dt_min=15.0)
    before = eng.snapshot()["T_1_1"]["depth_cm"]
    eng.step({}, dt_min=15.0, drainage_removal={"T_1_1": 2000.0})
    after = eng.snapshot()["T_1_1"]["depth_cm"]
    assert after < before


def test_surcharge_injection_increases_depth():
    eng = _cells()
    eng.inject_surcharge("T_1_1", 1000.0)
    # grid_side_m=1000 m → area = 1 km² = 1e6 m², 1000 m³ → 0.1 cm
    assert eng.snapshot()["T_1_1"]["depth_cm"] == pytest.approx(0.1, rel=0.1)