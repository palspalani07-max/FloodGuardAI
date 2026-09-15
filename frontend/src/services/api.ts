import type {
  ActiveAlert, DrainageStatus, FloodPrediction, GeoCollection, GridCell,
  Hotspot, RainfallNowcast, RouteResult, RoutingMode, SimulationScenario,
  SystemStatus, Weather,
} from "../types";

const BASE = "/api";

async function request<T>(path: string, options: RequestInit = {}, timeoutMs = 30000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),
  systemStatus: () => request<SystemStatus>("/system/status"),
  weatherCurrent: () => request<Weather>("/weather/current"),
  rainfallNowcast: () => request<RainfallNowcast>("/rainfall/nowcast"),
  floodForecast: () => request<FloodPrediction[]>("/flood/forecast"),
  floodGrid: (minutes: number) => request<GridCell[]>(`/flood/grid?minutes=${minutes}`),
  rainfallGrid: () => request<GridCell[]>("/rainfall/grid"),
  windGrid: () => request<GridCell[]>("/wind/grid"),
  hotspots: (minutes = 180) => request<Hotspot[]>(`/flood/hotspots?minutes=${minutes}`),
  street: (roadId: string) => request<FloodPrediction>(`/flood/street/${roadId}`),
  roadsGeoJson: (major = false) => request<GeoCollection>(`/roads/geojson?major=${major}`),
  drainageStatus: () => request<DrainageStatus>("/drainage/status"),
  drainageNodes: () => request<unknown[]>(`/drainage/nodes`),
  drainageEdges: () => request<unknown[]>(`/drainage/edges`),
  alerts: () => request<ActiveAlert[]>("/alerts"),
  locationAlerts: (lat: number, lon: number) =>
    request<ActiveAlert[]>(`/alerts/user-location?lat=${lat}&lon=${lon}`),
  safeRoute: (originLat: number, originLon: number, destLat: number, destLon: number,
    mode: RoutingMode = "NORMAL", forecastMinutes = 60, useOsrm = false) =>
    request<RouteResult>(
      `/route/safe?origin_lat=${originLat}&origin_lon=${originLon}&dest_lat=${destLat}` +
      `&dest_lon=${destLon}&mode=${mode}&forecast_minutes=${forecastMinutes}&use_osrm=${useOsrm}`,
    ),
  simulationStart: (scenario: SimulationScenario) =>
    request<{ status: string; scenario: SimulationScenario }>("/simulation/start", {
      method: "POST", body: JSON.stringify(scenario),
    }),
  simulationStop: () =>
    request<{ status: string }>("/simulation/stop", { method: "POST" }),
};