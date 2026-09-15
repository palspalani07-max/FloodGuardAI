import { useStore } from "../stores/appStore";
import type { Severity } from "../types";

export function RiskPill({ s }: { s: Severity }) {
  return <span className={`risk-pill risk-${s}`}>{s}</span>;
}

export default function HotspotsPanel() {
  const hotspots = useStore((s) => s.hotspots);
  const selectHotspot = useStore((s) => s.selectHotspot);
  const selected = useStore((s) => s.selectedHotspot);

  return (
    <div>
      <h5>Top flood hotspots · +180 min</h5>
      {hotspots.length === 0 && <div style={{ color: "var(--text-dim)", fontSize: 13 }}>No significant hotspots detected.</div>}
      {hotspots.map((h, i) => (
        <div
          key={h.road_id ?? i}
          className="hotspot-item"
          style={selected?.road_id === h.road_id ? { borderColor: "var(--accent)" } : {}}
          onClick={() => selectHotspot(h)}
        >
          <span className="hotspot-rank">{i + 1}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5 }}>{h.area_name}</div>
            <div style={{ fontSize: 11.5, color: "var(--text-dim)" }}>
              {h.depth_cm.toFixed(1)} cm · onset {h.arrival_minutes != null ? `+${h.arrival_minutes} min` : "n/a"}
            </div>
          </div>
          <RiskPill s={h.severity} />
        </div>
      ))}
    </div>
  );
}