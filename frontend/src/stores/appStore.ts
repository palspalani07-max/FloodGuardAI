import { create } from "zustand";
import type {
  ActiveAlert, DrainageStatus, FloodPrediction, GridCell, Hotspot,
  RainfallNowcast, RouteResult, SimulationScenario, SystemStatus, ViewMode, Weather,
  LayerKey, GeoCollection,
} from "../types";

// Chennai study-area center (also used as default map center)
export const CHENNAI = { lat: 13.0481, lon: 80.2604, zoom: 11.4 };

interface AppState {
  // data
  weather: Weather | null;
  nowcast: RainfallNowcast | null;
  floodGrid: GridCell[];
  rainGrid: GridCell[];
  windGrid: GridCell[];
  hotspots: Hotspot[];
  alerts: ActiveAlert[];
  drainage: DrainageStatus | null;
  system: SystemStatus | null;
  roads: GeoCollection | null;
  selectedMinute: number;
  activeLayers: LayerKey[];
  // routing
  route: RouteResult | null;
  routeLoading: boolean;
  // simulation
  scenario: SimulationScenario | null;
  simulationRunning: boolean;
  // location (user-provided for alerting)
  userLocation: { lat: number; lon: number } | null;
  // ui
  view: ViewMode;
  selectedRoad: FloodPrediction | null;
  selectedHotspot: Hotspot | null;
  lastUpdated: string;
  loading: boolean;

  set: (partial: Partial<AppState>) => void;
  setSelectedMinute: (m: number) => void;
  toggleLayer: (k: LayerKey) => void;
  setRoute: (r: RouteResult | null) => void;
  setScenario: (s: SimulationScenario | null) => void;
  setView: (v: ViewMode) => void;
  selectRoad: (r: FloodPrediction | null) => void;
  selectHotspot: (h: Hotspot | null) => void;
}

export const useStore = create<AppState>((set) => ({
  weather: null,
  nowcast: null,
  floodGrid: [],
  rainGrid: [],
  windGrid: [],
  hotspots: [],
  alerts: [],
  drainage: null,
  system: null,
  roads: null,
  selectedMinute: 0,
  activeLayers: ["roads", "flood"],
  route: null,
  routeLoading: false,
  scenario: null,
  simulationRunning: false,
  userLocation: null,
  view: "command",
  selectedRoad: null,
  selectedHotspot: null,
  lastUpdated: "",
  loading: true,

  set: (partial) => set(partial),
  setSelectedMinute: (m) => set({ selectedMinute: m }),
  toggleLayer: (k) =>
    set((s) => ({
      activeLayers: s.activeLayers.includes(k)
        ? s.activeLayers.filter((x) => x !== k)
        : [...s.activeLayers, k],
    })),
  setRoute: (r) => set({ route: r }),
  setScenario: (s) => set({ scenario: s }),
  setView: (v) => set({ view: v }),
  selectRoad: (r) => set({ selectedRoad: r, selectedHotspot: null }),
  selectHotspot: (h) => set({ selectedHotspot: h, selectedRoad: null }),
}));