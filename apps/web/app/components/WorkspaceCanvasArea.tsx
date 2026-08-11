import type { SidePanelKey } from "../utils/workspaceShell";
import { FloatingLayerManager, type PreviewLayerVisibility } from "./FloatingLayerManager";
import PreviewPanel from "./PreviewPanel";
import type { PreviewPanelProps } from "./previewPanelTypes";

type WorkspaceCanvasAreaProps = {
  siteScaleLocked: boolean;
  sidebarVisible: boolean;
  rightRailCollapsed: boolean;
  sidePanelForRender: SidePanelKey | null;
  previewSessionVersion: number;
  layerManagerOpen: boolean;
  previewLayers: PreviewLayerVisibility;
  previewPanelProps: PreviewPanelProps;
  onOpenPanel: (panel: SidePanelKey) => void;
  onCloseLayerManager: () => void;
  onApplyLayerPreset: (layers: PreviewLayerVisibility) => void;
  onToggleLayer: (key: keyof PreviewLayerVisibility, visible: boolean) => void;
};

export function WorkspaceCanvasArea({
  siteScaleLocked,
  sidebarVisible,
  rightRailCollapsed,
  sidePanelForRender,
  previewSessionVersion,
  layerManagerOpen,
  previewLayers,
  previewPanelProps,
  onOpenPanel,
  onCloseLayerManager,
  onApplyLayerPreset,
  onToggleLayer,
}: WorkspaceCanvasAreaProps) {
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
