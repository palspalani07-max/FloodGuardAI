from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    app_name: str = "FloodGuard AI"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    city_name: str = "Chennai"
    city_lat: float = 13.0827
    city_lon: float = 80.2707
    study_area_south: float = 12.99
    study_area_north: float = 13.17
    study_area_west: float = 80.15
    study_area_east: float = 80.32

    open_meteo_api_key: str = ""
    google_flood_api_key: str = ""
    nasa_earthdata_token: str = ""
    osrm_url: str = "http://router.project-osrm.org"
    database_url: Optional[str] = None
    redis_url: Optional[str] = None

    grid_resolution_m: float = 500.0
    forecast_steps: list[int] = [0, 15, 30, 45, 60, 90, 120, 150, 180]

    runoff_coefficients: dict = {
        "road": 0.90,
        "concrete": 0.95,
        "building": 0.95,
        "grass": 0.25,
        "soil": 0.35,
        "vegetation": 0.20,
    }

    flood_levels: dict = {
        "level_0_safe": 5,
        "level_1_minor": 15,
        "level_2_high": 30,
        "level_3_severe": 50,
        "level_4_critical": 999,
    }

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
