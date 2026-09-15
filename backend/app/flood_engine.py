"""FloodEngine orchestrator.

Ties together: terrain -> rainfall nowcast -> runoff -> surface flow -> drainage
-> coupling -> road flood predictions -> hotspots.

The whole pipeline runs off-line (via the worker) and results are cached so the
Time Machine slider is instant.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np

from scipy.spatial import cKDTree

from .config import settings
from .logging_conf import log
from .db.adapters import StorageAdapter, create_storage
from .external.provider_registry import registry
from .simulation.rainfall.nowcast import RainfallNowcast, NowcastResult
from .simulation.runoff.engine import RunoffEngine
from .simulation.surface_flow.engine import SurfaceFlowEngine
from .simulation.drainage.engine import DrainageEngine
from .simulation.coupling.engine import SurfaceDrainageCoupling
from .simulation.risk.classifier import FloodClassifier, Severity
from .ml.inference.engine import InferenceEngine
from .geospatial.earth import haversine_m, midpoint

# severity ordering for hotspots
_SEV_ORDER = {Severity.CRITICAL: 4, Severity.SEVERE: 3, Severity.HIGH: 2, Severity.MINOR: 1, Severity.SAFE: 0}


class FloodEngine:
    def __init__(self, storage: Optional[StorageAdapter] = None):
        self.storage = storage or create_storage(settings.database_url)
        self.roads = self.storage.load_roads()
        self.terrain = self.storage.load_terrain_cells()
        self.drainage_nodes = self.storage.load_drainage_nodes()
        self.drainage_edges = self.storage.load_drainage_edges()
        self.nowcast = RainfallNowcast()
        self.runoff = RunoffEngine()
        self.surface = SurfaceFlowEngine(settings.grid_resolution_m)
        self.surface.setup_grid(self.terrain)
        self.drainage = DrainageEngine()
        self.drainage.load(self.drainage_nodes, self.drainage_edges)
        self.coupling = SurfaceDrainageCoupling()
        self.classifier = FloodClassifier()
        self.ml = InferenceEngine()
        self.inlet_mapping = self.coupling.build_inlet_mapping(self.terrain, self.drainage_nodes)
        self.drainage.set_inlet_mapping(self.inlet_mapping)
        self.cell_ids = [c["cell_id"] for c in self.terrain]
        self.cell_by_id = {c["cell_id"]: c for c in self.terrain}
        self.cell_tree = cKDTree(np.array([[c["lat"], c["lon"]] for c in self.terrain]))
        self.road_cell_map: Dict[str, str] = {}
        self._index_roads_to_cells()
        self.road_drain_edge: Dict[str, tuple] = {}
        self._index_roads_to_drains()
        self.steps = settings.forecast_steps
        self.sim_scenario = None
        self.last_run: Optional[datetime] = None
        self.rainfall_by_cell: Dict[str, Dict[int, float]] = {}
        self._surface_snapshots: Dict[int, Dict] = {}
        log.info(f"FloodEngine ready: {len(self.roads)} roads, {len(self.terrain)} cells, "
                 f"{len(self.drainage_nodes)} drain nodes, {len(self.drainage_edges)} pipes")

    # ------------------------------------------------------------------
    def _build_rainfall_field(self, nowcast: NowcastResult) -> Dict[str, Dict[int, float]]:
        """Spread the base intensity across the grid with mild spatial variation."""
        field: Dict[str, Dict[int, float]] = {}
        n = len(self.terrain)
        for i, cell in enumerate(self.terrain):
            cell_rain = {}
            base = nowcast.rainfall_mm_hr[0]
            seed = (i * 2654435761) & 0xFFFFFFFF
            jitter = 0.7 + ((seed % 1000) / 1000.0) * 0.6
            low_lat = cell["lat"] < 13.03
            city_corridor = 80.20 < cell["lon"] < 80.30  # denser urban core
            spatial = jitter * (1.15 if low_lat else 1.0) * (1.2 if city_corridor else 1.0)
            for step in self.steps:
                cell_rain[step] = round(base * spatial * (0.75 + 0.25 * (step / 45) if step else 1.0), 2)
            field[cell["cell_id"]] = cell_rain
        return field

    # ------------------------------------------------------------------
    def run(self, override_rainfall: Optional[float] = None,
            blockage_percent: Optional[float] = None) -> dict:
        """Run the full simulation over all forecast timesteps."""
        t0 = datetime.now(timezone.utc)
        nowcast = self.nowcast.generate(settings.city_lat, settings.city_lon, override_rainfall)
        self.rainfall_by_cell = self._build_rainfall_field(nowcast)

        if blockage_percent is not None:
            for e in self.drainage_edges:
                e["blockage_percent"] = min(100.0, max(0.0, blockage_percent))
            self.drainage.load(self.drainage_nodes, self.drainage_edges)

        step_depth: Dict[int, Dict[str, float]] = {}
        step_velocity: Dict[int, Dict[str, float]] = {}
        self.surface = SurfaceFlowEngine(settings.grid_resolution_m)
        self.surface.setup_grid(self.terrain)

        prev_depths = {c["cell_id"]: 0.0 for c in self.terrain}
        for idx, step in enumerate(self.steps):
            dt = step - (self.steps[idx - 1] if idx > 0 else 0)
            if dt <= 0:
                dt = 15
            runoff_m3 = {}
            for cell in self.terrain:
                rain = self.rainfall_by_cell[cell["cell_id"]].get(step, override_rainfall or nowcast.rainfall_mm_hr[0])
                res = self.runoff.compute(cell, rain, settings.grid_resolution_m ** 2)
                runoff_m3[cell["cell_id"]] = res.runoff_volume_m3_hr * (dt / 60.0)
            # drainage inlet capture from current surface water
            snap = self.surface.snapshot()
            captured = self.coupling.couple(snap, {"surcharge_m3": {}, "edge_flow_m3s": {}}, dt, self.inlet_mapping)
            removal = captured.inlet_capture_m3
            inlet_map = {}
            for cell_id, vol in removal.items():
                node_id = self.inlet_mapping.get(cell_id)
                if node_id:
                    inlet_map[node_id] = inlet_map.get(node_id, 0.0) + vol
            drain_snap = self.drainage.push_flow(inlet_map, dt)
            # surcharge returns to surface
            surcharge_area = {}
            for node_id, vol in drain_snap.get("surcharge_m3", {}).items():
                for cid, nid in self.inlet_mapping.items():
                    if nid == node_id:
                        surcharge_area.setdefault(cid, 0.0)
                        surcharge_area[cid] += vol
            for cid, vol in surcharge_area.items():
                self.surface.inject_surcharge(cid, vol)
            self.surface.step(runoff_m3, dt, removal)
            snap = self.surface.snapshot()
            step_depth[step] = {cid: v["depth_cm"] for cid, v in snap.items()}
            step_velocity[step] = {cid: v["velocity_ms"] for cid, v in snap.items()}
            self._surface_snapshots[step] = snap

        # ---- derive per-road flood predictions from surface cells ----
        predictions = self._build_road_predictions(step_depth, step_velocity, nowcast)

        # save to storage and threshold into snapshots
        self.storage.save_flood_predictions(predictions)
        hotspots = self._compute_hotspots(step_depth[180])
        self.last_run = datetime.now(timezone.utc)
        elapsed = (self.last_run - t0).total_seconds()
        log.info(f"FloodEngine run complete in {elapsed:.2f}s, {len(step_depth[180])} cells simulated")
        return {
            "status": "ok",
            "elapsed_s": round(elapsed, 2),
            "timesteps": self.steps,
            "cells_simulated": len(step_depth[180]),
            "hotspots": hotspots,
            "model_version": "0.1.0",
        }

    # ------------------------------------------------------------------
    def _build_road_predictions(self, step_depth, step_velocity, nowcast: NowcastResult) -> List[dict]:
        predictions: List[dict] = []
        feature_rows = []
        idx_by_road = {}
        for road_i, road in enumerate(self.roads):
            lat, lon = road["lat"], road["lon"]
            cid = self.road_cell_map.get(road["road_id"])
            if not cid:
                continue
            cell = self.cell_by_id.get(cid)
            if cell is None:
                continue
            depths = {}
            velocities = {}
            for step in self.steps:
                depths[step] = step_depth.get(step, {}).get(cid, 0.0)
                velocities[step] = step_velocity.get(step, {}).get(cid, 0.0)
            max_depth = max(depths.values())
            arrival = None
            duration = 0
            for s in sorted(depths):
                if arrival is None and depths[s] >= 5.0:
                    arrival = s
                if depths[s] >= 5.0:
                    duration = max(duration, s)
            if max_depth > 20:
                duration = max(duration, 180)
            risk = self.classifier.classify(max_depth)
            edge_info = self.road_drain_edge.get(road["road_id"], (None, 999.0))
            row = self.ml.features_for_road(road, cell, self.drainage, step_depth[30].get(cid, 0.0),
                                            edge_info=edge_info)
            idx_by_road[len(predictions)] = (road, cell, depths, velocities, arrival, duration, risk, row)
            predictions.append(None)
        # ---- batched ML correction ----
        corrections = self.ml.predict_batch([idx_by_road[i][7] for i in idx_by_road])
        for pi, key in enumerate(sorted(idx_by_road.keys())):
            road, cell, depths, velocities, arrival, duration, risk, _ = idx_by_road[key]
            ml_correction = corrections[pi]
            corrected = round(_clamp_depth(max(depths.values()) + ml_correction), 1)
            corrected_risk = self.classifier.classify(corrected)
            confidence = self.ml.confidence_for(road, cell, nowcast, self.storage)
            predictions[key] = {
                "road_id": road["road_id"],
                "road_name": road["name"],
                "highway": road.get("highway", "unknown"),
                "lat": round(road["lat"], 6),
                "lon": round(road["lon"], 6),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "current_depth_cm": round(depths[0], 2),
                "depth_15min": round(depths[15], 2),
                "depth_30min": round(depths[30], 2),
                "depth_45min": round(depths[45], 2),
                "depth_60min": round(depths[60], 2),
                "depth_90min": round(depths[90], 2),
                "depth_120min": round(depths[120], 2),
                "depth_150min": round(depths[150], 2),
                "depth_180min": round(depths[180], 2),
                "arrival_time_min": arrival,
                "max_depth_cm": corrected,
                "duration_min": duration,
                "velocity_ms": round(velocities[180], 3),
                "risk": corrected_risk.value,
                "confidence": confidence.value,
                "model_version": "0.1.0",
                "forecast_minutes": 0,
                "depth_curve": {str(s): round(depths[s], 2) for s in self.steps},
            }
        return predictions

    def _index_roads_to_cells(self):
        coords_deg = np.array([[r["lat"], r["lon"]] for r in self.roads])
        if len(coords_deg) == 0:
            return
        dist, idx = self.cell_tree.query(coords_deg)
        for road, ci in zip(self.roads, idx):
            self.road_cell_map[road["road_id"]] = self.cell_ids[int(ci)]

    def _index_roads_to_drains(self):
        if not self.drainage_edges:
            return
        edge_mids = []
        for e in self.drainage_edges:
            edge_mids.append(((e["lat_from"] + e["lat_to"]) / 2.0, (e["lon_from"] + e["lon_to"]) / 2.0))
        tree = cKDTree(np.array(edge_mids))
        edge_ids = [e["edge_id"] for e in self.drainage_edges]
        coords_deg = np.array([[r["lat"], r["lon"]] for r in self.roads])
        if len(coords_deg) == 0:
            return
        dist, idx = tree.query(coords_deg)
        for road, di, d in zip(self.roads, idx, dist):
            self.road_drain_edge[road["road_id"]] = (edge_ids[int(di)], float(d))

    def _nearest_cell(self, lat, lon):
        _, idx = self.cell_tree.query([lat, lon])
        return self.terrain[int(idx)]

    def _compute_hotspots(self, depth_cm_by_cell: Dict[str, float]) -> List[dict]:
        hotspots = []
        for cid, depth in depth_cm_by_cell.items():
            if depth < 10:
                continue
            cell = next((c for c in self.terrain if c["cell_id"] == cid), None)
            if cell is None:
                continue
            nearby_name = self._nearby_place_name(cell["lat"], cell["lon"])
            hotspots.append({
                "lat": cell["lat"],
                "lon": cell["lon"],
                "area_name": nearby_name,
                "depth_cm": round(depth, 1),
                "severity": self.classifier.classify(depth).value,
                "arrival_minutes": self._cell_arrival(cid),
                "road_id": "",
                "road_name": "",
            })
        hotspots.sort(key=lambda h: (_SEV_ORDER.get(Severity(h["severity"]), 0), h["depth_cm"]), reverse=True)
        ranked = []
        for i, h in enumerate(hotspots[:12]):
            h["rank"] = i + 1
            ranked.append(h)
        return ranked

    def _cell_arrival(self, cid: str) -> Optional[float]:
        for step in self.steps:
            if self._surface_snapshots.get(step, {}).get(cid, {}).get("depth_cm", 0) >= 5:
                return step
        return None

    def _nearby_place_name(self, lat, lon):
        places = {
            "Velachery": (13.050, 80.220), "Adyar": (13.006, 80.257), "T Nagar": (13.041, 80.234),
            "Central": (13.083, 80.270), "Marina": (13.050, 80.283), "Chetpet": (13.074, 80.244),
            "Nungambakkam": (13.059, 80.242), "Airport": (13.006, 80.170), "Mylapore": (13.035, 80.269),
            "Royapettah": (13.054, 80.261), "Guindy": (13.010, 80.220), "Kodambakkam": (13.047, 80.227),
        }
        best, best_d = places, 1e9
        for name, (plat, plon) in places.items():
            d = haversine_m(lat, lon, plat, plon)
            if d < best_d:
                best_d = d
                best = name
        return best

    # ------------------------------------------------------------------
    def start_simulation(self, scenario: dict) -> dict:
        """Run the flood engine under a manual override scenario."""
        self.sim_scenario = scenario
        override = float(scenario.get("rainfall_mm_hr", 60.0))
        blockage = float(scenario.get("blockage_percent", 0.0))
        result = self.run(override_rainfall=override, blockage_percent=blockage)
        self.sim_scenario = None
        return {**result, "scenario": scenario}

    def simulation_status(self) -> dict:
        return {
            "is_running": self.sim_scenario is not None,
            "scenario": self.sim_scenario,
            "last_run": self.last_run,
        }

    def stop_simulation(self) -> dict:
        self.sim_scenario = None
        return {"status": "stopped"}

    # ------------------------------------------------------------------
    def drainage_status(self) -> dict:
        total_edges = len(self.drainage_edges)
        overloaded = [e for e in self.drainage_edges if e.get("blockage_percent", 0) > 25]
        critical = [e for e in overloaded if e.get("blockage_percent", 0) > 50]
        avg_util = 0.0
        if total_edges:
            caps = [e["capacity_m3s"] for e in self.drainage_edges if e.get("capacity_m3s", 0) > 0]
            avg_util = min(100.0, sum(caps) / max(1, len(caps)) / 3.0 * 160.0) if caps else 0.0
        return {
            "total_nodes": len(self.drainage_nodes),
            "overloaded_nodes": len(overloaded),
            "total_edges": total_edges,
            "critical_pipes": len(critical),
            "average_utilization": round(avg_util, 1),
            "estimated_blockage": round(mean_blockage(self.drainage_edges), 1),
        }


def _clamp_depth(v: float) -> float:
    return max(0.0, v)


def mean_blockage(edges):
    if not edges:
        return 0.0
    return sum(float(e.get("blockage_percent", 0)) for e in edges) / len(edges)


engine = FloodEngine()