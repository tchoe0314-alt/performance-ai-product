import type { ComponentProps, Dispatch, SetStateAction } from "react";

import { WorkspaceCanvasArea } from "../components/WorkspaceCanvasArea";
import type { PreviewPanelProps } from "../components/previewPanelTypes";
import type { BuildingPlacement, ProjectRecord } from "../types";
import type { RecentChange } from "../utils/dashboardTypes";

type WorkspaceCanvasAreaProps = ComponentProps<typeof WorkspaceCanvasArea>;
type AiRealismEvent = Parameters<NonNullable<PreviewPanelProps["onAiRealismChange"]>>[0];

type SelectedAccessIssue = {
  buildingId: string;
  accessId: string;
  pathId: string;
} | null;

type UseDashboardCanvasAreaPropsInput = Omit<WorkspaceCanvasAreaProps, "projectName" | "previewPanelProps"> & {
  authToken?: string | null;
  currentProject: ProjectRecord | null;
  previewReview: PreviewPanelProps["previewReview"];
  onRefreshPreview: PreviewPanelProps["onRefreshPreview"];
  busy: boolean;
  planPreviewUrl: string;
  planPreviewProjectId?: string | null;
  projectId: string;
  previewMode: PreviewPanelProps["previewMode"];
  previewQuality: PreviewPanelProps["previewQuality"];
  canvasPreviewInteraction: PreviewPanelProps["previewInteraction"];
  draftingWorkspaceActive: boolean;
  systemStatuses: PreviewPanelProps["systemStatuses"];
  hasTerrainSource: boolean;
  hasSourceBackedSurfaceEvidence: boolean;
  hasBasinPlaced: boolean;
  siteTooLargeForGrading: boolean;
  hasHardSystemBlock: boolean;
  hasBackendResult: boolean;
  placedObjectCount: number;
  placementModeEnabled: boolean;
  activePlacementId: string | null;
  onViewportCenter: PreviewPanelProps["onViewportCenter"];
  externalRectUndo: PreviewPanelProps["externalRectUndo"];
  onPlaceBuilding: PreviewPanelProps["onPlaceBuilding"];
  onPlaceObject: PreviewPanelProps["onPlaceObject"];
  onCreateCustomGeometry: PreviewPanelProps["onCreateCustomGeometry"];
  onCreateSiteBoundary: NonNullable<PreviewPanelProps["onCreateSiteBoundary"]>;
  onUnlockSite: NonNullable<PreviewPanelProps["onUnlockSite"]>;
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects: PreviewPanelProps["cadEntityPreviewObjects"];
  suggestedPlacements: BuildingPlacement[];
  selectedObjectIds: string[];
  focusDetectedId: string | null;
  onFocusDetectedIdChange: Dispatch<SetStateAction<string | null>>;
  focusObjectId: string | null;
  onFocusObjectIdChange: Dispatch<SetStateAction<string | null>>;
  lotWidth: number;
  lotHeight: number;
  onViewportFootprint: PreviewPanelProps["onViewportFootprint"];
  onUpdateBuilding: PreviewPanelProps["onUpdateBuilding"];
  onDetectedPlacementsChange: Dispatch<SetStateAction<BuildingPlacement[]>>;
  onPersistDetectedPlacements: (placements: BuildingPlacement[]) => void;
  analysisPaths: PreviewPanelProps["analysisPaths"];
  selectedAccessIssue: SelectedAccessIssue;
  analysisFocusLocked: boolean;
  onAnalysisSelectedIssueIdChange: Dispatch<SetStateAction<string | null>>;
  onAnalysisFocusLockedChange: Dispatch<SetStateAction<boolean>>;
  onRemoveBuilding: PreviewPanelProps["onRemoveBuilding"];
  onRestoreBuilding: NonNullable<PreviewPanelProps["onRestoreBuilding"]>;
  onSelectBuilding: PreviewPanelProps["onSelectBuilding"];
  onOpenObjectInspector: NonNullable<PreviewPanelProps["onOpenObjectInspector"]>;
  onSelectObjects: NonNullable<PreviewPanelProps["onSelectObjects"]>;
  onSetPreviewMode: PreviewPanelProps["onSetPreviewMode"];
  onSetPreviewInteraction: PreviewPanelProps["onSetPreviewInteraction"];
  onSetPreviewQuality: PreviewPanelProps["onSetPreviewQuality"];
  onDrawingActiveChange: NonNullable<PreviewPanelProps["onDrawingActiveChange"]>;
  onRecordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  onPushRecoveryMessage: (message: string) => void;
  previewRefreshing: boolean;
  previewRefreshNote: string | null;
  preview3DEffectiveItems: PreviewPanelProps["preview3DEffectiveItems"];
  usingAnnotation3D: boolean;
  hasGradingSurface: boolean;
  onPreviewFullscreenOpenChange: Dispatch<SetStateAction<boolean>>;
  previewFullscreenOpen: boolean;
  planPreviewAnnotations: PreviewPanelProps["planPreviewAnnotations"];
  selectedIssueLabel: string;
  showMeasurements: boolean;
  showCalculations: boolean;
  measurementOverlayStats: PreviewPanelProps["measurementOverlayStats"];
  calculationOverlayStats: PreviewPanelProps["calculationOverlayStats"];
  gradingEarthworkUx: PreviewPanelProps["gradingEarthworkUx"];
  geocode: PreviewPanelProps["geocode"];
  mapScaleFtPerPx: PreviewPanelProps["mapScaleFtPerPx"];
  mapScaleSource: PreviewPanelProps["mapScaleSource"];
  siteRotationDeg: number;
  showSiteBounds: boolean;
  siteDrawRequest: number;
  gradingBlocker: PreviewPanelProps["gradingBlocker"];
  fitToSiteRequest: number;
  mapCenterRequest: number;
  alignToRoadRequest: number;
  onMapCenter: PreviewPanelProps["onMapCenter"];
  siteLocked: boolean;
  onLockSite: NonNullable<PreviewPanelProps["onLockSite"]>;
  stormHydrologyOverlay: PreviewPanelProps["stormHydrologyOverlay"];
  sourceContextBadges: PreviewPanelProps["sourceContextBadges"];
  onSiteRotationDegChange: Dispatch<SetStateAction<number>>;
  onSiteRotationInputChange: Dispatch<SetStateAction<string>>;
  onScheduleRotationSave: (value: number) => void;
  surveyPoints: PreviewPanelProps["surveyPoints"];
  onMapScaleFtPerPxChange: Dispatch<SetStateAction<number | null>>;
  onMapScaleSourceChange: Dispatch<SetStateAction<"mapbox" | "manual" | "approximate">>;
  onScheduleScaleSave: (ftPerPx: number, source: "mapbox") => void;
  mapDebugOverlay: boolean;
  cadToolRequest: PreviewPanelProps["cadToolRequest"];
};

export function useDashboardCanvasAreaProps({
  authToken,
  currentProject,
  previewReview,
  onRefreshPreview,
  busy,
  planPreviewUrl,
  planPreviewProjectId,
  projectId,
  previewMode,
  canvasPreviewInteraction,
  draftingWorkspaceActive,
  previewQuality,
  systemStatuses,
  hasTerrainSource,
  hasSourceBackedSurfaceEvidence,
  hasBasinPlaced,
  siteTooLargeForGrading,
  hasHardSystemBlock,
  hasBackendResult,
  placedObjectCount,
  placementModeEnabled,
  activePlacementId,
  onViewportCenter,
  externalRectUndo,
  onPlaceBuilding,
  onPlaceObject,
  onCreateCustomGeometry,
  onCreateSiteBoundary,
  onUnlockSite,
  buildingPlacements,
  cadEntityPreviewObjects,
  suggestedPlacements,
  selectedObjectIds,
  focusDetectedId,
  onFocusDetectedIdChange,
  focusObjectId,
  onFocusObjectIdChange,
  lotWidth,
  lotHeight,
  onViewportFootprint,
  onUpdateBuilding,
  onDetectedPlacementsChange,
  onPersistDetectedPlacements,
  analysisPaths,
  selectedAccessIssue,
  analysisFocusLocked,
  onAnalysisSelectedIssueIdChange,
  onAnalysisFocusLockedChange,
  onRemoveBuilding,
  onRestoreBuilding,
  onSelectBuilding,
  onOpenObjectInspector,
  onSelectObjects,
  onSetPreviewMode,
  onSetPreviewInteraction,
  onSetPreviewQuality,
  onDrawingActiveChange,
  onRecordRecentChange,
  onPushRecoveryMessage,
  previewRefreshing,
  previewRefreshNote,
  preview3DEffectiveItems,
  usingAnnotation3D,
  hasGradingSurface,
  onPreviewFullscreenOpenChange,
  previewFullscreenOpen,
  planPreviewAnnotations,
  selectedIssueLabel,
  showMeasurements,
  showCalculations,
  measurementOverlayStats,
  calculationOverlayStats,
  gradingEarthworkUx,
  geocode,
  mapScaleFtPerPx,
  mapScaleSource,
  siteRotationDeg,
  showSiteBounds,
  siteDrawRequest,
  gradingBlocker,
  fitToSiteRequest,
  mapCenterRequest,
  alignToRoadRequest,
  onMapCenter,
  siteLocked,
  onLockSite,
  stormHydrologyOverlay,
  sourceContextBadges,
  onSiteRotationDegChange,
  onSiteRotationInputChange,
  onScheduleRotationSave,
  surveyPoints,
  onMapScaleFtPerPxChange,
  onMapScaleSourceChange,
  onScheduleScaleSave,
  mapDebugOverlay,
  cadToolRequest,
  ...canvasAreaProps
}: UseDashboardCanvasAreaPropsInput): WorkspaceCanvasAreaProps {
  const handleAiRealismChange = (event: AiRealismEvent) => {
    onRecordRecentChange({
      type: "ai_realism_recorded",
      label:
        event.type === "generated"
          ? "AI visualization regenerated"
          : event.type === "stale"
            ? "AI visualization stale"
            : "AI visualization blocked",
      detail: event.detail,
      undoBlockedReason: "AI visualization is a visual preview record. Regenerate from the current review layout instead of undoing it.",
    });
    onPushRecoveryMessage(`${event.detail} AI visualization remains visual preview only.`);
  };

  return {
    ...canvasAreaProps,
    previewPanelProps: {
      authToken,
      previewReview,
      onRefreshPreview,
      busy,
      planPreviewUrl,
      planPreviewProjectId,
      currentProjectId: projectId || currentProject?.project_id || null,
      previewMode,
      previewInteraction: canvasPreviewInteraction,
      draftingWorkspaceActive,
      previewQuality,
      systemStatuses,
      hasTerrainSource,
      hasSourceBackedSurfaceEvidence,
      hasBasinPlaced,
      siteTooLargeForGrading,
      hasHardSystemBlock,
      hasGeneratedPlan: Boolean(planPreviewUrl && hasBackendResult),
      placementMode: placementModeEnabled,
      onViewportCenter,
      externalRectUndo,
      onPlaceBuilding,
      onPlaceObject,
      onCreateCustomGeometry,
      onCreateSiteBoundary,
      onUnlockSite,
      buildingPlacements,
      cadEntityPreviewObjects,
      suggestedPlacements,
      selectedBuildingId: activePlacementId,
      selectedObjectIds,
      focusDetectedId,
      onClearFocusDetected: () => onFocusDetectedIdChange(null),
      focusObjectId,
      onClearFocusObject: () => onFocusObjectIdChange(null),
      lotWidth,
      lotHeight,
      onViewportFootprint,
      onUpdateBuilding,
      onUpdateSuggested: (id, updates) => {
        onDetectedPlacementsChange((prev) => {
          const nextDetected = prev.map((item) => (item.id === id ? { ...item, ...updates } : item));
          onPersistDetectedPlacements(nextDetected);
          return nextDetected;
        });
      },
      analysisPaths,
      analysisHighlight: selectedAccessIssue
        ? {
            buildingId: selectedAccessIssue.buildingId,
            accessId: selectedAccessIssue.accessId,
            pathId: selectedAccessIssue.pathId,
          }
        : null,
      analysisFocusLocked,
      onClearHighlights: () => {
        onAnalysisSelectedIssueIdChange(null);
        onAnalysisFocusLockedChange(false);
      },
      onResetView: () => {
        onAnalysisSelectedIssueIdChange(null);
        onFocusDetectedIdChange(null);
        onAnalysisFocusLockedChange(false);
      },
      onRemoveBuilding,
      onRestoreBuilding,
      onSelectBuilding,
      onOpenObjectInspector,
      onSelectObjects,
      onSetPreviewMode,
      onSetPreviewInteraction,
      onSetPreviewQuality,
      onDrawingActiveChange,
      onAiRealismChange: handleAiRealismChange,
      previewRefreshing,
      previewRefreshNote,
      preview3DEffectiveItems,
      usingAnnotation3D,
      hasGradingSurface,
      onOpenFullscreen: () => onPreviewFullscreenOpenChange(true),
      previewFullscreenOpen,
      onCloseFullscreen: () => onPreviewFullscreenOpenChange(false),
      planPreviewAnnotations,
      selectedIssueLabel,
      showMeasurements,
      showCalculations,
      measurementOverlayStats,
      calculationOverlayStats,
      gradingEarthworkUx,
      geocode,
      mapScaleFtPerPx,
      mapScaleSource,
      siteRotationDeg,
      showSiteBounds,
      siteDrawRequest,
      gradingBlocker,
      fitToSiteRequest,
      mapCenterRequest,
      alignToRoadRequest,
      onMapCenter,
      siteLocked,
      onLockSite,
      stormHydrologyOverlay,
      sourceContextBadges,
      onSetSiteRotationDeg: (value) => {
        onSiteRotationDegChange(value);
        onSiteRotationInputChange(String(value));
        onScheduleRotationSave(value);
      },
      surveyPoints,
      onMapScaleUpdate: ({ ftPerPx, source }) => {
        if (!Number.isFinite(ftPerPx) || ftPerPx <= 0) return;
        onMapScaleFtPerPxChange(ftPerPx);
        onMapScaleSourceChange(source);
        if (siteLocked) return;
        onScheduleScaleSave(ftPerPx, source);
      },
      debugStats: {
        enabled: mapDebugOverlay,
        projectId: projectId || currentProject?.project_id || "",
        canonicalCount: buildingPlacements.length,
        placedCount: placedObjectCount,
        previewImageActive: Boolean(planPreviewUrl),
        placementMode: placementModeEnabled,
        selectedId: activePlacementId,
      },
      cadToolRequest,
    },
  };
}
