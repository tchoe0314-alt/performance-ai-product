import { expect, test } from "@playwright/test";

test("an approval hold does not create overlapping project or job polling", async ({ page }) => {
  let jobListCalls = 0;
  let jobDetailCalls = 0;
  let projectResultCalls = 0;
  let continueCalls = 0;
  let queueCalls = 0;
  let continued = false;
  let jobListInFlight = 0;
  let maxJobListInFlight = 0;
  let jobDetailInFlight = 0;
  let maxJobDetailInFlight = 0;

  const project = {
    project_id: "project-awaiting",
    name: "Approval checkpoint project",
    description: "",
    has_result: true,
    updated_at: Date.now() / 1000,
    project_input: {
      input_mode: "user",
      manual_fields: { lot: { w: 720, h: 520 } },
      meta: { site_inputs: { site_alignment_locked: true } },
    },
  };
  const job = {
    job_id: "job-awaiting",
    project_id: project.project_id,
    job_type: "orchestrate",
    status: "awaiting_approval",
    stage: "Awaiting Approval",
    stage_detail: "Storm checkpoint is ready for review.",
    progress: 60,
    updated_at: Date.now() / 1000,
    can_cancel: true,
    can_retry: false,
    can_resume: true,
    result: {
      success: true,
      final_plan: { project_name: project.name, actions: [], meta: {} },
      metadata: {
        runtime_phase_checkpoint: {
          stage_name: "storm_pipes",
          status: "complete",
          yielded: true,
        },
      },
    },
  };

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/api/auth/status") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, auth_enabled: true, account_setup: "configured" }) });
      return;
    }
    if (path === "/api/auth/me") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, user: { user_id: "user-1", email: "user@example.com", name: "User" } }) });
      return;
    }
    if (path === "/api/projects" && request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [project] }) });
      return;
    }
    if (path === `/api/projects/${project.project_id}`) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, project }) });
      return;
    }
    if (path === `/api/projects/${project.project_id}/result`) {
      projectResultCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, project_id: project.project_id, latest_result: job.result }) });
      return;
    }
    if (path === "/api/jobs/orchestrate" && request.method() === "POST") {
      queueCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: { ...job, status: "queued", stage: "Queued", stage_detail: "Workflow queued." },
        }),
      });
      return;
    }
    if (path === "/api/jobs" && request.method() === "GET") {
      jobListCalls += 1;
      jobListInFlight += 1;
      maxJobListInFlight = Math.max(maxJobListInFlight, jobListInFlight);
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          jobs: [continued ? { ...job, status: "running", stage: "Utilities", can_resume: false } : job],
        }),
      });
      jobListInFlight -= 1;
      return;
    }
    if (path === `/api/jobs/${job.job_id}`) {
      jobDetailCalls += 1;
      jobDetailInFlight += 1;
      maxJobDetailInFlight = Math.max(maxJobDetailInFlight, jobDetailInFlight);
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, job: continued ? { ...job, status: "running", stage: "Utilities", can_resume: false } : job }),
      });
      jobDetailInFlight -= 1;
      return;
    }
    if (path === `/api/jobs/${job.job_id}/continue` && request.method() === "POST") {
      continueCalls += 1;
      continued = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            ...job,
            status: "running",
            stage: "Utilities",
            stage_detail: "Continuing to the next applicable stage.",
            can_resume: false,
          },
        }),
      });
      return;
    }
    if (path === "/api/preview") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, image_url: "", summary: {} }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });

  await page.addInitScript((projectId) => {
    window.localStorage.setItem("civora-ai-token", "test-token");
    window.localStorage.setItem("civora.activeProjectId", projectId);
    window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, project.project_id);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  await page.getByRole("button", { name: /^Generate\b/i }).filter({ visible: true }).first().click();
  await page.getByTestId("generate-main-action").click();
  await expect.poll(() => queueCalls).toBe(1);
  await expect(page.getByTestId("generate-review-hold")).toContainText(/Review storm pipes/i);
  await expect(page.getByTestId("generate-main-action")).toContainText(/Continue after storm pipes/i);
  const jobListCallsBeforeContinue = jobListCalls;
  await page.getByTestId("generate-main-action").click();
  await expect.poll(() => continueCalls).toBe(1);
  await expect(page.getByTestId("generate-latest-status")).toContainText(/Continuing to the next applicable stage/i);

  expect(jobListCalls).toBeLessThanOrEqual(jobListCallsBeforeContinue + 1);
  expect(jobDetailCalls).toBeLessThanOrEqual(2);
  expect(maxJobListInFlight).toBeLessThanOrEqual(1);
  expect(maxJobDetailInFlight).toBeLessThanOrEqual(1);
  expect(projectResultCalls).toBeLessThanOrEqual(3);
});

test("a completed job does not block the next review export", async ({ page }) => {
  let exportCalls = 0;
  const project = {
    project_id: "project-export-ready",
    name: "Export Ready Review",
    description: "",
    has_result: true,
    updated_at: Date.now() / 1000,
    project_input: {
      input_mode: "user",
      manual_fields: { lot: { w: 720, h: 520 } },
      meta: { site_inputs: { site_alignment_locked: true } },
    },
  };
  const result = {
    success: true,
    final_plan: {
      project_name: project.name,
      actions: [],
      meta: {
        export_package_report_v1: { review_ready: true, blockers: [] },
      },
    },
  };
  const completedJob = {
    job_id: "job-completed",
    project_id: project.project_id,
    job_type: "orchestrate",
    status: "completed",
    stage: "Complete",
    stage_detail: "Review workflow completed.",
    progress: 100,
    updated_at: Date.now() / 1000,
    can_cancel: false,
    can_retry: false,
    can_resume: false,
    result,
  };

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/auth/status") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, auth_enabled: true, account_setup: "configured" }) });
      return;
    }
    if (path === "/api/auth/me") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, user: { user_id: "user-1", email: "user@example.com", name: "User" } }) });
      return;
    }
    if (path === "/api/projects" && request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [project] }) });
      return;
    }
    if (path === `/api/projects/${project.project_id}`) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, project }) });
      return;
    }
    if (path === `/api/projects/${project.project_id}/result`) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, project_id: project.project_id, latest_result: result }) });
      return;
    }
    if (path === "/api/jobs" && request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [completedJob] }) });
      return;
    }
    if (path === `/api/jobs/${completedJob.job_id}`) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, job: completedJob }) });
      return;
    }
    if (path === "/api/jobs/export/dxf" && request.method() === "POST") {
      exportCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            ...completedJob,
            job_id: "job-export-dxf",
            job_type: "export_dxf",
            status: "queued",
            stage: "Queued",
            stage_detail: "DXF review export queued.",
            progress: 0,
          },
        }),
      });
      return;
    }
    if (path === "/api/preview") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, image_url: "", summary: {} }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });

  await page.addInitScript((projectId) => {
    window.localStorage.setItem("civora-ai-token", "test-token");
    window.localStorage.setItem("civora.activeProjectId", projectId);
    window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, project.project_id);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  await page.getByRole("button", { name: /^Deliver\b/i }).filter({ visible: true }).first().click();
  const deliverPanel = page.getByTestId("workspace-right-panel");
  await expect(deliverPanel).toContainText(/Review package/i);
  await deliverPanel.getByRole("button", { name: /Make Review Package/i }).click();
  await deliverPanel.getByRole("button", { name: "Export DXF" }).click();
  await expect.poll(() => exportCalls).toBe(1);
  await expect(page.getByTestId("deliver-export-status")).toContainText(/DXF review export queued as job-export-dxf/i);
  await expect(page.getByTestId("deliver-export-status")).not.toContainText(/already running|waiting for the current/i);
});

test("a completed staged run replaces the queued global status", async ({ page }) => {
  const project = {
    project_id: "project-status-complete",
    name: "Completed Status Project",
    description: "",
    has_result: false,
    updated_at: Date.now() / 1000,
    project_input: {
      input_mode: "user",
      manual_fields: { lot: { w: 720, h: 520 } },
      meta: { site_inputs: { site_alignment_locked: true } },
    },
  };
  const result = {
    success: true,
    final_plan: { project_name: project.name, actions: [], meta: {} },
  };
  const completedJob = {
    job_id: "job-status-complete",
    project_id: project.project_id,
    job_type: "orchestrate",
    status: "completed",
    stage: "Complete",
    stage_detail: "Review workflow completed.",
    progress: 100,
    updated_at: Date.now() / 1000,
    can_cancel: false,
    can_retry: false,
    can_resume: false,
    result,
  };

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/auth/status") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, auth_enabled: true }) });
      return;
    }
    if (path === "/api/auth/me") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, user: { user_id: "user-1", email: "user@example.com", name: "User" } }) });
      return;
    }
    if (path === "/api/projects" && request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [project] }) });
      return;
    }
    if (path === `/api/projects/${project.project_id}`) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, project }) });
      return;
    }
    if (path === `/api/projects/${project.project_id}/result`) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, project_id: project.project_id, latest_result: result }) });
      return;
    }
    if (path === "/api/jobs/orchestrate" && request.method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, job: { ...completedJob, status: "queued", stage: "Queued", result: null } }),
      });
      return;
    }
    if (path === "/api/jobs" && request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [completedJob] }) });
      return;
    }
    if (path === `/api/jobs/${completedJob.job_id}`) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, job: completedJob }) });
      return;
    }
    if (path === "/api/preview") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, image_url: "", summary: {} }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });

  await page.addInitScript((projectId) => {
    window.localStorage.setItem("civora-ai-token", "test-token");
    window.localStorage.setItem("civora.activeProjectId", projectId);
    window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, project.project_id);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  await page.getByRole("button", { name: /^Generate\b/i }).filter({ visible: true }).first().click();
  await page.getByTestId("generate-main-action").click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Generate completed", { timeout: 15_000 });
  await expect(page.getByTestId("project-status-summary")).not.toContainText("Generate queued");
});
