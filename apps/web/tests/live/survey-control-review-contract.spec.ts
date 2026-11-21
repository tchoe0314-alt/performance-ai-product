import { expect, test } from "@playwright/test";

import type { ProjectRecord } from "../../app/types";
import {
  canReviewSurveyControl,
  latestMatchingSurveyControlReview,
  sameSurveyControlReviewTarget,
  surveyControlReviewMessage,
  surveyControlReviewTarget,
} from "../../app/utils/surveyControlReview";

const digestA = `sha256:${"a".repeat(64)}`;
const digestB = `sha256:${"b".repeat(64)}`;

function project(options: {
  projectId?: string;
  role?: ProjectRecord["access_role"];
  sourceId?: string;
  digest?: string;
  complete?: boolean;
  review?: Record<string, unknown>;
} = {}): ProjectRecord {
  const projectId = options.projectId ?? "project-a";
  const sourceId = options.sourceId ?? "survey-a.csv";
  const digest = options.digest ?? digestA;
  return {
    project_id: projectId,
    name: "Synthetic survey review",
    access_role: options.role ?? "reviewer",
    project_input: {
      meta: {
        site_inputs: {
          survey_file: {
            stored_filename: sourceId,
            source_reference: { source_id: sourceId, source_digest: digest, immutable: true },
          },
          survey_control_evidence_review: {
            status: options.complete === false ? "blocked" : "complete_for_review",
            source_digest: options.complete === false ? "" : digest,
          },
        },
      },
    },
    metadata: options.review ? { survey_control_reviews_v1: [options.review] } : {},
  };
}

test("survey review visibility follows the existing project role", () => {
  expect(canReviewSurveyControl(project({ role: "viewer" }))).toBe(false);
  for (const role of ["reviewer", "editor", "admin", "owner"] as const) {
    expect(canReviewSurveyControl(project({ role }))).toBe(true);
  }
  expect(surveyControlReviewTarget(project({ complete: false }))?.completeForReview).toBe(false);
});

test("only the server record bound to the exact current source is displayed", () => {
  const accepted = {
    review_id: "review-a",
    project_id: "project-a",
    source_id: "survey-a.csv",
    source_digest: digestA,
    decision: "accepted_for_review",
    review_only: true,
    grading_authorized: false,
  };
  const current = project({ review: accepted });
  expect(latestMatchingSurveyControlReview(current)?.review_id).toBe("review-a");
  expect(surveyControlReviewMessage(latestMatchingSurveyControlReview(current))).toContain("grading authorization");

  const replaced = project({ sourceId: "survey-b.csv", digest: digestB, review: accepted });
  expect(latestMatchingSurveyControlReview(replaced)).toBeNull();
  expect(sameSurveyControlReviewTarget(replaced, surveyControlReviewTarget(current)!)).toBe(false);

  const switched = project({ projectId: "project-b", review: accepted });
  expect(latestMatchingSurveyControlReview(switched)).toBeNull();
  expect(sameSurveyControlReviewTarget(switched, surveyControlReviewTarget(current)!)).toBe(false);
});

test("rejection remains review-only and does not imply a grading decision", () => {
  expect(surveyControlReviewMessage({ decision: "rejected" })).toContain("Rejected for review");
  expect(surveyControlReviewMessage(null)).toContain("No server-recorded review decision");
});
