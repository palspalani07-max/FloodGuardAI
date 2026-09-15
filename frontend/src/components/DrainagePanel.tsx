import { useStore } from "../stores/appStore";

export default function DrainagePanel() {
  const d = useStore((s) => s.drainage);
  if (!d) return <div className="card" style={{ color: "var(--text-dim)", fontSize: 13 }}>Drainage telemetry pending…</div>;

  const pct = (x: number) => `${x.toFixed(1)}%`;
  const capRisk = d.critical_pipes > 0 ? "var(--severe)" : d.average_utilization > 75 ? "var(--high)" : "var(--safe)";

  return (
    <div>
      <h5>Drain network health</h5>
      <div className="grid2">
        <div className="kv"><span className="k">Nodes</span><span className="v">{d.total_nodes}</span></div>
        <div className="kv"><span className="k">Overloaded</span><span className="v" style={{ color: d.overloaded_nodes ? "var(--severe)" : "var(--safe)" }}>{d.overloaded_nodes}</span></div>
        <div className="kv"><span className="k">Pipes</span><span className="v">{d.total_edges}</span></div>
        <div className="kv"><span className="k">Critical pipes</span><span className="v" style={{ color: capRisk }}>{d.critical_pipes}</span></div>
      </div>
      <div style={{ marginTop: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
          <span style={{ color: "var(--text-dim)", fontWeight: 600 }}>Average capacity utilization</span>
          <strong>{pct(d.average_utilization)}</strong>
        </div>
        <div className="track" style={{ height: 10, marginTop: 4 }}>
          <div
            className="fill"
            style={{
              width: `${Math.min(100, d.average_utilization)}%`,
              background: d.average_utilization > 75 ? "var(--severe)" : "var(--accent)",
            }}
          />
        </div>
        <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginTop: 6 }}>
          Estimated blockage {pct(d.estimated_blockage)} across critical inlets.
        </div>
      </div>
    </div>
  );
}