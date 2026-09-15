"""Registers and reports the health of all external data providers."""
from typing import Dict, List

from ..config import settings
from ..logging_conf import log
from .openmeteo import OpenMeteoProvider
from .nasa import NASAProvider
from .google_flood import GoogleFloodProvider
from .radar import RadarProvider


class ProviderRegistry:
    def __init__(self, settings=settings):
        self.settings = settings
        self.providers = {
            "open_meteo": OpenMeteoProvider(settings),
            "nasa_gpm": NASAProvider(settings),
            "google_flood": GoogleFloodProvider(settings),
            "radar": RadarProvider(settings),
        }

    def get(self, name: str):
        return self.providers.get(name)

    def status_list(self) -> List[dict]:
        items = self.providers["open_meteo"].status_info()
        out = []
        for name, provider in self.providers.items():
            info = provider.status_info()
            info["data_type"] = provider.status
            out.append(info)
        return out

    def open_meteo(self) -> OpenMeteoProvider:
        return self.providers["open_meteo"]

    def nasa(self) -> NASAProvider:
        return self.providers["nasa_gpm"]

    def google_flood(self) -> GoogleFloodProvider:
        return self.providers["google_flood"]

    def radar(self) -> RadarProvider:
        return self.providers["radar"]


registry = ProviderRegistry()