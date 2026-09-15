import { useEffect, useMemo, useState } from "react";
import { useStore } from "../stores/appStore";
import type { ActiveAlert, Severity } from "../types";

export default function Notifications() {
  const alerts = useStore((s) => s.alerts);
  const [seen, setSeen] = useState<Set<string>>(() => new Set());

  const critical = useMemo(
    () => alerts.filter((a) => a.severity === "CRITICAL" || a.severity === "SEVERE"),
    [alerts],
  );
  const isNew = (a: ActiveAlert) => !seen.has(a.alert_id);

  useEffect(() => {
    for (const a of critical) {
      if (!seen.has(a.alert_id)) {
        setTimeout(() => setSeen((p) => new Set(p).add(a.alert_id)), 9000);
      }
    }
  }, [critical, seen]);

  const fresh = critical.filter(isNew).slice(-3);
  if (fresh.length === 0) return null;

  return (
    <div className="notif-toast">
      {fresh.map((a) => (
        <div key={a.alert_id} className={`toast alert-${a.severity as Severity}`}>
          <strong>⚠ {a.severity} ALERT · {a.road_name ?? a.area_name}</strong>
          <div style={{ marginTop: 3 }}>{a.message}</div>
        </div>
      ))}
    </div>
  );
}