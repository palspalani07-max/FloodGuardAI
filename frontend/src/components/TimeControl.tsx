import { useStore } from "../stores/appStore";

const STEPS = [0, 15, 30, 45, 60, 90, 120, 150, 180];

export default function TimeControl() {
  const min = useStore((s) => s.selectedMinute);
  const setMin = useStore((s) => s.setSelectedMinute);
  return (
    <div className="time-control">
      <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-dim)" }}>FORECAST</span>
      {STEPS.map((m) => (
        <button key={m} className={min === m ? "active" : ""} onClick={() => setMin(m)}>
          {m === 0 ? "NOW" : `+${m}`}
        </button>
      ))}
    </div>
  );
}