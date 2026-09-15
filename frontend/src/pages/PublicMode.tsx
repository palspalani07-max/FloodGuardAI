import { useState } from "react";
import MapView from "../map/MapView";
import StatusSummary from "../components/StatusSummary";
import Notifications from "../components/Notifications";
import { api } from "../services/api";
import { useStore, CHENNAI } from "../stores/appStore";
import { RiskPill } from "../components/HotspotsPanel";
import type { RouteResult } from "../types";

export default function PublicMode() {
  const nowcast = useStore((s) => s.nowcast);
  const hotspots = useStore((s) => s.hotspots);
  const alerts = useStore((s) => s.alerts);
  const route = useStore((s) => s.route);
  const setRoute = useStore((s) => s.setRoute);
  const set = useStore((s) => s.set);
  const [from, setFrom] = useState(() => `${CHENNAI.lat.toFixed(4)}, ${CHENNAI.lon.toFixed(4)}`);
  const [to, setTo] = useState("13.0630, 80.2300");
  const [busy, setBusy] = useState(false);

  async function plan() {
    const a = from.split(",").map((x) => parseFloat(x.trim()));
    const b = to.split(",").map((x) => parseFloat(x.trim()));
    if (a.length < 2 || b.length < 2 || isNaN(a[0]) || isNaN(b[0])) { alert("Enter lat, lon pairs."); return; }
    setBusy(true); set({ routeLoading: true });
    try { setRoute(await api.safeRoute(a[0], a[1], b[0], b[1], "NORMAL", 60, false)); }
    catch (e) { console.error(e); setRoute(null); }
    finally { set({ routeLoading: false }); setBusy(false); }
  }

  const rain = nowcast?.rainfall_mm_hr?.["0"] ?? 0;
  const severe = alerts.filter((a) => a.severity === "CRITICAL" || a.severity === "SEVERE").length;
  const cr = hotspots.filter((h) => h.severity === "HIGH" || h.severity === "SEVERE" || h.severity === "CRITICAL");

  return (
    <div className="app-body" style={{ flexDirection: "column" }}>
      <div style={{ flex: 1, position: "relative", minHeight: 0 }}>
        <MapView onRoadClick={() => {}} />
        <StatusSummary />
        <Notifications />

        {cr.length > 0 && (
          <div className="layer-control" style={{ top: "auto", bottom: 12, right: 12, width: 220 }}>
            <h4>Flooding reported nearby</h4>
            {cr.slice(0, 4).map((h, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", borderBottom: "1px dashed var(--glass-border)" }}>
                <span style={{ fontSize: 12.5 }}>{h.area_name}</span>
                <RiskPill s={h.severity} />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card" style={{ margin: 10, padding: 14, width: "auto" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input value={from} placeholder="From lat, lon" onChange={(e) => setFrom(e.target.value)} style={{ flex: 1, padding: 9, borderRadius: 10, border: "1px solid var(--glass-border)" }} />
          <span style={{ color: "var(--text-dim)" }}>→</span>
          <input value={to} placeholder="To lat, lon" onChange={(e) => setTo(e.target.value)} style={{ flex: 1, padding: 9, borderRadius: 10, border: "1px solid var(--glass-border)" }} />
          <button className="btn btn-primary" onClick={plan} disabled={busy}>🚗 Find safe route</button>
        </div>
        {route && <RouteSummary r={route} />}
        <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginTop: 8 }}>
          Rain intensity now: <strong>{rain.toFixed(1)} mm/hr</strong> · {severe > 0 ? `${severe} severe alerts active ⚠` : "no severe alerts ✓"}
        </div>
      </div>
    </div>
  );
}

function RouteSummary({ r }: { r: RouteResult }) {
  return (
    <div style={{ marginTop: 10, padding: 10, borderRadius: 12, background: "var(--accent-soft)", border: "1px solid var(--glass-border)" }}>
      <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
        <strong>{r.distance_km.toFixed(1)} km</strong>
        <span>⏱ {r.estimated_minutes} min{r.additional_minutes > 0 ? ` (+${r.additional_minutes} due to flooding)` : ""}</span>
        <RiskPill s={r.risk} />
        {r.diverted && <span style={{ color: "var(--severe)", fontWeight: 700 }}>⚠ Rerouted around flooding</span>}
      </div>
    </div>
  );
}