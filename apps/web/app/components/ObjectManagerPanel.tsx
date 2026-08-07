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
    <div className="space-y-4">
      <DrawCadToolsPanel {...cadTools} />
      <NeedsPlacementTray {...needsPlacement} />
      <SelectedObjectCard {...selectedObject} />
      {statusMessage ? (
        <p className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700" data-testid="object-manager-status">
          {statusMessage}
        </p>
      ) : null}

      <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="object-manager-panel">
        <ObjectManagerOverview {...overview} />
        <ObjectManagerHiddenState {...hiddenState} />
        <ObjectManagerListPanel {...objectList} />
        <ObjectManagerLayerControls {...layerControls} />
        <RecentChangesPanel {...recentChanges} />
        {selectedTools ? <ObjectManagerSelectedToolsPanel {...selectedTools} /> : null}
      </div>
    </div>
  );
}
