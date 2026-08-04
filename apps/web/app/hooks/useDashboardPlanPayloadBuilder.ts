import { useCallback, useEffect, useRef } from "react";
import type { MutableRefObject } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  ControlOverrides,
  PlanRequestPayload,
  PlanResponse,
  ProjectRecord,
} from "../types";
import { buildDashboardManualFields } from "../utils/dashboardManualFields";
import {
  REACTIVE_EDIT_POLICY_PREFERENCE,
  REACTIVE_SYSTEM_STAGE_MAP,
  type EngineeringSystemKey,
  type SystemGenerationTarget,
  type SystemStatus,
} from "../utils/workflowConstants";

type BuildManualFields = (
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

type UseDashboardPlanPayloadBuilderInput = {
  assistedEnabled: boolean;
  backendResult: PlanResponse | null;
  buildManualFields: BuildManualFields;
  buildingCount: string;
  buildingDepth: string;
  buildingPlacements: BuildingPlacement[];
  buildingWidth: string;
  chatMessagesRef: MutableRefObject<ChatMessage[]>;
  currentProject: ProjectRecord | null;
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
  roads: boolean;
  setback: string;
  siteName: string;
  siteScaleLocked: boolean;
  systemStatuses: Record<EngineeringSystemKey, SystemStatus>;
  units: string;
  utilities: boolean;
};

export function useDashboardPlanPayloadBuilder({
  assistedEnabled,
  backendResult,
  buildManualFields,
  buildingCount,
  buildingDepth,
  buildingPlacements,
  buildingWidth,
  chatMessagesRef,
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
  roads,
  setback,
  siteName,
  siteScaleLocked,
  systemStatuses,
  units,
  utilities,
}: UseDashboardPlanPayloadBuilderInput) {
  const latestBackendResultRef = useRef<PlanResponse | null>(backendResult);
  const latestSystemStatusesRef = useRef<Record<EngineeringSystemKey, SystemStatus>>(systemStatuses);

  useEffect(() => {
    latestBackendResultRef.current = backendResult;
  }, [backendResult]);

  useEffect(() => {
    latestSystemStatusesRef.current = systemStatuses;
  }, [systemStatuses]);

  const buildPayloadFromOverrides = useCallback((
    overrides: ControlOverrides = {},
    promptOverride?: string,
    projectIdOverride?: string | null,
    placementsOverride?: BuildingPlacement[],
  ): PlanRequestPayload => {
    const nextSiteName = overrides.siteName ?? siteName;
    const nextFileName = overrides.fileName ?? fileName;
    const nextUnits = overrides.units ?? units;
    const nextProjectType = overrides.projectType ?? projectType;
    const nextRoads = overrides.roads ?? roads;
    const nextGrading = overrides.grading ?? grading;
    const nextDrainage = overrides.drainage ?? drainage;
    const nextUtilities = overrides.utilities ?? utilities;
    const nextBuildingCount = overrides.buildingCount ?? buildingCount;
    const nextMinSlopePct = overrides.minSlopePct ?? minSlopePct;
    const nextPipeMinSlopePct = overrides.pipeMinSlopePct ?? pipeMinSlopePct;
    const nextMaxParkingSlopePct = overrides.maxParkingSlopePct ?? maxParkingSlopePct;
    const nextMaxRoadGradePct = overrides.maxRoadGradePct ?? maxRoadGradePct;
    const nextMaxAdaCrossSlopePct = overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct;
    const effectivePlacements = placementsOverride ?? buildingPlacements;
    const canonicalSite = effectivePlacements.find((item) => item.type === "site");
    const effectiveSiteAlignmentLocked = siteScaleLocked || canonicalSite?.locked === true;

    return {
      project_id:
        projectIdOverride !== undefined ? projectIdOverride : projectId || null,
      full_design_mode: true,
      input_mode: assistedEnabled ? "assisted" : "user",
      strict_mode: false,
      prompt_text: (promptOverride ?? prompt) || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: {
          ...(currentProject?.project_input?.meta?.site_inputs ?? {}),
          site_alignment_locked: effectiveSiteAlignmentLocked,
        },
        system_dirty_state: systemStatuses,
        reactive_edit_policy_preference: REACTIVE_EDIT_POLICY_PREFERENCE,
        site_object_id: buildingPlacements.find((item) => item.type === "site")?.id ?? null,
        assisted_enabled: assistedEnabled,
      },
      manual_fields: buildManualFields({
        nextSiteName,
        nextFileName,
        nextUnits,
        nextProjectType,
        nextLotWidth: overrides.lotWidth ?? lotWidth,
        nextLotHeight: overrides.lotHeight ?? lotHeight,
        nextSetback: overrides.setback ?? setback,
        nextBuildingWidth: overrides.buildingWidth ?? buildingWidth,
        nextBuildingDepth: overrides.buildingDepth ?? buildingDepth,
        nextBuildingCount,
        nextParkingCount: overrides.parkingCount ?? parkingCount,
        nextMinSlopePct,
        nextPipeMinSlopePct,
        nextMaxParkingSlopePct,
        nextMaxRoadGradePct,
        nextMaxAdaCrossSlopePct,
        nextRoads,
        nextGrading,
        nextDrainage,
        nextUtilities,
        placementsOverride,
      }),
      allow_ai_fill_for_blanks: assistedEnabled,
    };
  }, [
    assistedEnabled,
    buildManualFields,
    buildingCount,
    buildingDepth,
    buildingPlacements,
    buildingWidth,
    chatMessagesRef,
    currentProject?.project_input?.meta?.site_inputs,
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
    roads,
    setback,
    siteName,
    siteScaleLocked,
    systemStatuses,
    units,
    utilities,
  ]);

  const withReactiveRerunContext = useCallback(
    (
      requestPayload: PlanRequestPayload,
      requestedSystem: SystemGenerationTarget,
    ): PlanRequestPayload => {
      if (requestedSystem === "full") return requestPayload;
      const checkpointFinalPlan = latestBackendResultRef.current?.final_plan;
      if (!checkpointFinalPlan || typeof checkpointFinalPlan !== "object") {
        return requestPayload;
      }
      const changedSystems = Object.entries(latestSystemStatusesRef.current)
        .filter(([system, status]) => status === "stale" && system in REACTIVE_SYSTEM_STAGE_MAP)
        .map(([system]) => system as keyof typeof REACTIVE_SYSTEM_STAGE_MAP);
      if (!changedSystems.includes(requestedSystem)) {
        changedSystems.push(requestedSystem);
      }
      const changedTargets = Array.from(
        new Set(
          changedSystems.flatMap((system) => REACTIVE_SYSTEM_STAGE_MAP[system] ?? []),
        ),
      );
      if (!changedTargets.length) return requestPayload;

      const existingMeta = (requestPayload.meta ?? {}) as Record<string, unknown>;
      const existingOrchestratorMeta =
        existingMeta.orchestrator_meta && typeof existingMeta.orchestrator_meta === "object"
          ? (existingMeta.orchestrator_meta as Record<string, unknown>)
          : {};
      const existingRuntimeResume =
        existingOrchestratorMeta.runtime_resume &&
        typeof existingOrchestratorMeta.runtime_resume === "object"
          ? (existingOrchestratorMeta.runtime_resume as Record<string, unknown>)
          : {};

      return {
        ...requestPayload,
        meta: {
          ...existingMeta,
          requested_system: requestedSystem,
          changed_targets: changedTargets,
          stale_outputs: changedTargets,
          reactive_checkpoint_final_plan: checkpointFinalPlan,
          reactive_partial_rerun_request: {
            enabled: true,
            requested_system: requestedSystem,
            checkpoint_attached: true,
            changed_targets: changedTargets,
          },
          orchestrator_meta: {
            ...existingOrchestratorMeta,
            runtime_resume: {
              ...existingRuntimeResume,
              final_plan: checkpointFinalPlan,
              reactive_checkpoint_source: "web_current_backend_result",
            },
          },
        },
      };
    },
    [],
  );

  return {
    buildPayloadFromOverrides,
    withReactiveRerunContext,
  };
}
