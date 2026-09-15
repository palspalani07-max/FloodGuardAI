"""Surface-Drainage coupling.

Each drainage inlet connects to surface cells and water exchanges both ways:
    Surface -> Drain  (capture)
    Drain -> Surface   (surcharge)
"""
from dataclasses import dataclass, field
from typing import Dict, List

from ...logging_conf import log


@dataclass
class CouplingResult:
    inlet_capture_m3: Dict[str, float] = field(default_factory=dict)
    pipe_flow_m3s: Dict[str, float] = field(default_factory=dict)
    remaining_surface_water_m3: Dict[str, float] = field(default_factory=dict)
    surcharge_volume_m3: Dict[str, float] = field(default_factory=dict)
    step: int = 0


class SurfaceDrainageCoupling:
    def __init__(self, capture_rate: float = 0.4, inlet_capacity_m3s: float = 2.0):
        self.capture_rate = capture_rate
        self.inlet_capacity_m3s = inlet_capacity_m3s

    def build_inlet_mapping(self, terrain_cells: List[dict], drainage_nodes: List[dict]) -> Dict[str, str]:
        mapping = {}
        for cell in terrain_cells:
            best_node, best_d = None, 1e9
            for node in drainage_nodes:
                d = (cell["lat"] - node["lat"]) ** 2 + (cell["lon"] - node["lon"]) ** 2
                if d < best_d:
                    best_d = d
                    best_node = node
            if best_node is not None and best_d < 0.5 ** 2:
                mapping[cell["cell_id"]] = best_node["node_id"]
        return mapping

    def couple(self, surface_snapshot: Dict[str, dict], drainage: dict, dt_min: float = 15.0,
               inlet_mapping: Dict[str, str] = None) -> CouplingResult:
        result = CouplingResult(step=0)
        inlet_mapping = inlet_mapping or {}
        dt_sec = dt_min * 60.0
        # nodes -> set of attached surface cells (for capacity sharing)
        node_cells: Dict[str, List[str]] = {}
        for cell_id, node_id in inlet_mapping.items():
            node_cells.setdefault(node_id, []).append(cell_id)
        # surface -> drainage capture, limited by inlet capacity shared across cells
        for cell_id, state in surface_snapshot.items():
            depth = state["depth_cm"]
            if depth <= 0.5:
                continue
            node_id = inlet_mapping.get(cell_id)
            if node_id is None:
                continue
            available_m3 = (depth / 100.0) * (500.0 ** 2)
            shared_cap = self.inlet_capacity_m3s * dt_sec / max(1, len(node_cells.get(node_id, [cell_id])))
            capture_m3 = min(available_m3, shared_cap)
            result.inlet_capture_m3[cell_id] = round(capture_m3, 3)
        # drain -> surface surcharge (from overloaded pipes)
        for node_id, volume in (drainage or {}).get("surcharge_m3", {}).items():
            for cell_id, mapped_node in inlet_mapping.items():
                if mapped_node == node_id:
                    result.surcharge_volume_m3[cell_id] = round(volume, 3)
        result.pipe_flow_m3s = (drainage or {}).get("edge_flow_m3s", {})
        return result