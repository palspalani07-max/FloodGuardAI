"""Data integrity checks for the pre-fetched Chennai datasets."""
import json
import os

DATA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))


def test_roads_geojson_present_and_large():
    with open(os.path.join(DATA, "chennai_roads.geojson")) as f:
        gj = json.load(f)
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) > 10000
    # every road must have a geometry with >= 2 coordinate pairs
    for feat in gj["features"][:200]:
        assert len(feat["geometry"]["coordinates"]) >= 2


def test_terrain_grid_schema():
    with open(os.path.join(DATA, "terrain_grid.json")) as f:
        cells = json.load(f)
    assert len(cells) > 1000
    for c in cells[:20]:
        assert {"cell_id", "lat", "lon", "elevation_m", "slope", "imperviousness"} <= set(c)


def test_drainage_nodes_and_edges_count():
    with open(os.path.join(DATA, "drainage_nodes.json")) as f:
        nodes = json.load(f)
    with open(os.path.join(DATA, "drainage_edges.json")) as f:
        edges = json.load(f)
    assert len(nodes) > 200
    assert len(edges) > 100
    nids = {n["node_id"] for n in nodes}
    for e in edges:
        assert e["from_node"] in nids
        assert e["to_node"] in nids
        assert e["capacity_m3s"] > 0