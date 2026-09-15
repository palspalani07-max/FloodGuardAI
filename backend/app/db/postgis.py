"""PostGIS storage backend (activated when DATABASE_URL is configured).

Uses GeoAlchemy2 / psycopg2. The schema in database/schema.sql mirrors the tables.
"""
from datetime import datetime
from typing import Dict, List, Optional

from ..logging_conf import log
from .adapters import StorageAdapter


class PostGISStorage(StorageAdapter):
    def __init__(self, database_url: str):
        self.database_url = database_url
        try:
            import psycopg2  # noqa
        except ImportError:
            raise RuntimeError("psycopg2 not installed")
        self.conn = self._connect()
        log.info("PostGISStorage connected")

    def _connect(self):
        from sqlalchemy import create_engine
        engine = create_engine(self.database_url)
        return engine.connect()

    def _query(self, sql: str, params: tuple = ()):
        result = self.conn.execute(sql, params)
        rows = result.fetchall()
        cols = [c[0] for c in result.cursor.description]
        return [dict(zip(cols, row)) for row in rows]

    def load_roads(self) -> List[dict]:
        rows = self._query("SELECT road_id, name, length_m, width_m, surface_type, "
                           "elevation_m, slope, speed_limit, road_class, "
                           "ST_AsGeoJSON(geometry) AS geom FROM roads")
        for r in rows:
            geom = r.pop("geom", None)
            if geom:
                import json
                r["geometry"] = json.loads(geom)
        return rows

    def load_drainage_nodes(self) -> List[dict]:
        rows = self._query("SELECT node_id, node_type, elevation_m, storage_capacity, "
                           "inlet_capacity, current_water_level, "
                           "ST_Y(geometry) AS lat, ST_X(geometry) AS lon FROM drainage_nodes")
        return [{"node_id": r["node_id"], "node_type": r["node_type"], "elevation_m": r["elevation_m"],
                 "storage_capacity": r["storage_capacity"], "inlet_capacity": r["inlet_capacity"],
                 "current_water_level": r["current_water_level"], "lat": r["lat"], "lon": r["lon"]} for r in rows]

    def load_drainage_edges(self) -> List[dict]:
        rows = self._query("SELECT edge_id, from_node, to_node, length_m, diameter_m, slope, "
                           "roughness, capacity_m3s, blockage_percent, current_flow_m3s, "
                           "ST_Y(ST_StartPoint(geometry)) AS lat_from, ST_X(ST_StartPoint(geometry)) AS lon_from, "
                           "ST_Y(ST_EndPoint(geometry)) AS lat_to, ST_X(ST_EndPoint(geometry)) AS lon_to "
                           "FROM drainage_edges")
        return rows

    def load_terrain_cells(self) -> List[dict]:
        rows = self._query("SELECT cell_id, elevation_m, slope, flow_direction, imperviousness, "
                           "ST_Y(geometry) AS lat, ST_X(geometry) AS lon FROM terrain_cells")
        return [{"cell_id": r["cell_id"], "elevation_m": r["elevation_m"], "slope": r["slope"],
                 "flow_direction": r["flow_direction"], "imperviousness": r["imperviousness"],
                 "lat": r["lat"], "lon": r["lon"]} for r in rows]

    def save_flood_predictions(self, predictions: List[dict]):
        for p in predictions:
            self._query("INSERT INTO flood_predictions (road_id, timestamp, forecast_minutes, depth_cm, "
                        "velocity_ms, arrival_time_min, duration_min, risk, confidence, model_version) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (p["road_id"], datetime.utcnow(), p.get("forecast_minutes", 0), p.get("max_depth_cm", 0),
                         p.get("velocity_ms", 0), p.get("arrival_time_min"), p.get("duration_min", 0),
                         p.get("risk", "SAFE"), p.get("confidence", "MEDIUM"), p.get("model_version", "0.1.0")))

    def get_flood_predictions(self, forecast_minutes: Optional[int] = None):
        if forecast_minutes is None:
            sql = "SELECT * FROM flood_predictions WHERE timestamp = (SELECT MAX(timestamp) FROM flood_predictions)"
        else:
            sql = "SELECT * FROM flood_predictions WHERE forecast_minutes = %s"
        return self._query(sql, (forecast_minutes,) if forecast_minutes is not None else ())

    def save_alerts(self, alerts: List[dict]):
        self._query("DELETE FROM alerts WHERE status = 'active'")
        for a in alerts:
            self._query("INSERT INTO alerts (road_id, severity, message, status) VALUES (%s, %s, %s, %s)",
                        (a.get("road_id"), a.get("severity", "SAFE"), a.get("message", ""), "active"))

    def get_active_alerts(self) -> List[dict]:
        return self._query("SELECT * FROM alerts WHERE status = 'active'")

    def save_weather(self, data: dict):
        self._query("UPDATE observations SET water_depth_cm = %s, confidence = %s WHERE observation_id = 'system_weather'",
                    (data.get("temperature_c", 0), "HIGH"))

    def get_weather(self) -> Optional[dict]:
        rows = self._query("SELECT * FROM observations WHERE observation_id = 'system_weather' LIMIT 1")
        return rows[0] if rows else None

    def health(self) -> dict:
        return {"status": "ok", "backend": "postgis", "database_url": self.database_url}