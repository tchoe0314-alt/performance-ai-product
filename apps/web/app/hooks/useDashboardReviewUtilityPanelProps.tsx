import { useMemo } from "react";
import type { ComponentProps, Dispatch, SetStateAction } from "react";

import { AnalysisPanel } from "../components/AnalysisPanel";
import { DashboardDetailsPanel } from "../components/DashboardDetailsPanel";
import { LayersPanel } from "../components/LayersPanel";
import { ModelReviewPanel } from "../components/ModelReviewPanel";
import { SelectedObjectInspectorPanel } from "../components/SelectedObjectInspectorPanel";
import { WorkspaceSettingsPanel } from "../components/WorkspaceSettingsPanel";
import type { BuildingPlacement, Issue, SourceConfidenceEntry } from "../types";
import {
  getObjectDimensionsLabel,
  getObjectDisplayType,
  getObjectEditBlocker,
  getObjectLayerLabel,
  getObjectReviewLabel,
  getObjectSourceLabel,
  normalizeGeometryPoints,
} from "../utils/objectGeometry";
import type { DisciplineToggle } from "../types";

type ModelReviewPanelProps = ComponentProps<typeof ModelReviewPanel>;
type DashboardDetailsPanelProps = ComponentProps<typeof DashboardDetailsPanel>;
type LayersPanelProps = ComponentProps<typeof LayersPanel>;
type AnalysisPanelProps = ComponentProps<typeof AnalysisPanel>;
type WorkspaceSettingsPanelProps = ComponentProps<typeof WorkspaceSettingsPanel>;

type AccessAnalysisIssue = {
  id: string;
  message: string;
};

type UseDashboardReviewUtilityPanelPropsInput = {
  previewMode: ModelReviewPanelProps["previewMode"];
  previewQuality: ModelReviewPanelProps["previewQuality"] & WorkspaceSettingsPanelProps["previewQuality"];
  hasGradingSurface: boolean;
  hasHardSystemBlock: boolean;
  placedObjectCount: number;
  issues: Issue[];
  analysisIssues: AccessAnalysisIssue[];
  roads: boolean;
  utilities: boolean;
  hasBasinPlaced: boolean;
  buildingPlacements: BuildingPlacement[];
  selectedBuilding: BuildingPlacement | null;
  sourceConfidenceByObjectId: Map<string, SourceConfidenceEntry>;
  objectManagerStatusMessage: string;
  objectClipboardCount: number;
  activePlacementId: string | null;
  onActivePlacementIdChange: Dispatch<SetStateAction<string | null>>;
  onReportObjectActionBlocker: (message: string) => void;
  onUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  onToggleBuildingLock: (id: string) => void;
  onUpdateObjectVertex: ComponentProps<typeof SelectedObjectInspectorPanel>["onUpdateVertex"];
  onInsertObjectVertex: ComponentProps<typeof SelectedObjectInspectorPanel>["onInsertVertex"];
  onDeleteObjectVertex: ComponentProps<typeof SelectedObjectInspectorPanel>["onDeleteVertex"];
  onSnapObjectVertexToNearestEndpoint: ComponentProps<typeof SelectedObjectInspectorPanel>["onSnapVertex"];
  onAlignObjectVertexToPrevious: ComponentProps<typeof SelectedObjectInspectorPanel>["onAlignVertex"];
  onObjectManagerSelect: (id: string) => void;
  onPlacementModeEnabledChange: Dispatch<SetStateAction<boolean>>;
  onFocusObjectIdChange: Dispatch<SetStateAction<string | null>>;
  onCloseSidePanel: () => void;
  onObjectManagerCopy: ComponentProps<typeof SelectedObjectInspectorPanel>["onCopy"];
  onObjectManagerPaste: ComponentProps<typeof SelectedObjectInspectorPanel>["onPaste"];
  onObjectManagerTransform: ComponentProps<typeof SelectedObjectInspectorPanel>["onTransform"];
  onObjectManagerDelete: ComponentProps<typeof SelectedObjectInspectorPanel>["onDelete"];
  previewLayers: LayersPanelProps["layers"];
  onPreviewLayersChange: LayersPanelProps["onLayersChange"];
  systemCompleteCount: number;
  blockedSystemCount: number;
  drainageIssueApplyLabel: (issue: Issue) => string | null;
  canApplyDrainageIssue: (issue: Issue) => boolean;
  onApplyDrainageIssue: (issue: Issue) => void;
  onAnalyzeSiteAccess: () => void;
  onOpenDashboard: () => void;
  leftSidebarOpen: boolean;
  assistedEnabled: boolean;
  sidebarReleaseStatus: string;
  standardsStatus: string;
  disciplineToggles: DisciplineToggle[];
  onOpenStandards: () => void;
  onOpenDeliverables: () => void;
};

export function useDashboardReviewUtilityPanelProps({
  previewMode,
  previewQuality,
  hasGradingSurface,
  hasHardSystemBlock,
  placedObjectCount,
  issues,
  analysisIssues,
  roads,
  utilities,
  hasBasinPlaced,
  buildingPlacements,
  selectedBuilding,
  sourceConfidenceByObjectId,
  objectManagerStatusMessage,
  objectClipboardCount,
  activePlacementId,
  onActivePlacementIdChange,
  onReportObjectActionBlocker,
  onUpdateBuilding,
  onToggleBuildingLock,
  onUpdateObjectVertex,
  onInsertObjectVertex,
  onDeleteObjectVertex,
  onSnapObjectVertexToNearestEndpoint,
  onAlignObjectVertexToPrevious,
  onObjectManagerSelect,
  onPlacementModeEnabledChange,
  onFocusObjectIdChange,
  onCloseSidePanel,
  onObjectManagerCopy,
  onObjectManagerPaste,
  onObjectManagerTransform,
  onObjectManagerDelete,
  previewLayers,
  onPreviewLayersChange,
  systemCompleteCount,
  blockedSystemCount,
  drainageIssueApplyLabel,
  canApplyDrainageIssue,
  onApplyDrainageIssue,
  onAnalyzeSiteAccess,
  onOpenDashboard,
  leftSidebarOpen,
  assistedEnabled,
  sidebarReleaseStatus,
  standardsStatus,
  disciplineToggles,
  onOpenStandards,
  onOpenDeliverables,
}: UseDashboardReviewUtilityPanelPropsInput) {
  const modelReviewPanelProps = useMemo<ModelReviewPanelProps>(() => ({
    previewMode,
    previewQuality,
    hasGradingSurface,
    hasHardSystemBlock,
    placedObjectCount,
    issueCount: issues.length + analysisIssues.length,
  }), [analysisIssues.length, hasGradingSurface, hasHardSystemBlock, issues.length, placedObjectCount, previewMode, previewQuality]);

  const detailsPanelProps = useMemo<DashboardDetailsPanelProps>(() => ({
    profileRows: [
      { label: "Road profiles", value: roads ? "Review" : "No generated roads" },
      { label: "Pipe profiles", value: utilities ? "Review" : "No generated pipes" },
      { label: "Basin sections", value: hasBasinPlaced ? "Available" : "Needs basin" },
      {
        label: "ADA paths",
        value: buildingPlacements.some((item) => item.type === "sidewalk") ? "Review" : "Needs paths",
      },
    ],
    selectedInspector: (
      <SelectedObjectInspectorPanel
        selectedBuilding={selectedBuilding}
        confidenceEntry={selectedBuilding ? sourceConfidenceByObjectId.get(selectedBuilding.id) : null}
        objectManagerStatusMessage={objectManagerStatusMessage}
        objectClipboardCount={objectClipboardCount}
        displayType={selectedBuilding ? getObjectDisplayType(selectedBuilding) : ""}
        reviewLabel={selectedBuilding ? getObjectReviewLabel(selectedBuilding) : ""}
        sourceLabel={selectedBuilding ? getObjectSourceLabel(selectedBuilding) : ""}
        layerLabel={selectedBuilding ? getObjectLayerLabel(selectedBuilding) : ""}
        dimensionsLabel={selectedBuilding ? getObjectDimensionsLabel(selectedBuilding) : ""}
        editableGeometry={selectedBuilding ? normalizeGeometryPoints(selectedBuilding.geometry) : undefined}
        editBlocked={selectedBuilding ? Boolean(getObjectEditBlocker(selectedBuilding, "resize")) : false}
        onRename={(item, value) => {
          const blocker = getObjectEditBlocker(item, "rename");
          if (blocker) {
            onReportObjectActionBlocker(blocker);
            return;
          }
          onUpdateBuilding(item.id, { label: value });
        }}
        onToggleLock={(item) => onToggleBuildingLock(item.id)}
        onToggleHidden={(item) =>
          onUpdateBuilding(item.id, {
            meta: {
              ...(item.meta ?? {}),
              ui_hidden: !Boolean(item.meta?.ui_hidden),
            },
          })
        }
        onUpdateObject={(item, updates) => onUpdateBuilding(item.id, updates)}
        onUpdateVertex={onUpdateObjectVertex}
        onInsertVertex={onInsertObjectVertex}
        onDeleteVertex={onDeleteObjectVertex}
        onSnapVertex={onSnapObjectVertexToNearestEndpoint}
        onAlignVertex={onAlignObjectVertexToPrevious}
        onMove={(item) => {
          onObjectManagerSelect(item.id);
          onPlacementModeEnabledChange(true);
        }}
        onFocus={(item) => {
          onFocusObjectIdChange(item.id);
          onCloseSidePanel();
        }}
        onCopy={onObjectManagerCopy}
        onPaste={onObjectManagerPaste}
        onTransform={onObjectManagerTransform}
        onDelete={onObjectManagerDelete}
      />
    ),
    objects: buildingPlacements,
    activePlacementId,
    onSelectObject: onActivePlacementIdChange,
  }), [
    activePlacementId,
    buildingPlacements,
    hasBasinPlaced,
    objectClipboardCount,
    objectManagerStatusMessage,
    onActivePlacementIdChange,
    onCloseSidePanel,
    onAlignObjectVertexToPrevious,
    onDeleteObjectVertex,
    onFocusObjectIdChange,
    onInsertObjectVertex,
    onObjectManagerCopy,
    onObjectManagerDelete,
    onObjectManagerPaste,
    onObjectManagerSelect,
    onObjectManagerTransform,
    onPlacementModeEnabledChange,
    onReportObjectActionBlocker,
    onSnapObjectVertexToNearestEndpoint,
    onToggleBuildingLock,
    onUpdateBuilding,
    onUpdateObjectVertex,
    roads,
    selectedBuilding,
    sourceConfidenceByObjectId,
    utilities,
  ]);

  const layersPanelProps = useMemo<LayersPanelProps>(() => ({
    layers: previewLayers,
    onLayersChange: onPreviewLayersChange,
  }), [onPreviewLayersChange, previewLayers]);

  const analysisPanelProps = useMemo<AnalysisPanelProps>(() => ({
    modelIssueCount: issues.length,
    accessIssueCount: analysisIssues.length,
    systemsCompleteCount: systemCompleteCount,
    blockedSystemCount,
    issues: [
      ...issues.map((issue, index) => {
        const applyLabel = drainageIssueApplyLabel(issue) ?? undefined;
        return {
          id: `issue-${index}`,
          severity: issue.severity,
          message: issue.message,
          code: issue.code,
          applyLabel,
          canApply: applyLabel ? canApplyDrainageIssue(issue) : false,
          onApply: applyLabel ? () => onApplyDrainageIssue(issue) : undefined,
        };
      }),
      ...analysisIssues.map((issue) => ({
        id: issue.id,
        message: issue.message,
        severity: "warning" as const,
      })),
    ],
    onRunAccessAnalysis: onAnalyzeSiteAccess,
    onOpenDashboard,
  }), [
    analysisIssues,
    blockedSystemCount,
    canApplyDrainageIssue,
    drainageIssueApplyLabel,
    issues,
    onAnalyzeSiteAccess,
    onApplyDrainageIssue,
    onOpenDashboard,
    systemCompleteCount,
  ]);

  const workspaceSettingsPanelProps = useMemo<WorkspaceSettingsPanelProps>(() => ({
    previewQuality,
    leftSidebarOpen,
    assistedEnabled,
    releaseStatus: sidebarReleaseStatus,
    standardsStatus,
    disciplineToggles,
    onOpenStandards,
    onOpenDeliverables,
  }), [
    assistedEnabled,
    disciplineToggles,
    leftSidebarOpen,
    onOpenDeliverables,
    onOpenStandards,
    previewQuality,
    sidebarReleaseStatus,
    standardsStatus,
  ]);

  return {
    analysisPanelProps,
    detailsPanelProps,
    layersPanelProps,
    modelReviewPanelProps,
    workspaceSettingsPanelProps,
  };
}
