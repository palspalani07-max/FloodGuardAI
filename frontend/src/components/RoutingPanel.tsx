import { useState } from "react";
import { useStore } from "../stores/appStore";
import { api } from "../services/api";
import type { RouteResult, RoutingMode } from "../types";
import { RiskPill } from "./HotspotsPanel";

const PRESETS: [string, string][] = [
  ["Marina Beach Run", "13.0521, 80.2820"],
  ["Central Station → Airport", "13.0819, 80.2705, 12.9941, 80.1709"],
  ["T Nagar → Velachery", "13.0418, 80.2341, 12.9791, 80.2208"],
];

export default function RoutingPanel() {
  const [from, setFrom] = useState(PRESETS[1][1].split(", ").slice(0, 2).join(", "));
  const [to, setTo] = useState(PRESETS[1][1].split(", ").slice(2, 4).join(", "));
  const [mode, setMode] = useState<RoutingMode>("NORMAL");
  const [useOsrm, setUseOsrm] = useState(false);
  const [parsing, setParsing] = useState(false);
  const route = useStore((s) => s.route);
  const routeLoading = useStore((s) => s.routeLoading);
  const setRoute = useStore((s) => s.setRoute);
  const set = useStore((s) => s.set);

  function parse(v: string): [number, number] | null {
    const parts = v.split(",").map((x) => parseFloat(x.trim()));
    if (parts.length < 2 || isNaN(parts[0]) || isNaN(parts[1])) return null;
    return [parts[0], parts[1]];
  }

  async function go() {
    const a = parse(from), b = parse(to);
    if (!a || !b) { alert("Enter coordinates as lat, lon"); return; }
    setParsing(true); set({ routeLoading: true });
    try {
      const r = await api.safeRoute(a[0], a[1], b[0], b[1], mode, 60, useOsrm);
      setRoute(r);
    } catch (e) { console.error(e); setRoute(null); }
    finally { set({ routeLoading: false }); setParsing(false); }
  }

  function preset(i: number) {
    const raw = PRESETS[i][1].split(", ").map((x) => parseFloat(x));
    setFrom(`${raw[0]}, ${raw[1]}`);
    if (raw.length === 4) setTo(`${raw[2]}, ${raw[3]}`);
  }

  return (
    <div>
      <h5>Safe routing · flood-aware</h5>
      <div className="btn-row">
        {PRESETS.map((p, i) => (
          <button key={p[0]} className="btn btn-ghost btn-sm" onClick={() => preset(i)}>{p[0]}</button>
        ))}
      </div>
      <div className="route-inputs">
        <input value={from} placeholder="Origin lat, lon" onChange={(e) => setFrom(e.target.value)} />
        <input value={to} placeholder="Destination lat, lon" onChange={(e) => setTo(e.target.value)} />
        <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center", flexWrap: "wrap" }}>
          {(["NORMAL", "EMERGENCY", "PUBLIC_TRANSPORT"] as RoutingMode[]).map((m) => (
            <label key={m} style={{ fontSize: 12, fontWeight: 600 }}>
              <input type="radio" name="mode" checked={mode === m} onChange={() => setMode(m)} /> {m}
            </label>
          ))}
          <label style={{ fontSize: 12, fontWeight: 600 }}>
            <input type="checkbox" checked={useOsrm} onChange={() => setUseOsrm(!useOsrm)} /> Use OSRM engine
          </label>
        </div>
        <button className="btn btn-primary" style={{ width: "100%" }} onClick={go} disabled={routeLoading || parsing}>
          {routeLoading ? "Planning…" : "↻ Compute safest route"}
        </button>
      </div>

      {route && (
        <div className="route-res" style={{ marginTop: 10 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong style={{ fontSize: 14 }}>{route.distance_km.toFixed(1)} km</strong>
            <RiskPill s={route.risk} />
          </div>
          <div className="route-box">
            {route.estimated_minutes} min ETA
            {route.additional_minutes > 0 ? ` · +${route.additional_minutes} min vs normal` : ""}
          </div>
          <div className="route-box">
            Max depth {route.max_depth_cm.toFixed(1)} cm · {route.avoided_roads} roads avoided
          </div>
          {route.diverted && (
            <div className="route-box" style={{ borderColor: "var(--high)", color: "var(--severe)", fontWeight: 600 }}>
              ⚠ Auto-diverted: {route.diversion_reason}
            </div>
          )}
          <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 6 }}>
            {useOsrm ? "OSRM engine (live road graph)" : "Internal flood-aware engine (simulated)"} · {route.route.length} waypoints
          </div>
        </div>
      )}
    </div>
  );
}