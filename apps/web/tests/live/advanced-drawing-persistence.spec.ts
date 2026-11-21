import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { openCadPrecisionTools } from "./testUiHelpers";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const explicitlyLocal = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1" && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);

async function openDraw(page: Page) {
  await openWorkspaceTool(page, "Draw");
  const section = page.getByTestId("draw-cad-tools-section");
  await expect(section).toBeVisible();
  const objectManager = page.getByTestId("object-manager-panel");
  if (!(await objectManager.evaluate(element => element.hasAttribute("open")))) await objectManager.locator("summary").click();
}

async function revealTool(page: Page, tool: string) {
  await openDraw(page);
  const section = page.getByTestId("draw-cad-tools-section");
  let button = section.getByTestId(`cad-tool-${tool}`).filter({ visible: true }).first();
  if (!(await button.isVisible().catch(() => false))) {
    for (const summary of await section.locator("details summary").all()) {
      const details = summary.locator("xpath=ancestor::details[1]");
      if (!(await details.evaluate(element => (element as HTMLDetailsElement).open))) await summary.click();
      button = section.getByTestId(`cad-tool-${tool}`).filter({ visible: true }).first();
      if (await button.isVisible().catch(() => false)) break;
    }
  }
  await expect(button).toBeVisible();
  return button;
}

async function runCommand(page: Page, value: string) {
  const dock = await openCadPrecisionTools(page);
  const input = dock.getByLabel("Draft command input");
  await input.fill(value);
  await dock.getByRole("button", { name: "Run", exact: true }).click();
  return dock;
}

test("advanced authored drafting survives save and reopen with stable review metadata", async ({ page, request }) => {
  test.skip(!explicitlyLocal, "Disposable localhost account only.");
  const email = `advanced-draw-${randomUUID()}@example.test`;
  const password = "Disposable-advanced-draw-123";
  const registered = await request.post(`${api}/api/auth/register`, { data: { email, password, name: "Advanced draw fixture" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json();
  const headers = { Authorization: `Bearer ${token}` };
  const projectName = `Advanced drawing ${randomUUID()}`;
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name: projectName,
    project_input: {
      input_mode: "user", strict_mode: false, allow_ai_fill_for_blanks: false,
      manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 600, h: 500 }, site_objects: [] },
      meta: { site_inputs: { site_alignment_locked: true } },
    },
  } });
  expect(created.status()).toBe(200);
  const project = (await created.json()).project;

  await page.addInitScript(value => {
    sessionStorage.setItem("civora-ai-token", value);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${projectName}` }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openDraw(page);

  await (await revealTool(page, "arc")).click();
  let dock = await openCadPrecisionTools(page);
  await expect(dock.getByLabel("Draft command input")).toHaveValue(/^ARC /);
  await dock.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/ARC created/i);

  await (await revealTool(page, "text")).click();
  dock = await openCadPrecisionTools(page);
  await expect(dock.getByLabel("Draft command input")).toHaveValue(/^TEXT /);
  await dock.getByRole("button", { name: "Run", exact: true }).click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/TEXT created/i);

  for (const [start, end] of [["100,100", "200,100"], ["200,100", "300,100"]]) {
    await runCommand(page, "LINE");
    await runCommand(page, start);
    await runCommand(page, end);
    await runCommand(page, "");
  }
  await openDraw(page);
  const sourceLines = page.getByTestId("object-manager-row").filter({ hasText: /Command Line/ });
  await expect(sourceLines).toHaveCount(2);
  await sourceLines.nth(0).getByTestId("object-manager-bulk-select").check();
  await sourceLines.nth(1).getByTestId("object-manager-bulk-select").check();
  await (await revealTool(page, "join")).click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/JOIN created .* from 2 draft source objects/);
  await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

  dock = await openCadPrecisionTools(page);
  await dock.getByLabel("Draft dimension mode").selectOption("aligned");
  await dock.getByLabel("Draft dimension label").fill("200 ft review");
  await dock.getByRole("button", { name: "Dim" }).click();
  await expect(page.getByTestId("cad-dimension-label")).toContainText("200 ft review");

  await (await revealTool(page, "split")).click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/SPLIT restored 2 source trace objects/);
  await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
  await expect(page.getByTestId("object-manager-row").filter({ hasText: /Command Line/ })).toHaveCount(2);

  await openDraw(page);
  await page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-area").click();
  dock = await openCadPrecisionTools(page);
  for (const [x, y] of [["120", "180"], ["240", "180"], ["220", "260"]]) {
    await dock.getByLabel("Draft X coordinate").fill(x);
    await dock.getByLabel("Draft Y coordinate").fill(y);
    await dock.getByRole("button", { name: "XY" }).click();
  }
  await expect(page.getByTestId("canvas-quick-finish").filter({ visible: true }).first()).toBeEnabled();
  await page.getByTestId("canvas-quick-finish").filter({ visible: true }).first().click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/AREA created editable draft geometry for review/);
  await openDraw(page);
  const area = page.getByTestId("object-manager-row").filter({ hasText: /Custom Area/ }).first();
  await expect(area).toBeVisible();
  await area.getByTestId("object-manager-select").click();
  await area.getByTestId("object-manager-inspect").click();
  await (await revealTool(page, "hatch")).click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/HATCH applied as draft review fill/);
  await expect(page.getByTestId("cad-hatch-fill").first()).toBeVisible();

  dock = await openCadPrecisionTools(page);
  await dock.getByLabel("Draft object name").fill("Persisted Hatch Area");
  await dock.getByLabel("Draft object layer property").fill("C-ANNO");
  await dock.getByLabel("Draft source note").fill("synthetic authored geometry");
  await dock.getByLabel("Draft review note").fill("review only; not construction release");
  await dock.getByRole("button", { name: "Apply outline classification and properties" }).click();
  await expect(page.getByTestId("object-manager-row").filter({ hasText: "Persisted Hatch Area" })).toBeVisible();
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    const saved = (await response.json()).project.project_input.manual_fields.site_objects as Array<Record<string, unknown>>;
    return saved.length;
  }).toBeGreaterThanOrEqual(5);

  const beforeResponse = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
  const before = (await beforeResponse.json()).project.project_input.manual_fields.site_objects as Array<Record<string, unknown>>;
  const beforeIds = before.map(object => String(object.id)).sort();
  expect(new Set(beforeIds).size).toBe(beforeIds.length);
  expect(before.some(object => String(object.label).includes("Arc"))).toBe(true);
  expect(before.some(object => String(object.label).toLowerCase().includes("note"))).toBe(true);
  expect(before.filter(object => String(object.label).includes("Command Line"))).toHaveLength(2);
  expect(before.find(object => object.label === "Persisted Hatch Area")).toMatchObject({
    meta: { cad_layer: "C-ANNO", cad_hatch_enabled: true, construction_release_allowed: false },
  });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${projectName}` }).click();
  await openDraw(page);
  await expect(page.getByTestId("object-manager-row").filter({ hasText: /Arc/ }).first()).toBeVisible();
  await expect(page.getByTestId("object-manager-row").filter({ hasText: /note/i }).first()).toBeVisible();
  await expect(page.getByTestId("object-manager-row").filter({ hasText: /Command Line/ })).toHaveCount(2);
  await expect(page.getByTestId("object-manager-row").filter({ hasText: "Persisted Hatch Area" })).toBeVisible();
  await expect(page.getByTestId("cad-hatch-fill").first()).toBeVisible();
  await expect(page.getByTestId("cad-dimension-label")).toContainText("200 ft review");

  const afterResponse = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
  const after = (await afterResponse.json()).project.project_input.manual_fields.site_objects as Array<Record<string, unknown>>;
  expect(after.map(object => String(object.id)).sort()).toEqual(beforeIds);
  const persistedArea = after.find(object => object.label === "Persisted Hatch Area") as Record<string, unknown>;
  expect(persistedArea).toMatchObject({
    meta: { cad_layer: "C-ANNO", cad_hatch_enabled: true, construction_release_allowed: false },
  });
  expect(JSON.stringify(persistedArea)).toContain("review only; not construction release");
});
