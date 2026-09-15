import { useStore } from "../stores/appStore";
import type { LayerKey } from "../types";

const LAYERS: { k: LayerKey; label: string; color: string }[] = [
  { k: "roads", label: "Roads · flood risk", color: "linear-gradient(90deg,#2e9e53,#f0c419,#f2961c,#e64a45,#b01245)" },
  { k: "flood", label: "Flood grid cells", color: "linear-gradient(90deg,#f0c419,#f2961c,#e64a45,#b01245)" },
  { k: "rain", label: "Rainfall grid", color: "linear-gradient(90deg,#3b82f6,#22d3ee,#1d4ed8)" },
  { k: "wind", label: "Wind field", color: "repeating-linear-gradient(45deg,#22d3ee,#22d3ee 2px,#e0f2fe 2px,#e0f2fe 4px)" },
  { k: "hotspots", label: "Hotspots", color: "linear-gradient(135deg,#b01245,#e64a45)" },
  { k: "routes", label: "Safe route", color: "linear-gradient(90deg,#35c3ff,#1677d3)" },
  { k: "alerts", label: "Active alerts", color: "linear-gradient(90deg,#f2961c,#b01245)" },
];

export default function LayerControl() {
  const active = useStore((s) => s.activeLayers);
  const toggle = useStore((s) => s.toggleLayer);
  return (
    <div className="layer-control">
      <h4>Layers</h4>
      {LAYERS.map((l) => (
        <label className="layer-row" key={l.k}>
          <input type="checkbox" checked={active.includes(l.k)} onChange={() => toggle(l.k)} />
          <span className="swatch" style={{ background: l.color }} />
          {l.label}
        </label>
      ))}
    </div>
  );
}