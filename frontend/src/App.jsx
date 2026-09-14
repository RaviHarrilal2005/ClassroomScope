import { ViewStateProvider } from "./state/ViewStateContext";
import DashboardShell from "./components/DashboardShell";

export default function App() {
  return (
    <ViewStateProvider>
      <DashboardShell />
    </ViewStateProvider>
  );
}
