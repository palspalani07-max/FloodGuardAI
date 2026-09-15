"""Terrain / DEM loading.

Supports real DEM GeoTIFF input when a file is present in data/ (rasterio).
Falls back to synthetic terrain (clearly labelled SIMULATION DATA).
"""
import json
import os
from typing import Dict, List

from ..logging_conf import log

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")


class TerrainLoader:
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.abspath(DATA_DIR)

    def load_terrain_cells(self) -> List[dict]:
        """Load terrain grid from disk (synthetic fallback), building a DEM if a GeoTIFF exists."""
        tif_path = self._find_dem_tiff()
        if tif_path:
            try:
                return self._load_from_tiff(tif_path)
            except Exception as e:
                log.warning(f"Could not load DEM {tif_path}: {e}. Falling back to synthetic terrain (SIMULATION DATA).")
        return self._load_synthetic()

    def _find_dem_tiff(self) -> str:
        for f in os.listdir(self.data_dir):
            if f.endswith((".tif", ".tiff")) and "dem" in f.lower():
                return os.path.join(self.data_dir, f)
        return ""

    def _load_synthetic(self) -> List[dict]:
        path = os.path.join(self.data_dir, "terrain_grid.json")
        if os.path.exists(path):
            with open(path) as f:
                cells = json.load(f)
            log.info(f"Loaded {len(cells)} synthetic terrain cells (SIMULATION DATA)")
            return cells
        log.error("No terrain data found. Run scripts/generate_terrain.py first.")
        return []

    def _load_from_tiff(self, tif_path: str) -> List[dict]:
        import rasterio
        import numpy as np
        cells = []
        with rasterio.open(tif_path) as src:
            dem = src.read(1).astype(float)
            transform = src.transform
            ny, nx = dem.shape
            res = abs(transform[0])
            for i in range(0, ny, max(1, int(res / 500))):
                for j in range(0, nx, max(1, int(res / 500))):
                    lon, lat = rasterio.transform.xy(transform, i, j)
                    elev = float(dem[i, j]) if not np.isnan(dem[i, j]) else 0.0
                    slope = 0.0  # refined in grid postprocess
                    cells.append({
                        "cell_id": f"T_{i}_{j}",
                        "lat": round(float(lat), 6),
                        "lon": round(float(lon), 6),
                        "elevation_m": round(elev, 2),
                        "slope": slope,
                        "flow_direction": 0,
                        "imperviousness": 0.55,
                        "land_cover": "mixed",
                    })
        log.info(f"Loaded {len(cells)} terrain cells from DEM {tif_path}")
        return cells