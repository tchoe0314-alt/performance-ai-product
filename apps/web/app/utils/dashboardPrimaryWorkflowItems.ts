import {
  Box,
  FileText,
  Gauge,
  Layers,
  MapPinned,
  SlidersHorizontal,
} from "lucide-react";

import type { PrimaryWorkflowItem } from "./dashboardTypes";
import type { SidebarStatus, WorkspaceMode } from "./workspaceShell";
import type { EngineeringSystemKey, SystemStatus } from "./workflowConstants";

type DashboardPrimaryWorkflowItemsContext = {
  sidebarModeStatus: (mode: WorkspaceMode) => SidebarStatus;
  panelStatus: (panel: PrimaryWorkflowItem["panel"]) => SidebarStatus;
  siteScaleLocked: boolean;
  placedObjectCount: number;
  pendingPlacementCount: number;
  hasHardSystemBlock: boolean;
  controlsHealthStatus: SidebarStatus;
  systemStatuses: Record<EngineeringSystemKey, SystemStatus>;
  issueCount: number;
  backendResultPresent: boolean;
  exportBlockReason: string | null;
};

export function buildDashboardPrimaryWorkflowItems({
  sidebarModeStatus,
  panelStatus,
  siteScaleLocked,
  placedObjectCount,
  pendingPlacementCount,
  hasHardSystemBlock,
  controlsHealthStatus,
  systemStatuses,
  issueCount,
  backendResultPresent,
  exportBlockReason,
}: DashboardPrimaryWorkflowItemsContext): PrimaryWorkflowItem[] {
  return [
    {
      key: "setup",
      label: "Setup",
      caption: "Address, boundary, sources",
      panel: "site_existing",
      icon: MapPinned,
      status: sidebarModeStatus("setup"),
      metric: siteScaleLocked ? "Site locked" : "Needs boundary",
    },
    {
      key: "draw",
      label: "Draw",
      caption: "Canvas and drafting",
      panel: "objects",
      icon: Box,
      status: siteScaleLocked ? panelStatus("objects") : "review",
      metric: `${placedObjectCount} objects`,
    },
    {
      key: "objects",
      label: "Object Manager",
      caption: "Objects, layers, tools",
      panel: "objects",
      icon: Layers,
      status: panelStatus("objects"),
      metric: `${placedObjectCount} placed / ${pendingPlacementCount} pending`,
    },
    {
      key: "design",
      label: "Generate",
      caption: "Grading, storm, utilities",
      panel: "generate",
      icon: SlidersHorizontal,
      status: hasHardSystemBlock ? "block" : controlsHealthStatus,
      metric: `${Object.values(systemStatuses).filter((status) => status === "fresh").length} fresh`,
    },
    {
      key: "analyze",
      label: "Project Health",
      caption: "Issues, quantities, jobs",
      panel: "analysis",
      icon: Gauge,
      status: issueCount ? "review" : backendResultPresent ? "ok" : "idle",
      metric: `${issueCount} issue${issueCount === 1 ? "" : "s"}`,
    },
    {
      key: "deliver",
      label: "Deliver",
      caption: "Sheets and exports",
      panel: "deliverables",
      icon: FileText,
      status: sidebarModeStatus("deliver"),
      metric: exportBlockReason ? "Export needs input" : "Review package",
    },
  ];
}
