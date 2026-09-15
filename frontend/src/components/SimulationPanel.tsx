import { useState } from "react";
import { useStore } from "../stores/appStore";
import { api } from "../services/api";
import type { SimulationScenario } from "../types";

const PRESETS: SimulationScenario[] = [
  { name: "NORMAL", rainfall_mm_hr: 5, duration_min: 60, blockage_percent: 0 },
  { name: "HEAVY STORM", rainfall_mm_hr: 30, duration_min: 90, blockage_percent: 10 },
  { name: "EXTREME FLOOD", rainfall_mm_hr: 60, duration_min: 120, blockage_percent: 20 },
];

export default function SimulationPanel() {
  const scenario = useStore((s) => s.scenario);
  const running = useStore((s) => s.simulationRunning);
  const setScenario = useStore((s) => s.setScenario);
  const set = useStore((s) => s.set);
  const [busy, setBusy] = useState(false);

  const scn = scenario ?? PRESETS[0];

  async function start(p: SimulationScenario) {
    setBusy(true);
    try {
      await api.simulationStart(p);
      setScenario(p);
      set({ simulationRunning: true });
    } catch (e) {
      console.error(e);
    } finally { setBusy(false); }
  }
  async function stop() {
    setBusy(true);
    try {
      await api.simulationStop();
      setScenario(null);
      set({ simulationRunning: false });
    } catch (e) { console.error(e); }
    finally { setBusy(false); }
  }

  return (
    <div>
      <h5>Scenario simulation</h5>
      {PRESETS.map((p) => (
        <div
          key={p.name}
          className={`scn ${scn.name === p.name ? "active" : ""}`}
          onClick={() => !running && start(p)}
        >
          <div style={{ flex: 1 }}>
            <strong>{p.name}</strong>
            <div className="bar" style={{ width: `${Math.min(100, p.rainfall_mm_hr)}%` }} />
          </div>
          <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
            {p.rainfall_mm_hr} mm/hr · {p.blockage_percent}% blockage
          </span>
        </div>
      ))}
      <div className="btn-row">
        {running ? (
          <button className="btn btn-ghost" onClick={stop} disabled={busy}>
            ⏹ Stop simulation
          </button>
        ) : (
          <button className="btn btn-primary" disabled={busy} onClick={() => start(scn)}>
            ▶ Run {scn.name.toLowerCase()}
          </button>
        )}
      </div>
      {running && (
        <div style={{ fontSize: 12, color: "var(--accent-2)", fontWeight: 700 }}>
          ● Simulation running — dashboard now shows the scenario forecast.
        </div>
      )}
    </div>
  );
}