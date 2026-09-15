"""Drainage network hydraulic engine.

Uses the Manning equation for pipe capacity:
    Q = (1/n) * A * R^(2/3) * S^(1/2)
For circular pipes: A = pi*D^2/4, R = D/4.
Blockage reduces effective capacity: effective_capacity = base * (1 - blockage).
If inflow > effective capacity the node is marked OVERLOADED and surcharge is
generated which returns water to the surface model.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from ...logging_conf import log


@dataclass
class DrainageGraph:
    nodes: Dict[str, dict] = field(default_factory=dict)
    edges: Dict[str, dict] = field(default_factory=dict)


class ManningCalculator:
    @staticmethod
    def pipe_capacity(diameter_m: float, slope: float, roughness: float = 0.013) -> float:
        if diameter_m <= 0 or slope <= 0:
            return 0.0
        area = 3.141592653589793 * (diameter_m / 2.0) ** 2
        hydraulic_radius = diameter_m / 4.0
        capacity = (1.0 / roughness) * area * (hydraulic_radius ** (2.0 / 3.0)) * (slope ** 0.5)
        return capacity

    @staticmethod
    def effective_capacity(base_capacity: float, blockage_percent: float) -> float:
        b = max(0.0, min(100.0, blockage_percent)) / 100.0
        return base_capacity * (1.0 - b)


class DrainageEngine:
    def __init__(self, manning: ManningCalculator = None):
        self.manning = manning or ManningCalculator()
        self.graph = DrainageGraph()
        self.node_flow: Dict[str, float] = {}
        self.edge_flow: Dict[str, float] = {}
        self.surcharge: Dict[str, float] = {}
        self.overloaded_nodes = set()
        self.overloaded_edges = set()

    def load(self, nodes: List[dict], edges: List[dict]):
        self.graph = DrainageGraph()
        for n in nodes:
            self.graph.nodes[n["node_id"]] = dict(n)
        for e in edges:
            eff_cap = self.manning.effective_capacity(e["capacity_m3s"], e["blockage_percent"])
            self.graph.edges[e["edge_id"]] = {**e, "effective_capacity_m3s": eff_cap}
        self.reset()

    def reset(self):
        self.node_flow = {nid: 0.0 for nid in self.graph.nodes}
        self.edge_flow = {eid: 0.0 for eid in self.graph.edges}
        self.surcharge = {}
        self.overloaded_nodes = set()
        self.overloaded_edges = set()

    def push_flow(self, node_inlet: Dict[str, float], dt_min: float = 15.0):
        """node_inlet maps drainage node_id -> volume (m3) entering that node."""
        dt_sec = dt_min * 60.0
        if dt_sec <= 0:
            return
        self.reset()
        # route inlet volume directly into the mapped nodes
        for node_id, volume in node_inlet.items():
            if volume <= 0 or node_id not in self.node_flow:
                continue
            self.node_flow[node_id] += volume / dt_sec  # m3/s
        # propagate through edges
        sorted_nodes = sorted(self.graph.nodes.values(), key=lambda n: n["elevation_m"])
        for node in sorted_nodes:
            nid = node["node_id"]
            inflow = self.node_flow.get(nid, 0.0)
            node_cap = node.get("inlet_capacity", 1.0)
            if inflow > node_cap:
                overflow = inflow - node_cap
                self.surcharge[nid] = overflow * dt_sec
                self.overloaded_nodes.add(nid)
                inflow = node_cap
            outflow = inflow
            for eid in self.graph.edges.values():
                if eid["from_node"] != nid:
                    continue
                eff_cap = eid["effective_capacity_m3s"]
                if outflow > eff_cap:
                    self.edge_flow[eid["edge_id"]] = eff_cap
                    self.overloaded_edges.add(eid["edge_id"])
                    self.surcharge[eid.get("to_node", nid)] = self.surcharge.get(eid.get("to_node", nid), 0.0) + (outflow - eff_cap) * dt_sec
                    outflow = 0.0
                else:
                    self.edge_flow[eid["edge_id"]] = outflow
                    if eid.get("to_node") in self.graph.nodes:
                        self.node_flow[eid["to_node"]] += outflow
                    outflow = 0.0
        return self.snapshot()

    def _nearest_node(self, surface_cell_id: str):
        # For prototype, nearest node by elevation priority is replaced by a
        # call into coupling to map inlet - see coupling engine.
        return None

    def set_inlet_mapping(self, mapping: Dict[str, str]):
        self._cell_to_node = mapping

    def nearest_node_for_cell(self, cell_id: str):
        return self._cell_to_node.get(cell_id)

    def snapshot(self) -> dict:
        return {
            "nodes": self.graph.nodes,
            "edges": self.graph.edges,
            "node_flow_m3s": {k: round(v, 4) for k, v in self.node_flow.items()},
            "edge_flow_m3s": {k: round(v, 4) for k, v in self.edge_flow.items()},
            "surcharge_m3": {k: round(v, 3) for k, v in self.surcharge.items()},
            "overloaded_nodes": sorted(self.overloaded_nodes),
            "overloaded_edges": sorted(self.overloaded_edges),
        }