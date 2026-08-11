import type { DrawMode } from "./cadToolTypes";

type PreviewMode = "2d" | "3d";
type PreviewInteraction = "static" | "edit";

type BuildPreviewInteractionStateOptions = {
  mapboxToken?: string;
  geocode?: { lat?: number | string | null; lng?: number | string | null } | null;
  buildingPlacementCount: number;
  suggestedPlacementCount: number;
  surveyPointCount: number;
  previewQuality: "standard" | "high";
  compactViewport: boolean;
  mapOverlayEnabled: boolean;
  previewMode: PreviewMode;
  previewInteraction: PreviewInteraction;
  drawMode: DrawMode;
  hasGeneratedPlan: boolean;
  placementMode: boolean;
  selectedBuildingId?: string | null;
  planPreviewProjectId?: string | null;
  currentProjectId?: string | null;
  lotWidth: number;
  lotHeight: number;
  preview3DItemCount: number;
  planPreviewUrl?: string | null;
  siteLocked?: boolean;
  canDrawObjects: boolean;
  draggingBuildingActive: boolean;
  rotateDragActive: boolean;
  canvasPanActive: boolean;
  mapLocked: boolean;
};

export type PreviewInteractionState = ReturnType<typeof buildPreviewInteractionState>;

export function buildPreviewInteractionState({
  mapboxToken,
  geocode,
  buildingPlacementCount,
  suggestedPlacementCount,
  surveyPointCount,
  previewQuality,
  compactViewport,
  mapOverlayEnabled,
  previewMode,
  previewInteraction,
  drawMode,
  hasGeneratedPlan,
  placementMode,
  selectedBuildingId,
  planPreviewProjectId,
  currentProjectId,
  lotWidth,
  lotHeight,
  preview3DItemCount,
  planPreviewUrl,
  siteLocked,
  canDrawObjects,
  draggingBuildingActive,
  rotateDragActive,
  canvasPanActive,
  mapLocked,
}: BuildPreviewInteractionStateOptions) {
  const mapAvailable = Boolean(mapboxToken) && Boolean(geocode?.lat && geocode?.lng);
  const highQualityObjectCount = buildingPlacementCount + suggestedPlacementCount + surveyPointCount;
  const useLightHighQuality = previewQuality === "high" && (compactViewport || highQualityObjectCount > 220);
  const showMapBase = mapAvailable && mapOverlayEnabled;
  const showMap = showMapBase && previewMode === "2d";
  const showMap3D = showMapBase && previewMode === "3d";
  const allowMapInteraction =
    showMap &&
    (previewInteraction === "static" || drawMode === "pan") &&
    !placementMode &&
    !rotateDragActive &&
    !mapLocked;
  const showGeneratedPlan =
    !showMap &&
    previewInteraction === "static" &&
    drawMode === "select" &&
    hasGeneratedPlan &&
    !placementMode &&
    !selectedBuildingId &&
    (!planPreviewProjectId || !currentProjectId || planPreviewProjectId === currentProjectId);
  const hasLiveObjects =
    buildingPlacementCount > 0 ||
    suggestedPlacementCount > 0 ||
    surveyPointCount > 0 ||
    Boolean(lotWidth && lotHeight);
  const allowEdits = previewInteraction === "edit";
  const activeDrawMode =
    (drawMode === "site" && !siteLocked) ||
    ((drawMode === "polyline" || drawMode === "polygon" || drawMode === "rect" || drawMode === "point") && canDrawObjects);
  const drawingOwnsCanvasHits = placementMode || activeDrawMode || drawMode === "pan";
  const drawingSurfaceInteractive =
    Boolean(placementMode) ||
    activeDrawMode ||
    draggingBuildingActive ||
    rotateDragActive ||
    canvasPanActive ||
    (allowEdits && drawMode === "select") ||
    (showMap && previewInteraction === "edit" && !mapLocked);

  return {
    mapAvailable,
    highQualityObjectCount,
    useLightHighQuality,
    showMapBase,
    showMap,
    showMap3D,
    mapPitch: showMap3D ? 58 : 0,
    allowMapInteraction,
    showGeneratedPlan,
    hasLiveObjects,
    canUse3D: showMap || hasLiveObjects || preview3DItemCount > 0 || Boolean(planPreviewUrl),
    showHover: previewInteraction === "static",
    allowEdits,
    showQuickDrawPalette: false,
    showMobileDrawToolbar:
      previewMode === "2d" &&
      drawMode !== "select" &&
      drawMode !== "pan" &&
      compactViewport,
    activeDrawMode,
    drawingOwnsCanvasHits,
    drawingSurfaceInteractive,
    overlayPointerEvents:
      allowMapInteraction || !drawingSurfaceInteractive
        ? "pointer-events-none"
        : "pointer-events-auto",
    passiveOverlayPointerEvents: drawingOwnsCanvasHits ? "pointer-events-none" : "pointer-events-auto",
  };
}
