import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { buildActiveBriefSummary } from "../../app/utils/activeBriefSummary";

const pilotInput = () => withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 900, h: 700 }, site_plan: { parking_count: 60 }, site_objects: [
  { id: "site", label: "Pilot parcel", type: "site", x: 0, y: 0, w: 900, d: 700, placed: true },
  { id: "office", label: "Pilot office", type: "building", x: 300, y: 120, w: 160, d: 90, placed: true },
  { id: "parking", label: "Pilot parking", type: "parking", x: 240, y: 360, w: 330, d: 150, placed: true, stall_count: 60 },
  { id: "entry", label: "Fixed access", type: "entrance", x: 60, y: 650, w: 20, d: 20, placed: true, locked: true },
] } });

test("adding parking through chat does not overwrite a sourced requirement", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `protected-parking-${randomUUID()}@example.test`, password: "Disposable-123", name: "Protected parking regression" } });
  expect(registered.status()).toBe(200); const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const input = pilotInput(), row = buildActiveBriefSummary(input).find(item => item.id === "required-parking")!;
  input.meta = { site_inputs: { active_brief_classifications_v1: { version: 1, fields: { "required-parking": { priority: "required", trust: "sourced", source_reference: "Regression requirement reference", value_key: row.valueKey } } } } };
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Protected parking command", project_input: withCanonicalCanvasSnapshot(input) } });
  expect(created.status()).toBe(200); const { project } = await created.json();
  const saved = async () => resolveCanonicalCanvasInput((await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input);
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Protected parking command", exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("add 40 parking stalls");
  await page.getByTestId("civora-command-input").press("Enter");
  await expect.poll(async () => (await saved()).manual_fields?.site_objects?.length ?? 0).toBeGreaterThan(4);
  expect((await saved()).manual_fields?.site_plan?.parking_count).toBe(60);
  await openWorkspaceTool(page, "Setup");
  const parking = page.getByTestId("active-brief-summary").getByTestId("brief-value-required-parking");
  await expect(parking).toContainText("60 spaces");
  await expect(parking.getByTestId("brief-trust")).toContainText("sourced");
});

test("shared viewer can compare but cannot apply geometry alternatives", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const register = async (name: string) => {
    const response = await request.post(`${api}/api/auth/register`, { data: { email: `layout-view-${randomUUID()}@example.test`, password: "Disposable-123", name } });
    expect(response.status()).toBe(200); return response.json();
  };
  const owner = await register("Owner"), viewer = await register("Viewer"), headers = { Authorization: `Bearer ${owner.token}` };
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Read-only layouts", project_input: pilotInput() } });
  expect(created.status()).toBe(200); const { project } = await created.json();
  const invited = await request.post(`${api}/api/projects/${project.project_id}/admin/invites`, { headers, data: { email: viewer.user.email, role: "viewer" } });
  expect(invited.status()).toBe(200);
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, viewer.token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Read-only layouts", exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openWorkspaceTool(page, "Generate");
  await page.getByTestId("generate-layout-options").click();
  const options = page.locator('[data-testid^="layout-alternative-layout-alternative-"]');
  await expect(options).toHaveCount(5); await options.nth(1).click();
  await page.getByTestId("layout-alternatives-apply").click();
  await expect(page.getByTestId("layout-alternatives-card")).toBeVisible();
  const unchanged = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
  expect(unchanged.revision_token).toBe(project.revision_token);
});

test("real website previews five geometry options, applies one, reopens and undoes; changed brief rejects old options", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `layout-loop-${randomUUID()}@example.test`, password: "Disposable-123", name: "Layout regression" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const objects = [
    { id: "site", label: "Pilot parcel", type: "site", x: 0, y: 0, w: 900, d: 700, placed: true },
    { id: "office", label: "Pilot office", type: "building", x: 300, y: 120, w: 160, d: 90, placed: true },
    { id: "parking", label: "Pilot parking", type: "parking", x: 240, y: 360, w: 330, d: 150, placed: true, stall_count: 60, meta: { requested_stalls: 60 } },
    { id: "entry", label: "Fixed access", type: "entrance", x: 60, y: 650, w: 20, d: 20, placed: true, locked: true },
  ];
  const input = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", site_objects: objects, lot: { x: 0, y: 0, w: 900, h: 700 }, site_plan: { parking_count: 60 } } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Pilot layout loop", project_input: input } });
  expect(created.status()).toBe(200); const { project } = await created.json();
  const saved = async () => resolveCanonicalCanvasInput((await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input);
  const geometry = async () => ((await saved()).manual_fields?.site_objects ?? []).map(item => [item.id, item.x, item.y, item.w, item.d]);
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Pilot layout loop", exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  const initial = await geometry();
  const compare = async () => {
    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await page.getByTestId("civora-command-input").fill("show me 5 layout options");
    await page.getByTestId("civora-command-input").press("Enter");
    await expect(page.locator('[data-testid^="layout-alternative-layout-alternative-"]')).toHaveCount(5);
  };
  await openWorkspaceTool(page, "Generate");
  await page.getByTestId("generate-layout-options").click();
  await expect(page.locator('[data-testid^="layout-alternative-layout-alternative-"]')).toHaveCount(5);
  expect(await geometry()).toEqual(initial);
  await page.locator('[data-testid^="layout-alternative-layout-alternative-"][data-changed-types*="building"]').first().click();
  await page.getByTestId("layout-alternatives-apply").click();
  await expect(page.getByTestId("layout-alternatives-card")).toHaveCount(0);
  await expect.poll(geometry).not.toEqual(initial);
  const chosen = await geometry();
  expect(chosen.find(item => item[0] === "entry")).toEqual(initial.find(item => item[0] === "entry"));
  await page.reload(); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  expect(await geometry()).toEqual(chosen);
  await page.getByRole("button", { name: "Undo last draft change", exact: true }).click();
  await expect.poll(geometry).toEqual(initial);
  await compare();
  if (await page.getByTestId("layout-alternatives-minimize").isVisible()) await page.getByTestId("layout-alternatives-minimize").click();
  await openWorkspaceTool(page, "Setup");
  const parking = page.getByTestId("active-brief-summary").getByTestId("brief-value-required-parking");
  await parking.getByRole("button", { name: "Edit Required parking", exact: true }).click();
  await parking.getByRole("textbox", { name: "Required parking value" }).fill("140");
  await parking.getByRole("button", { name: "Apply", exact: true }).click();
  await expect.poll(async () => (await saved()).manual_fields?.site_plan?.parking_count).toBe(140);
  if (await page.getByTestId("layout-alternatives-expand").isVisible()) await page.getByTestId("layout-alternatives-expand").click();
  await page.getByTestId("layout-alternatives-apply").click();
  await expect(page.getByTestId("layout-alternatives-card")).toHaveCount(0);
  expect(await geometry()).toEqual(initial);
  expect((await saved()).manual_fields?.site_plan?.parking_count).toBe(140);
});
