import { expect, test, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const baseObjects = [
  { id: "site", label: "Synthetic site", type: "site", x: 0, y: 0, w: 600, d: 400, placed: true, locked: true, source: "user" },
  { id: "office", label: "Review office", type: "office_building", x: 120, y: 120, w: 100, d: 60, placed: true, source: "manual_drawn" },
];

async function fixture(request: APIRequestContext, withAccess: boolean) {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `review-scan-${randomUUID()}@example.test`, password: "Disposable-123", name: "Review scan test" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json();
  const objects = withAccess ? [...baseObjects, { id: "road", label: "Review road", type: "road", x: 60, y: 220, w: 420, d: 30, placed: true, source: "manual_drawn" }] : baseObjects;
  const name = `Review scan ${randomUUID()}`;
  const created = await request.post(`${api}/api/projects`, { headers: { Authorization: `Bearer ${token}` }, data: { name, project_input: withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 600, h: 400 }, site_objects: objects } }) } });
  expect(created.status()).toBe(200);
  return { api, token, name, project: (await created.json()).project };
}

test.describe("Review access scan effects", () => {
  test.beforeEach(() => test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1", "Disposable localhost only."));

  test("confirmed building and road produce conceptual access overlay without mutating saved geometry", async ({ page, context, request }) => {
    const item = await fixture(request, true);
    const headers = { Authorization: `Bearer ${item.token}` };
    const saved = async () => (await (await request.get(`${item.api}/api/projects/${item.project.project_id}`, { headers })).json()).project.project_input;
    const before = JSON.stringify(await saved());
    await context.addInitScript(token => { localStorage.setItem("civora-ai-token", token); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, item.token);
    await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    await page.getByTestId("header-projects-button").click();
    await page.getByRole("button", { name: `Open project ${item.name}`, exact: true }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
    await openWorkspaceTool(page, "Review");
    await page.getByRole("button", { name: "Run review scan", exact: true }).click();
    await expect(page.getByText("Site access analysis complete (conceptual).", { exact: true })).toBeVisible();
    const layers = page.getByTestId("preview-layer-menu");
    if (!(await layers.evaluate(node => (node as HTMLDetailsElement).open))) await layers.locator(":scope > summary").click();
    if (await page.getByTestId("preview-source-layer-proposed").getAttribute("aria-pressed") === "false") await page.getByTestId("preview-source-layer-proposed").click();
    await expect(page.getByTestId("analysis-paths-overlay")).toHaveCount(1);
    await expect(page.getByTestId("analysis-path-office-road")).toHaveCount(1);
    expect(JSON.stringify(await saved())).toBe(before);
  });

  test("missing access gives exact guidance, creates no overlay, and preserves saved geometry", async ({ page, context, request }) => {
    const item = await fixture(request, false);
    const headers = { Authorization: `Bearer ${item.token}` };
    const saved = async () => (await (await request.get(`${item.api}/api/projects/${item.project.project_id}`, { headers })).json()).project.project_input;
    const before = JSON.stringify(await saved());
    await context.addInitScript(token => { localStorage.setItem("civora-ai-token", token); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, item.token);
    await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    await page.getByTestId("header-projects-button").click();
    await page.getByRole("button", { name: `Open project ${item.name}`, exact: true }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
    await openWorkspaceTool(page, "Review");
    await page.getByRole("button", { name: "Run review scan", exact: true }).click();
    await expect(page.getByText("Add or confirm roads, driveways, or access objects to run access analysis.", { exact: true }).first()).toBeVisible();
    await expect(page.getByTestId("analysis-paths-overlay")).toHaveCount(0);
    expect(JSON.stringify(await saved())).toBe(before);
  });
});
