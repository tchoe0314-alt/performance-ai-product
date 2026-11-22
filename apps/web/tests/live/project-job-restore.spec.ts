import { expect, test, type Route } from "@playwright/test";

import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const project = {
  project_id: "project-reopen-held-layout",
  name: "Reopen held layout",
  description: "",
  has_result: true,
  updated_at: 1_795_300_001,
  project_input: {
    input_mode: "user",
    manual_fields: {
      units: "ft",
      project_type: "industrial_site",
      lot: { x: 0, y: 0, w: 551, h: 559 },
      site_objects: [{
        id: "parcel-reopen",
        type: "site",
        label: "Saved site boundary",
        x: 0,
        y: 0,
        w: 551,
        d: 559,
        placed: true,
        locked: true,
      }],
    },
    meta: { site_inputs: { site_alignment_locked: true } },
  },
};

const checkpointResult = {
  success: true,
  final_plan: { project_name: project.name, actions: [], meta: {} },
  metadata: {
    runtime_phase_checkpoint: {
      stage_name: "layout",
      yielded: true,
      awaiting_approval: true,
    },
  },
};

const heldJob = {
  job_id: "job-reopen-held-layout",
  project_id: project.project_id,
  job_type: "orchestrate",
  status: "awaiting_approval",
  stage: "Awaiting Approval",
  stage_detail: "Layout stage completed.",
  progress: 12,
  updated_at: 1_795_300_002,
  can_cancel: true,
  can_resume: true,
  result: checkpointResult,
};

async function fulfillSave(route: Route): Promise<boolean> {
  if (new URL(route.request().url()).pathname !== "/api/projects" || route.request().method() !== "POST") {
    return false;
  }
  await route.fulfill({ json: { success: true, project } });
  return true;
}

test("opening a saved project reconciles a held job missed by the cold auth refresh", async ({ page }) => {
  let jobListCalls = 0;
  let detailCalls = 0;
  await page.route("**/api/**", async route => {
    if (await fulfillSave(route)) return;
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/me") return route.fulfill({ json: { user: { user_id: "qa-user", name: "QA", email: "qa@example.test" } } });
    if (path === "/api/auth/status") return route.fulfill({ json: { auth_enabled: true, public_registration_enabled: false } });
    if (path === "/api/projects" && route.request().method() === "GET") return route.fulfill({ json: { projects: [project] } });
    if (path === `/api/projects/${project.project_id}`) return route.fulfill({ json: { project } });
    if (path === `/api/projects/${project.project_id}/result`) return route.fulfill({ json: { latest_result: checkpointResult } });
    if (path === "/api/jobs") {
      jobListCalls += 1;
      // Model the observed reconnect window: auth restoration completes before
      // the newly durable job is visible, but project-open reconciliation sees it.
      return route.fulfill({ json: { jobs: jobListCalls === 1 ? [] : [
        { ...heldJob, job_id: "job-other-project", project_id: "project-other", updated_at: heldJob.updated_at + 10 },
        { ...heldJob, job_id: "job-failed-same-project", status: "failed", can_resume: false, updated_at: heldJob.updated_at + 5 },
        heldJob,
      ] } });
    }
    if (path === `/api/jobs/${heldJob.job_id}`) {
      detailCalls += 1;
      return route.fulfill({ json: { job: heldJob } });
    }
    if (path === "/api/preview") return route.fulfill({ json: { success: true, image_url: "", summary: {} } });
    return route.fulfill({ json: { success: true } });
  });

  await page.addInitScript(() => {
    localStorage.setItem("civora-ai-token", "fixture-token");
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${project.name}`, exact: true }).click();
  await openWorkspaceTool(page, "Generate");

  await expect(page.getByTestId("generate-review-hold")).toContainText(/Review layout/i);
  await expect(page.getByTestId("generate-main-action")).toContainText(/Continue after layout/i);
  expect(jobListCalls).toBe(2);
  expect(detailCalls).toBe(1);
});

test("project reopen does not offer Continue for missing, terminal, or another project's job", async ({ page }) => {
  await page.route("**/api/**", async route => {
    if (await fulfillSave(route)) return;
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/auth/me") return route.fulfill({ json: { user: { user_id: "qa-user", name: "QA", email: "qa@example.test" } } });
    if (path === "/api/auth/status") return route.fulfill({ json: { auth_enabled: true, public_registration_enabled: false } });
    if (path === "/api/projects" && route.request().method() === "GET") return route.fulfill({ json: { projects: [project] } });
    if (path === `/api/projects/${project.project_id}`) return route.fulfill({ json: { project } });
    if (path === `/api/projects/${project.project_id}/result`) return route.fulfill({ json: { latest_result: checkpointResult } });
    if (path === "/api/jobs") return route.fulfill({ json: { jobs: [
      { ...heldJob, job_id: "job-other-project", project_id: "project-other" },
      { ...heldJob, job_id: "job-failed-same-project", status: "failed", can_resume: false },
    ] } });
    if (path === "/api/preview") return route.fulfill({ json: { success: true, image_url: "", summary: {} } });
    return route.fulfill({ json: { success: true } });
  });
  await page.addInitScript(() => {
    localStorage.setItem("civora-ai-token", "fixture-token");
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${project.name}`, exact: true }).click();
  await openWorkspaceTool(page, "Generate");
  await expect(page.getByTestId("generate-main-action")).toHaveText("Generate");
  await expect(page.getByTestId("generate-review-hold")).toHaveCount(0);
});
