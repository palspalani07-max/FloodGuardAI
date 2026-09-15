import { useStore } from "../stores/appStore";
import { RiskPill } from "./HotspotsPanel";

const STEPS = [0, 15, 30, 45, 60, 90, 120, 150, 180];

export default function StreetDetailPanel() {
  const road = useStore((s) => s.selectedRoad);
  if (!road) {
    return (
      <div className="card" style={{ color: "var(--text-dim)", fontSize: 13 }}>
        Click any street on the map to see its flood timeline, depth and risk.
      </div>
    );
  }
  const curve = road.depth_curve ?? {
    0: road.current_depth_cm, 15: road.depth_15min, 30: road.depth_30min, 45: road.depth_45min,
    60: road.depth_60min, 90: road.depth_90min, 120: road.depth_120min, 150: road.depth_150min,
    180: road.depth_180min,
  };
  const maxDepth = Math.max(...Object.values(curve).map(Number), road.max_depth_cm ?? 0);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontSize: 15 }}>{road.road_name || road.road_id}</strong>
        <RiskPill s={road.risk} />
      </div>
      <div style={{ fontSize: 11.5, color: "var(--text-dim)", margin: "2px 0 8px" }}>
        {road.highway} · {road.lat.toFixed(5)}, {road.lon.toFixed(5)} · {road.confidence} confidence
      </div>
      <div className="grid2">
        <div className="kv"><span className="k">Peak depth</span><span className="v">{maxDepth.toFixed(1)} cm</span></div>
        <div className="kv"><span className="k">Onset</span><span className="v">{road.arrival_time_min != null ? `${road.arrival_time_min} min` : "—"}</span></div>
        <div className="kv"><span className="k">Duration</span><span className="v">{road.duration_min} min</span></div>
        <div className="kv"><span className="k">Flow velocity</span><span className="v">{road.velocity_ms.toFixed(2)} m/s</span></div>
      </div>
      <div className="depth-bars">
        {STEPS.map((m) => {
          const d = curve[m.toString()] ?? 0;
          const pct = Math.min(100, maxDepth > 0 ? (d / maxDepth) * 100 : 0);
          return (
            <div className="depth-bar" key={m}>
              <span style={{ width: 34 }}>{m === 0 ? "now" : `+${m}`}</span>
              <div className="track"><div className="fill" style={{ width: `${pct}%` }} /></div>
              <span style={{ width: 40, textAlign: "right" }}>{d.toFixed(1)} cm</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}