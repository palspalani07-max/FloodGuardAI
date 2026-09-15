"""Generate synthetic DEM and drainage network for Chennai study area."""
import numpy as np
import json
import os
import math

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BBOX = {"south": 12.99, "north": 13.17, "west": 80.15, "east": 80.32}

KNOWN_ELEVATIONS = {
    "airport": (13.005, 80.170, 12.0),
    "velachery": (13.050, 80.220, 2.5),
    "adyar": (13.006, 80.257, 1.5),
    "t_nagar": (13.041, 80.234, 6.0),
    "central": (13.083, 80.270, 8.0),
    "marina": (13.050, 80.283, 2.0),
    "chetpet": (13.074, 80.244, 10.0),
    "nungambakkam": (13.059, 80.242, 11.0),
    "adyar_river": (13.010, 80.265, 0.5),
    "cooum_river": (13.065, 80.272, 1.0),
}


def generate_synthetic_dem(resolution=500):
    import numpy as np
    from scipy.ndimage import gaussian_filter
    lat_range = np.arange(BBOX["south"], BBOX["north"], resolution / 111320)
    lon_range = np.arange(BBOX["west"], BBOX["east"], resolution / (111320 * math.cos(math.radians(13.08))))
    elev_plane = np.zeros((len(lat_range), len(lon_range)))

    def _plane(lat, lon):
        # west high -> east low (Chennai rises inland to the west), with a
        # gentle south-north tilt; ~7 m drop across the study area.
        e = 9.0 - (lon - BBOX["west"]) / (BBOX["east"] - BBOX["west"]) * 7.0
        e += (lat - BBOX["south"]) / (BBOX["north"] - BBOX["south"]) * 1.5
        return e

    def _gauss(lat, lon, c_lat, c_lon, amp, sigma_deg):
        d2 = ((lat - c_lat) / sigma_deg) ** 2 + ((lon - c_lon) / sigma_deg) ** 2
        return amp * math.exp(-d2)

    for i, lat in enumerate(lat_range):
        for j, lon in enumerate(lon_range):
            elev = _plane(lat, lon)
            # river corridors and depressions (lower than surroundings)
            elev -= _gauss(lat, lon, 13.006, 80.257, 4.0, 0.035)   # Adyar mouth
            elev -= _gauss(lat, lon, 13.010, 80.265, 2.5, 0.02)    # Adyar river
            elev -= _gauss(lat, lon, 13.065, 80.272, 2.5, 0.02)    # Cooum river
            elev -= _gauss(lat, lon, 13.05, 80.22, 3.2, 0.032)     # Velachery basin
            elev -= _gauss(lat, lon, 13.05, 80.283, 2.2, 0.03)     # Marina coastal plain
            elev -= _gauss(lat, lon, 13.006, 80.17, 1.5, 0.03)     # Airport low apron
            # small-scale smoothed terrain roughness
            elev += np.random.normal(0, 0.35)
            elev = max(0.2, min(elev, 14.0))
            elev_plane[i, j] = elev

    # gaussian smoothing removes pits, producing continuous drainage basins
    elev_smooth = gaussian_filter(elev_plane, sigma=2.0)
    dem = np.maximum(0.2, np.minimum(14.0, elev_smooth))
    return dem, lat_range, lon_range


def _nearest_feature(lat, lon):
    min_name, min_dist = "", 99999
    for name, (elat, elon, _) in KNOWN_ELEVATIONS.items():
        d = math.sqrt((lat - elat) ** 2 + (lon - elon) ** 2)
        if d < min_dist:
            min_dist = d
            min_name = name
    return min_name


def generate_terrain_grid():
    dem, lat_range, lon_range = generate_synthetic_dem()
    grid = []
    for i, lat in enumerate(lat_range):
        for j, lon in enumerate(lon_range):
            row_above = dem[i - 1, j] if i > 0 else dem[i, j]
            row_below = dem[i + 1, j] if i < len(lat_range) - 1 else dem[i, j]
            col_left = dem[i, j - 1] if j > 0 else dem[i, j]
            col_right = dem[i, j + 1] if j < len(lon_range) - 1 else dem[i, j]
            slope = math.sqrt(((row_below - row_above) / (2 * 500)) ** 2 + ((col_right - col_left) / (2 * 500)) ** 2)
            flow_dir = _calc_flow_dir(dem, i, j)
            imp = _estimate_imperviousness(lat, lon)
            name = _nearest_feature(lat, lon)
            grid.append({
                "cell_id": f"T_{i}_{j}",
                "lat": round(float(lat), 6),
                "lon": round(float(lon), 6),
                "elevation_m": round(float(dem[i, j]), 2),
                "slope": round(slope, 6),
                "flow_direction": flow_dir,
                "imperviousness": imp,
                "land_cover": _classify_land_cover(imp),
            })
    return grid


def _calc_flow_dir(dem, i, j):
    dirs = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    best_dir, best_drop = 0, 0
    for idx, (di, dj) in enumerate(dirs):
        ni, nj = i + di, j + dj
        if 0 <= ni < dem.shape[0] and 0 <= nj < dem.shape[1]:
            drop = dem[i, j] - dem[ni, nj]
            if drop > best_drop:
                best_drop = drop
                best_dir = 1 << idx
    return best_dir


def _estimate_imperviousness(lat, lon):
    for name, (elat, elon, _) in KNOWN_ELEVATIONS.items():
        dist = math.sqrt((lat - elat) ** 2 + (lon - elon) ** 2) * 111320
        if dist < 200:
            if "river" in name:
                return 0.3
            if "velachery" in name or "t_nagar" in name:
                return 0.85
    return 0.55


def _classify_land_cover(imp):
    if imp > 0.8:
        return "concrete"
    elif imp > 0.6:
        return "road"
    elif imp > 0.4:
        return "mixed"
    elif imp > 0.25:
        return "grass"
    else:
        return "vegetation"


def generate_drainage_network(terrain_grid):
    np.random.seed(42)
    nodes = []
    edges = []
    node_id = 0
    edge_id = 0
    sorted_grid = sorted(terrain_grid, key=lambda c: c["elevation_m"])

    for cell in sorted_grid:
        if np.random.random() < 0.28:
            node_id += 1
            n = DrainageNode(
                node_id=f"DN_{node_id}",
                lat=cell["lat"],
                lon=cell["lon"],
                elevation_m=cell["elevation_m"] - 1.5,
                node_type="manhole",
            )
            nodes.append(n)

    for i, n1 in enumerate(nodes):
        for j, n2 in enumerate(nodes):
            if i >= j:
                continue
            dist = math.sqrt((n1["lat"] - n2["lat"]) ** 2 + (n1["lon"] - n2["lon"]) ** 2) * 111320
            if dist < 850 and np.random.random() < 0.55:
                edge_id += 1
                slope = max(0.001, abs(n1["elevation_m"] - n2["elevation_m"]) / dist)
                diameter = np.random.choice([0.3, 0.45, 0.6, 0.9, 1.2, 1.5, 2.0, 2.5])
                roughness = np.random.choice([0.011, 0.013, 0.015])
                area = math.pi * (diameter / 2) ** 2
                hydraulic_radius = diameter / 4
                capacity = (1 / roughness) * area * (hydraulic_radius ** (2 / 3)) * (slope ** 0.5)
                lower, higher = (n1, n2) if n1["elevation_m"] > n2["elevation_m"] else (n2, n1)
                edges.append({
                    "edge_id": f"DE_{edge_id}",
                    "from_node": lower["node_id"],
                    "to_node": higher["node_id"],
                    "lat_from": lower["lat"],
                    "lon_from": lower["lon"],
                    "lat_to": higher["lat"],
                    "lon_to": higher["lon"],
                    "length_m": round(dist, 1),
                    "diameter_m": diameter,
                    "slope": round(slope, 4),
                    "roughness": roughness,
                    "capacity_m3s": round(capacity, 4),
                    "blockage_percent": round(np.random.uniform(0, 0.15), 2),
                    "current_flow_m3s": 0.0,
                    "is_overloaded": False,
                })
    return nodes, edges


class DrainageNode(dict):
    pass


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    print("Generating synthetic terrain grid...")
    terrain = generate_terrain_grid()
    with open(os.path.join(DATA_DIR, "terrain_grid.json"), "w") as f:
        json.dump(terrain, f)
    print(f"  Saved {len(terrain)} terrain cells")

    print("Generating drainage network...")
    nodes, edges = generate_drainage_network(terrain)
    with open(os.path.join(DATA_DIR, "drainage_nodes.json"), "w") as f:
        json.dump(nodes, f)
    with open(os.path.join(DATA_DIR, "drainage_edges.json"), "w") as f:
        json.dump(edges, f)
    print(f"  Saved {len(nodes)} nodes, {len(edges)} edges")


if __name__ == "__main__":
    main()
