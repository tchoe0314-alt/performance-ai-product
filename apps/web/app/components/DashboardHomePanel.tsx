import type { ComponentProps } from "react";

import { DashboardEngineDepthPanel } from "./DashboardEngineDepthPanel";
import { DashboardGuidancePanel } from "./DashboardGuidancePanel";
import { DashboardIssueReportPanel } from "./DashboardIssueReportPanel";
import { DashboardProgressTimeline } from "./DashboardProgressTimeline";
import { DashboardProjectSummary } from "./DashboardProjectSummary";
import { DashboardRunReviewPanel } from "./DashboardRunReviewPanel";
import { DashboardStatusPanels } from "./DashboardStatusPanels";
import { TakeoffSnapshotPanel } from "./TakeoffSnapshotPanel";
import { DisclosurePanel } from "./ui";

type DashboardHomePanelProps = {
  projectSummary: ComponentProps<typeof DashboardProjectSummary>;
  progressTimeline: ComponentProps<typeof DashboardProgressTimeline>;
  engineDepth: ComponentProps<typeof DashboardEngineDepthPanel> | null;
  guidance: ComponentProps<typeof DashboardGuidancePanel>;
  issueReport: ComponentProps<typeof DashboardIssueReportPanel>;
  runReview: ComponentProps<typeof DashboardRunReviewPanel> | null;
  statusPanels: ComponentProps<typeof DashboardStatusPanels>;
  takeoffSnapshot: ComponentProps<typeof TakeoffSnapshotPanel>;
};

export function DashboardHomePanel({
  projectSummary,
  progressTimeline,
  engineDepth,
  guidance,
  issueReport,
  runReview,
  statusPanels,
  takeoffSnapshot,
}: DashboardHomePanelProps) {
  return (
    <div className="space-y-3" data-testid="clean-project-health-panel">
      <DashboardProjectSummary {...projectSummary} />
      <DashboardGuidancePanel {...guidance} />
      <DisclosurePanel title="Progress" subtitle="Project stages and recent activity" status="Timeline">
        <DashboardProgressTimeline {...progressTimeline} />
      </DisclosurePanel>
      {engineDepth ? (
        <DisclosurePanel title="Engineering systems" subtitle="Evidence depth and system readiness" status="Details">
          <DashboardEngineDepthPanel {...engineDepth} />
        </DisclosurePanel>
      ) : null}
      <DisclosurePanel title="Issues and evidence" subtitle="Diagnostics, sources, and review details" status="Details">
        <DashboardIssueReportPanel {...issueReport} />
        {runReview ? <DashboardRunReviewPanel {...runReview} /> : null}
      </DisclosurePanel>
      <DisclosurePanel title="Status" subtitle="Standards, sources, exports, and system state" status="Details">
        <DashboardStatusPanels {...statusPanels} />
      </DisclosurePanel>
      <DisclosurePanel title="Quantities" subtitle="Current takeoff snapshot" status="Snapshot">
        <TakeoffSnapshotPanel {...takeoffSnapshot} />
      </DisclosurePanel>
    </div>
  );
}
