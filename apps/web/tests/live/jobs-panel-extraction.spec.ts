import { expect, test, type Page } from "@playwright/test";
import { JobsPanel } from "../../app/components/JobsPanel";
import { buildDashboardWorkflowState } from "../../app/utils/dashboardWorkflowState";
import type { JobSummary } from "../../app/types";
import { mergeJobSummaries } from "../../app/utils/jobSummaryMerge";

test("lightweight refresh retains completed downloads without restoring stale calculation results", () => {
  const artifact = { artifact_id: "a", filename: "plan.dxf", download_path: "/download/a" };
  const detail = { job_id: "export", job_type: "export_dxf", status: "completed", updated_at: 20,
    artifact_history: [artifact], result: { artifact } } as unknown as JobSummary;
  const refreshed = mergeJobSummaries([detail], [{ job_id: "export", status: "completed", updated_at: 20 } as JobSummary]);
  expect(refreshed[0].artifact_history).toEqual([artifact]);
  expect(refreshed[0].result).toEqual({ artifact });
  expect(mergeJobSummaries([detail], [{ job_id: "export", status: "running", updated_at: 19 } as JobSummary])[0].status).toBe("completed");
  expect(mergeJobSummaries([detail], [{ job_id: "export", status: "running", updated_at: 21 } as JobSummary])[0].result).toBeUndefined();
  expect(mergeJobSummaries([detail], [])).toEqual([]);
});

test("historical job artifacts keep their identity and label when history sources merge", () => {
  const artifact = { artifact_id: "historical-1", filename: "old.pdf", download_path: "/api/artifacts/old.pdf", snapshot_status: "historical" };
  const state = buildDashboardWorkflowState({ jobs: [{ job_id: "export-1", job_type: "export_pdf", status: "failed",
    result: { artifact }, artifact_history: [artifact] } as unknown as JobSummary],
    selectedRunId: "", activeJobId: "", selectedJobId: "", projectId: "", jobClockMs: Date.now(),
    busy: false, activePlanTool: "run", statusMessage: "",
  });
  expect(state.artifactHistory).toHaveLength(1);
  expect(state.artifactHistory[0].snapshot_status).toBe("historical");
});

test("historical artifacts are labelled and retain their download action", () => {
  const tree = JobsPanel({ activeJob: null, selectedJob: null, jobHistory: [], jobStatusCounts: {},
    artifactHistory: [{ artifact_id: "historical-1", filename: "old-plan.pdf", kind: "pdf",
      snapshot_status: "historical", download_path: "/api/artifacts/old-plan.pdf" }],
    activeJobStale: false, selectedJobStale: false, statusMessage: "", formatTimestamp: () => "Now",
    toReadableLabel: value => value, jobDetailMessage: () => "", onRefresh: () => {}, onSelectJob: () => {},
    onCancelJob: () => {}, onRetryJob: () => {}, onResumeJob: () => {}, onDownloadArtifact: () => {},
  });
  const view = JSON.stringify(tree);
  expect(view).toContain("Historical");
  expect(view).toContain("old-plan.pdf");
  expect(view).toContain("Download");
});

async function openJobsPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=jobs", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("async-jobs-panel");
  await expect(panel).toBeVisible({ timeout: 5_000 });
  await expect(panel).toContainText("Job workflow");
  await expect(panel).toContainText("History");
  await expect(panel).toContainText("Artifact history");
  return panel;
}

test("Jobs panel remains reachable and reports refresh blockers clearly", async ({ page }) => {
  const panel = await openJobsPanel(page);

  await expect(panel).toContainText("No active job");
  await expect(panel).toContainText("No background jobs yet.");
  await expect(panel).toContainText("No generated artifacts have been recorded yet.");

  await panel.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByTestId("jobs-refresh-status")).toContainText("Sign in/connect backend to refresh jobs.");
});
