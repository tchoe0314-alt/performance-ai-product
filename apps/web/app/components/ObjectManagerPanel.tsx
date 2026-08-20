import type { ComponentProps } from "react";
import { DrawCadToolsPanel } from "./DrawCadToolsPanel";
import { NeedsPlacementTray } from "./NeedsPlacementTray";
import { ObjectManagerHiddenState } from "./ObjectManagerHiddenState";
import { ObjectManagerLayerControls } from "./ObjectManagerLayerControls";
import { ObjectManagerListPanel } from "./ObjectManagerListPanel";
import { ObjectManagerOverview } from "./ObjectManagerOverview";
import { ObjectManagerSelectedToolsPanel } from "./ObjectManagerSelectedToolsPanel";
import { RecentChangesPanel } from "./RecentChangesPanel";
import { SelectedObjectCard } from "./SelectedObjectCard";
import { DisclosurePanel } from "./ui";

export type ObjectManagerPanelProps = {
  cadTools: ComponentProps<typeof DrawCadToolsPanel>;
  needsPlacement: ComponentProps<typeof NeedsPlacementTray>;
  selectedObject: ComponentProps<typeof SelectedObjectCard>;
  overview: ComponentProps<typeof ObjectManagerOverview>;
  hiddenState: ComponentProps<typeof ObjectManagerHiddenState>;
  layerControls: ComponentProps<typeof ObjectManagerLayerControls>;
  statusMessage: string;
  recentChanges: ComponentProps<typeof RecentChangesPanel>;
  selectedTools: ComponentProps<typeof ObjectManagerSelectedToolsPanel> | null;
  objectList: ComponentProps<typeof ObjectManagerListPanel>;
};

export function ObjectManagerPanel({
  cadTools,
  needsPlacement,
  selectedObject,
  overview,
  hiddenState,
  layerControls,
  statusMessage,
  recentChanges,
  selectedTools,
  objectList,
}: ObjectManagerPanelProps) {
  return (
    <div className="space-y-3" data-testid="clean-draw-panel">
      <DrawCadToolsPanel {...cadTools} />
      <NeedsPlacementTray {...needsPlacement} />
      {selectedObject.selectedObject ? (
        <div data-testid="preview-object-manager">
          <SelectedObjectCard {...selectedObject} />
        </div>
      ) : null}
      {statusMessage ? (
        <p className="rounded-[7px] border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600" data-testid="object-manager-status">
          {statusMessage}
        </p>
      ) : null}

      <DisclosurePanel
        defaultOpen={!selectedObject.selectedObject && overview.totalCount > 0}
        title="Objects"
        subtitle="Select, focus, rename, hide, or delete"
        status={overview.totalCount}
        testId="object-manager-panel"
      >
        <div data-testid="preview-object-manager-list">
          <ObjectManagerOverview {...overview} />
          <ObjectManagerHiddenState {...hiddenState} />
          <ObjectManagerListPanel {...objectList} />
        </div>
      </DisclosurePanel>
      <DisclosurePanel title="Layers" subtitle="Visibility and drawing style" status="Optional" testId="object-manager-layers">
        <ObjectManagerLayerControls {...layerControls} />
      </DisclosurePanel>
      {selectedTools ? (
        <DisclosurePanel defaultOpen title="Modify" subtitle="Transform and edit the selected object" status="Selected">
          <ObjectManagerSelectedToolsPanel {...selectedTools} />
        </DisclosurePanel>
      ) : null}
      <DisclosurePanel
        title="Recent changes"
        subtitle="Undo or inspect draft actions"
        status={recentChanges.changes.length}
        testId="object-manager-recent-changes"
      >
        <RecentChangesPanel {...recentChanges} />
      </DisclosurePanel>
    </div>
  );
}
