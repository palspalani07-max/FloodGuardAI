import { useStore } from "../stores/appStore";
import { RiskPill } from "./HotspotsPanel";

export default function AlertsPanel() {
  const alerts = useStore((s) => s.alerts);
  return (
    <div>
      <h5>Active warnings ({alerts.length})</h5>
      {alerts.length === 0 && (
        <div style={{ color: "var(--safe)", fontSize: 13, fontWeight: 600 }}>
          ✓ No active flood warnings right now.
        </div>
      )}
      {alerts.map((a) => (
        <div key={a.alert_id} className={`alert-item alert-${a.severity}`}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <strong>{a.road_name || a.area_name || "Road"}</strong>
            <RiskPill s={a.severity} />
          </div>
          <div style={{ marginTop: 4, color: "var(--text)" }}>{a.message}</div>
          <div style={{ marginTop: 4, fontSize: 11, color: "var(--text-dim)" }}>
            Max {a.max_depth_cm?.toFixed?.(1) ?? "n/a"} cm
            {a.arrival_time_min != null ? ` · onset +${a.arrival_time_min} min` : ""}
            {" · "}{new Date(a.created_at).toLocaleTimeString()}
          </div>
        </div>
      ))}
    </div>
  );
}