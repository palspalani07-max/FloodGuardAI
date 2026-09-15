"""Fetch real OSM road data for Chennai study area."""
import requests
import json
import time
import sys
import os

BBOX = (12.99, 80.15, 13.17, 80.32)
HIGHWAY_TAGS = ["trunk", "primary", "secondary", "tertiary", "residential", "unclassified"]

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def fetch_osm_roads():
    os.makedirs(DATA_DIR, exist_ok=True)
    s, w, n, e = BBOX
    tags = "|".join(HIGHWAY_TAGS)
    query = f"""[out:json][timeout:120];
    way["highway"~"^({tags})$"]({s},{w},{n},{e});
    out geom;
    """
    print(f"Fetching OSM roads for bbox {BBOX}...")
    for attempt in range(3):
        try:
            r = requests.get(
                OVERPASS_URL,
                params={"data": query},
                timeout=120,
                headers={"User-Agent": "floodguard-ai/0.1 (research)"},
            )
            if r.status_code == 200:
                break
            print(f"  attempt {attempt+1}: status {r.status_code}, retrying...")
            time.sleep(3)
        except requests.RequestException as e:
            print(f"  attempt {attempt+1}: {e}, retrying...")
            time.sleep(5)
    else:
        print("Failed to fetch OSM data after 3 attempts.")
        sys.exit(1)

    data = r.json()
    elements = data.get("elements", [])
    print(f"  Received {len(elements)} ways")

    features = []
    for el in elements:
        if "geometry" not in el or not el["geometry"]:
            continue
        tags = el.get("tags", {})
        coords = [(p["lat"], p["lon"]) for p in el["geometry"]]
        if len(coords) < 2:
            continue
        length = _haversine_length(coords)
        feature = {
            "type": "Feature",
            "id": el["id"],
            "properties": {
                "road_id": str(el["id"]),
                "name": tags.get("name", tags.get("name:en", f"Road_{el['id']}")),
                "highway": tags.get("highway", "unknown"),
                "surface": tags.get("surface", "unknown"),
                "oneway": tags.get("oneway", "no"),
                "lanes": int(tags.get("lanes", 2)) if tags.get("lanes", "").isdigit() else 2,
                "width_m": _safe_float(tags.get("width", "10.0"), 10.0),
                "length_m": length,
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[p["lon"], p["lat"]] for p in el["geometry"]],
            },
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}
    out_path = os.path.join(DATA_DIR, "chennai_roads.geojson")
    with open(out_path, "w") as f:
        json.dump(geojson, f)
    print(f"  Saved {len(features)} road features to {out_path}")

    stats = {}
    for feat in features:
        hw = feat["properties"]["highway"]
        stats[hw] = stats.get(hw, 0) + 1
    print(f"  Road types: {stats}")
    return geojson


def _safe_float(val, default=0.0):
    if isinstance(val, (int, float)):
        return float(val)
    try:
        import re
        m = re.search(r'[\d.]+', str(val))
        return float(m.group()) if m else default
    except (ValueError, AttributeError):
        return default


def _haversine_length(coords):
    import math
    total = 0.0
    for i in range(1, len(coords)):
        lat1, lon1 = math.radians(coords[i - 1][0]), math.radians(coords[i - 1][1])
        lat2, lon2 = math.radians(coords[i][0]), math.radians(coords[i][1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        total += 2 * 6371000 * math.asin(math.sqrt(a))
    return round(total, 1)


if __name__ == "__main__":
    fetch_osm_roads()
