import { useCallback } from "react";
import type { MutableRefObject } from "react";

import type {
  Assumption,
  BuildingPlacement,
  ChatMessage,
  ControlOverrides,
  Issue,
  JobSummary,
  ManualFailure,
  PlanExplanation,
  PlanMeta,
  ProgressTimelineV1,
  ProjectRecord,
  SetupWizardStateV1,
} from "../types";
import { createChatMessage, extractDesignMemory } from "../utils/chat";
import { toArray } from "../utils/formatting";
import type {
  EngineeringSystemKey,
  SystemStatus,
} from "../utils/workflowConstants";

type UseDashboardChatDecisionContextBuilderInput = {
  appliedAddressLabel: string;
  assistedEnabled: boolean;
  assumptions: Assumption[];
  backendResultHasFinalPlan: boolean;
  buildingCount: string;
  buildingDepth: string;
  buildingPlacements: BuildingPlacement[];
  buildingWidth: string;
  chatMessagesRef: MutableRefObject<ChatMessage[]>;
  currentExplanation: PlanExplanation;
  currentManualFailures: ManualFailure[];
  currentPlanMeta: PlanMeta;
  currentProject: ProjectRecord | null;
  currentTruthAudit: Record<string, unknown>;
  drainage: boolean;
  fileName: string;
  grading: boolean;
  hasAssumedTerrainSlope: boolean;
  hasLocationEvidence: boolean;
  hasTerrainSource: boolean;
  hasVerifiedSurveyControl: boolean;
  issues: Issue[];
  lotHeight: string;
  lotWidth: string;
  mapAnalysisSuccess: boolean;
  maxAdaCrossSlopePct: string;
  maxParkingSlopePct: string;
  maxRoadGradePct: string;
  minSlopePct: string;
  onlineSourceLookupLabel: string;
  parkingCount: string;
  pendingPlacementObjects: BuildingPlacement[];
  pipeMinSlopePct: string;
  planPreviewUrl: string | null;
  placedObjectCount: number;
  progressTimelineState: ProgressTimelineV1;
  projectType: string;
  roads: boolean;
  setback: string;
  setupWizardState: SetupWizardStateV1;
  siteAddress: string;
  siteName: string;
  siteScaleLocked: boolean;
  systemStatuses: Record<EngineeringSystemKey, SystemStatus>;
  units: string;
  utilities: boolean;
  visibleActiveJob: JobSummary | null;
};

export function useDashboardChatDecisionContextBuilder({
  appliedAddressLabel,
  assistedEnabled,
  assumptions,
  backendResultHasFinalPlan,
  buildingCount,
  buildingDepth,
  buildingPlacements,
  buildingWidth,
  chatMessagesRef,
  currentExplanation,
  currentManualFailures,
  currentPlanMeta,
  currentProject,
  currentTruthAudit,
  drainage,
  fileName,
  grading,
  hasAssumedTerrainSlope,
  hasLocationEvidence,
  hasTerrainSource,
  hasVerifiedSurveyControl,
  issues,
  lotHeight,
  lotWidth,
  mapAnalysisSuccess,
  maxAdaCrossSlopePct,
  maxParkingSlopePct,
  maxRoadGradePct,
  minSlopePct,
  onlineSourceLookupLabel,
  parkingCount,
  pendingPlacementObjects,
  pipeMinSlopePct,
  planPreviewUrl,
  placedObjectCount,
  progressTimelineState,
  projectType,
  roads,
  setback,
  setupWizardState,
  siteAddress,
  siteName,
  siteScaleLocked,
  systemStatuses,
  units,
  utilities,
  visibleActiveJob,
}: UseDashboardChatDecisionContextBuilderInput) {
  return useCallback(
    (overrides: ControlOverrides = {}, message: string) => {
      const liveThread = chatMessagesRef.current;
      const designMemory = extractDesignMemory(liveThread);
      const storedMemory =
        currentProject?.project_input?.meta?.chat_memory &&
        typeof currentProject.project_input.meta.chat_memory === "object"
          ? currentProject.project_input.meta.chat_memory
          : null;
      const mergedPreferences = [
        ...toArray((storedMemory as { preferences?: string[] } | null)?.preferences),
        ...designMemory.preferences,
      ].slice(-8);
      const mergedConstraints = [
        ...toArray((storedMemory as { constraints?: string[] } | null)?.constraints),
        ...designMemory.constraints,
      ].slice(-8);

      return {
        strategy_mode: assistedEnabled ? "assisted" : "user",
        site_name: overrides.siteName ?? siteName,
        file_name: overrides.fileName ?? fileName,
        project_type: overrides.projectType ?? projectType,
        units: overrides.units ?? units,
        lot_width: overrides.lotWidth ?? lotWidth,
        lot_height: overrides.lotHeight ?? lotHeight,
        building_width: overrides.buildingWidth ?? buildingWidth,
        building_depth: overrides.buildingDepth ?? buildingDepth,
        setback: overrides.setback ?? setback,
        building_count: overrides.buildingCount ?? buildingCount,
        parking_count: overrides.parkingCount ?? parkingCount,
        min_slope_pct: overrides.minSlopePct ?? minSlopePct,
        pipe_min_slope_pct: overrides.pipeMinSlopePct ?? pipeMinSlopePct,
        max_parking_slope_pct: overrides.maxParkingSlopePct ?? maxParkingSlopePct,
        max_road_grade_pct: overrides.maxRoadGradePct ?? maxRoadGradePct,
        max_ada_cross_slope_pct: overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct,
        roads: overrides.roads ?? roads,
        grading: overrides.grading ?? grading,
        drainage: overrides.drainage ?? drainage,
        utilities: overrides.utilities ?? utilities,
        has_plan: backendResultHasFinalPlan,
        has_preview: Boolean(planPreviewUrl),
        site_locked: siteScaleLocked,
        site_address: siteAddress,
        applied_address: appliedAddressLabel,
        online_source_lookup: onlineSourceLookupLabel,
        has_location_evidence: hasLocationEvidence,
        has_site_boundary: buildingPlacements.some((item) => item.type === "site"),
        has_terrain_source: hasTerrainSource,
        has_assumed_terrain_slope: hasAssumedTerrainSlope,
        has_verified_survey_control: hasVerifiedSurveyControl,
        placed_object_count: placedObjectCount,
        pending_placement_count: pendingPlacementObjects.length,
        pending_placement_objects: pendingPlacementObjects.map((item) => ({
          id: item.id,
          label: item.label,
          type: item.type,
        })),
        system_statuses: systemStatuses,
        map_analysis_success: mapAnalysisSuccess,
        setup_wizard_state_v1: setupWizardState,
        current_project: currentProject
          ? {
              project_id: currentProject.project_id,
              name: currentProject.name,
            }
          : null,
        current_explanation: currentExplanation,
        current_truth_audit: currentTruthAudit,
        engineering_status: currentPlanMeta?.engineering_status ?? {},
        convergence_summary: currentPlanMeta?.convergence_summary ?? {},
        manual_failures: currentManualFailures,
        assumptions,
        produced_deliverables: Array.isArray(currentPlanMeta?.deliverables?.produced)
          ? currentPlanMeta.deliverables.produced
          : [],
        issues,
        memory_summary: {
          preferences: mergedPreferences,
          constraints: mergedConstraints,
          open_questions: toArray((storedMemory as { open_questions?: string[] } | null)?.open_questions).slice(-6),
          examples: [...mergedPreferences, ...mergedConstraints].slice(-8),
        },
        current_phase:
          String(visibleActiveJob?.stage || "") ||
          String((currentPlanMeta?.runtime_phase_checkpoint as { stage_name?: string } | undefined)?.stage_name || ""),
        current_phase_detail: String(visibleActiveJob?.stage_detail || ""),
        progress_timeline_v1: progressTimelineState,
        chat_thread: [
          ...liveThread,
          createChatMessage("user", message),
        ].map(({ role, content, kind }) => ({ role, content, kind })),
      };
    },
    [
      appliedAddressLabel,
      assistedEnabled,
      assumptions,
      backendResultHasFinalPlan,
      buildingCount,
      buildingDepth,
      buildingPlacements,
      buildingWidth,
      chatMessagesRef,
      currentExplanation,
      currentManualFailures,
      currentPlanMeta,
      currentProject,
      currentTruthAudit,
      drainage,
      fileName,
      grading,
      hasAssumedTerrainSlope,
      hasLocationEvidence,
      hasTerrainSource,
      hasVerifiedSurveyControl,
      issues,
      lotHeight,
      lotWidth,
      mapAnalysisSuccess,
      maxAdaCrossSlopePct,
      maxParkingSlopePct,
      maxRoadGradePct,
      minSlopePct,
      onlineSourceLookupLabel,
      parkingCount,
      pendingPlacementObjects,
      pipeMinSlopePct,
      planPreviewUrl,
      placedObjectCount,
      progressTimelineState,
      projectType,
      roads,
      setback,
      setupWizardState,
      siteAddress,
      siteName,
      siteScaleLocked,
      systemStatuses,
      units,
      utilities,
      visibleActiveJob,
    ],
  );
}
