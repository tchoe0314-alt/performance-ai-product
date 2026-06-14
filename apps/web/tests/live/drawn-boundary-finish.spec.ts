import { expect, type Page, type Locator, test } from "@playwright/test";

async function clickSurfaceAt(surface: Locator, xRatio: number, yRatio: number) {
  await surface.scrollIntoViewIfNeeded();
  const box = await surface.boundingBox();
  expect(box).not.toBeNull();
  await surface.page().mouse.click(box!.x + box!.width * xRatio, box!.y + box!.height * yRatio);
}

async function openBlankWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundary=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Detention Basin A").first()).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("primary-workflow-sidebar").getByRole("button", { name: /Setup Site/i }).click({ noWaitAfter: true });
  await page.getByRole("button", { name: "Start a blank site and clear address map evidence" }).click({ noWaitAfter: true });
  await expect(page.getByTestId("site-status")).toContainText("Selecting Site");
  await expect(page.getByText("Detention Basin A")).toHaveCount(0);
  await expect(page.getByText("Multifamily Building A")).toHaveCount(0);
  const close = page.getByRole("button", { name: "Close" });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
  }
}

test.describe("drawn site boundary Finish workflow", () => {
  test("locks a blank drawn boundary and enables draft manual objects", async ({ page }) => {
    await openBlankWorkspace(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    const surface = page.getByTestId("preview-drawing-surface");
    await canvas.getByRole("button", { name: "Draw Site Boundary" }).click();

    await clickSurfaceAt(surface, 0.22, 0.42);
    await clickSurfaceAt(surface, 0.72, 0.44);
    await clickSurfaceAt(surface, 0.62, 0.78);
    await expect(canvas.getByRole("button", { name: "Finish" })).toBeEnabled();
    await canvas.getByRole("button", { name: "Finish" }).click();

    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    await expect(canvas).toContainText("Locked canonical site");
    await expect(canvas.getByRole("button", { name: "Draw Site Boundary" })).toBeVisible();
    await expect(canvas.getByRole("button", { name: "Change Site Boundary" })).toBeVisible();
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Point" })).toBeEnabled();

    await canvas.getByRole("button", { name: "Change Site Boundary" }).click();
    await expect(page.getByTestId("site-status")).toContainText("Selecting Site");
    await page.getByTestId("primary-workflow-sidebar").getByRole("button", { name: /Setup Site/i }).click({ noWaitAfter: true });
    await page.getByRole("button", { name: "Lock current site boundary for engineer review" }).click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    const relockClose = page.getByRole("button", { name: "Close" });
    if (await relockClose.isVisible().catch(() => false)) {
      await relockClose.click();
    }
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Point" })).toBeEnabled();

    const beforeObjects = await page.locator("[data-object-overlay]").count();
    await canvas.getByRole("button", { name: "Add Box" }).click();
    await clickSurfaceAt(surface, 0.28, 0.5);
    await clickSurfaceAt(surface, 0.44, 0.66);
    await expect(page.getByText("Custom Rectangle 1").first()).toBeVisible();

    await canvas.getByRole("button", { name: "Add Area" }).click();
    await clickSurfaceAt(surface, 0.5, 0.52);
    await clickSurfaceAt(surface, 0.66, 0.58);
    await clickSurfaceAt(surface, 0.58, 0.72);
    await canvas.getByRole("button", { name: "Finish" }).click();
    await expect(page.getByText("Custom Area 2").first()).toBeVisible();

    await canvas.getByRole("button", { name: "Add Line" }).click();
    await clickSurfaceAt(surface, 0.24, 0.74);
    await clickSurfaceAt(surface, 0.5, 0.82);
    await canvas.getByRole("button", { name: "Finish" }).click();

    await canvas.getByRole("button", { name: "Add Point" }).click();
    await clickSurfaceAt(surface, 0.78, 0.72);
    await expect.poll(async () => (await page.locator("[data-object-overlay]").count()) - beforeObjects).toBeGreaterThanOrEqual(4);

    await page.getByRole("button", { name: "Open chat from sidebar command" }).click();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("make this a basin");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.locator("p.whitespace-pre-wrap").filter({ hasText: "draft geometry and still requires engineer review" })).toBeVisible();

    await page.getByRole("button", { name: "Open canvas from sidebar command" }).click();
    await page.getByRole("button", { name: "Selected Details" }).click();
    const rightPanel = page.getByTestId("workspace-right-panel");
    await expect(rightPanel.locator("p").filter({ hasText: /^Basin \/ Detention Pond \d+$/ })).toBeVisible();
    await expect(rightPanel.locator('input[value="manual_drawn"]')).toBeVisible();
    await expect(
      rightPanel.locator("button", { hasText: /Basin \/ Detention Pond \d+/ }).filter({
        hasText: "Canonical geometry · Draft review required",
      }),
    ).toBeVisible();
  });

  test("mobile keeps draw controls reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundaryMobile=1", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Draw Site Boundary" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Line" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Area" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Box" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Point" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("CAD precision controls support coordinates, snaps, transforms, layers, and history", async ({ page }) => {
    await openBlankWorkspace(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    const surface = page.getByTestId("preview-drawing-surface");
    await canvas.getByRole("button", { name: "Draw Site Boundary" }).click();
    await clickSurfaceAt(surface, 0.2, 0.35);
    await clickSurfaceAt(surface, 0.78, 0.35);
    await clickSurfaceAt(surface, 0.72, 0.78);
    await canvas.getByRole("button", { name: "Finish" }).click();

    const cadTools = page.getByTestId("cad-precision-tools");
    await expect(cadTools).toBeVisible();
    await expect(cadTools).toContainText("CAD precision");
    await expect(cadTools.getByLabel("CAD X coordinate")).toBeVisible();
    await expect(cadTools.getByLabel("CAD Y coordinate")).toBeVisible();
    await expect(cadTools.getByText("Snap", { exact: true })).toBeVisible();
    await expect(cadTools.getByText("Ortho", { exact: true })).toBeVisible();

    await cadTools.getByLabel("CAD X coordinate").fill("120");
    await cadTools.getByLabel("CAD Y coordinate").fill("120");
    await cadTools.getByRole("button", { name: "XY" }).click();
    await cadTools.getByLabel("CAD X coordinate").fill("250");
    await cadTools.getByLabel("CAD Y coordinate").fill("120");
    await cadTools.getByRole("button", { name: "XY" }).click();
    await canvas.getByRole("button", { name: "Finish" }).click();
    await expect(page.getByText("Custom Line 1").first()).toBeVisible();

    await page.getByText("Custom Line 1").first().click();
    await expect(cadTools).toContainText("Length");
    await expect(cadTools).toContainText("Angle");
    await expect(page.getByTestId("cad-topology-status")).toContainText("Topology");
    await cadTools.getByLabel("CAD transform value").fill("15");
    await cadTools.getByRole("button", { name: "Move selected CAD objects" }).click();
    await expect(cadTools).toContainText("Move");
    await cadTools.getByRole("button", { name: "Undo CAD command" }).click();
    await cadTools.getByRole("button", { name: "Redo CAD command" }).click();

    await cadTools.getByLabel("CAD command input").fill("offset 10");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("OFFSET applied 10 ft");
    await cadTools.getByLabel("CAD transform value").fill("8");
    await cadTools.getByRole("button", { name: "Extend selected CAD object" }).click();
    await expect(cadTools).toContainText("EXTEND applied");
    await cadTools.getByRole("button", { name: "Trim selected CAD object" }).click();
    await expect(cadTools).toContainText("TRIM applied");
    await cadTools.getByLabel("CAD command input").fill("fillet 4");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("FILLET blocked");

    await page.getByText("Custom Area 2").first().click();
    await cadTools.getByLabel("CAD command input").fill("fillet 4");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("FILLET applied");
    await page.getByText("Custom Line 1").first().click();

    await cadTools.getByLabel("CAD layer").selectOption("C-UTIL");
    await cadTools.getByRole("button", { name: "Layer" }).click();
    await expect(cadTools).toContainText("Layer");
    await cadTools.getByLabel("CAD dimension mode").selectOption("aligned");
    await cadTools.getByLabel("CAD dimension label").fill("130.0 ft review");
    await cadTools.getByRole("button", { name: "Dim" }).click();
    await expect(page.getByTestId("cad-dimension-label")).toContainText("130.0 ft review");

    await cadTools.getByLabel("CAD command input").fill("move 5");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("MOVE applied");

    await cadTools.getByLabel("CAD X coordinate").fill("300");
    await cadTools.getByLabel("CAD Y coordinate").fill("140");
    await cadTools.getByLabel("CAD symbol").selectOption("hydrant");
    await cadTools.getByRole("button", { name: "Insert" }).click();
    await expect(page.getByTestId("cad-symbol").first()).toBeVisible();

    await page.getByText("Custom Line 1").first().click();
    await cadTools.getByLabel("CAD object name").fill("Draft Utility Review Line");
    await cadTools.getByLabel("CAD object type").fill("custom");
    await cadTools.getByLabel("CAD object layer property").fill("C-UTIL");
    await cadTools.getByLabel("CAD source note").fill("manual field sketch");
    await cadTools.getByLabel("CAD review note").fill("verify before engineering use");
    await cadTools.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("Draft Utility Review Line").first()).toBeVisible();

    const utilityLayerToggle = cadTools.locator("button").filter({ hasText: /^C-UTIL$/ }).first();
    await utilityLayerToggle.click();
    await expect(page.getByText("Draft Utility Review Line").first()).toHaveCount(0);
    await utilityLayerToggle.click();
    await expect(page.getByText("Draft Utility Review Line").first()).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
