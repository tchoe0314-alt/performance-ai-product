import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const disposableLocal = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1"
  && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);

test("GEN-01 fresh Industrial project preserves its explicit program through the real review checkpoint", async ({ page, context, request }) => {
  test.skip(!disposableLocal, "Requires the disposable localhost API and in-process worker.");
  test.setTimeout(150_000);

  const registration = await request.post(`${api}/api/auth/register`, { data: {
    email: `gen01-industrial-${randomUUID()}@example.test`,
    password: "Disposable-industrial-123",
    name: "GEN-01 synthetic fixture",
  } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json();
  const headers = { Authorization: `Bearer ${token}` };
  const projectName = `GEN-01 fresh Industrial ${randomUUID()}`;
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
        site_plan: {
          building_program_sf: 14_400,
          building_count: 1,
          building_type: "industrial",
          parking_count: 48,
        },
        // A locked parcel is the only authored geometry. No authored or
        // historical generated building can satisfy the assertions below.
        site_objects: [{
          id: "gen01-parcel",
          label: "GEN-01 synthetic parcel",
          type: "site",
          x: 0,
          y: 0,
          w: 600,
          d: 400,
          placed: true,
          locked: true,
          source: "manual_drawn",
        }],
      },
      meta: { site_inputs: { site_alignment_locked: true } },
    }),
  } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();

  await context.addInitScript((value) => {
    localStorage.setItem("civora-ai-token", value);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${projectName}`, exact: true }).click();

  await openWorkspaceTool(page, "Setup");
  await expect(page.getByLabel("Project type")).toHaveValue("");
  await page.getByLabel("Project type").selectOption("industrial_site");
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    return (await response.json()).project.project_input.manual_fields.project_type;
  }).toBe("industrial_site");

  await page.reload({ waitUntil: "domcontentloaded" });
  await openWorkspaceTool(page, "Setup");
  await expect(page.getByLabel("Project type")).toHaveValue("industrial_site");
  const before = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields;
  expect(before.site_objects.filter((item: { type?: string }) => String(item.type || "").includes("building"))).toEqual([]);
  expect(before.site_plan).toMatchObject({ building_program_sf: 14_400, parking_count: 48 });

  await openWorkspaceTool(page, "Generate");
  const queuedResponse = page.waitForResponse(
    response => response.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(response.url()),
    { timeout: 20_000 },
  );
  await page.getByTestId("generate-main-action").click();
  const queued = await queuedResponse;
  expect(queued.status()).toBe(200);
  const queuedBody = await queued.json();
  expect(queuedBody.job?.job_id).toBeTruthy();
  const jobId = queuedBody.job.job_id as string;

  let job: any = null;
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/jobs/${jobId}`, { headers });
    expect(response.status()).toBe(200);
    job = (await response.json()).job;
    return job.status;
  }, { timeout: 120_000, intervals: [500, 1_000, 2_000] }).toBe("awaiting_approval");

  expect(job.result?.parsed_payload).toMatchObject({
    project_type: "industrial_site",
    site_type: "industrial_site",
    site_plan: {
      building_program_sf: 14_400,
      building_type: "industrial",
      parking_count: 48,
    },
  });
  expect(job.result?.metadata?.runtime_phase_checkpoint).toMatchObject({
    stage_name: "grading",
    yielded: true,
  });
  expect(job.result?.final_plan?.meta?.phase_checkpoints?.layout).toMatchObject({
    status: "failed",
    ready: false,
  });
  expect(job.can_resume).toBe(true);

  const saved = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields;
  expect(saved.project_type).toBe("industrial_site");
  expect(saved.site_plan).toMatchObject({ building_program_sf: 14_400, parking_count: 48 });
  const buildings = saved.site_objects.filter((item: { type?: string }) => String(item.type || "").includes("building"));
  expect(buildings).toHaveLength(1);
  expect(buildings[0]).toMatchObject({
    type: "industrial_building",
    meta: {
      requested_area_sf: 14_400,
      requested_project_type: "industrial_site",
    },
  });
  expect(saved.site_objects.some((item: { type?: string }) => item.type === "office_building")).toBe(false);
  expect(saved.site_objects.some((item: { type?: string; label?: string }) =>
    item.type === "parking" && /48 stalls/i.test(String(item.label || "")))).toBe(true);

  await expect(page.getByTestId("generate-review-hold")).toContainText(/Review grading/i);
  await expect(page.getByTestId("generate-main-action")).toContainText(/Continue after grading/i);
  // Rendering and polling must never consume the approval automatically.
  const stillHeld = await (await request.get(`${api}/api/jobs/${jobId}`, { headers })).json();
  expect(stillHeld.job.status).toBe("awaiting_approval");
});
