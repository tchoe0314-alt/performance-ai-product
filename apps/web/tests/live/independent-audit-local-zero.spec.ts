import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

for (const requirement of [{ setback: 0, parking: 0 }, { setback: 20, parking: 140 }]) {
test(`requirements ${requirement.setback}/${requirement.parking} survive real project opening and an unrelated header save`, async ({ page, context, request }, info) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const signup = await request.post(`${api}/api/auth/register`, { data: { email: `zero-audit-${randomUUID()}@example.test`, password: "Disposable-123", name: "Independent zero audit" } });
  expect(signup.status()).toBe(200);
  const { token } = await signup.json(), headers = { Authorization: `Bearer ${token}` };
  const input = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", setback: requirement.setback, lot: { x: 0, y: 0, w: 900, h: 700 }, site_plan: { parking_count: requirement.parking }, site_objects: [] } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Zero requirements audit", project_input: input } });
  expect(created.status()).toBe(200); const project = (await created.json()).project;
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click(); await page.getByRole("button", { name: "Open project Zero requirements audit", exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openWorkspaceTool(page, "Setup");
  const summary = page.getByTestId("active-brief-summary");
  const before = { setback: await summary.getByTestId("brief-value-setbacks").textContent(), parking: await summary.getByTestId("brief-value-required-parking").textContent() };
  await info.attach("zero-before-save", { body: JSON.stringify(before), contentType: "application/json" });
  await page.getByRole("button", { name: "Project details", exact: true }).click();
  const details = page.getByTestId("project-header-details");
  await details.getByLabel("Project name", { exact: true }).fill("Zero requirements audit renamed");
  await details.getByRole("button", { name: "Save details", exact: true }).click();
  await expect.poll(async () => (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.name).toBe("Zero requirements audit renamed");
  await expect.soft(page.getByTestId("header-save-status")).toContainText("Saved");
  const saved = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
  const restored = resolveCanonicalCanvasInput(saved.project_input);
  await info.attach("zero-after-save", { body: JSON.stringify({ setback: restored.manual_fields?.setback ?? "ABSENT", parking: restored.manual_fields?.site_plan?.parking_count ?? "ABSENT" }), contentType: "application/json" });
  await page.screenshot({ path: info.outputPath("zero-requirements-after-save.png") });
  expect.soft(before.setback).toContain(`${requirement.setback} ft`);
  expect.soft(restored.manual_fields?.setback).toBe(requirement.setback);
  expect.soft(restored.manual_fields?.site_plan?.parking_count).toBe(requirement.parking);
});
}

test("deleting the final object saves an empty canonical canvas and survives reload", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const signup = await request.post(`${api}/api/auth/register`, { data: { email: `empty-canvas-${randomUUID()}@example.test`, password: "Disposable-123", name: "Empty canvas regression" } });
  expect(signup.status()).toBe(200);
  const { token } = await signup.json(), headers = { Authorization: `Bearer ${token}` };
  const input = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 900, h: 700 }, site_objects: [{ id: "last-building", label: "Last building", type: "building", x: 100, y: 100, w: 100, d: 100, source: "manual_drawn" }] } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Final object regression", project_input: input } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Final object regression", exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openWorkspaceTool(page, "Draw");
  const panel = page.getByTestId("object-manager-panel");
  if (!(await panel.evaluate(element => element.hasAttribute("open")))) await panel.locator("summary").click();
  const row = page.getByTestId("object-manager-row").filter({ hasText: "Last building" });
  await row.getByTestId("object-manager-delete").click();
  await expect(row).toHaveCount(0);
  await expect.poll(async () => {
    const saved = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
    return resolveCanonicalCanvasInput(saved.project_input).manual_fields?.site_objects;
  }).toEqual([]);
  await expect(page.getByTestId("header-save-status")).toContainText("Saved");
  await page.reload();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await openWorkspaceTool(page, "Draw");
  await expect(page.getByTestId("object-manager-row").filter({ hasText: "Last building" })).toHaveCount(0);
});
