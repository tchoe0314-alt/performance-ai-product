import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const disposableLocal = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1"
  && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);
type HeldJob = {
  job_id: string;
  status: string;
  can_resume?: boolean;
  result?: { metadata?: { runtime_phase_checkpoint?: { stage_name?: string; yielded?: boolean } } };
};

test("REL-01 reconnects to the same held job without approving or dispatching again", async ({ page, context, request }) => {
  test.skip(!disposableLocal, "Requires the disposable localhost API and in-process worker.");
  test.setTimeout(150_000);

  const registration = await request.post(`${api}/api/auth/register`, { data: {
    email: `rel01-reconnect-${randomUUID()}@example.test`,
    password: "Disposable-reconnect-123",
    name: "REL-01 synthetic fixture",
  } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json();
  const headers = { Authorization: `Bearer ${token}` };
  const projectName = `REL-01 reconnect ${randomUUID()}`;
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name: projectName,
    project_input: withCanonicalCanvasSnapshot({
      input_mode: "assisted",
      allow_ai_fill_for_blanks: true,
      prompt_text: "Prepare the saved site program without changing its requested type or counts.",
      manual_fields: {
        units: "ft",
        project_type: "",
        lot: { x: 0, y: 0, w: 600, h: 400 },
        site_plan: { building_program_sf: 14_400, building_count: 1, building_type: "industrial", parking_count: 48 },
        site_objects: [{
          id: "rel01-parcel", label: "REL-01 parcel", type: "site",
          x: 0, y: 0, w: 600, d: 400, placed: true, locked: true, source: "manual_drawn",
        }],
      },
      meta: { site_inputs: { site_alignment_locked: true } },
    }),
  } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();

  let orchestratePosts = 0;
  let continuePosts = 0;
  let exportRequests = 0;
  page.on("request", browserRequest => {
    const path = new URL(browserRequest.url()).pathname;
    if (browserRequest.method() === "POST" && path === "/api/jobs/orchestrate") orchestratePosts += 1;
    if (browserRequest.method() === "POST" && /\/api\/jobs\/[^/]+\/continue$/.test(path)) continuePosts += 1;
    if (/\/(?:export|artifacts)(?:\/|$)/.test(path)) exportRequests += 1;
  });
  await context.addInitScript(value => {
    localStorage.setItem("civora-ai-token", value.token);
    localStorage.setItem("civora.activeProjectId", value.projectId);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, { token, projectId: project.project_id });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${projectName}`, exact: true }).click();
  await openWorkspaceTool(page, "Setup");
  await page.getByLabel("Project type").selectOption("industrial_site");
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    return (await response.json()).project.project_input.manual_fields.project_type;
  }).toBe("industrial_site");

  await openWorkspaceTool(page, "Generate");
  const queuedResponse = page.waitForResponse(response =>
    response.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(response.url()));
  await page.getByTestId("generate-main-action").click();
  const queued = await queuedResponse;
  expect(queued.status()).toBe(200);
  const jobId = (await queued.json()).job.job_id as string;
  expect(jobId).toBeTruthy();
  expect(orchestratePosts).toBe(1);

  await context.setOffline(true);
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/jobs/${jobId}`, { headers });
    return ((await response.json()).job as HeldJob).status;
  }, { timeout: 120_000, intervals: [500, 1_000, 2_000] }).toBe("awaiting_approval");
  const heldJob = (await (await request.get(`${api}/api/jobs/${jobId}`, { headers })).json()).job as HeldJob;
  expect(heldJob?.result?.metadata?.runtime_phase_checkpoint).toMatchObject({ stage_name: "layout", yielded: true });
  expect(heldJob?.can_resume).toBe(true);
  expect(continuePosts).toBe(0);

  await context.setOffline(false);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await openWorkspaceTool(page, "Generate");
  await expect(page.getByTestId("generate-review-hold")).toContainText(/Review layout/i, { timeout: 30_000 });
  await expect(page.getByTestId("generate-main-action")).toContainText(/Continue after layout/i);

  const reloadedJob = (await (await request.get(`${api}/api/jobs/${jobId}`, { headers })).json()).job;
  expect(reloadedJob.job_id).toBe(jobId);
  expect(reloadedJob.status).toBe("awaiting_approval");
  expect(reloadedJob.result?.metadata?.runtime_phase_checkpoint).toMatchObject({ stage_name: "layout", yielded: true });
  const jobs = (await (await request.get(`${api}/api/jobs`, { headers })).json()).jobs as Array<{ job_id: string; project_id: string }>;
  expect(jobs.filter(job => job.project_id === project.project_id).map(job => job.job_id)).toEqual([jobId]);
  expect(orchestratePosts).toBe(1);
  expect(continuePosts).toBe(0);
  expect(exportRequests).toBe(0);

  const reopened = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields;
  expect(reopened.project_type).toBe("industrial_site");
  expect(reopened.site_plan).toMatchObject({ building_program_sf: 14_400, parking_count: 48 });
  expect(reopened.site_objects.some((item: { type?: string; meta?: { requested_area_sf?: number } }) =>
    item.type === "industrial_building" && item.meta?.requested_area_sf === 14_400)).toBe(true);
});
