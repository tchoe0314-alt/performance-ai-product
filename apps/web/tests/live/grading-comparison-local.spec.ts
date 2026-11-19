import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

test("genuine grading comparison survives reopen and disappears after geometry edit", async ({ page, context, request }) => {
  test.setTimeout(180_000);
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !api.startsWith("http://127.0.0.1:"), "Disposable local backend only.");
  const name = `Grading comparison ${randomUUID()}`;
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `grading-${randomUUID()}@example.test`, password: "Disposable-123", name } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const input = withCanonicalCanvasSnapshot({ input_mode: "assisted", allow_ai_fill_for_blanks: true, manual_fields: {
    project_name: name, units: "ft", project_type: "commercial_pad", terrain: "2% slope west to east", setback: 20,
    lot: { x: 0, y: 0, w: 240, h: 180 }, building_width: 60, building_depth: 40,
    site_plan: { building_program_sf: 2400, building_count: 1, building_type: "office", parking_count: 12 },
    site_objects: [
      { id: "parcel", label: "Synthetic parcel", type: "site", x: 0, y: 0, w: 240, d: 180, placed: true },
      { id: "office", label: "Synthetic office", type: "office_building", x: 80, y: 40, w: 60, d: 40, placed: true },
      { id: "parking", label: "Synthetic parking", type: "parking", x: 60, y: 115, w: 120, d: 50, placed: true, meta: { requested_stalls: 12 } },
    ],
  }, meta: { site_inputs: { site_alignment_locked: true } } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: input } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await openWorkspaceTool(page, "Generate");
  const execution = page.waitForResponse(response => response.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(response.url()), { timeout: 20_000 });
  await page.getByTestId("generate-main-action").click();
  const response = await execution;
  expect(response.status()).toBe(200);
  const { job } = await response.json();
  expect(job).toBeTruthy();
  await expect.poll(async () => {
    const current = (await (await request.get(`${api}/api/jobs/${job.job_id}`, { headers })).json()).job;
    if (current.status === "awaiting_approval") {
      const proceed = page.getByTestId("generate-main-action");
      if ((await proceed.textContent())?.includes("Continue after")) await proceed.click();
    }
    return current.status;
  }, { timeout: 120_000, intervals: [1000] }).toBe("completed");
  const savedResult = await request.get(`${api}/api/projects/${project.project_id}/result`, { headers });
  const resultPayload = await savedResult.json();
  expect(resultPayload.result_freshness_v1.status).toBe("current");
  const grading = resultPayload.latest_result.final_plan.meta.grading;
  const cells = grading.surface_model.surface_comparison.cells;
  expect(cells.length).toBeGreaterThan(0);
  const first = cells[0];
  await page.reload();
  const panel = page.getByTestId("grading-earthwork-panel");
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(panel).toContainText(`${Number(grading.earthwork.cut_cf).toFixed(1)} cf`);
  await expect(panel).toContainText(`${Number(grading.earthwork.fill_cf).toFixed(1)} cf`);
  for (const mode of ["existing", "proposed", "difference"] as const) {
    await page.getByTestId(`grading-view-${mode}`).click();
    await expect(page.getByTestId(`grading-view-${mode}`)).toHaveAttribute("aria-pressed", "true");
  }
  await page.getByTestId("grading-comparison-cell").first().click({ force: true });
  const selected = page.getByTestId("grading-selected-area");
  await expect(selected).toContainText(`${Number(first.existing_elevation_ft).toFixed(2)} ft`);
  await expect(selected).toContainText(`${Number(first.proposed_elevation_ft).toFixed(2)} ft`);
  await expect(selected).toContainText(`${Number(first.delta_ft) > 0 ? "+" : ""}${Number(first.delta_ft).toFixed(2)} ft`);
  await expect(selected).toContainText(`excavation ${Number(first.cut_cf).toFixed(1)} cf`);
  await page.reload();
  await expect(page.getByTestId("grading-earthwork-panel")).toBeVisible({ timeout: 30_000 });
  const current = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
  const edited = structuredClone(current.project_input);
  const office = edited.manual_fields.site_objects.find((item: { id: string }) => item.id === "office");
  office.x += 5;
  edited.meta.system_dirty_state.grading = "stale";
  const updated = await request.post(`${api}/api/projects`, { headers, data: { project_id: project.project_id, name, project_input: edited, expected_revision: current.revision_token } });
  expect(updated.status()).toBe(200);
  await page.reload();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await expect(page.getByTestId("grading-earthwork-panel")).toHaveCount(0);
});
