import type { ProjectRecord } from "../types";

export type SurveyControlReviewRecord = {
  review_id?: string;
  project_id?: string;
  source_id?: string;
  source_digest?: string;
  reviewer_user_id?: string;
  reviewer_role?: string;
  decision?: "accepted_for_review" | "rejected" | string;
  reviewed_at?: number;
  review_only?: boolean;
  grading_authorized?: boolean;
  construction_release_allowed?: boolean;
};

export type SurveyControlReviewTarget = {
  projectId: string;
  sourceId: string;
  sourceDigest: string;
  completeForReview: boolean;
};

const roleRank: Record<string, number> = { viewer: 0, reviewer: 1, editor: 2, admin: 3, owner: 4 };

export function surveyControlReviewTarget(project: ProjectRecord | null): SurveyControlReviewTarget | null {
  const siteInputs = project?.project_input?.meta?.site_inputs ?? {};
  const surveyFile = siteInputs.survey_file && typeof siteInputs.survey_file === "object"
    ? siteInputs.survey_file as Record<string, unknown>
    : {};
  const source = surveyFile.source_reference && typeof surveyFile.source_reference === "object"
    ? surveyFile.source_reference as Record<string, unknown>
    : {};
  const evidence = siteInputs.survey_control_evidence_review && typeof siteInputs.survey_control_evidence_review === "object"
    ? siteInputs.survey_control_evidence_review as Record<string, unknown>
    : {};
  const sourceId = String(source.source_id ?? "").trim();
  const sourceDigest = String(source.source_digest ?? "").trim().toLowerCase();
  if (!project?.project_id || source.immutable !== true || !sourceId || !/^sha256:[0-9a-f]{64}$/.test(sourceDigest)) return null;
  return {
    projectId: project.project_id,
    sourceId,
    sourceDigest,
    completeForReview: evidence.status === "complete_for_review" && String(evidence.source_digest ?? "").trim().toLowerCase() === sourceDigest,
  };
}

export function canReviewSurveyControl(project: ProjectRecord | null): boolean {
  return (roleRank[project?.access_role ?? "owner"] ?? -1) >= roleRank.reviewer;
}

export function latestMatchingSurveyControlReview(project: ProjectRecord | null): SurveyControlReviewRecord | null {
  const target = surveyControlReviewTarget(project);
  if (!target) return null;
  const history = Array.isArray(project?.metadata?.survey_control_reviews_v1)
    ? project.metadata.survey_control_reviews_v1 as SurveyControlReviewRecord[]
    : [];
  return [...history].reverse().find((item) =>
    item?.project_id === target.projectId
    && item?.source_id === target.sourceId
    && String(item?.source_digest ?? "").toLowerCase() === target.sourceDigest
  ) ?? null;
}

export function sameSurveyControlReviewTarget(
  project: ProjectRecord | null,
  expected: SurveyControlReviewTarget,
): boolean {
  const current = surveyControlReviewTarget(project);
  return Boolean(current
    && current.projectId === expected.projectId
    && current.sourceId === expected.sourceId
    && current.sourceDigest === expected.sourceDigest);
}

export function surveyControlReviewMessage(review: SurveyControlReviewRecord | null): string {
  if (!review) return "No server-recorded review decision for this exact survey source.";
  if (review.decision === "accepted_for_review") {
    return "Accepted for review. Survey certification, grading authorization, and construction release remain blocked.";
  }
  if (review.decision === "rejected") return "Rejected for review. Replace or correct the survey-control evidence before resubmitting.";
  return "The server returned an unsupported survey-control review state.";
}
