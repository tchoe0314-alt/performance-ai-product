import {
  AlertCircle,
  Crosshair,
  FileText,
  Gauge,
  Hand,
  Layers,
  MapPinned,
  MousePointer2,
  Move,
  Pencil,
  Ruler,
  SlidersHorizontal,
} from "lucide-react";

import type { WorkspaceToolbarTool } from "../components/WorkspaceCanvasChromePanel";
import type { PrimaryWorkflowKey } from "./dashboardTypes";
import type { SidePanelKey } from "./workspaceShell";

type ContextualToolbarTool = WorkspaceToolbarTool & {
  modes: PrimaryWorkflowKey[];
};

export function buildDashboardContextualToolbarTools({
  activePrimaryWorkflowKey,
  sidePanelForRender,
  siteScaleLocked,
  previewInteraction,
  showMeasurements,
  showCalculations,
  layerManagerOpen,
  onOpenPanel,
  onToggleSiteLock,
  onUnlockSite,
  onStartSiteBoundaryDraw,
  onSetPreviewInteraction,
  onToggleMeasurements,
  onToggleCalculations,
  onToggleLayerManager,
}: {
  activePrimaryWorkflowKey: PrimaryWorkflowKey;
  sidePanelForRender: SidePanelKey | null;
  siteScaleLocked: boolean;
  previewInteraction: string;
  showMeasurements: boolean;
  showCalculations: boolean;
  layerManagerOpen: boolean;
  onOpenPanel: (panel: SidePanelKey) => void;
  onToggleSiteLock: () => void;
  onUnlockSite: () => void;
  onStartSiteBoundaryDraw: () => void;
  onSetPreviewInteraction: (interaction: "static" | "edit") => void;
  onToggleMeasurements: () => void;
  onToggleCalculations: () => void;
  onToggleLayerManager: () => void;
}): WorkspaceToolbarTool[] {
  const tools: ContextualToolbarTool[] = [
    {
      label: "Address",
      icon: MapPinned,
      modes: ["setup", "draw"],
      action: () => onOpenPanel("site_existing"),
      active: sidePanelForRender === "site_existing",
    },
    {
      label: siteScaleLocked ? "Unlock" : "Lock site",
      icon: Crosshair,
      modes: ["setup", "draw"],
      action: siteScaleLocked ? onUnlockSite : onToggleSiteLock,
      active: siteScaleLocked,
      testId: "site-lock-toolbar",
    },
    {
      label: "Import",
      icon: FileText,
      modes: ["setup", "deliver"],
      action: () => onOpenPanel("import_survey"),
      active: sidePanelForRender === "import_survey",
    },
    {
      label: "Select",
      icon: MousePointer2,
      modes: ["draw", "design", "analyze", "deliver"],
      action: () => onSetPreviewInteraction("static"),
      active: previewInteraction === "static",
    },
    {
      label: "Pan",
      icon: Hand,
      modes: ["draw", "design", "analyze", "deliver"],
      action: () => onSetPreviewInteraction("static"),
      active: false,
    },
    {
      label: "Draw Site Boundary",
      icon: Crosshair,
      modes: ["setup", "draw"],
      action: onStartSiteBoundaryDraw,
      active: !siteScaleLocked && activePrimaryWorkflowKey === "draw",
      testId: "workspace-draw-site-boundary-shortcut",
    },
    {
      label: "Change Site Boundary",
      icon: Crosshair,
      modes: ["draw"],
      action: onUnlockSite,
      active: siteScaleLocked,
      testId: "change-site-boundary-toolbar",
    },
    {
      label: "Draw tools",
      icon: Pencil,
      modes: ["draw"],
      action: () => onOpenPanel("model"),
      active: activePrimaryWorkflowKey === "draw",
    },
    {
      label: "Modify",
      icon: Move,
      modes: ["setup", "draw"],
      action: () => onSetPreviewInteraction("edit"),
      active: previewInteraction === "edit",
      testId: "workspace-preview-interaction-edit",
    },
    {
      label: "Measure",
      icon: Ruler,
      modes: ["draw", "analyze"],
      action: onToggleMeasurements,
      active: showMeasurements,
    },
    {
      label: "Calcs",
      icon: Gauge,
      modes: ["analyze"],
      action: onToggleCalculations,
      active: showCalculations,
    },
    {
      label: "Snaps",
      icon: Crosshair,
      modes: ["draw"],
      action: () => onOpenPanel("model"),
      active: previewInteraction === "edit",
    },
    {
      label: "Layers",
      icon: Layers,
      modes: ["setup", "draw", "design", "analyze", "deliver"],
      action: onToggleLayerManager,
      active: layerManagerOpen,
    },
    {
      label: "Run",
      icon: SlidersHorizontal,
      modes: ["design", "analyze"],
      action: () => onOpenPanel("generate"),
      active: sidePanelForRender === "generate",
    },
    {
      label: "Issues",
      icon: AlertCircle,
      modes: ["analyze"],
      action: () => onOpenPanel("analysis"),
      active: sidePanelForRender === "analysis",
    },
    {
      label: "Sheets",
      icon: FileText,
      modes: ["deliver"],
      action: () => onOpenPanel("deliverables"),
      active: sidePanelForRender === "deliverables",
    },
  ];
  return tools.filter((tool) => tool.modes.includes(activePrimaryWorkflowKey));
}
