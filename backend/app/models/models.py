from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    SAFE = "SAFE"
    MINOR = "MINOR"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RoadStatus(str, Enum):
    NORMAL = "NORMAL"
    HIGH_RISK = "HIGH_RISK"
    FLOOD_IMPACTED = "FLOOD_IMPACTED"
    CLOSED = "CLOSED"


class RoutingMode(str, Enum):
    NORMAL = "NORMAL"
    EMERGENCY = "EMERGENCY"
    PUBLIC_TRANSPORT = "PUBLIC_TRANSPORT"


class ProviderName(str, Enum):
    OPEN_METEO = "OPEN_METEO"
    NASA_GPM = "NASA_GPM"
    GOOGLE_FLOOD = "GOOGLE_FLOOD"
    RADAR = "RADAR"
    DATABASE = "DATABASE"
    REDIS = "REDIS"
    FLOOD_ENGINE = "FLOOD_ENGINE"
    ROUTING = "ROUTING"


class Point(BaseModel):
    lat: float
    lon: float


class WeatherData(BaseModel):
    temperature_c: float = 0.0
    wind_speed_kmh: float = 0.0
    wind_direction_deg: float = 0.0
    precipitation_mm: float = 0.0
    humidity_percent: float = 0.0
    conditions: str = "unknown"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "unknown"


class WeatherForecast(BaseModel):
    hourly_times: list[str] = []
    hourly_precipitation: list[float] = []
    hourly_temperature: list[float] = []
    hourly_wind_speed: list[float] = []
    hourly_wind_direction: list[float] = []
    hourly_probability: list[float] = []
    source: str = "unknown"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RainfallCell(BaseModel):
    cell_id: str
    lat: float
    lon: float
    rainfall_mm_hr: float
    timestamp: datetime
    source: str = "unknown"
    confidence: Confidence = Confidence.MEDIUM
    forecast_minutes: int = 0


class TerrainCell(BaseModel):
    cell_id: str
    lat: float
    lon: float
    elevation_m: float
    slope: float = 0.0
    flow_direction: int = 0
    imperviousness: float = 0.5
    land_cover: str = "unknown"
    water_depth_cm: float = 0.0


class DrainageNode(BaseModel):
    node_id: str
    lat: float
    lon: float
    node_type: str = "manhole"
    elevation_m: float = 0.0
    storage_capacity: float = 0.0
    inlet_capacity: float = 1.0
    current_water_level: float = 0.0
    is_overloaded: bool = False


class DrainageEdge(BaseModel):
    edge_id: str
    from_node: str
    to_node: str
    lat_from: float = 0.0
    lon_from: float = 0.0
    lat_to: float = 0.0
    lon_to: float = 0.0
    length_m: float = 100.0
    diameter_m: float = 0.6
    slope: float = 0.001
    roughness: float = 0.013
    capacity_m3s: float = 0.0
    blockage_percent: float = 0.0
    current_flow_m3s: float = 0.0
    is_overloaded: bool = False


class FloodPrediction(BaseModel):
    road_id: str
    road_name: str
    lat: float
    lon: float
    timestamp: datetime
    current_depth_cm: float = 0.0
    depth_15min: float = 0.0
    depth_30min: float = 0.0
    depth_45min: float = 0.0
    depth_60min: float = 0.0
    depth_90min: float = 0.0
    depth_120min: float = 0.0
    depth_150min: float = 0.0
    depth_180min: float = 0.0
    arrival_time_min: Optional[float] = None
    max_depth_cm: float = 0.0
    duration_min: float = 0.0
    velocity_ms: float = 0.0
    risk: Severity = Severity.SAFE
    confidence: Confidence = Confidence.MEDIUM
    model_version: str = "0.1.0"


class FloodHotspot(BaseModel):
    rank: int
    lat: float
    lon: float
    area_name: str
    depth_cm: float
    severity: Severity
    arrival_minutes: Optional[float] = None
    road_id: str = ""
    road_name: str = ""


class Alert(BaseModel):
    alert_id: str
    lat: float
    lon: float
    severity: Severity
    message: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: str = "active"
    road_id: Optional[str] = None


class RouteSegment(BaseModel):
    lat: float
    lon: float
    road_id: str = ""
    road_name: str = ""
    depth_cm: float = 0.0
    flood_risk: Severity = Severity.SAFE


class RouteResult(BaseModel):
    mode: RoutingMode
    distance_km: float
    estimated_minutes: float
    max_depth_cm: float
    risk: Severity
    avoided_roads: int
    additional_minutes: float = 0.0
    route: list[RouteSegment] = []
    diverted: bool = False
    diversion_reason: str = ""


class DrainageStatus(BaseModel):
    total_nodes: int = 0
    overloaded_nodes: int = 0
    total_edges: int = 0
    critical_pipes: int = 0
    average_utilization: float = 0.0
    estimated_blockage: float = 0.0


class SimulationScenario(BaseModel):
    name: str = "HEAVY"
    rainfall_mm_hr: float = 60.0
    duration_min: int = 180
    blockage_percent: float = 0.0


class ProviderStatus(BaseModel):
    name: ProviderName
    status: str = "unavailable"
    last_updated: Optional[datetime] = None
    data_age_seconds: Optional[float] = None
    data_type: str = "SIMULATED"


class SystemStatus(BaseModel):
    version: str = "0.1.0"
    city: str = "Chennai"
    is_live: bool = False
    last_ingestion: Optional[datetime] = None
    last_forecast: Optional[datetime] = None
    last_simulation: Optional[datetime] = None
    providers: list[ProviderStatus] = []
    data_freshness_seconds: Optional[float] = None


class StreetDetail(BaseModel):
    road_id: str
    road_name: str
    current_depth_cm: float
    depth_forecast: dict[str, float] = {}
    max_depth_cm: float = 0.0
    arrival_time_min: Optional[float] = None
    duration_min: float = 0.0
    velocity_ms: float = 0.0
    risk: Severity = Severity.SAFE
    confidence: Confidence = Confidence.MEDIUM
    drain_utilization: float = 0.0
    nearby_drain_node: Optional[str] = None
    status: RoadStatus = RoadStatus.NORMAL


class WeatherFloodInsight(BaseModel):
    current_weather: WeatherData
    cumulative_rain_mm: float = 0.0
    flood_risk: Severity = Severity.SAFE
    expected_flood_increase_cm: float = 0.0
    expected_increase_minutes: int = 60
