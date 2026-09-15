import { useStore } from "../stores/appStore";

export default function Legend() {
  const active = useStore((s) => s.activeLayers);
  if (!active.includes("roads") && !active.includes("flood")) return null;
  return (
    <div className="legend">
      <strong>Flood depth (cm)</strong>
      <div
        className="grad"
        style={{ background: "linear-gradient(90deg,#2e9e53,#f0c419,#f2961c,#e64a45,#b01245)" }}
      />
      <div className="lrow">
        <span>≤5</span><span>15</span><span>30</span><span>50</span><span>60+</span>
      </div>
    </div>
  );
}