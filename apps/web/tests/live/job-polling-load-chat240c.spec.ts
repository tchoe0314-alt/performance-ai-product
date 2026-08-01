import { expect, test } from "@playwright/test";

test("an approval hold does not create overlapping project or job polling", async ({ page }) => {
  let jobListCalls = 0;
  let jobDetailCalls = 0;
  let projectResultCalls = 0;

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
    if (path === "/api/jobs" && request.method() === "GET") {
      jobListCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [job] }) });
      return;
    }
    if (path === `/api/jobs/${job.job_id}`) {
      jobDetailCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, job }) });
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
  await page.waitForTimeout(8_000);

  expect(jobListCalls).toBeLessThanOrEqual(2);
  expect(jobDetailCalls).toBeLessThanOrEqual(1);
  expect(projectResultCalls).toBeLessThanOrEqual(3);
});
