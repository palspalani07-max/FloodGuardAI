"""Storage adapters.

PostGISStorage is used when DATABASE_URL is provided; otherwise the system runs
on InMemoryStorage (Geopandas/DataFrames in memory). The interface keeps the
flood engine decoupled from the storage backend.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class StorageAdapter(ABC):
    @abstractmethod
    def load_roads(self) -> List[dict]: ...

    @abstractmethod
    def load_drainage_nodes(self) -> List[dict]: ...

    @abstractmethod
    def load_drainage_edges(self) -> List[dict]: ...

    @abstractmethod
    def load_terrain_cells(self) -> List[dict]: ...

    @abstractmethod
    def save_flood_predictions(self, predictions: List[dict]): ...

    @abstractmethod
    def get_flood_predictions(self, forecast_minutes: Optional[int] = None) -> List[dict]: ...

    @abstractmethod
    def save_alerts(self, alerts: List[dict]): ...

    @abstractmethod
    def get_active_alerts(self) -> List[dict]: ...

    @abstractmethod
    def save_weather(self, data: dict): ...

    @abstractmethod
    def get_weather(self) -> Optional[dict]: ...

    @abstractmethod
    def health(self) -> dict: ...


def create_storage(database_url: Optional[str] = None):
    if database_url:
        try:
            from .postgis import PostGISStorage
            return PostGISStorage(database_url)
        except Exception as e:
            from ...logging_conf import log
            log.warning(f"PostGIS unavailable ({e}); falling back to InMemoryStorage")
    from .in_memory import InMemoryStorage
    return InMemoryStorage()