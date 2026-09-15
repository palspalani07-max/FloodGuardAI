"""RadarProvider abstraction.

The interface supports an authorized Doppler Weather Radar source (e.g. an IMD
radar feed) in the future. For the prototype, the implementation wraps available
precipitation sources (Open-Meteo / NASA GPM). We never fabricate access to a
radar API that is not actually available.
"""
from abc import abstractmethod
from datetime import datetime, timezone
from typing import List, Optional

from ..base import BaseProvider
from ...models import RainfallCell


class RadarProvider(BaseProvider):
    name = "radar"
    requires_auth = True
    source_label = "RADAR (not configured)"

    def __init__(self, settings):
        super().__init__(settings)
        # Radar access is not available in the prototype environment.
        self.available = False

    def get_latest_rainfall(self, lat: float, lon: float) -> Optional[RainfallCell]:
        return None

    def get_rainfall_forecast(self, lat: float, lon: float) -> List[RainfallCell]:
        return []

    def get_rainfall_grid(self, bbox: tuple) -> List[RainfallCell]:
        return []

    def get_timestamp(self) -> Optional[datetime]:
        return None