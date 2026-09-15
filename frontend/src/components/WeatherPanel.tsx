import { useStore } from "../stores/appStore";
import { RiskPill } from "./HotspotsPanel";

const STEP = [0, 15, 30, 45, 60, 90, 120, 150, 180];
const DIR = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

export default function WeatherPanel() {
  const weather = useStore((s) => s.weather);
  const nowcast = useStore((s) => s.nowcast);
  if (!weather) return <div className="card" style={{ color: "var(--text-dim)", fontSize: 13 }}>Weather pending…</div>;

  const dir = DIR[Math.round(((weather.wind_direction_deg % 360) / 45)) % 8];
  const rain = nowcast?.rainfall_mm_hr ?? {};
  const peak = Math.max(...Object.values(rain).map(Number), 0);

  return (
    <div>
      <h5>Live weather · {weather.conditions} · {weather.source}</h5>
      <div className="grid2">
        <div className="kv"><span className="k">Temperature</span><span className="v">{weather.temperature_c.toFixed(1)} °C</span></div>
        <div className="kv"><span className="k">Wind</span><span className="v">{weather.wind_speed_kmh.toFixed(1)} km/h {dir}</span></div>
        <div className="kv"><span className="k">Humidity</span><span className="v">{weather.humidity_percent.toFixed(0)} %</span></div>
        <div className="kv"><span className="k">Gust exposure</span><span className="v">{weather.wind_speed_kmh > 40 ? "High" : weather.wind_speed_kmh > 25 ? "Moderate" : "Low"}</span></div>
      </div>

      {nowcast && (
        <>
          <h5 style={{ marginTop: 12 }}>Rainfall nowcast (mm/hr) · {nowcast.confidence}</h5>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 44 }}>
            {STEP.map((m) => {
              const v = rain[m.toString()] ?? 0;
              const h = Math.max(3, (v / (peak || 1)) * 40);
              return (
                <div key={m} style={{ flex: 1, textAlign: "center" }}>
                  <div style={{ height: h, background: "linear-gradient(180deg,#38bdf8,#1d4ed8)", borderRadius: "4px 4px 0 0" }} title={`${m} min: ${v.toFixed(1)}`} />
                  <div style={{ fontSize: 9, color: "var(--text-dim)" }}>{m === 0 ? "now" : m}</div>
                </div>
              );
            })}
          </div>
        </>
      )}

      <h5 style={{ marginTop: 12 }}>Flood intensity outlook (web only — confirm with depth data)</h5>
      <div className="grid2">
        <div className="kv"><span className="k">Peak rain</span><span className="v">{peak.toFixed(1)} mm/hr</span></div>
        <div className="kv">
          <span className="k">Outlook</span>
          <span><RiskPill s={peak > 60 ? "CRITICAL" : peak > 30 ? "SEVERE" : peak > 15 ? "HIGH" : peak > 5 ? "MINOR" : "SAFE"} /></span>
        </div>
      </div>
    </div>
  );
}