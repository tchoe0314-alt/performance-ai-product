import type { ComponentProps } from "react";

import type { BuildingPlacement, GradingEarthworkUx } from "../types";
import type { DrawMode } from "../utils/cadToolTypes";
import { formatMetric } from "../utils/formatting";
import { buildPreviewParkingMapModules } from "../utils/previewParkingMapModules";
import type { buildWaterFireFlowViewModel } from "../utils/previewWaterFireFlow";
import { PreviewBasePlanGrid } from "./PreviewBasePlanGrid";
import { PreviewCadMarkers } from "./PreviewCadMarkers";
import { PreviewDraftGeometryOverlay } from "./PreviewDraftGeometryOverlay";
import { PreviewGradingEarthworkDock } from "./PreviewGradingEarthworkDock";
import { PreviewParkingModules } from "./PreviewParkingModules";
import { PreviewPolygonObjects } from "./PreviewPolygonObjects";
import { PreviewPolylineObjects } from "./PreviewPolylineObjects";
import { PreviewRectObjects } from "./PreviewRectObjects";
import { PreviewSuggestedGeometry } from "./PreviewSuggestedGeometry";
import { PreviewSvgDefs } from "./PreviewSvgDefs";
import { PreviewWaterFireFlowOverlay } from "./PreviewWaterFireFlowOverlay";

type WaterFireFlowViewModel = ReturnType<typeof buildWaterFireFlowViewModel>;
type PlanScaleBar = ComponentProps<typeof PreviewBasePlanGrid>["planScaleBar"];
type DraftSiteSize = { width: number; height: number };
type DraftRectPercent = { left: number; top: number; width: number; height: number };

type PreviewPlanCanvasLayersProps = {
  overlayBoundsResolved: { left: number; top: number; width: number; height: number } | null;
  previewMode: "2d" | "3d";
  siteLocked: boolean;
  showSiteBounds: boolean;
  drawMode: DrawMode;
  legendPalette: {
    siteBorder: string;
    siteFill: string;
    detectedStroke: string;
    detectedFill: string;
  };
  viewportTransformStyle: { transform: string; transformOrigin: string };
  buildingPlacements: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  surveyPointCount: number;
  hasTerrainSurfaceEvidence: boolean;
  showMap: boolean;
  isHighQuality: boolean;
  lotWidth: number;
  lotHeight: number;
  planScaleBar: PlanScaleBar;
  visibleCadObjects: BuildingPlacement[];
  selectedBuildingId: string | null;
  currentSiteSize: { width: number; height: number };
  sitePointToSvgPercent: (point: [number, number]) => string;
  mapAnchoredRectPercent: (item: BuildingPlacement) => { left: number; top: number; width: number; height: number };
  shouldRevealObjectLabel: (item: BuildingPlacement) => boolean;
  getObjectGeometryPoints: (item: BuildingPlacement) => Array<[number, number]>;
  accessPointsForParking: Array<{ x: number; y: number }>;
  showParkingAnalysis: boolean;
  waterFireFlow: WaterFireFlowViewModel;
  previewQuality: "standard" | "high";
  sitePointToPreviewPercent: (point: [number, number]) => [number, number];
  activeSnapPoint: { x: number; y: number } | null;
  draftPoints: Array<[number, number]>;
  draftPreviewPoint: [number, number] | null;
  drawingLotWidth: number;
  drawingLotHeight: number;
  siteTupleToPercent: (point: [number, number], siteSize: DraftSiteSize) => [number, number];
  siteRectToPercent: (
    rect: { x: number; y: number; width: number; height: number },
    siteSize: DraftSiteSize,
  ) => DraftRectPercent;
  showEarthworkUx: boolean;
  gradingEarthworkUx?: GradingEarthworkUx | null;
};

export function PreviewPlanCanvasLayers({
  overlayBoundsResolved,
  previewMode,
  siteLocked,
  showSiteBounds,
  drawMode,
  legendPalette,
  viewportTransformStyle,
  buildingPlacements,
  suggestedPlacements,
  surveyPointCount,
  hasTerrainSurfaceEvidence,
  showMap,
  isHighQuality,
  lotWidth,
  lotHeight,
  planScaleBar,
  visibleCadObjects,
  selectedBuildingId,
  currentSiteSize,
  sitePointToSvgPercent,
  mapAnchoredRectPercent,
  shouldRevealObjectLabel,
  getObjectGeometryPoints,
  accessPointsForParking,
  showParkingAnalysis,
  waterFireFlow,
  previewQuality,
  sitePointToPreviewPercent,
  activeSnapPoint,
  draftPoints,
  draftPreviewPoint,
  drawingLotWidth,
  drawingLotHeight,
  siteTupleToPercent,
  siteRectToPercent,
  showEarthworkUx,
  gradingEarthworkUx,
}: PreviewPlanCanvasLayersProps) {
  if (!overlayBoundsResolved || previewMode !== "2d") return null;
  const hasSurveyOrTerrainEvidence = surveyPointCount > 0 || hasTerrainSurfaceEvidence;

  return (
    <div
      className="pointer-events-none absolute z-10"
      style={{
        left: overlayBoundsResolved.left,
        top: overlayBoundsResolved.top,
        width: overlayBoundsResolved.width,
        height: overlayBoundsResolved.height,
      }}
    >
      {!siteLocked && (showSiteBounds || drawMode === "site") ? (
        <div
          className={`absolute inset-0 rounded-[16px] border border-dashed ${legendPalette.siteBorder} ${legendPalette.siteFill}`}
          style={viewportTransformStyle}
        />
      ) : null}
      {buildingPlacements.length || suggestedPlacements.length || hasSurveyOrTerrainEvidence ? (
        <svg
          className="absolute inset-0"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={viewportTransformStyle}
        >
          <PreviewSvgDefs />
          <PreviewBasePlanGrid
            showMap={showMap}
            isHighQuality={isHighQuality}
            siteLocked={siteLocked}
            hasSurveyOrTerrainEvidence={hasSurveyOrTerrainEvidence}
            lotWidth={lotWidth}
            lotHeight={lotHeight}
            planScaleBar={planScaleBar}
          />
          <PreviewPolylineObjects
            objects={visibleCadObjects}
            selectedBuildingId={selectedBuildingId}
            isHighQuality={isHighQuality}
            currentSiteSize={currentSiteSize}
            sitePointToSvgPercent={sitePointToSvgPercent}
          />
          <PreviewRectObjects
            objects={visibleCadObjects}
            selectedBuildingId={selectedBuildingId}
            isHighQuality={isHighQuality}
            mapAnchoredRectPercent={mapAnchoredRectPercent}
          />
          <PreviewPolygonObjects
            objects={visibleCadObjects}
            selectedBuildingId={selectedBuildingId}
            isHighQuality={isHighQuality}
            sitePointToSvgPercent={sitePointToSvgPercent}
          />
          <PreviewCadMarkers
            objects={visibleCadObjects}
            selectedBuildingId={selectedBuildingId}
            currentSiteSize={currentSiteSize}
            sitePointToPreviewPercent={sitePointToPreviewPercent}
            mapAnchoredRectPercent={mapAnchoredRectPercent}
            shouldRevealObjectLabel={shouldRevealObjectLabel}
            getObjectGeometryPoints={getObjectGeometryPoints}
          />
          <PreviewParkingModules
            objects={visibleCadObjects}
            accessPoints={accessPointsForParking}
            showParkingAnalysis={showParkingAnalysis}
            buildParkingModules={buildPreviewParkingMapModules}
            sitePointToSvgPercent={sitePointToSvgPercent}
          />
          <PreviewSuggestedGeometry
            objects={suggestedPlacements}
            selectedBuildingId={selectedBuildingId}
            detectedStroke={legendPalette.detectedStroke}
            detectedFill={legendPalette.detectedFill}
            sitePointToSvgPercent={sitePointToSvgPercent}
          />
          <PreviewWaterFireFlowOverlay
            waterFireFlow={waterFireFlow}
            previewQuality={previewQuality}
            sitePointToPreviewPercent={sitePointToPreviewPercent}
          />
          <PreviewDraftGeometryOverlay
            activeSnapPoint={activeSnapPoint}
            draftPoints={draftPoints}
            draftPreviewPoint={draftPreviewPoint}
            drawMode={drawMode}
            drawingLotWidth={drawingLotWidth}
            drawingLotHeight={drawingLotHeight}
            lotWidth={lotWidth}
            lotHeight={lotHeight}
            sitePointToPreviewPercent={sitePointToPreviewPercent}
            siteTupleToPercent={siteTupleToPercent}
            siteRectToPercent={siteRectToPercent}
          />
        </svg>
      ) : null}
      {showEarthworkUx && gradingEarthworkUx ? (
        <PreviewGradingEarthworkDock
          gradingEarthworkUx={gradingEarthworkUx}
          formatMetric={formatMetric}
        />
      ) : null}
    </div>
  );
}
