import type { ComponentProps } from "react";

import { DashboardEngineDepthPanel } from "./DashboardEngineDepthPanel";
import { DashboardGuidancePanel } from "./DashboardGuidancePanel";
import { DashboardIssueReportPanel } from "./DashboardIssueReportPanel";
import { DashboardProgressTimeline } from "./DashboardProgressTimeline";
import { DashboardProjectSummary } from "./DashboardProjectSummary";
import { DashboardRunReviewPanel } from "./DashboardRunReviewPanel";
import { DashboardStatusPanels } from "./DashboardStatusPanels";
import { TakeoffSnapshotPanel } from "./TakeoffSnapshotPanel";

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
    <div className="space-y-4">
      <DashboardProjectSummary {...projectSummary} />
      <DashboardProgressTimeline {...progressTimeline} />
      {engineDepth ? <DashboardEngineDepthPanel {...engineDepth} /> : null}
      <DashboardGuidancePanel {...guidance} />
      <DashboardIssueReportPanel {...issueReport} />
      {runReview ? <DashboardRunReviewPanel {...runReview} /> : null}
      <DashboardStatusPanels {...statusPanels} />
      <TakeoffSnapshotPanel {...takeoffSnapshot} />
    </div>
  );
}
