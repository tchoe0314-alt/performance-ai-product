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
  layerManagerOpen: boolean;
  previewLayers: PreviewLayerVisibility;
  selectedBuilding: BuildingPlacement | null | undefined;
  selectedObjectConfidence?: Parameters<typeof FloatingObjectInspector>[0]["selectedObjectConfidence"];
  moveEditFeedback?: string;
  previewInteraction: PreviewPanelProps["previewInteraction"];
  denseConceptActive: boolean;
  sidePanelVisible: boolean;
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
  layerManagerOpen,
  previewLayers,
  selectedBuilding,
  selectedObjectConfidence,
  moveEditFeedback,
  previewInteraction,
  denseConceptActive,
  sidePanelVisible,
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
  return (
    <main data-testid="workspace-canvas-shell" className="absolute inset-0 min-h-0 min-w-0 overflow-hidden">
      <div className="absolute inset-0 min-h-0 min-w-0 overflow-hidden">
        <div
          data-testid="site-status"
          className={`pointer-events-none absolute left-[112px] top-4 z-30 rounded-full border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] shadow-sm backdrop-blur-xl max-lg:left-4 max-lg:top-4 ${
            siteScaleLocked
              ? "border-emerald-200 bg-emerald-50/90 text-emerald-700"
              : "border-amber-200 bg-amber-50/90 text-amber-700"
          }`}
        >
          {siteScaleLocked ? "Site Locked" : "Site Not Locked"}
        </div>
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
          {selectedBuilding && !(previewInteraction === "edit" && activeWorkflowKey === "draw") ? (
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
            active={denseConceptActive}
            sidePanelVisible={sidePanelVisible}
            rightRailCollapsed={rightRailCollapsed}
            objectCount={denseConceptObjectCount}
            onEditObjects={() => onOpenPanel("objects")}
            onGenerate={() => onOpenPanel("generate")}
            onDeliver={() => onOpenPanel("deliverables")}
            onHighQuality={() => onPreviewQualitySelect("high")}
          />
          <div
            data-testid="workspace-canvas-frame"
            className={`absolute inset-0 z-0 h-full w-full overflow-hidden lg:left-[112px] lg:w-auto ${
              rightRailCollapsed
                ? "lg:right-0"
                : sidePanelForRender === "deliverables"
                  ? "lg:right-[784px]"
                  : "lg:right-[408px]"
            }`}
            style={{ height: "100%" }}
          >
            <div className="h-full w-full">
              <PreviewPanel {...previewPanelProps} />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
