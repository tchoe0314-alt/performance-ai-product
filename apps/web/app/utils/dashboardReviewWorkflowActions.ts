import { getJson, postJson } from "../../lib/api";
import type {
  CandidateReviewCorrection,
  CandidateReviewDecision,
  CandidateReviewInbox,
  CivoraVisionQualityReport,
  CivoraVisionTrainingDataset,
  DesignAlternativesV1,
  PlanResponse,
  ProjectRecord,
} from "../types";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type DesignAlternativesAction = "generate" | "compare" | "choose" | "merge" | "revise";

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
  candidateId,
  currentProjectId,
  projectId,
  setBackendResult,
  setCurrentProject,
  setStatusMessage,
  token,
  correction,
}: {
  action: CandidateReviewDecision;
  candidateId: string;
  currentProjectId?: string;
  projectId: string;
  setBackendResult: StateSetter<PlanResponse | null>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setStatusMessage: StateSetter<string>;
  token: string | null;
  correction?: CandidateReviewCorrection;
}) {
  const activeProjectId = projectId || currentProjectId;
  const correctionAction = action === "correct" || action === "reclassify" || action === "redraw";
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
              ? "Correcting"
              : "Keeping"
      } candidate...`,
    );
    const data = await postJson<{
      success: boolean;
      project?: ProjectRecord;
      candidate_review_inbox_v1?: CandidateReviewInbox;
      civora_vision_training_dataset_v1?: CivoraVisionTrainingDataset;
      civora_vision_quality_report_v1?: CivoraVisionQualityReport;
      truth_label?: string;
    }>(
      `/api/projects/${activeProjectId}/candidate-review`,
      {
        candidate_ids: [candidateId],
        action,
        reason:
          correction?.reason ?? (action === "accept"
            ? "Accepted from Candidate Review Inbox as draft/review-required project evidence."
            : action === "reject"
              ? "Rejected from Candidate Review Inbox."
              : correctionAction
                ? "Corrected from Candidate Review Inbox and retained as draft/review-required evidence."
                : "Kept pending from Candidate Review Inbox."),
        corrected_feature_type: correction?.correctedFeatureType ?? "",
        corrected_geometry: correction?.correctedGeometry,
        correction_coordinate_space: correction?.correctionCoordinateSpace ?? "",
      },
      { token },
    );
    const updatedProject = data.project
      ? {
          ...data.project,
          project_input: data.candidate_review_inbox_v1
            ? {
                ...(data.project.project_input ?? {}),
                meta: {
                  ...(data.project.project_input?.meta ?? {}),
                  site_inputs: {
                    ...(data.project.project_input?.meta?.site_inputs ?? {}),
                    candidate_review_inbox_v1: data.candidate_review_inbox_v1,
                    ...(data.civora_vision_training_dataset_v1
                      ? { civora_vision_training_dataset_v1: data.civora_vision_training_dataset_v1 }
                      : {}),
                    ...(data.civora_vision_quality_report_v1
                      ? { civora_vision_quality_report_v1: data.civora_vision_quality_report_v1 }
                      : {}),
                  },
                },
              }
            : data.project.project_input,
        }
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
      });
    }
    setStatusMessage(
      action === "accept"
        ? "Candidate accepted as draft/review-required evidence."
        : action === "reject"
          ? "Candidate rejected and preserved in the audit trail."
          : correctionAction
            ? "Detection correction saved as draft evidence and learning feedback."
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
