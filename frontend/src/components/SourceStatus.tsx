import { useStore } from "../stores/appStore";

export default function SourceStatus() {
  const system = useStore((s) => s.system);
  if (!system) return <div className="card" style={{ color: "var(--text-dim)", fontSize: 13 }}>Source status pending…</div>;
  const st = (s: string) => (s === "OK" || s === "LIVE" || s === "HEALTHY" ? "OK" : s === "UNAVAILABLE" || s === "DOWN" ? "DOWN" : s);
  const sys = (s: string) => (s === "OK" || s === "LIVE" || s === "HEALTHY" ? "var(--safe)" : "var(--severe)");

  return (
    <div>
      <h5>Data sources · freshness {system.data_freshness_seconds != null ? `${system.data_freshness_seconds}s` : "n/a"}</h5>
      {system.providers.map((p) => (
        <div className="src-row" key={p.name}>
          <span>{p.name} <span style={{ color: "var(--text-dim)" }}>· {p.data_type}</span></span>
          <span className="st" style={{ color: sys(st(p.status)), background: `color-mix(in srgb, ${sys(st(p.status))} 12%, white)` }}>
            {st(p.status)}
            {p.data_age_seconds != null ? ` · ${p.data_age_seconds}s` : ""}
          </span>
        </div>
      ))}
      <div style={{ fontSize: 11.5, color: "var(--text-dim)", marginTop: 8 }}>
        Live: Open-Meteo (weather·forecast) · Simulated locally: terrain, drainage network, NASA/Google-style rainfall & radar.
      </div>
    </div>
  );
}