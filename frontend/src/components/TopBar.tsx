import { useStore } from "../stores/appStore";

export default function TopBar() {
  const system = useStore((s) => s.system);
  const lastUpdated = useStore((s) => s.lastUpdated);
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);

  return (
    <header className="topbar">
      <div className="brand">
        <span className="logo">◍</span>
        FLOODGUARD&nbsp;<span style={{ color: "var(--accent-2)" }}>AI</span>
        <span className="live-pill"><span className="live-dot" /> LIVE</span>
      </div>
      <span className="city">📍 Chennai · 13.05°N 80.26°E</span>
      <div className="spacer" />
      <span className="updated">
        Model v{system?.version ?? "0.1.0"} · updated {lastUpdated || "—"}
      </span>
      <div className="view-toggle">
        <button className={view === "command" ? "active" : ""} onClick={() => setView("command")}>
          🏛 Command
        </button>
        <button className={view === "public" ? "active" : ""} onClick={() => setView("public")}>
          🚇 Public
        </button>
      </div>
    </header>
  );
}