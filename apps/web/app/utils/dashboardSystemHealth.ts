import type { SystemStatus } from "./workflowConstants";

export type DashboardSystemHealthItem = {
  key: string;
  label: string;
  state: "blocked" | "complete" | "not_configured";
  detail: string;
};

const firstMatchingBlocker = (blockers: string[], pattern: RegExp) =>
  blockers.find((item) => pattern.test(item));

export const buildDashboardSystemHealthItems = ({
  canonicalWorkspaceBlockers,
  hasHardSystemBlock,
  hasTerrainSource,
  siteScaleLocked,
  siteTooLargeForGrading,
  systemStatuses,
}: {
  canonicalWorkspaceBlockers: string[];
  hasHardSystemBlock: boolean;
  hasTerrainSource: boolean;
  siteScaleLocked: boolean;
  siteTooLargeForGrading: boolean;
  systemStatuses: Record<string, SystemStatus>;
}): DashboardSystemHealthItem[] => {
  const dataBlocker = firstMatchingBlocker(canonicalWorkspaceBlockers, /source|standards|survey|terrain|address/i);
  const gradingBlocker = firstMatchingBlocker(canonicalWorkspaceBlockers, /terrain|survey|grading|site too large/i);
  const drainageBlocker = firstMatchingBlocker(canonicalWorkspaceBlockers, /outfall|basin|drainage|terrain|survey/i);
  const utilityBlocker = firstMatchingBlocker(canonicalWorkspaceBlockers, /utility|standards|source/i);
  return [
    {
      key: "data",
      label: "Data",
      state: dataBlocker ? "blocked" : siteScaleLocked || hasTerrainSource ? "complete" : "not_configured",
      detail: dataBlocker || (siteScaleLocked ? "Site locked" : "Needs site setup"),
    },
    {
      key: "roadway",
      label: "Roadway",
      state: systemStatuses.roads === "fresh" && systemStatuses.parking === "fresh" ? "complete" : "not_configured",
      detail: systemStatuses.roads === "fresh" ? "Complete" : "Not configured / not rendered",
    },
    {
      key: "grading",
      label: "Grading",
      state: gradingBlocker ? "blocked" : siteTooLargeForGrading ? "blocked" : systemStatuses.grading === "fresh" ? "complete" : "not_configured",
      detail: gradingBlocker || (siteTooLargeForGrading ? "Site too large" : systemStatuses.grading === "fresh" ? "Complete" : "Needs terrain/run"),
    },
    {
      key: "drainage",
      label: "Drainage",
      state: drainageBlocker || hasHardSystemBlock ? "blocked" : systemStatuses.drainage === "fresh" ? "complete" : "not_configured",
      detail: drainageBlocker || (hasHardSystemBlock ? "Review blockers" : systemStatuses.drainage === "fresh" ? "Complete" : "Needs basin/run"),
    },
    {
      key: "utilities",
      label: "Utilities",
      state: utilityBlocker || hasHardSystemBlock ? "blocked" : systemStatuses.utilities === "fresh" ? "complete" : "not_configured",
      detail: utilityBlocker || (hasHardSystemBlock ? "Needs input / review" : systemStatuses.utilities === "fresh" ? "Complete" : "Not configured / not rendered"),
    },
  ];
};
