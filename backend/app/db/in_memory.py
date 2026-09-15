"""In-memory storage backend (default for prototype / no-PostGIS environments)."""
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..logging_conf import log
from .adapters import StorageAdapter

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data")


class InMemoryStorage(StorageAdapter):
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.abspath(DATA_DIR)
        self.roads = self._load_roads()
        self.drainage_nodes = self._load_drainage_nodes()
        self.drainage_edges = self._load_drainage_edges()
        self.terrain_cells = self._load_terrain()
        self.flood_predictions: Dict[int, List[dict]] = {}
        self.alerts: List[dict] = []
        self.weather: Optional[dict] = None
        self.last_ingestion: Optional[datetime] = None
        log.info("InMemoryStorage initialised")

    def _load_roads(self) -> List[dict]:
        path = os.path.join(self.data_dir, "chennai_roads.geojson")
        if not os.path.exists(path):
            log.warning("No roads data found. Run scripts/fetch_osm_data.py")
            return []
        with open(path) as f:
            gj = json.load(f)
        roads = []
        for feat in gj["features"]:
            props = feat["properties"]
            geom = feat["geometry"]
            roads.append({
                "road_id": props.get("road_id", str(feat["id"])),
                "name": props.get("name", f"Road_{feat['id']}"),
                "highway": props.get("highway", "unknown"),
                "length_m": props.get("length_m", 100.0),
                "width_m": props.get("width_m", 10.0),
                "surface": props.get("surface", "unknown"),
                "lanes": props.get("lanes", 2),
                "geometry": geom,
                "lat": geom["coordinates"][len(geom["coordinates"]) // 2][1],
                "lon": geom["coordinates"][len(geom["coordinates"]) // 2][0],
            })
        log.info(f"Loaded {len(roads)} roads")
        return roads

    def _load_drainage_nodes(self) -> List[dict]:
        path = os.path.join(self.data_dir, "drainage_nodes.json")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return json.load(f)

    def _load_drainage_edges(self) -> List[dict]:
        path = os.path.join(self.data_dir, "drainage_edges.json")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return json.load(f)

    def _load_terrain(self) -> List[dict]:
        from ..geospatial.terrain import TerrainLoader
        loader = TerrainLoader(self.data_dir)
        return loader.load_terrain_cells()

    # ---- StorageAdapter interface --------------------------------------
    def load_roads(self) -> List[dict]:
        return self.roads

    def load_drainage_nodes(self) -> List[dict]:
        return self.drainage_nodes

    def load_drainage_edges(self) -> List[dict]:
        return self.drainage_edges

    def load_terrain_cells(self) -> List[dict]:
        return self.terrain_cells

    def save_flood_predictions(self, predictions: List[dict]):
        snapshot = int(predictions[0]["forecast_minutes"]) if predictions else 0
        self.flood_predictions[snapshot] = predictions

    def get_flood_predictions(self, forecast_minutes: Optional[int] = None):
        if forecast_minutes is None:
            out = []
            for snap in self.flood_predictions.values():
                out.extend(snap)
            return out
        return self.flood_predictions.get(forecast_minutes, [])

    def save_alerts(self, alerts: List[dict]):
        self.alerts = alerts

    def get_active_alerts(self) -> List[dict]:
        now = datetime.now(timezone.utc)
        return [a for a in self.alerts if a.get("status") == "active" and (not a.get("expires_at") or a["expires_at"] > now)]

    def save_weather(self, data: dict):
        self.weather = data

    def get_weather(self) -> Optional[dict]:
        return self.weather

    def health(self) -> dict:
        return {
            "status": "ok",
            "backend": "in_memory",
            "roads": len(self.roads),
            "drainage_nodes": len(self.drainage_nodes),
            "drainage_edges": len(self.drainage_edges),
            "terrain_cells": len(self.terrain_cells),
            "flood_snapshots": list(self.flood_predictions.keys()),
        }