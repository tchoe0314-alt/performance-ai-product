import { getJson, postJson } from "../../lib/api";
import type {
  CandidateReviewCorrection,
  CandidateReviewDecision,
  CandidateReviewInbox,
  CivoraVisionGroundTruthDataset,
  CivoraVisionQualityReport,
  CivoraVisionReviewWorkspace,
  CivoraVisionTrainingDataset,
  DesignAlternativesV1,
  PlanResponse,
  ProjectInput,
  ProjectRecord,
} from "../types";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type DesignAlternativesAction = "generate" | "compare" | "choose" | "merge" | "revise";

const CANDIDATE_REVIEW_SITE_INPUT_KEYS = [
  "candidate_review_inbox_v1",
  "candidate_review_decisions_v1",
  "candidate_review_accepted_drafts_v1",
  "candidate_review_rejected_v1",
  "source_confidence_map_v1",
  "civora_vision_training_dataset_v1",
  "civora_vision_quality_report_v1",
  "civora_vision_ground_truth_ledger_v1",
  "civora_vision_ground_truth_dataset_v1",
  "civora_vision_split_registry_v1",
  "civora_vision_active_learning_queue_v1",
  "civora_vision_ground_truth_coverage_v1",
  "civora_vision_review_workspace_v1",
] as const;

export function mergeCandidateReviewProject({
  currentProject,
  responseProject,
  preserveSiteAlignmentLocked,
  candidateReviewInbox,
  visionTrainingDataset,
  visionQualityReport,
  visionGroundTruthDataset,
  visionReviewWorkspace,
}: {
  currentProject: ProjectRecord | null;
  responseProject: ProjectRecord;
  preserveSiteAlignmentLocked?: boolean;
  candidateReviewInbox?: CandidateReviewInbox;
  visionTrainingDataset?: CivoraVisionTrainingDataset;
  visionQualityReport?: CivoraVisionQualityReport;
  visionGroundTruthDataset?: CivoraVisionGroundTruthDataset;
  visionReviewWorkspace?: CivoraVisionReviewWorkspace;
}): ProjectRecord {
  const currentInput = (currentProject?.project_input ?? {}) as ProjectInput;
  const responseInput = (responseProject.project_input ?? {}) as ProjectInput;
  const currentMeta = (currentInput.meta ?? {}) as Record<string, unknown>;
  const responseMeta = (responseInput.meta ?? {}) as Record<string, unknown>;
  const currentSiteInputs = (currentMeta.site_inputs ?? {}) as Record<string, unknown>;
  const responseSiteInputs = (responseMeta.site_inputs ?? {}) as Record<string, unknown>;
  const candidateState: Record<string, unknown> = {};
  CANDIDATE_REVIEW_SITE_INPUT_KEYS.forEach((key) => {
    if (responseSiteInputs[key] !== undefined) candidateState[key] = responseSiteInputs[key];
  });
  if (candidateReviewInbox) candidateState.candidate_review_inbox_v1 = candidateReviewInbox;
  if (visionTrainingDataset) candidateState.civora_vision_training_dataset_v1 = visionTrainingDataset;
  if (visionQualityReport) candidateState.civora_vision_quality_report_v1 = visionQualityReport;
  if (visionGroundTruthDataset) candidateState.civora_vision_ground_truth_dataset_v1 = visionGroundTruthDataset;
  if (visionReviewWorkspace) candidateState.civora_vision_review_workspace_v1 = visionReviewWorkspace;

  return {
    ...(currentProject ?? {}),
    ...responseProject,
    project_input: {
      ...responseInput,
      ...currentInput,
      manual_fields: {
        ...(responseInput.manual_fields ?? {}),
        ...(currentInput.manual_fields ?? {}),
      },
      meta: {
        ...responseMeta,
        ...currentMeta,
        site_inputs: {
          ...responseSiteInputs,
          ...currentSiteInputs,
          ...candidateState,
          ...(preserveSiteAlignmentLocked ? { site_alignment_locked: true } : {}),
        },
      },
    },
    latest_result: responseProject.latest_result ?? currentProject?.latest_result ?? null,
  } as ProjectRecord;
}

function patchPlanMeta(
  setBackendResult: StateSetter<PlanResponse | null>,
  metaPatch: Record<string, unknown>,
) {
  setBackendResult((prev) => {
    if (!prev?.final_plan) return prev;
    return {
      ...prev,
      final_plan: {
        ...prev.final_plan,
        meta: {
          ...(prev.final_plan.meta ?? {}),
          ...metaPatch,
        },
      },
    };
  });
}

export async function runDashboardCandidateReviewDecision({
  action,
  candidateIds,
  currentProject,
  siteScaleLocked,
  currentProjectId,
  projectId,
  setBackendResult,
  setCurrentProject,
  setStatusMessage,
  token,
  correction,
}: {
  action: CandidateReviewDecision;
  candidateIds: string | string[];
  currentProject: ProjectRecord | null;
  siteScaleLocked: boolean;
  currentProjectId?: string;
  projectId: string;
  setBackendResult: StateSetter<PlanResponse | null>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setStatusMessage: StateSetter<string>;
  token: string | null;
  correction?: CandidateReviewCorrection;
}) {
  const activeProjectId = projectId || currentProjectId;
  const reviewedCandidateIds = Array.isArray(candidateIds) ? candidateIds : [candidateIds];
  const correctionAction =
    action === "correct" ||
    action === "reclassify" ||
    action === "redraw" ||
    action === "merge" ||
    action === "split";
  if (!token || !activeProjectId) {
    setStatusMessage("Save or load a project before reviewing candidates.");
    return null;
  }
  try {
    setStatusMessage(
      `${
        action === "accept"
          ? "Accepting"
          : action === "reject"
            ? "Rejecting"
            : correctionAction
              ? action === "merge"
                ? "Merging"
                : action === "split"
                  ? "Splitting"
                  : "Correcting"
              : "Keeping"
      } candidate...`,
    );
    const data = await postJson<{
      success: boolean;
      project?: ProjectRecord;
      candidate_review_inbox_v1?: CandidateReviewInbox;
      civora_vision_training_dataset_v1?: CivoraVisionTrainingDataset;
      civora_vision_quality_report_v1?: CivoraVisionQualityReport;
      civora_vision_ground_truth_dataset_v1?: CivoraVisionGroundTruthDataset;
      civora_vision_review_workspace_v1?: CivoraVisionReviewWorkspace;
      truth_label?: string;
    }>(
      `/api/projects/${activeProjectId}/candidate-review`,
      {
        candidate_ids: reviewedCandidateIds,
        action,
        reason:
          correction?.reason ?? (action === "accept"
            ? "Accepted from Review Detected Items as draft/review-required project evidence."
            : action === "reject"
              ? "Rejected from Review Detected Items."
              : correctionAction
                ? action === "merge"
                  ? "Merged reviewed detections into one source-traceable outline."
                  : action === "split"
                    ? "Split the reviewed detection into source-traceable outlines."
                    : "Corrected from Review Detected Items and retained as draft/review-required evidence."
                : "Kept pending in Review Detected Items."),
        corrected_feature_type: correction?.correctedFeatureType ?? "",
        corrected_geometry: correction?.correctedGeometry,
        correction_coordinate_space: correction?.correctionCoordinateSpace ?? "",
        replacement_geometries: correction?.replacementGeometries ?? [],
        replacement_feature_types: correction?.replacementFeatureTypes ?? [],
      },
      { token },
    );
    const updatedProject = data.project
      ? mergeCandidateReviewProject({
          currentProject,
          responseProject: data.project,
          preserveSiteAlignmentLocked: siteScaleLocked,
          candidateReviewInbox: data.candidate_review_inbox_v1,
          visionTrainingDataset: data.civora_vision_training_dataset_v1,
          visionQualityReport: data.civora_vision_quality_report_v1,
          visionGroundTruthDataset: data.civora_vision_ground_truth_dataset_v1,
          visionReviewWorkspace: data.civora_vision_review_workspace_v1,
        })
      : null;
    if (updatedProject) {
      setCurrentProject(updatedProject);
      if (updatedProject.latest_result) {
        setBackendResult(updatedProject.latest_result);
      }
    }
    if (data.candidate_review_inbox_v1) {
      patchPlanMeta(setBackendResult, {
        candidate_review_inbox_v1: data.candidate_review_inbox_v1,
        ...(data.civora_vision_training_dataset_v1
          ? { civora_vision_training_dataset_v1: data.civora_vision_training_dataset_v1 }
          : {}),
        ...(data.civora_vision_quality_report_v1
          ? { civora_vision_quality_report_v1: data.civora_vision_quality_report_v1 }
          : {}),
        ...(data.civora_vision_ground_truth_dataset_v1
          ? { civora_vision_ground_truth_dataset_v1: data.civora_vision_ground_truth_dataset_v1 }
          : {}),
        ...(data.civora_vision_review_workspace_v1
          ? { civora_vision_review_workspace_v1: data.civora_vision_review_workspace_v1 }
          : {}),
      });
    }
    setStatusMessage(
      action === "accept"
        ? "Candidate accepted as draft/review-required evidence."
        : action === "reject"
          ? "Candidate rejected and preserved in the audit trail."
          : correctionAction
            ? action === "merge"
              ? "Reviewed detections merged and recorded in the learning ledger."
              : action === "split"
                ? "Reviewed detection split and recorded in the learning ledger."
                : "Detection correction saved as draft evidence and learning feedback."
            : "Candidate kept pending.",
    );
    return updatedProject;
  } catch (error) {
    setStatusMessage(error instanceof Error ? error.message : "Candidate review update failed.");
    return null;
  }
}

export async function exportDashboardVisionLearningManifest({
  currentProjectId,
  projectId,
  setStatusMessage,
  token,
}: {
  currentProjectId?: string;
  projectId: string;
  setStatusMessage: StateSetter<string>;
  token: string | null;
}) {
  const activeProjectId = projectId || currentProjectId;
  if (!token || !activeProjectId) {
    setStatusMessage("Save or load a project before exporting Civora Vision learning data.");
    return false;
  }
  try {
    const data = await getJson<Record<string, unknown>>(
      `/api/projects/${activeProjectId}/vision-learning`,
      { token },
    );
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${activeProjectId}_civora_vision_learning.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    setStatusMessage("Civora Vision learning manifest exported. Source image bytes are not included.");
    return true;
  } catch (error) {
    setStatusMessage(error instanceof Error ? error.message : "Civora Vision learning export failed.");
    return false;
  }
}

export async function runDashboardDesignAlternativesAction({
  action,
  currentProjectId,
  designAlternativeCount,
  optionNumber,
  projectId,
  setActiveSidePanel,
  setActiveWorkspaceMode,
  setBackendResult,
  setCurrentProject,
  setStatusMessage,
  token,
}: {
  action: DesignAlternativesAction;
  currentProjectId?: string;
  designAlternativeCount: number;
  optionNumber?: number;
  projectId: string;
  setActiveSidePanel: (value: "reports") => void;
  setActiveWorkspaceMode: (value: "review") => void;
  setBackendResult: StateSetter<PlanResponse | null>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setStatusMessage: StateSetter<string>;
  token: string | null;
}) {
  const activeProjectId = projectId || currentProjectId;
  if (!token || !activeProjectId) {
    setStatusMessage("Save or load a project before working with design alternatives.");
    return;
  }
  try {
    setStatusMessage(
      action === "generate"
        ? "Generating review-required design alternatives..."
        : action === "compare"
          ? "Comparing alternatives..."
          : action === "revise"
            ? "Adding another review-required layout..."
            : "Selecting draft alternative direction...",
    );
    const data = await postJson<{
      success: boolean;
      project?: ProjectRecord;
      design_alternatives_v1?: DesignAlternativesV1;
      truth_label?: string;
    }>(
      `/api/projects/${activeProjectId}/design-alternatives`,
      {
        action,
        requested_count: Math.max(3, designAlternativeCount || 3),
        option_number: optionNumber,
        reason:
          action === "generate"
            ? "Generated from Alternatives panel."
            : action === "compare"
              ? "Compared from Alternatives panel."
              : action === "revise"
                ? "Requested another layout from Alternatives panel."
                : `Selected option ${optionNumber ?? ""} from Alternatives panel.`,
      },
      { token },
    );
    if (data.project) {
      setCurrentProject(data.project);
      if (data.project.latest_result) {
        setBackendResult(data.project.latest_result);
      }
    }
    if (data.design_alternatives_v1) {
      patchPlanMeta(setBackendResult, {
        design_alternatives_v1: data.design_alternatives_v1,
      });
    }
    setActiveWorkspaceMode("review");
    setActiveSidePanel("reports");
    setStatusMessage(
      action === "generate"
        ? "Alternatives generated for review."
        : action === "compare"
          ? "Alternatives compared for review."
          : action === "revise"
            ? "Another layout concept was added for review."
            : "Alternative selected as a draft review direction.",
    );
  } catch (error) {
    setStatusMessage(error instanceof Error ? error.message : "Design alternatives update failed.");
  }
}
