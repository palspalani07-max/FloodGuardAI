"""Routing provider interface."""
from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import RouteResult, RouteSegment


class BaseRoutingProvider(ABC):
    name = "base"

    @abstractmethod
    def get_route(self, origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float,
                  avoid_road_ids: Optional[set] = None) -> RouteResult: ...

    @abstractmethod
    def health(self) -> dict: ...