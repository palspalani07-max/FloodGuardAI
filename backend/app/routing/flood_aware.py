"""Flood-aware routing provider.

Uses the real OSM road network (loaded from the GeoJSON fetched by scripts/fetch_osm_data.py)
and a NetworkX graph. Dijkstra-style routing with flood penalty:
    total_cost = travel_time + lambda * flood_penalty
Lambda depends on routing mode (emergency = highest flood penalty).
"""
import math
import networkx as nx
from typing import Dict, List, Optional, Set

from ..config import settings
from ..logging_conf import log
from ..models import RouteResult, RouteSegment, RoutingMode, Severity
from ..geospatial.earth import haversine_m
from ..db.adapters import StorageAdapter, create_storage
from ..simulation.risk.classifier import FloodClassifier, Severity as FloodSeverity

_MODE_LAMBDA = {
    RoutingMode.NORMAL: 30.0,
    RoutingMode.EMERGENCY: 150.0,
    RoutingMode.PUBLIC_TRANSPORT: 50.0,
}

_SEV_PENALTY = {
    "SAFE": 0.0, "MINOR": 1.0, "HIGH": 5.0, "SEVERE": 25.0, "CRITICAL": 200.0
}


class FloodAwareProvider:
    name = "flood_aware"
    SPEED_KMH = {"trunk": 60, "primary": 50, "secondary": 40, "tertiary": 30, "residential": 25, "unclassified": 25}

    def __init__(self, storage: Optional[StorageAdapter] = None):
        self.storage = storage or create_storage(settings.database_url)
        self.roads = self.storage.load_roads()
        self.graph = nx.DiGraph()
        self.classifier = FloodClassifier()
        self._build_graph()
        self.flood_predictions: Dict[str, dict] = {}
        self._initialised = True
        log.info(f"FloodAwareProvider ready: {len(self.roads)} roads, {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")

    def _build_graph(self):
        road_by_id = {}
        for road in self.roads:
            gid = road["road_id"]
            road_by_id[gid] = road
            geom = road.get("geometry", {})
            coords = geom.get("coordinates", [])
            if len(coords) < 2:
                continue
            hw = road.get("highway", "tertiary")
            speed = self.SPEED_KMH.get(hw, 30)
            length = road.get("length_m", 0) or 1
            for ci in range(len(coords) - 1):
                p1, p2 = coords[ci], coords[ci + 1]
                n1 = f"{p1[0]:.6f}_{p1[1]:.6f}"
                n2 = f"{p2[0]:.6f}_{p2[1]:.6f}"
                d_m = haversine_m(p1[1], p1[0], p2[1], p2[0])
                travel_min = (d_m / 1000.0 / speed) * 60.0
                if not self.graph.has_edge(n1, n2):
                    self.graph.add_edge(n1, n2, weight=travel_min, road_id=gid, length_m=d_m)
                    self.graph.add_edge(n2, n1, weight=travel_min, road_id=gid, length_m=d_m)

    def _set_flood_penalties(self, mode: RoutingMode, predictions_by_road: Dict[str, dict],
                             avoid_road_ids: Optional[Set[str]] = None):
        lam = _MODE_LAMBDA.get(mode, 30.0)
        for u, v, data in self.graph.edges(data=True):
            road_id = data.get("road_id", "")
            pred = predictions_by_road.get(road_id, {})
            if avoid_road_ids and road_id in avoid_road_ids:
                data["adjusted_weight"] = 1e6
                continue
            base = data["weight"]
            severity = pred.get("risk", "SAFE")
            pen = _SEV_PENALTY.get(severity, 0) + pred.get("max_depth_cm", 0) * 0.1
            data["adjusted_weight"] = base + lam * pen

    def get_route(self, origin_lat, origin_lon, dest_lat, dest_lon,
                  avoid_road_ids=None, mode=RoutingMode.NORMAL,
                  predictions_by_road=None) -> RouteResult:
        predictions_by_road = predictions_by_road or self.flood_predictions
        self._set_flood_penalties(mode, predictions_by_road, avoid_road_ids)
        origin = f"{origin_lon:.6f}_{origin_lat:.6f}"
        dest = f"{dest_lon:.6f}_{dest_lat:.6f}"
        nearest_origin = self._nearest_node(origin_lat, origin_lon)
        nearest_dest = self._nearest_node(dest_lat, dest_lon)
        if not nearest_origin or not nearest_dest:
            return RouteResult(mode=mode.value, distance_km=0, estimated_minutes=0, max_depth_cm=0,
                               risk=FloodSeverity.SAFE, avoided_roads=0)
        try:
            path = nx.dijkstra_path(self.graph, nearest_origin, nearest_dest, weight="adjusted_weight")
            segment_road_ids = set()
            road_set = set(avoid_road_ids or [])
            avoided = set()
            segments = []
            total_dist = 0.0
            max_depth = 0.0
            for i in range(len(path) - 1):
                data = self.graph.get_edge_data(path[i], path[i + 1])
                road_id = data.get("road_id", "")
                segment_road_ids.add(road_id)
                lon, lat = map(float, path[i].split("_"))
                pred = predictions_by_road.get(road_id, {})
                depth = pred.get("max_depth_cm", 0.0)
                severity = self.classifier.classify(depth)
                if severity.value in ("HIGH", "SEVERE", "CRITICAL"):
                    avoided.add(road_id)
                segments.append(RouteSegment(lat=lat, lon=lon, road_id=road_id,
                                             depth_cm=depth, flood_risk=severity))
                total_dist += data.get("length_m", 0)
                max_depth = max(max_depth, depth)
            total_minutes = sum(data.get("weight", 0) for u, v in
                                ((path[i], path[i + 1]) for i in range(len(path) - 1))
                                if (data := self.graph.get_edge_data(u, v)))
            risk = self.classifier.classify(max_depth)
            diverted = len(avoided) > 0
            diversion_reason = f"Automatically diverted due to predicted flooding" if diverted else ""
            return RouteResult(
                mode=mode.value,
                distance_km=round(total_dist / 1000, 2),
                estimated_minutes=round(total_minutes, 1),
                max_depth_cm=round(max_depth, 1),
                risk=risk,
                avoided_roads=len(avoided),
                route=segments,
                diverted=diverted,
                diversion_reason=diversion_reason,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            log.debug(f"Route not found: {e}")
            return RouteResult(mode=mode.value, distance_km=0, estimated_minutes=0, max_depth_cm=0,
                               risk=FloodSeverity.SAFE, avoided_roads=0)

    def _nearest_node(self, lat, lon):
        target = f"{lon:.6f}_{lat:.6f}"
        if target in self.graph:
            return target
        best, best_d = None, 1e18
        for n in self.graph.nodes:
            try:
                p_lon, p_lat = map(float, n.split("_"))
            except ValueError:
                continue
            d = (lat - p_lat) ** 2 + (lon - p_lon) ** 2
            if d < best_d:
                best_d = d
                best = n
        return best if best_d < 0.02 ** 2 else None

    def health(self) -> dict:
        return {"name": "flood_aware", "roads": len(self.roads), "nodes": len(self.graph.nodes),
                "edges": len(self.graph.edges)}


provider = FloodAwareProvider()