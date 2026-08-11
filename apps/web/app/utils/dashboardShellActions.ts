import type { MutableRefObject } from "react";

import type { CadToolRequestForPreview } from "./dashboardTypes";
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "./performanceProbes";
import {
  workspaceModeByPanel,
  workspacePanelByMode,
  type SidePanelKey,
  type WorkspaceMode,
} from "./workspaceShell";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type PanelProbeRef = MutableRefObject<{
  label: string;
  panel: SidePanelKey | null;
  startedAt: number;
} | null>;

export function runDashboardOpenSidePanel({
  panel,
  panelOpenProbeRef,
  sidePanelCloseTimeoutRef,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setCadToolRequest,
  setLayerManagerOpen,
  setPlacementModeEnabled,
  setPreviewInteraction,
  setRightRailCollapsed,
}: {
  panel: SidePanelKey | null;
  panelOpenProbeRef: PanelProbeRef;
  sidePanelCloseTimeoutRef: MutableRefObject<number | null>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setCadToolRequest: StateSetter<CadToolRequestForPreview | null>;
  setLayerManagerOpen: StateSetter<boolean>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setRightRailCollapsed: StateSetter<boolean>;
}) {
  if (sidePanelCloseTimeoutRef.current !== null) {
    window.clearTimeout(sidePanelCloseTimeoutRef.current);
    sidePanelCloseTimeoutRef.current = null;
  }
  if (panel) {
    panelOpenProbeRef.current = {
      label: panel === "projects" ? "projects.drawer.open" : "panel.open",
      panel,
      startedAt: markCivoraInteraction(),
    };
  }
  setLayerManagerOpen(false);
  if (panel) {
    setRightRailCollapsed(false);
  }
  const drawAdjacentPanels: SidePanelKey[] = ["objects", "details", "layers", "model"];
  if (panel && !drawAdjacentPanels.includes(panel)) {
    setPlacementModeEnabled(false);
    setPreviewInteraction("static");
    setCadToolRequest({ id: Date.now() + Math.random(), tool: "select", silent: true });
  }
  setActiveSidePanel(panel);
  if (!panel) return;
  if (panel !== "chat" && panel !== "projects" && panel !== "trust") {
    setActiveWorkspaceMode(workspaceModeByPanel[panel]);
  }
}

export function runDashboardCloseSidePanel({
  activeSidePanel,
  panelCloseProbeRef,
  sidePanelCloseTimeoutRef,
  setActiveSidePanel,
  setRenderedSidePanel,
  setRightRailCollapsed,
  setSidePanelVisible,
}: {
  activeSidePanel: SidePanelKey | null;
  panelCloseProbeRef: PanelProbeRef;
  sidePanelCloseTimeoutRef: MutableRefObject<number | null>;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setRenderedSidePanel: StateSetter<SidePanelKey | null>;
  setRightRailCollapsed: StateSetter<boolean>;
  setSidePanelVisible: StateSetter<boolean>;
}) {
  if (sidePanelCloseTimeoutRef.current !== null) {
    window.clearTimeout(sidePanelCloseTimeoutRef.current);
  }
  panelCloseProbeRef.current = {
    label: activeSidePanel === "projects" ? "projects.drawer.close" : "panel.close",
    panel: activeSidePanel,
    startedAt: markCivoraInteraction(),
  };
  // Close intent must be committed together. Leaving either flag open lets the
  // panel-state effect interpret the transition as a new open request.
  setActiveSidePanel(null);
  setRightRailCollapsed(true);
  setSidePanelVisible(false);
  sidePanelCloseTimeoutRef.current = window.setTimeout(() => {
    setRenderedSidePanel(null);
    const probe = panelCloseProbeRef.current;
    if (probe) {
      measureCivoraInteractionAfterPaint(probe.label, probe.startedAt, { panel: probe.panel ?? "none" });
      panelCloseProbeRef.current = null;
    }
    sidePanelCloseTimeoutRef.current = null;
  }, 180);
}

export function runDashboardOpenPanelFromDrawer({
  panel,
  openSidePanel,
}: {
  panel: SidePanelKey;
  openSidePanel: (panel: SidePanelKey) => void;
}) {
  openSidePanel(panel);
}

export function runDashboardTriggerCadTool({
  label,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setCadToolRequest,
  setPreviewInteraction,
  setRightRailCollapsed,
  setStatusMessage,
  setWorkspaceChromeMinimized,
  tool,
}: {
  label: string;
  setActiveSidePanel: StateSetter<SidePanelKey | null>;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setCadToolRequest: StateSetter<CadToolRequestForPreview | null>;
  setPreviewInteraction: StateSetter<"static" | "edit">;
  setRightRailCollapsed: StateSetter<boolean>;
  setStatusMessage: (message: string) => void;
  setWorkspaceChromeMinimized: StateSetter<boolean>;
  tool: CadToolRequestForPreview["tool"];
}) {
  const startedAt = markCivoraInteraction();
  setActiveWorkspaceMode("canvas");
  setPreviewInteraction("edit");
  setWorkspaceChromeMinimized(true);
  // On compact screens the drawer would cover the drawing surface. Desktop
  // keeps the tool palette visible while the contextual HUD shifts clear of it.
  setRightRailCollapsed(typeof window !== "undefined" && window.innerWidth < 1024);
  setActiveSidePanel("objects");
  setCadToolRequest({ id: Date.now() + Math.random(), tool });
  setStatusMessage(`${label} tool selected. Use the canvas or command line for the next step.`);
  measureCivoraInteractionAfterPaint("draw.canvas.tool.click", startedAt, { tool, label });
}

export function runDashboardOpenWorkspaceMode({
  mode,
  openSidePanel,
  setActiveWorkspaceMode,
  setLeftSidebarOpen,
}: {
  mode: WorkspaceMode;
  openSidePanel: (panel: SidePanelKey) => void;
  setActiveWorkspaceMode: StateSetter<WorkspaceMode>;
  setLeftSidebarOpen: StateSetter<boolean>;
}) {
  const nextPanel = workspacePanelByMode[mode];
  setActiveWorkspaceMode(mode);
  if (typeof window !== "undefined" && window.innerWidth < 1024) {
    setLeftSidebarOpen(true);
    window.requestAnimationFrame(() => openSidePanel(nextPanel));
    return;
  }
  openSidePanel(nextPanel);
}
