import pytest

from app.simulation.runoff.engine import RunoffEngine


@pytest.fixture(scope="module")
def runoff() -> RunoffEngine:
    return RunoffEngine()


def test_runoff_no_rain(runoff):
    cell = {"cell_id": "T_0_0", "land_cover": "road", "imperviousness": 0.9}
    res = runoff.compute(cell, 0.0, 250000.0)
    assert res.runoff_volume_m3_hr == 0.0
    assert res.runoff_depth_mm == 0.0


def test_runoff_scales_with_rain(runoff):
    cell = {"cell_id": "T_0_0", "land_cover": "road", "imperviousness": 0.9}
    light = runoff.compute(cell, 10.0, 250000.0)
    heavy = runoff.compute(cell, 60.0, 250000.0)
    assert heavy.runoff_depth_mm > light.runoff_depth_mm
    assert heavy.runoff_volume_m3_hr > light.runoff_volume_m3_hr


def test_runoff_infiltration_and_depression_subtracted(runoff):
    cell = {"cell_id": "T_1_1", "land_cover": "grass", "imperviousness": 0.1}
    res = runoff.compute(cell, 5.0, 250000.0)
    # infiltration (3*0.9 + 0.3*0.1) + depression (5*0.9 + 1.5*0.1) > 5 mm rain
    assert res.runoff_volume_m3_hr == 0.0


def test_runoff_coefficient_shape(runoff):
    assert runoff.coefficient_for("road") > runoff.coefficient_for("vegetation")


def test_compute_all_uses_lookup(runoff):
    cells = [
        {"cell_id": "a", "land_cover": "road", "imperviousness": 0.9},
        {"cell_id": "b", "land_cover": "grass", "imperviousness": 0.1},
    ]
    results = runoff.compute_all(cells, {"a": 50.0, "b": 50.0}, 250000.0)
    by_id = {r.cell_id: r for r in results}
    assert by_id["a"].runoff_volume_m3_hr > by_id["b"].runoff_volume_m3_hr