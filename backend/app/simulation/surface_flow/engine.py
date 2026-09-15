"""2D surface water flow model.

For each cell: hydraulic head = elevation + water depth.
Water moves toward neighbouring lower cells. Drainage removes water via inlets.
Surplus from overloaded drains returns as surcharge.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ...logging_conf import log


@dataclass
class SurfaceState:
    cell_id: str
    lat: float
    lon: float
    elevation_m: float
    water_depth_cm: float = 0.0
    inflow_m3: float = 0.0
    outflow_m3: float = 0.0
    surcharge_m3: float = 0.0
    velocity_ms: float = 0.0
    neighbor_drains: List[str] = field(default_factory=list)


class SurfaceFlowEngine:
    def __init__(self, grid_side_m: float = 500.0):
        self.grid_side_m = grid_side_m
        self.col_dims = {}  # cell_id -> (lat_idx, lon_idx)

    def setup_grid(self, terrain_cells: List[dict]):
        self.states = {}
        for cell in terrain_cells:
            st = SurfaceState(
                cell_id=cell["cell_id"],
                lat=cell["lat"],
                lon=cell["lon"],
                elevation_m=cell["elevation_m"],
            )
            self.states[cell["cell_id"]] = st
        # index lat/lon to compute neighbours deterministically
        lats = sorted({c["lat"] for c in terrain_cells})
        lons = sorted({c["lon"] for c in terrain_cells})
        self.lats = lats
        self.lons = lons
        self.lat_index = {v: i for i, v in enumerate(lats)}
        self.lon_index = {v: i for i, v in enumerate(lons)}
        for cell in terrain_cells:
            self.col_dims[cell["cell_id"]] = (self.lat_index[cell["lat"]], self.lon_index[cell["lon"]])

    def neighbours(self, cell_id: str) -> List[str]:
        i, j = self.col_dims[cell_id]
        out = []
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < len(self.lats) and 0 <= nj < len(self.lons):
                nid = f"T_{ni}_{nj}"
                if nid in self.states:
                    out.append(nid)
        return out

    def step(self, runoff_m3: Dict[str, float], dt_min: float = 15.0,
             drainage_removal: Optional[Dict[str, float]] = None):
        """One timestep of surface water routing."""
        drainage_removal = drainage_removal or {}
        dt_sec = dt_min * 60.0
        # 1. add rainfall runoff
        for cell_id, vol in runoff_m3.items():
            if cell_id in self.states:
                self.states[cell_id].inflow_m3 += vol
                self.states[cell_id].water_depth_cm += (vol / (self.grid_side_m ** 2)) * 100.0
        # 2. move water toward the lowest-head neighbour (steepest descent, D8-like)
        cell_ids = list(self.states.keys())
        for cid in cell_ids:
            st = self.states[cid]
            if st.water_depth_cm <= 0.05:
                continue
            nids = self.neighbours(cid)
            if not nids:
                continue
            head = st.elevation_m + st.water_depth_cm / 100.0
            best_nid, best_head = None, head
            for nid in nids:
                nh = self.states[nid].elevation_m + self.states[nid].water_depth_cm / 100.0
                if nh < best_head - 1e-6:
                    best_head = nh
                    best_nid = nid
            if best_nid is None:
                continue
            nst = self.states[best_nid]
            dh_cm = max(0.0, (head - best_head) * 100.0)
            # relax toward equal head: transfer up to 40% of the head difference,
            # and at most 80% of this cell's standing water per timestep.
            flux_cm = min(st.water_depth_cm * 0.8, dh_cm * 0.4)
            if flux_cm <= 0.001:
                continue
            vol = (flux_cm / 100.0) * (self.grid_side_m ** 2)
            st.water_depth_cm -= flux_cm
            nst.water_depth_cm += flux_cm
            st.outflow_m3 += vol
            nst.inflow_m3 += vol
            st.velocity_ms = max(st.velocity_ms, 0.1 + 0.6 * (flux_cm * 100.0 / dt_sec))
        # 3. drainage inlet removal
        for cell_id, removal_m3 in drainage_removal.items():
            if cell_id not in self.states:
                continue
            st = self.states[cell_id]
            depth_cm_removal = (removal_m3 / (self.grid_side_m ** 2)) * 100.0
            st.water_depth_cm = max(0.0, st.water_depth_cm - depth_cm_removal)
        # 4. surcharge return (handled via coupling, inject surcharge volume)
        return self.snapshot()

    def inject_surcharge(self, cell_id: str, volume_m3: float):
        if cell_id in self.states:
            st = self.states[cell_id]
            st.surcharge_m3 += volume_m3
            st.water_depth_cm += (volume_m3 / (self.grid_side_m ** 2)) * 100.0

    def snapshot(self) -> Dict[str, dict]:
        return {
            cid: {
                "cell_id": st.cell_id,
                "lat": st.lat,
                "lon": st.lon,
                "depth_cm": round(st.water_depth_cm, 2),
                "velocity_ms": round(st.velocity_ms, 4),
                "elevation_m": st.elevation_m,
            }
            for cid, st in self.states.items()
        }