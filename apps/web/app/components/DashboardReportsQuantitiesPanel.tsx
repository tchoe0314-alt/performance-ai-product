import type { ComponentProps } from "react";
import type { SidePanelKey } from "../utils/workspaceShell";
import { QuantitiesPanel } from "./QuantitiesPanel";
import { ReportsPanel } from "./ReportsPanel";

type ReportsPanelProps = ComponentProps<typeof ReportsPanel>;
type QuantitiesPanelProps = ComponentProps<typeof QuantitiesPanel>;

type DashboardReportsQuantitiesPanelProps = {
  activePanel: Extract<SidePanelKey, "reports" | "quantities">;
  reports: ReportsPanelProps;
  quantities: QuantitiesPanelProps;
};

export function DashboardReportsQuantitiesPanel({
  activePanel,
  reports,
  quantities,
}: DashboardReportsQuantitiesPanelProps) {
  return (
    <div className="space-y-3">
      {activePanel === "reports" ? <ReportsPanel {...reports} /> : null}
      {activePanel === "quantities" ? <QuantitiesPanel {...quantities} /> : null}
    </div>
  );
}
