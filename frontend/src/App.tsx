import { useCallback, useEffect, useRef, useState } from "react";
import RainWebGL from "./webanim/RainWebGL";
import TopBar from "./components/TopBar";
import CommandCenter from "./pages/CommandCenter";
import PublicMode from "./pages/PublicMode";
import { api } from "./services/api";
import { useStore } from "./stores/appStore";

const POLL_MS = 15000;

export default function App() {
  const view = useStore((s) => s.view);
  const selectedMinute = useStore((s) => s.selectedMinute);
  const scenario = useStore((s) => s.scenario);
  const set = useStore((s) => s.set);
  const selectRoad = useStore((s) => s.selectRoad);
  const floodGrid = useStore((s) => s.floodGrid);
  const nowcast = useStore((s) => s.nowcast);
  const simRunning = useStore((s) => s.simulationRunning);
  const [_tick, setTick] = useState(0);
  const scenarioRef = useRef(scenario);

  useEffect(() => { scenarioRef.current = scenario; }, [scenario]);

  const refresh = useCallback(async () => {
    const isSim = scenarioRef.current != null;
    try {
      const [system, weather, nc, hotspots, alerts, drainage, roads, rain, wind] = await Promise.all([
        api.systemStatus(),
        api.weatherCurrent(),
        api.rainfallNowcast(),
        api.hotspots(180),
        api.alerts(),
        api.drainageStatus(),
        api.roadsGeoJson(true),
        api.rainfallGrid(),
        api.windGrid(),
      ]);
      set({
        system, weather, nowcast: nc, hotspots, alerts, drainage, roads,
        rainGrid: rain, windGrid: wind,
        lastUpdated: new Date().toLocaleTimeString(),
        loading: false,
      });
      if (isSim) {
        set({ simulationRunning: true });
      }
    } catch (e) {
      console.warn("poll failed", e);
      set({ loading: false });
    }
  }, [set]);

  // flood grid re-fetch on minute change
  useEffect(() => {
    if (!useStore.getState().system) return;
    api.floodGrid(selectedMinute).then((g) => set({ floodGrid: g })).catch(console.warn);
    api.floodForecast().then((preds) => {
      const cur = preds.find((p) => p.road_id === useStore.getState().selectedRoad?.road_id);
      if (cur) selectRoad(cur);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedMinute, _tick, scenario, simRunning]);

  // background polling loop
  useEffect(() => {
    refresh();
    const id = setInterval(() => { refresh(); setTick((t) => t + 1); }, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const onRoadClick = useCallback((id: string) => {
    api.street(id).then(selectRoad).catch(console.warn);
  }, [selectRoad]);

  // WebGL intensity from live data (visuals only — numbers come from backend)
  const rainNow = nowcast?.rainfall_mm_hr?.["0"]
    ?? (floodGrid.length > 0 ? Math.max(...floodGrid.map((c) => c.depth_cm ?? 0)) / 60 : 0);
  const rainLevel = Math.min(1, rainNow / 60);
  const waterLevel = Math.min(1, Math.max(...floodGrid.map((c) => c.depth_cm ?? 0), 0) / 60);
  const animate = !useStore.getState().loading;

  return (
    <div className="app-shell">
      <RainWebGL rainLevel={animate ? rainLevel : 0.15} waterLevel={animate ? waterLevel : 0.02} />
      <TopBar />
      {view === "command"
        ? <CommandCenter onRoadClick={onRoadClick} />
        : <PublicMode />}
      {simRunning && (
        <div style={{ position: "fixed", zIndex: 30, bottom: 74, right: 14, background: "rgba(176,18,69,0.15)", border: "1px solid var(--critical)", color: "var(--critical)", fontWeight: 700, borderRadius: 12, padding: "8px 14px", fontSize: 13 }}>
          🎮 SCENARIO MODE — synthetic forecast
        </div>
      )}
    </div>
  );
}