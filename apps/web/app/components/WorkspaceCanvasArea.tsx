import type { Dispatch, SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import type { PrimaryWorkflowItem } from "../utils/dashboardTypes";
import type { SidePanelKey } from "../utils/workspaceShell";
import { DenseConceptActionStrip } from "./DenseConceptActionStrip";
import { FloatingLayerManager, type PreviewLayerVisibility } from "./FloatingLayerManager";
import { FloatingObjectInspector } from "./FloatingObjectInspector";
import PreviewPanel from "./PreviewPanel";
import type { PreviewPanelProps } from "./previewPanelTypes";
import { WorkspaceCanvasChromePanel, type WorkspaceToolbarTool } from "./WorkspaceCanvasChromePanel";

type WorkspaceCanvasAreaProps = {
  siteScaleLocked: boolean;
  workspaceChromeHidden: boolean;
  sidebarVisible: boolean;
  rightRailCollapsed: boolean;
  sidePanelForRender: SidePanelKey | null;
  projectName: string;
  activeWorkflowKey: string;
  workflowItems: PrimaryWorkflowItem[];
  toolbarTools: WorkspaceToolbarTool[];
  previewMode: "2d" | "3d";
  previewQuality: "standard" | "high";
  previewSessionVersion: number;
  layerManagerOpen: boolean;
  previewLayers: PreviewLayerVisibility;
  selectedBuilding: BuildingPlacement | null | undefined;
  selectedObjectConfidence?: Parameters<typeof FloatingObjectInspector>[0]["selectedObjectConfidence"];
  moveEditFeedback?: string;
  previewInteraction: PreviewPanelProps["previewInteraction"];
  denseConceptActive: boolean;
  denseConceptObjectCount: number;
  previewPanelProps: PreviewPanelProps;
  onOpenPanel: (panel: SidePanelKey) => void;
  onMinimizeChrome: () => void;
  onPreviewModeSelect: (mode: "2d" | "3d") => void;
  onPreviewQualitySelect: (quality: "standard" | "high") => void;
  onSetRightRailCollapsed: Dispatch<SetStateAction<boolean>>;
  onCloseLayerManager: () => void;
  onApplyLayerPreset: (layers: PreviewLayerVisibility) => void;
  onToggleLayer: (key: keyof PreviewLayerVisibility, visible: boolean) => void;
  onEditSelectedObject: () => void;
  onFocusSelectedObject: () => void;
  onOpenSelectedObjectDetails: () => void;
};

export function WorkspaceCanvasArea({
  siteScaleLocked,
  workspaceChromeHidden,
  sidebarVisible,
  rightRailCollapsed,
  sidePanelForRender,
  projectName,
  activeWorkflowKey,
  workflowItems,
  toolbarTools,
  previewMode,
  previewQuality,
  previewSessionVersion,
  layerManagerOpen,
  previewLayers,
  selectedBuilding,
  selectedObjectConfidence,
  moveEditFeedback,
  previewInteraction,
  denseConceptActive,
  denseConceptObjectCount,
  previewPanelProps,
  onOpenPanel,
  onMinimizeChrome,
  onPreviewModeSelect,
  onPreviewQualitySelect,
  onSetRightRailCollapsed,
  onCloseLayerManager,
  onApplyLayerPreset,
  onToggleLayer,
  onEditSelectedObject,
  onFocusSelectedObject,
  onOpenSelectedObjectDetails,
}: WorkspaceCanvasAreaProps) {
  const floatingInspectorAllowed = !sidePanelForRender && rightRailCollapsed;
  const drawerOpen = !rightRailCollapsed && Boolean(sidePanelForRender);
  const drawerSize = sidePanelForRender === "deliverables" ? "wide" : "standard";

  return (
    <main
      data-testid="workspace-canvas-shell"
      data-site-locked={siteScaleLocked}
      className="pointer-events-none absolute inset-0 min-h-0 min-w-0 overflow-hidden"
    >
      <div className="absolute inset-0 min-h-0 min-w-0 overflow-hidden">
        <div className="contents">
          <WorkspaceCanvasChromePanel
            hidden={workspaceChromeHidden}
            sidebarVisible={sidebarVisible}
            rightRailCollapsed={rightRailCollapsed}
            projectName={projectName}
            activeWorkflowKey={activeWorkflowKey}
            workflowItems={workflowItems}
            toolbarTools={toolbarTools}
            previewMode={previewMode}
            previewQuality={previewQuality}
            onOpenPanel={onOpenPanel}
            onMinimize={onMinimizeChrome}
            onPreviewModeSelect={(mode) => {
              onPreviewModeSelect(mode);
              if (mode === "3d") {
                onSetRightRailCollapsed(true);
              }
            }}
            onPreviewQualitySelect={onPreviewQualitySelect}
          />
          {layerManagerOpen ? (
            <FloatingLayerManager
              layers={previewLayers}
              rightRailCollapsed={rightRailCollapsed}
              onClose={onCloseLayerManager}
              onApplyPreset={onApplyLayerPreset}
              onToggleLayer={onToggleLayer}
              onOpenFullDetails={() => onOpenPanel("layers")}
            />
          ) : null}
          {selectedBuilding && floatingInspectorAllowed && !(previewInteraction === "edit" && activeWorkflowKey === "draw") ? (
            <FloatingObjectInspector
              selectedBuilding={selectedBuilding}
              selectedObjectConfidence={selectedObjectConfidence}
              moveEditFeedback={moveEditFeedback}
              onEdit={onEditSelectedObject}
              onFocus={onFocusSelectedObject}
              onOpenDetails={onOpenSelectedObjectDetails}
            />
          ) : null}
          <DenseConceptActionStrip
            active={denseConceptActive && previewQuality === "standard"}
            previewMode={previewMode}
            rightRailCollapsed={rightRailCollapsed}
            objectCount={denseConceptObjectCount}
            onEditObjects={() => onOpenPanel("objects")}
            onGenerate={() => onOpenPanel("generate")}
            onDeliver={() => onOpenPanel("deliverables")}
            onHighQuality={() => onPreviewQualitySelect("high")}
          />
          <div
            data-testid="workspace-canvas-frame"
            data-drawer-state={drawerOpen ? "open" : "closed"}
            data-drawer-size={drawerSize}
            data-navigation-state={sidebarVisible ? "visible" : "hidden"}
            className="civora-workspace-canvas-frame pointer-events-auto absolute inset-y-0 z-0 overflow-hidden"
          >
            <div className="h-full w-full">
              <PreviewPanel key={previewSessionVersion} {...previewPanelProps} />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
