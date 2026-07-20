import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
}

async function openDrawPanel(page: Page) {
  if (await page.getByTestId("draw-cad-tools-section").isVisible().catch(() => false)) return;
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  const objectManager = page.getByRole("button", { name: /^Object Manager$/ }).filter({ visible: true }).first();
  const drawStep = page.getByRole("button", { name: "Go to workflow step 2" }).filter({ visible: true }).first();
  const drawButton = page.getByRole("button", { name: /^Draw$/ }).filter({ visible: true }).first();
  if (await objectManager.isVisible().catch(() => false)) await objectManager.click();
  else if (await drawStep.isVisible().catch(() => false)) await drawStep.click();
  else if (await drawButton.isVisible().catch(() => false)) await drawButton.click();
  else await page.keyboard.press("D");
  await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible({ timeout: 10_000 });
}

async function largestOverlayPoints(page: Page) {
  await expect(page.locator("[data-cad-object-id]").first()).toBeVisible({ timeout: 10_000 });
  const points = await page.locator("[data-cad-object-id]").evaluateAll((elements) => {
    const candidates = elements
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return {
          left: rect.left,
          top: rect.top,
          width: rect.width,
          height: rect.height,
          area: rect.width * rect.height,
          visible:
            rect.width >= 60 &&
            rect.height >= 40 &&
            rect.right > 0 &&
            rect.bottom > 0 &&
            rect.left < window.innerWidth &&
            rect.top < window.innerHeight &&
            style.visibility !== "hidden" &&
            style.display !== "none",
        };
      })
      .filter((candidate) => candidate.visible)
      .sort((a, b) => b.area - a.area);
    const rect = candidates[0];
    if (!rect) return null;
    return {
      lineA: { x: rect.left + rect.width * 0.22, y: rect.top + rect.height * 0.32 },
      lineB: { x: rect.left + rect.width * 0.78, y: rect.top + rect.height * 0.32 },
      areaA: { x: rect.left + rect.width * 0.22, y: rect.top + rect.height * 0.68 },
      areaB: { x: rect.left + rect.width * 0.78, y: rect.top + rect.height * 0.68 },
      areaC: { x: rect.left + rect.width * 0.5, y: rect.top + rect.height * 0.88 },
    };
  });
  expect(points, "Expected a large visible existing object overlay to draw over").not.toBeNull();
  return points!;
}

async function pointIsObjectOverlay(page: Page, point: { x: number; y: number }) {
  return page.evaluate(
    ({ x, y }) => Boolean(document.elementFromPoint(x, y)?.closest("[data-object-overlay]")),
    point,
  );
}

test.describe("dense canvas draw hit capture", () => {
  test("active Line and Area tools capture clicks over existing object overlays", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const feedback = page.getByTestId("cad-command-feedback-panel");
    const points = await largestOverlayPoints(page);
    expect(await pointIsObjectOverlay(page, points.lineA)).toBe(true);

    await cadTools.getByTestId("cad-tool-line").click();
    await expect(feedback).toContainText(/LINE tool active|LINE active/i);
    await expect.poll(() => pointIsObjectOverlay(page, points.lineA)).toBe(false);
    await page.mouse.click(points.lineA.x, points.lineA.y);
    await page.mouse.click(points.lineB.x, points.lineB.y);
    await expect(feedback).toContainText(/LINE created|Custom Line/i);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: /Custom Line/ }).first()).toBeVisible();

    await cadTools.getByTestId("cad-tool-area").click();
    await expect(feedback).toContainText(/AREA tool active|Add Area active/i);
    await expect.poll(() => pointIsObjectOverlay(page, points.areaA)).toBe(false);
    await page.mouse.click(points.areaA.x, points.areaA.y);
    await page.mouse.click(points.areaB.x, points.areaB.y);
    await page.mouse.click(points.areaC.x, points.areaC.y);
    await expect(page.getByTestId("canvas-quick-finish").filter({ visible: true }).first()).toBeEnabled();
    await page.getByTestId("canvas-quick-finish").filter({ visible: true }).first().click();
    await expect(feedback).toContainText(/AREA created editable draft geometry for review/);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: /Custom Area/ }).first()).toBeVisible();
  });
});
