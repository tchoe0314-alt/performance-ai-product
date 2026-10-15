import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

test("local website saves five strategies, compares and chooses without inventing layout geometry or fresh quantities", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `strategies-${randomUUID()}@example.test`, password: "Disposable-123", name: "Strategy regression" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const input = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", site_objects: [{ id: "office", type: "building", label: "Office", x: 100, y: 100, w: 120, d: 80, placed: true }] } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Strategy regression", project_input: input, latest_result: { success: true, final_plan: { units: "ft", actions: [], meta: { quantities: { totals: { paving_area_sf: 9999 } } } } } } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  const saved = async () => {
    const details = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
    const result = await request.get(`${api}/api/projects/${project.project_id}/result`, { headers });
    expect(result.status()).toBe(200);
    return { ...details, latest_result: (await result.json()).latest_result };
  };
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Strategy regression", exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openWorkspaceTool(page, "Deliver");
  await page.getByTestId("workspace-stage-panel").selectOption("reports");
  const alternatives = page.getByTestId("design-alternatives-panel");
  await alternatives.getByRole("button", { name: "Show 5 Strategies" }).click();
  await expect.poll(async () => (await saved()).latest_result.final_plan.meta.design_alternatives_v1?.alternative_count).toBe(5);
  await expect(alternatives.getByRole("button", { name: "Use Option", exact: true })).toHaveCount(5);
  await expect(alternatives).toContainText("No alternative geometry or feasibility checks.");
  await alternatives.getByRole("button", { name: "Compare", exact: true }).click();
  await alternatives.getByRole("button", { name: "Use Option", exact: true }).nth(4).click();
  await expect.poll(async () => (await saved()).latest_result.final_plan.meta.design_alternatives_v1.selected_alternative?.option_number).toBe(5);
  const reopened = await saved();
  expect(reopened.project_input.manual_fields.site_objects).toEqual(input.manual_fields?.site_objects);
  expect(reopened.latest_result.final_plan.meta.quantities.totals.paving_area_sf).toBe(9999);
  expect(reopened.latest_result.final_plan.meta.design_alternatives_v1.quantity_basis.available).toBe(false);
  for (const option of reopened.latest_result.final_plan.meta.design_alternatives_v1.alternatives) expect(option.cost_quantity_comparison.available).toBe(false);
  await page.reload(); await openWorkspaceTool(page, "Deliver");
  await page.getByTestId("workspace-stage-panel").selectOption("reports");
  await expect(alternatives).toContainText("selected");
});

test("Design alternatives panel remains reachable after extraction", async ({ page }) => {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=reports", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  const panel = page.getByTestId("workspace-right-panel");
  const alternatives = panel.getByTestId("design-alternatives-panel");
  await expect(alternatives).toBeVisible({ timeout: 5_000 });
  await expect(alternatives).toContainText("Design Alternatives");
  await expect(alternatives).toContainText("Review required");
  await expect(alternatives).toContainText("Options");
  await expect(alternatives).toContainText("Accepted inputs");
  await expect(alternatives.getByRole("button", { name: "Show 5 Strategies" })).toBeVisible();
  await expect(alternatives).toContainText("No alternative geometry or feasibility checks.");
  await expect(alternatives.getByRole("button", { name: "Compare" })).toBeDisabled();
  await expect(alternatives).toContainText(/concept alternatives|review only|review-required/i);
});
