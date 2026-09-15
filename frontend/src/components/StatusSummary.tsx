import { useStore } from "../stores/appStore";
import type { Severity } from "../types";

function sevInt(s: Severity) { return s === "SAFE" ? 0 : s === "MINOR" ? 1 : s === "HIGH" ? 2 : s === "SEVERE" ? 3 : 4; }
function worst(a: Severity, b: Severity): Severity {
  return ["SAFE", "MINOR", "HIGH", "SEVERE", "CRITICAL"][Math.max(sevInt(a), sevInt(b))] as Severity;
}

export default function StatusSummary() {
  const weather = useStore((s) => s.weather);
  const nowcast = useStore((s) => s.nowcast);
  const floodGrid = useStore((s) => s.floodGrid);
  const hotspots = useStore((s) => s.hotspots);

  const rainNow = nowcast?.rainfall_mm_hr?.["0"] ?? weather?.precipitation_mm ?? 0;
  const rainPeak = Math.max(...Object.values(nowcast?.rainfall_mm_hr ?? {}).map(Number), 0);
  let floodedRoads = 0;
  let worstRisk: Severity = "SAFE";
  for (const p of floodGrid) {
    if ((p.depth_cm ?? 0) > 5) floodedRoads++;
    worstRisk = worst(worstRisk, p.risk ?? "SAFE");
  }
  const critical = hotspots.filter((h) => h.severity !== "SAFE" && h.severity !== "MINOR").length;

  return (
    <div className="status-summary">
      <div className="stat-card">
        <div className="lab">RAINFALL</div>
        <div className="val" style={{ color: "var(--accent)" }}>{rainNow.toFixed(1)}</div>
        <div className="unit">mm/hr · peak {rainPeak.toFixed(1)}</div>
      </div>
      <div className="stat-card">
        <div className="lab">WIND</div>
        <div className="val">{weather?.wind_speed_kmh ?? 0}</div>
        <div className="unit">km/h {weather ? `from ${(weather.wind_direction_deg + 0).toFixed(0)}°` : ""}</div>
      </div>
      <div className="stat-card">
        <div className="lab">FLOODED ROADS</div>
        <div className="val" style={{ color: floodedRoads > 200 ? "var(--severe)" : "var(--safe)" }}>
          {floodedRoads.toLocaleString()}
        </div>
        <div className="unit">of {floodGrid.length.toLocaleString()} grid cells</div>
      </div>
      <div className="stat-card">
        <div className="lab">CRITICAL ZONES</div>
        <div className="val" style={{ color: critical > 0 ? "var(--critical)" : "var(--safe)" }}>{critical}</div>
        <div className="unit">high+ severity</div>
      </div>
    </div>
  );
}