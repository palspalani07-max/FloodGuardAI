export type Severity = "SAFE" | "MINOR" | "HIGH" | "SEVERE" | "CRITICAL";
export type Confidence = "HIGH" | "MEDIUM" | "LOW";
export type RoutingMode = "NORMAL" | "EMERGENCY" | "PUBLIC_TRANSPORT";

export interface Weather {
  temperature_c: number;
  wind_speed_kmh: number;
  wind_direction_deg: number;
  precipitation_mm: number;
  humidity_percent: number;
  conditions: string;
  timestamp: string;
  source: string;
}

export interface RainfallNowcast {
  timesteps: number[];
  rainfall_mm_hr: Record<string, number>;
  confidence: string;
  source: string;
}

export interface GridCell {
  lat: number;
  lon: number;
  depth_cm?: number;
  risk?: Severity;
  rainfall_mm_hr?: number;
  u_ms?: number;
  v_ms?: number;
}

export interface FloodPrediction {
  road_id: string;
  road_name: string;
  highway?: string;
  lat: number;
  lon: number;
  timestamp: string;
  current_depth_cm: number;
  depth_15min: number;
  depth_30min: number;
  depth_45min: number;
  depth_60min: number;
  depth_90min: number;
  depth_120min: number;
  depth_150min: number;
  depth_180min: number;
  arrival_time_min: number | null;
  max_depth_cm: number;
  duration_min: number;
  velocity_ms: number;
  risk: Severity;
  confidence: Confidence;
  depth_curve: Record<string, number>;
}

export interface Hotspot {
  rank: number;
  lat: number;
  lon: number;
  area_name: string;
  depth_cm: number;
  severity: Severity;
  arrival_minutes: number | null;
  road_id?: string;
  road_name?: string;
}

export interface ActiveAlert {
  alert_id: string;
  lat: number;
  lon: number;
  severity: Severity;
  message: string;
  created_at: string;
  expires_at: string | null;
  status: string;
  road_id?: string;
  road_name?: string;
  area_name?: string;
  max_depth_cm?: number;
  arrival_time_min?: number;
  distance_m?: number;
}

export interface RouteSegment {
  lat: number;
  lon: number;
  road_id: string;
  road_name: string;
  depth_cm: number;
  flood_risk: Severity;
}

export interface RouteResult {
  mode: RoutingMode;
  distance_km: number;
  estimated_minutes: number;
  max_depth_cm: number;
  risk: Severity;
  avoided_roads: number;
  additional_minutes: number;
  route: RouteSegment[];
  diverted: boolean;
  diversion_reason: string;
}

export interface DrainageStatus {
  total_nodes: number;
  overloaded_nodes: number;
  total_edges: number;
  critical_pipes: number;
  average_utilization: number;
  estimated_blockage: number;
}

export interface ProviderStatus {
  name: string;
  status: string;
  last_updated: string | null;
  data_age_seconds: number | null;
  data_type: string;
}

export interface SystemStatus {
  version: string;
  city: string;
  is_live: boolean;
  last_ingestion: string | null;
  last_forecast: string | null;
  providers: ProviderStatus[];
  data_freshness_seconds: number | null;
  db_health: Record<string, unknown>;
}

export interface SimulationScenario {
  name: string;
  rainfall_mm_hr: number;
  duration_min: number;
  blockage_percent: number;
  is_active?: boolean;
  running?: boolean;
}

export interface GeoFeature {
  type: "Feature";
  properties: Record<string, unknown>;
  geometry: { type: string; coordinates: unknown };
}

export interface GeoCollection {
  type: "FeatureCollection";
  features: GeoFeature[];
}

export type LayerKey = "rain" | "wind" | "temperature" | "flood" | "drainage" | "roads" | "hotspots" | "routes" | "alerts";

export type ViewMode = "command" | "public";