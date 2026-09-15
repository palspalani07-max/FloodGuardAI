import MapView from "../map/MapView";
import SidePanel from "../components/SidePanel";
import StatusSummary from "../components/StatusSummary";
import LayerControl from "../components/LayerControl";
import TimeControl from "../components/TimeControl";
import Legend from "../components/Legend";
import Notifications from "../components/Notifications";

export default function CommandCenter({ onRoadClick }: { onRoadClick: (id: string) => void }) {
  return (
    <div className="app-body">
      <SidePanel />
      <div style={{ position: "relative", flex: 1 }}>
        <MapView onRoadClick={onRoadClick} />
        <StatusSummary />
        <LayerControl />
        <TimeControl />
        <Legend />
        <Notifications />
      </div>
    </div>
  );
}