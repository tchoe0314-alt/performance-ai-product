import { postJson } from "../../lib/api";
import type {
  CandidateReviewInbox,
  DesignAlternativesV1,
  PlanResponse,
  ProjectRecord,
} from "../types";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

type CandidateReviewDecision = "accept" | "reject" | "pending";
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
}: {
  action: CandidateReviewDecision;
  candidateId: string;
  currentProjectId?: string;
  projectId: string;
  setBackendResult: StateSetter<PlanResponse | null>;
  setCurrentProject: StateSetter<ProjectRecord | null>;
  setStatusMessage: StateSetter<string>;
  token: string | null;
}) {
  const activeProjectId = projectId || currentProjectId;
  if (!token || !activeProjectId) {
    setStatusMessage("Save or load a project before reviewing candidates.");
    return;
  }
  try {
    setStatusMessage(`${action === "accept" ? "Accepting" : action === "reject" ? "Rejecting" : "Keeping"} candidate...`);
    const data = await postJson<{
      success: boolean;
      project?: ProjectRecord;
      candidate_review_inbox_v1?: CandidateReviewInbox;
      truth_label?: string;
    }>(
      `/api/projects/${activeProjectId}/candidate-review`,
      {
        candidate_ids: [candidateId],
        action,
        reason:
          action === "accept"
            ? "Accepted from Candidate Review Inbox as draft/review-required project evidence."
            : action === "reject"
              ? "Rejected from Candidate Review Inbox."
              : "Kept pending from Candidate Review Inbox.",
      },
      { token },
    );
    if (data.project) {
      setCurrentProject(data.project);
      if (data.project.latest_result) {
        setBackendResult(data.project.latest_result);
      }
    } else if (data.candidate_review_inbox_v1) {
      patchPlanMeta(setBackendResult, {
        candidate_review_inbox_v1: data.candidate_review_inbox_v1,
      });
    }
    setStatusMessage(
      action === "accept"
        ? "Candidate accepted as draft/review-required evidence."
        : action === "reject"
          ? "Candidate rejected and preserved in the audit trail."
          : "Candidate kept pending.",
    );
  } catch (error) {
    setStatusMessage(error instanceof Error ? error.message : "Candidate review update failed.");
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
    } else if (data.design_alternatives_v1) {
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
