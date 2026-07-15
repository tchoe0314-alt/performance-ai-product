import { expect, test, type Locator, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
}

async function openDrawPanel(page: Page) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name: /^Draw$/ }).filter({ visible: true }).first().click();
  await page.getByRole("button", { name: /Object Manager/i }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Object Manager|CAD Tools/);
  await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible();
}

async function startBlankSite(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundary=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Setup\b/i }).filter({ visible: true }).first().click({ noWaitAfter: true });
  const addressDetails = page.getByTestId("setup-address-truth");
  await expect(addressDetails).toBeVisible();
  if (!(await addressDetails.evaluate((element) => element.hasAttribute("open")))) {
    await addressDetails.locator("summary").click();
  }
  await addressDetails
    .getByRole("button", { name: "Start a blank site from detailed setup controls and clear address map evidence" })
    .click({ noWaitAfter: true });
  await expect(page.getByTestId("site-status")).toContainText("Site Not Locked");
}

async function expectTopmost(locator: Locator, label: string) {
  await expect(locator).toBeVisible();
  const hitTest = await locator.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const hit = document.elementFromPoint(x, y);
    return {
      hitTag: hit?.tagName,
      hitText: hit?.textContent,
      containsHit: hit === element || element.contains(hit),
    };
  });
  expect(hitTest.containsHit, `Expected ${label} to be topmost; hit ${hitTest.hitTag}: ${hitTest.hitText}`).toBe(true);
}

async function clickExposedSurface(surface: Locator, xRatio: number, yRatio: number) {
  await surface.scrollIntoViewIfNeeded();
  const point = await surface.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      const clamp = (value: number) => Math.max(0.08, Math.min(0.92, value));
      const candidates: Array<{ x: number; y: number; distance: number }> = [];
      for (const xOffset of [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24, -0.32]) {
        for (const yOffset of [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24]) {
          const nextXRatio = clamp(ratios.xRatio + xOffset);
          const nextYRatio = clamp(ratios.yRatio + yOffset);
          const x = rect.left + rect.width * nextXRatio;
          const y = rect.top + rect.height * nextYRatio;
          const hit = document.elementFromPoint(x, y);
          const blocked = hit?.closest?.(
            '[data-object-overlay],button,input,select,textarea,aside,header,[data-testid="cad-precision-tools"],[data-testid="workspace-right-panel"]',
          );
          if ((hit === element || element.contains(hit)) && !blocked) {
            candidates.push({
              x,
              y,
              distance: Math.abs(nextXRatio - ratios.xRatio) + Math.abs(nextYRatio - ratios.yRatio),
            });
          }
        }
      }
      candidates.sort((a, b) => a.distance - b.distance);
      return candidates[0] ?? { x: rect.left + rect.width * clamp(ratios.xRatio), y: rect.top + rect.height * clamp(ratios.yRatio) };
    },
    { xRatio, yRatio },
  );
  await surface.page().mouse.click(point.x, point.y);
}

test.describe("Chat 221B draw drafting usability", () => {
  test("visible Draw Site Boundary button enables the drawing surface and Finish path", async ({ page }) => {
    await startBlankSite(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    const drawSite = page.getByTestId("draw-site-boundary-toolbar").filter({ visible: true }).first();
    const surface = page.getByTestId("preview-drawing-surface");

    if (await drawSite.isVisible().catch(() => false)) {
      const alreadyActive = await drawSite.evaluate((element) =>
        element.className.includes("bg-slate-950") || element.getAttribute("aria-pressed") === "true",
      );
      if (!alreadyActive) {
        await expectTopmost(drawSite, "Draw Site Boundary");
        await drawSite.click();
      }
    }

    await clickExposedSurface(surface, 0.25, 0.35);
    await clickExposedSurface(surface, 0.7, 0.38);
    await clickExposedSurface(surface, 0.58, 0.72);
    const finish = canvas.getByRole("button", { name: "Finish" }).filter({ visible: true }).first();
    await expect(finish).toBeEnabled();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
  });

  test("visible Add Line CAD control is above preview hit layers and changes state", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const addLine = cadTools.getByTestId("cad-tool-line");

    await expect(cadTools).toBeVisible();
    await expectTopmost(addLine, "Add Line");
    await addLine.click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE tool active|LINE active/i);
  });
});
