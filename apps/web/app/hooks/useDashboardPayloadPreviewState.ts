import { useCallback, useMemo } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  PlanRequestPayload,
  ProjectRecord,
  SurveySlopeResponse,
} from "../types";
import { buildDashboardManualFields } from "../utils/dashboardManualFields";
import { buildDashboardPayloadPreview } from "../utils/dashboardPayloads";
import type { SystemStatus } from "../utils/workflowConstants";

export type DashboardBuildManualFields = (
  fields: Omit<
    Parameters<typeof buildDashboardManualFields>[0],
    | "buildingPlacements"
    | "surveySlopeEstimate"
    | "drainageForcedInlets"
    | "drainageConnectOrphans"
    | "drainageAllowSlopeAdjust"
    | "drainageMaxSlopeAdjust"
  >,
) => ReturnType<typeof buildDashboardManualFields>;

type UseDashboardPayloadPreviewStateInput = {
  assistedEnabled: boolean;
  buildingPlacements: BuildingPlacement[];
  buildingCount: string;
  buildingDepth: string;
  buildingWidth: string;
  chatMessages: ChatMessage[];
  currentProject: ProjectRecord | null;
  drainageAllowSlopeAdjust: boolean;
  drainageConnectOrphans: boolean;
  drainageForcedInlets: Array<Record<string, unknown>>;
  drainageMaxSlopeAdjust: number;
  drainage: boolean;
  fileName: string;
  grading: boolean;
  imageName: string;
  lotHeight: string;
  lotWidth: string;
  maxAdaCrossSlopePct: string;
  maxParkingSlopePct: string;
  maxRoadGradePct: string;
  minSlopePct: string;
  parkingCount: string;
  pipeMinSlopePct: string;
  projectId: string;
  projectType: string;
  prompt: string;
  reactiveEditPolicyPreference: NonNullable<PlanRequestPayload["meta"]>["reactive_edit_policy_preference"];
  roads: boolean;
  setback: string;
  siteName: string;
  surveySlopeEstimate: SurveySlopeResponse | null;
  systemStatuses: Record<string, SystemStatus>;
  units: string;
  utilities: boolean;
};

export function useDashboardPayloadPreviewState({
  assistedEnabled,
  buildingPlacements,
  buildingCount,
  buildingDepth,
  buildingWidth,
  chatMessages,
  currentProject,
  drainageAllowSlopeAdjust,
  drainageConnectOrphans,
  drainageForcedInlets,
  drainageMaxSlopeAdjust,
  drainage,
  fileName,
  grading,
  imageName,
  lotHeight,
  lotWidth,
  maxAdaCrossSlopePct,
  maxParkingSlopePct,
  maxRoadGradePct,
  minSlopePct,
  parkingCount,
  pipeMinSlopePct,
  projectId,
  projectType,
  prompt,
  reactiveEditPolicyPreference,
  roads,
  setback,
  siteName,
  surveySlopeEstimate,
  systemStatuses,
  units,
  utilities,
}: UseDashboardPayloadPreviewStateInput) {
  const buildManualFields = useCallback<DashboardBuildManualFields>(
    (fields) =>
      buildDashboardManualFields({
        ...fields,
        buildingPlacements,
        surveySlopeEstimate,
        drainageForcedInlets,
        drainageConnectOrphans,
        drainageAllowSlopeAdjust,
        drainageMaxSlopeAdjust,
      }),
    [
      buildingPlacements,
      drainageAllowSlopeAdjust,
      drainageConnectOrphans,
      drainageForcedInlets,
      drainageMaxSlopeAdjust,
      surveySlopeEstimate,
    ],
  );

  const payloadPreview = useMemo(
    () =>
      buildDashboardPayloadPreview({
        projectId,
        assistedEnabled,
        prompt,
        imageName,
        chatMessages,
        currentProject,
        systemStatuses,
        reactiveEditPolicyPreference,
        siteObjectId: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
        manualFields: buildManualFields({
          nextSiteName: siteName,
          nextFileName: fileName,
          nextUnits: units,
          nextProjectType: projectType,
          nextLotWidth: lotWidth,
          nextLotHeight: lotHeight,
          nextSetback: setback,
          nextBuildingWidth: buildingWidth,
          nextBuildingDepth: buildingDepth,
          nextBuildingCount: buildingCount,
          nextParkingCount: parkingCount,
          nextMinSlopePct: minSlopePct,
          nextPipeMinSlopePct: pipeMinSlopePct,
          nextMaxParkingSlopePct: maxParkingSlopePct,
          nextMaxRoadGradePct: maxRoadGradePct,
          nextMaxAdaCrossSlopePct: maxAdaCrossSlopePct,
          nextRoads: roads,
          nextGrading: grading,
          nextDrainage: drainage,
          nextUtilities: utilities,
        }),
      }),
    [
      assistedEnabled,
      buildManualFields,
      buildingPlacements,
      buildingCount,
      buildingDepth,
      buildingWidth,
      chatMessages,
      currentProject,
      drainage,
      fileName,
      grading,
      imageName,
      lotHeight,
      lotWidth,
      maxAdaCrossSlopePct,
      maxParkingSlopePct,
      maxRoadGradePct,
      minSlopePct,
      parkingCount,
      pipeMinSlopePct,
      projectId,
      projectType,
      prompt,
      reactiveEditPolicyPreference,
      roads,
      setback,
      siteName,
      systemStatuses,
      units,
      utilities,
    ],
  );

  return {
    buildManualFields,
    payloadPreview,
  };
}
