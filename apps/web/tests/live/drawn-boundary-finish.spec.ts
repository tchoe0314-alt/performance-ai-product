import { expect, type Page, type Locator, test } from "@playwright/test";

async function clickSurfaceAt(surface: Locator, xRatio: number, yRatio: number) {
  await surface.scrollIntoViewIfNeeded();
  const point = await surface.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      const x = rect.left + rect.width * ratios.xRatio;
      const visibleYs: number[] = [];
      for (let index = 0; index <= 120; index += 1) {
        const y = rect.top + (rect.height * index) / 120;
        const hit = document.elementFromPoint(x, y);
        if (hit === element || element.contains(hit)) {
          visibleYs.push(y);
        }
      }
      if (!visibleYs.length) {
        return { x, y: rect.top + rect.height * ratios.yRatio };
      }
      const top = visibleYs[0];
      const bottom = visibleYs[visibleYs.length - 1];
      return { x, y: top + (bottom - top) * ratios.yRatio };
    },
    { xRatio, yRatio },
  );
  await surface.page().mouse.click(point.x, point.y);
}

async function openSetupControls(page: Page) {
  const sidebarSetup = page.getByTestId("primary-workflow-sidebar").getByRole("button", { name: /^Setup\b/i });
  if (await sidebarSetup.isVisible().catch(() => false)) {
    await sidebarSetup.click({ noWaitAfter: true });
  } else {
    await page.getByTestId("workspace-canvas-shell").getByRole("button", { name: /^Setup$/ }).click({ noWaitAfter: true });
  }
  const setupDetails = page.locator("details").filter({ hasText: "Detailed setup controls and evidence" }).first();
  if (await setupDetails.isVisible().catch(() => false)) {
    const isOpen = await setupDetails.evaluate((element) => element.hasAttribute("open"));
    if (!isOpen) {
      await setupDetails.locator("summary").filter({ hasText: "Detailed setup controls and evidence" }).click();
    }
  }
}

async function openBlankWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundary=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Detention Basin A").first()).toBeVisible({ timeout: 30_000 });

  await openSetupControls(page);
  await page.getByRole("button", { name: "Start a blank site from detailed setup controls and clear address map evidence" }).click({ noWaitAfter: true });
  await expect(page.getByTestId("site-status")).toContainText("Selecting Site");
  await expect(page.getByText("Detention Basin A")).toHaveCount(0);
  await expect(page.getByText("Multifamily Building A")).toHaveCount(0);
  const close = page.getByRole("button", { name: "Close" });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
  }
}

async function startBoundaryDraw(page: Page) {
  const toolbarButton = page.getByTestId("draw-site-boundary-toolbar");
  if (await toolbarButton.isVisible().catch(() => false)) {
    await toolbarButton.click();
    return;
  }
  await page.getByTestId("workspace-canvas-shell").getByRole("button", { name: "Draw Site Boundary" }).click();
}

async function finishDraft(page: Page, canvas: Locator) {
  const finish = canvas.getByRole("button", { name: "Finish" });
  if (await finish.isVisible().catch(() => false)) {
    await expect(finish).toBeEnabled();
  }
  await page.keyboard.press("Enter");
}

async function clickCanvasTool(canvas: Locator, name: string) {
  const tool = canvas.getByRole("button", { name });
  await expect(tool).toBeEnabled();
  await tool.evaluate((element: HTMLElement) => element.click());
}

async function clickVisibleControl(control: Locator) {
  await expect(control).toBeVisible();
  await control.evaluate((element: HTMLElement) => element.click());
}

test.describe("drawn site boundary Finish workflow", () => {
  test("locks a blank drawn boundary and enables draft manual objects", async ({ page }) => {
    await openBlankWorkspace(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    const surface = page.getByTestId("preview-drawing-surface");
    await startBoundaryDraw(page);

    await clickSurfaceAt(surface, 0.22, 0.42);
    await clickSurfaceAt(surface, 0.72, 0.44);
    await clickSurfaceAt(surface, 0.62, 0.78);
    await finishDraft(page, canvas);

    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    await expect(canvas).toContainText("Locked canonical site");
    await expect(page.getByTestId("draw-site-boundary-toolbar")).toBeVisible();
    await expect(page.getByTestId("change-site-boundary-toolbar")).toBeVisible();
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Point" })).toBeEnabled();

    await page.getByTestId("change-site-boundary-toolbar").click();
    await expect(page.getByTestId("site-status")).toContainText("Selecting Site");
    await openSetupControls(page);
    await page.getByRole("button", { name: "Lock current site boundary from detailed setup controls for engineer review" }).click();
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
    await clickCanvasTool(canvas, "Add Box");
    await clickSurfaceAt(surface, 0.28, 0.5);
    await clickSurfaceAt(surface, 0.44, 0.66);
    await expect(page.getByText("Custom Rectangle 1").first()).toBeVisible();

    await clickCanvasTool(canvas, "Add Area");
    await clickSurfaceAt(surface, 0.5, 0.52);
    await clickSurfaceAt(surface, 0.66, 0.58);
    await clickSurfaceAt(surface, 0.58, 0.72);
    await finishDraft(page, canvas);
    await expect(page.getByText("Custom Area 2").first()).toBeVisible();

    await clickCanvasTool(canvas, "Add Line");
    await clickSurfaceAt(surface, 0.24, 0.74);
    await clickSurfaceAt(surface, 0.5, 0.82);
    await finishDraft(page, canvas);

    await clickCanvasTool(canvas, "Add Point");
    await clickSurfaceAt(surface, 0.78, 0.72);
    await expect.poll(async () => (await page.locator("[data-object-overlay]").count()) - beforeObjects).toBeGreaterThanOrEqual(4);

    await clickVisibleControl(page.getByLabel(/Select Custom Point \d+/));
    await page.getByRole("button", { name: "Chat" }).first().click();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("make this a basin");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.locator("p.whitespace-pre-wrap").filter({ hasText: "draft geometry and still requires engineer review" })).toBeVisible();

    await page.getByRole("button", { name: /^Draw\b/i }).first().click();
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
    await expect(page.getByTestId("draw-site-boundary-toolbar")).toBeVisible();
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
    await startBoundaryDraw(page);
    await clickSurfaceAt(surface, 0.2, 0.35);
    await clickSurfaceAt(surface, 0.78, 0.35);
    await clickSurfaceAt(surface, 0.72, 0.78);
    await finishDraft(page, canvas);

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
    await finishDraft(page, canvas);
    await expect(page.getByText("Custom Line 1").first()).toBeVisible();

    await page.getByLabel("Select Custom Line 1").click();
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
    await expect(cadTools).toContainText(/EXTEND (applied|blocked: extend would leave the locked site extents)/);
    await cadTools.getByRole("button", { name: "Trim selected CAD object" }).click();
    await expect(cadTools).toContainText(/TRIM (applied|blocked: trim would leave the locked site extents)/);
    await cadTools.getByLabel("CAD command input").fill("fillet 4");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("FILLET blocked");

    await clickCanvasTool(canvas, "Add Area");
    await clickSurfaceAt(surface, 0.48, 0.5);
    await clickSurfaceAt(surface, 0.62, 0.56);
    await clickSurfaceAt(surface, 0.54, 0.7);
    await finishDraft(page, canvas);
    await expect(page.getByText("Custom Area 2").first()).toBeVisible();
    await page.getByLabel("Select Custom Area 2").click();
    await cadTools.getByLabel("CAD command input").fill("fillet 4");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("FILLET applied");
    await page.getByLabel("Select Custom Line 1").click();

    await cadTools.getByLabel("CAD layer").selectOption("C-UTIL");
    await clickVisibleControl(cadTools.getByRole("button", { name: "Layer" }));
    await expect(cadTools).toContainText("Layer");
    await cadTools.getByLabel("CAD dimension mode").selectOption("aligned");
    await cadTools.getByLabel("CAD dimension label").fill("130.0 ft review");
    await clickVisibleControl(cadTools.getByRole("button", { name: "Dim" }));
    await expect(page.getByTestId("cad-dimension-label")).toContainText("130.0 ft review");

    await cadTools.getByLabel("CAD command input").fill("move 5");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("MOVE applied");

    await cadTools.getByLabel("CAD X coordinate").fill("300");
    await cadTools.getByLabel("CAD Y coordinate").fill("140");
    await cadTools.getByLabel("CAD symbol", { exact: true }).selectOption("hydrant");
    await cadTools.getByRole("button", { name: "Insert" }).click();
    await expect(page.getByTestId("cad-symbol").first()).toBeVisible();

    await page.getByLabel("Select Custom Line 1").click();
    await cadTools.getByLabel("CAD object name").fill("Draft Utility Review Line");
    await cadTools.getByLabel("CAD object type").fill("custom");
    await cadTools.getByLabel("CAD object layer property").fill("C-UTIL");
    await cadTools.getByLabel("CAD source note").fill("manual field sketch");
    await cadTools.getByLabel("CAD review note").fill("verify before engineering use");
    await cadTools.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("Draft Utility Review Line").first()).toBeVisible();

    const utilityLayerToggle = cadTools.locator("button").filter({ hasText: /^C-UTIL$/ }).first();
    await utilityLayerToggle.click();
    await expect(page.getByLabel("Select Draft Utility Review Line")).toHaveCount(0);
    await utilityLayerToggle.click();
    await expect(page.getByLabel("Select Draft Utility Review Line")).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
