import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("workspace switches verified surface views and inspects signed cut/fill", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(!api.startsWith("http://127.0.0.1:"), "Disposable local backend only.");
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `grading-${randomUUID()}@example.test`, password: "Disposable-123", name: "Grading comparison" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json();
  const grading = { existing_surface: { nrows: 2, ncols: 3 }, proposed_surface: { nrows: 2, ncols: 3 },
    earthwork: { cut_cf: 100, fill_cf: 200, net_cf: 100 }, source_quality: "survey-backed", source_detail: "Synthetic known plane",
    surface_model: { schema_version: "surface_artifact_v1", model: "grid", source_type: "survey-backed", control_verified: true, bounds: [0, 0, 20, 10], contours: [], spot_elevations: [], slope_arrows: [], flow_paths: [], surface_comparison: { cells: [
      { x: 5, y: 5, width: 10, height: 10, existing_elevation_ft: 101, proposed_elevation_ft: 100, delta_ft: -1, cut_cf: 100, fill_cf: 0, mode: "cut" },
      { x: 15, y: 5, width: 10, height: 10, existing_elevation_ft: 100, proposed_elevation_ft: 102, delta_ft: 2, cut_cf: 0, fill_cf: 200, mode: "fill" },
    ] } } };
  const created = await request.post(`${api}/api/projects`, { headers: { Authorization: `Bearer ${token}` }, data: { name: "Known grading surfaces", project_input: { input_mode: "user", manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 20, h: 10 }, site_objects: [] }, meta: { system_dirty_state: { grading: "fresh", roads: "not_generated", parking: "not_generated", drainage: "not_generated", utilities: "not_generated" } } }, latest_result: { success: true, final_plan: { project_name: "Known grading surfaces", units: "ft", actions: [], meta: { grading } } } } });
  expect(created.status()).toBe(200);
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Known grading surfaces", exact: true }).click();
  await expect(page.getByTestId("grading-earthwork-panel")).toBeVisible();
  await expect(page.getByTestId("grading-earthwork-panel")).toContainText("Excavation");
  await page.getByTestId("grading-view-existing").click();
  await expect(page.getByTestId("grading-view-existing")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("grading-view-proposed").click();
  await expect(page.getByTestId("grading-view-proposed")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("grading-view-difference").click();
  await page.getByTestId("grading-comparison-cell").first().click({ force: true });
  await expect(page.getByTestId("grading-selected-area")).toContainText("101.00 ft");
  await expect(page.getByTestId("grading-selected-area")).toContainText("100.00 ft");
  await expect(page.getByTestId("grading-selected-area")).toContainText("-1.00 ft");
});
