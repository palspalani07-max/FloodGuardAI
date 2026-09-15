import { useState } from "react";
import WeatherPanel from "./WeatherPanel";
import HotspotsPanel from "./HotspotsPanel";
import AlertsPanel from "./AlertsPanel";
import DrainagePanel from "./DrainagePanel";
import StreetDetailPanel from "./StreetDetailPanel";
import SimulationPanel from "./SimulationPanel";
import RoutingPanel from "./RoutingPanel";
import SourceStatus from "./SourceStatus";

const TABS = [
  { id: "street", label: "Street", icon: "🛣" },
  { id: "hotspots", label: "Hotspots", icon: "🔥" },
  { id: "alerts", label: "Alerts", icon: "⚠" },
  { id: "weather", label: "Weather", icon: "🌦" },
  { id: "drainage", label: "Drainage", icon: "🕳" },
  { id: "routing", label: "Routing", icon: "🧭" },
  { id: "simulation", label: "Scenario", icon: "🎮" },
  { id: "sources", label: "Sources", icon: "📡" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function SidePanel() {
  const [tab, setTab] = useState<TabId>("street");

  return (
    <aside className="side-panel">
      <div className="panel-head">🛟 <span>Decision support</span></div>
      <div style={{ display: "flex", gap: 4, padding: "0 16px", flexWrap: "wrap" }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            className="btn btn-ghost btn-sm"
            style={tab === t.id ? { background: "var(--accent)", color: "#fff" } : {}}
            onClick={() => setTab(t.id)}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>
      <div className="panel-body" style={{ marginTop: 8 }}>
        <div className="card">
          {tab === "street" && <StreetDetailPanel />}
          {tab === "hotspots" && <HotspotsPanel />}
          {tab === "alerts" && <AlertsPanel />}
          {tab === "weather" && <WeatherPanel />}
          {tab === "drainage" && <DrainagePanel />}
          {tab === "routing" && <RoutingPanel />}
          {tab === "simulation" && <SimulationPanel />}
          {tab === "sources" && <SourceStatus />}
        </div>
      </div>
    </aside>
  );
}