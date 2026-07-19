import { expect, test, type Page, type TestInfo } from "@playwright/test";

test.use({ video: "on", screenshot: "on" });

const ignoredConsole = /401|auth|orchestrate|favicon/i;
const badWords = /construction-ready|approved for construction|stamped by Civora|sealed by Civora|signed by Civora/i;

async function shot(page: Page, testInfo: TestInfo, name: string) {
  await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
}

async function humanClick(locator: ReturnType<Page["locator"]>, label: string) {
  const target = locator.filter({ visible: true }).first();
  await expect(target, `${label} should be visible`).toBeVisible({ timeout: 10_000 });
  await target.scrollIntoViewIfNeeded();
  const box = await target.boundingBox();
  expect(box, `${label} should have a real click box`).not.toBeNull();
  await target.page().mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2, { steps: 6 });
  await target.page().mouse.click(box!.x + box!.width / 2, box!.y + box!.height / 2);
}

async function openPanel(page: Page, name: RegExp | string, expected?: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await humanClick(workspaceButton, "Open workspace controls");
  await humanClick(page.getByRole("button", { name }), `Open ${String(name)}`);
  if (expected) await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 10_000 });
}

async function clickSurface(page: Page, xRatio: number, yRatio: number) {
  const surface = page.getByTestId("preview-drawing-surface");
  await surface.scrollIntoViewIfNeeded();
  const point = await surface.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      return { x: rect.left + rect.width * ratios.xRatio, y: rect.top + rect.height * ratios.yRatio };
    },
    { xRatio, yRatio },
  );
  await page.mouse.move(point.x, point.y, { steps: 8 });
  await page.mouse.click(point.x, point.y);
}

async function visibleButtonCount(page: Page) {
  return page.locator("button").evaluateAll((buttons) =>
    buttons.filter((button) => {
      const rect = button.getBoundingClientRect();
      const style = window.getComputedStyle(button);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    }).length,
  );
}

async function expectNoObviousUiBreakage(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await expect(page.locator("body")).not.toContainText(badWords);
}

test("hosted human chaos pass clicks visible controls and builds a small site", async ({ page }, testInfo) => {
  test.setTimeout(300_000);
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  const timings: Array<{ label: string; ms: number }> = [];

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => failedRequests.push(`${request.method()} ${request.url()} ${request.failure()?.errorText ?? ""}`));

  const timed = async (label: string, fn: () => Promise<void>, limit = 3_500) => {
    const started = Date.now();
    await fn();
    const ms = Date.now() - started;
    timings.push({ label, ms });
    expect(ms, `${label} should feel responsive`).toBeLessThanOrEqual(limit);
  };

  await page.goto(`/demo/workspace?debugPreview=1&seedDemo=0&aiRealismProvider=mock&chaos=${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expectNoObviousUiBreakage(page);
  await shot(page, testInfo, "01-loaded");

  const initialButtons = await visibleButtonCount(page);
  expect(initialButtons).toBeGreaterThan(6);

  await timed("projects open/new/close", async () => {
    await humanClick(page.getByRole("button", { name: "Projects" }), "Projects");
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await humanClick(page.getByRole("button", { name: "New Project" }), "New Project");
    await page.keyboard.press("Escape");
  });
  await shot(page, testInfo, "02-new-project");

  await timed("setup address and centered site", async () => {
    await openPanel(page, /^Setup$/, /Address|Site Boundary|Survey|Auto Site Context/i);
    const addressDetails = page.getByTestId("setup-address-truth");
    if (!(await addressDetails.evaluate((node) => node.hasAttribute("open")))) await addressDetails.locator("summary").click();
    await page.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");
    const siteBox = page.getByTestId("setup-site-box-controls");
    if (!(await siteBox.evaluate((node) => node.hasAttribute("open")))) await siteBox.locator("summary").click();
    await page.getByLabel("Site width in feet").fill("1000");
    await page.getByLabel("Site depth in feet").fill("1000");
    await humanClick(page.getByTestId("create-centered-site-button"), "Create centered site");
    await expect(page.getByTestId("site-status")).toContainText(/Site Locked/i, { timeout: 30_000 });
  }, 30_000);
  await shot(page, testInfo, "03-site-ready");

  await timed("manual draw objects with mouse", async () => {
    await openPanel(page, /^Draw$/, /Draw|Object Manager|Tools/i);
    const tools = page.getByTestId("draw-cad-tools-section");
    await humanClick(tools.getByTestId("cad-tool-box"), "Add Box");
    await clickSurface(page, 0.35, 0.34);
    await clickSurface(page, 0.55, 0.48);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/BOX created|Custom Box|manual_drawn/i);
    await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill("Office Test Building");
    await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("building");
    await humanClick(tools.getByTestId("cad-tool-box"), "Add Box parking");
    await clickSurface(page, 0.18, 0.52);
    await clickSurface(page, 0.55, 0.72);
    await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill("Parking Test Field");
    await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("parking");
    await humanClick(tools.getByTestId("cad-tool-line"), "Add Line driveway");
    await clickSurface(page, 0.1, 0.6);
    await clickSurface(page, 0.34, 0.6);
    await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill("Driveway Test Connection");
    await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("road");
  }, 45_000);
  await shot(page, testInfo, "04-drawn-plan");

  await timed("object manager random edits", async () => {
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Test Building");
    await humanClick(page.getByTestId("preview-object-manager-focus"), "Focus selected object");
    const visibility = page.getByTestId("preview-object-manager-visibility").filter({ visible: true }).first();
    await humanClick(visibility, "Hide selected object");
    await expect(page.getByTestId("object-manager-panel")).toContainText(/Hidden|Visible/i);
    await humanClick(visibility, "Show selected object");
    await page.getByTestId("preview-object-manager-color").filter({ visible: true }).first().evaluate((input: HTMLInputElement) => {
      input.value = "#2563eb";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }, 20_000);
  await shot(page, testInfo, "05-object-manager-edits");

  await timed("preview mode and quality toggles", async () => {
    const high = page.getByTestId("preview-inner-quality-high").filter({ visible: true }).first();
    if (await high.isVisible().catch(() => false)) await humanClick(high, "High Quality");
    const ai = page.getByTestId("ai-realism-toggle").filter({ visible: true }).first();
    if (await ai.isVisible().catch(() => false)) await humanClick(ai, "AI Visualization toggle");
    const mode3d = page.getByTestId("preview-inner-mode-3d").filter({ visible: true }).first();
    if (await mode3d.isVisible().catch(() => false)) {
      await humanClick(mode3d, "3D mode");
      await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 30_000 });
      const mode2d = page.getByTestId("preview-inner-mode-2d").filter({ visible: true }).first();
      if (await mode2d.isVisible().catch(() => false)) await humanClick(mode2d, "2D mode");
    }
  }, 35_000);
  await shot(page, testInfo, "06-preview-toggles");

  await timed("generate and deliver visible flow", async () => {
    await openPanel(page, /^Generate$/, /Generate systems/i);
    await humanClick(page.getByTestId("generate-main-action"), "Generate");
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|blocked|Needs review/i, { timeout: 15_000 });
    await openPanel(page, /^Deliver$/, /Review package|Make Review Package/i);
    await humanClick(page.getByRole("button", { name: /Make Review Package/i }), "Make Review Package");
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|Package blocked|missing/i, { timeout: 15_000 });
  }, 45_000);
  await shot(page, testInfo, "07-generate-deliver");

  await timed("chat visible help and refusal", async () => {
    await humanClick(page.getByRole("button", { name: "Open chat from header" }), "Chat");
    const input = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
    await input.fill("what changed?");
    await input.press("Enter");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/changed|Generate|drawn|Auto Site/i, { timeout: 10_000 });
    await input.fill("make this construction ready");
    await input.press("Enter");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/can't stamp|review|required|engineer|construction/i, { timeout: 10_000 });
  }, 25_000);
  await shot(page, testInfo, "08-chat");

  await expectNoObviousUiBreakage(page);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((line) => !ignoredConsole.test(line))).toEqual([]);
  expect(failedRequests.filter((line) => !ignoredConsole.test(line))).toEqual([]);
  testInfo.attach("timings", {
    body: JSON.stringify(timings, null, 2),
    contentType: "application/json",
  });
});
