import { expect, type Page, type Locator, test } from "@playwright/test";

async function clickSurfaceAt(surface: Locator, xRatio: number, yRatio: number) {
  await surface.scrollIntoViewIfNeeded();
  const point = await surface.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      const clamp = (value: number) => Math.max(0.08, Math.min(0.92, value));
      const candidates: Array<{ x: number; y: number; distance: number }> = [];
      const xOffsets = [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24, -0.32];
      const yOffsets = [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24];
      for (const xOffset of xOffsets) {
        for (const yOffset of yOffsets) {
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
      if (candidates.length) {
        candidates.sort((a, b) => a.distance - b.distance);
        return { x: candidates[0].x, y: candidates[0].y };
      }
      return {
        x: rect.left + rect.width * clamp(ratios.xRatio),
        y: rect.top + rect.height * clamp(ratios.yRatio),
      };
    },
    { xRatio, yRatio },
  );
  await surface.page().mouse.click(point.x, point.y);
}

async function openSetupControls(page: Page) {
  const existingAddressDetails = page.getByTestId("setup-address-truth");
  const existingSiteDetails = page.getByTestId("setup-site-box-controls");
  if (await existingAddressDetails.isVisible().catch(() => false)) {
    if (!(await existingAddressDetails.evaluate((element) => element.hasAttribute("open")))) {
      await existingAddressDetails.locator("summary").click();
    }
    if (await existingSiteDetails.isVisible().catch(() => false)) {
      const siteOpen = await existingSiteDetails.evaluate((element) => element.hasAttribute("open"));
      if (!siteOpen) await existingSiteDetails.locator("summary").click();
    }
    return;
  }

  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click({ noWaitAfter: true });
  }
  const sidebarSetup = page.getByTestId("primary-workflow-sidebar").getByRole("button", { name: /^Setup\b/i });
  if (await sidebarSetup.isVisible().catch(() => false)) {
    await sidebarSetup.click({ noWaitAfter: true });
  } else if (await page.getByRole("button", { name: /^Setup\b/i }).first().isVisible().catch(() => false)) {
    await page.getByRole("button", { name: /^Setup\b/i }).first().click({ noWaitAfter: true });
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
  const addressDetails = page.getByTestId("setup-address-truth");
  if (await addressDetails.isVisible().catch(() => false)) {
    const isOpen = await addressDetails.evaluate((element) => element.hasAttribute("open"));
    if (!isOpen) {
      await addressDetails.locator("summary").click();
    }
  }
  const siteDetails = page.getByTestId("setup-site-box-controls");
  if (await siteDetails.isVisible().catch(() => false)) {
    const isOpen = await siteDetails.evaluate((element) => element.hasAttribute("open"));
    if (!isOpen) {
      await siteDetails.locator("summary").click();
    }
  }
}

async function openBlankWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundary=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await openDrawControls(page);
  await expect(page.getByTestId("workspace-right-panel")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw Canvas|Canvas|Object Manager/i, { timeout: 30_000 });

  await openSetupControls(page);
  await page
    .getByTestId("setup-address-truth")
    .getByRole("button", { name: "Start a blank site from detailed setup controls and clear address map evidence" })
    .click({ noWaitAfter: true });
  await expect(page.getByTestId("site-status")).toContainText("Site Not Locked");
  await expect(page.getByText("Detention Basin A")).toHaveCount(0);
  await expect(page.getByText("Multifamily Building A")).toHaveCount(0);
  await openDrawControls(page);
  await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible({ timeout: 30_000 });
  const close = page.getByRole("button", { name: "Close" });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
  }
}

async function startBoundaryDraw(page: Page) {
  const toolbarButton = page.getByTestId("draw-site-boundary-toolbar").filter({ visible: true }).first();
  if (await toolbarButton.isVisible().catch(() => false)) {
    const alreadyActive = await toolbarButton.evaluate((element) =>
      element.className.includes("bg-slate-950") || element.getAttribute("aria-pressed") === "true",
    );
    if (alreadyActive) return;
    await toolbarButton.click();
    return;
  }
  const canvasButton = page.getByTestId("workspace-canvas-shell").getByRole("button", { name: "Draw Site Boundary" }).first();
  const alreadyActive = await canvasButton.evaluate((element) =>
    element.className.includes("bg-slate-950") || element.getAttribute("aria-pressed") === "true",
  );
  if (alreadyActive) return;
  await canvasButton.click();
}

async function finishDraft(page: Page, canvas: Locator) {
  const quickFinish = canvas.getByTestId("canvas-quick-finish").filter({ visible: true }).first();
  if (await quickFinish.isVisible().catch(() => false)) {
    await expect(quickFinish).toBeEnabled();
    await quickFinish.click();
    return;
  }
  const finish = canvas.getByRole("button", { name: "Finish" }).filter({ visible: true }).first();
  if (!(await finish.isVisible().catch(() => false))) return;
  await expect(finish).toBeEnabled();
  await finish.click();
}

async function clickCanvasTool(canvas: Locator, name: string) {
  const quickPalette = canvas.getByTestId("canvas-quick-draw-palette");
  const quickTool = quickPalette.getByRole("button", { name }).filter({ visible: true }).first();
  if (await quickTool.isVisible().catch(() => false)) {
    await expect(quickTool).toBeEnabled();
    await quickTool.click();
    return;
  }

  const canvasTool = canvas.getByRole("button", { name }).filter({ visible: true }).first();
  if (await canvasTool.isVisible().catch(() => false)) {
    await expect(canvasTool).toBeEnabled();
    await canvasTool.click();
    return;
  }

  const toolByName: Record<string, string> = {
    "Add Line": "line",
    "Add Area": "area",
    "Add Box": "box",
    "Add Point": "point",
  };
  const managerToolId = toolByName[name];
  if (managerToolId) {
    const drawPanelButton = canvas
      .page()
      .getByTestId("primary-workflow-sidebar")
      .getByRole("button", { name: /^Draw\b/i })
      .filter({ visible: true })
      .first();
    if (await drawPanelButton.isVisible().catch(() => false)) {
      await drawPanelButton.click();
    }
    const managerTool = canvas.page().getByTestId(`cad-tool-${managerToolId}`).filter({ visible: true }).first();
    await expect(managerTool).toBeEnabled();
    await managerTool.click();
    await expect(canvas).toContainText(new RegExp(`${name.replace("Add ", "").toUpperCase()}|${managerToolId.toUpperCase()}|tool active`, "i"));
    return;
  }

  const tool = canvas.getByRole("button", { name }).filter({ visible: true }).first();
  await expect(tool).toBeEnabled();
  await tool.click();
}

async function clickVisibleControl(control: Locator) {
  await expect(control).toBeVisible();
  await control.evaluate((element: HTMLElement) => element.click());
}

async function selectObjectByName(page: Page, name: string) {
  const objectManager = page.getByTestId("preview-object-manager-list").filter({ visible: true }).first();
  if (await objectManager.isVisible().catch(() => false)) {
    await objectManager.selectOption({ label: name });
    return;
  }
  await clickVisibleControl(page.getByLabel(`Select ${name}`));
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
    await expect(page.getByTestId("draw-site-boundary-toolbar").filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByTestId("change-site-boundary-toolbar").filter({ visible: true }).first()).toBeVisible();
    const quickPalette = canvas.getByTestId("canvas-quick-draw-palette");
    await expect(quickPalette.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(quickPalette.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(quickPalette.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(quickPalette.getByRole("button", { name: "Add Point" })).toBeEnabled();

    await page.getByTestId("change-site-boundary-toolbar").filter({ visible: true }).first().click();
    await expect(page.getByTestId("site-status")).toContainText("Site Not Locked");
    await page.getByTestId("lock-site-boundary-toolbar").filter({ visible: true }).first().click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    const relockClose = page.getByRole("button", { name: "Close" });
    if (await relockClose.isVisible().catch(() => false)) {
      await relockClose.click();
    }
    await openDrawControls(page);
    await expect(quickPalette.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(quickPalette.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(quickPalette.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(quickPalette.getByRole("button", { name: "Add Point" })).toBeEnabled();

    const beforeObjects = await page.locator("[data-object-overlay]").count();
    await clickCanvasTool(canvas, "Add Box");
    await clickSurfaceAt(surface, 0.28, 0.5);
    await clickSurfaceAt(surface, 0.44, 0.66);
    await expect(page.getByText("Custom Rectangle 1").filter({ visible: true }).first()).toBeVisible();

    await clickCanvasTool(canvas, "Add Area");
    await clickSurfaceAt(surface, 0.5, 0.52);
    await clickSurfaceAt(surface, 0.66, 0.58);
    await clickSurfaceAt(surface, 0.58, 0.72);
    await finishDraft(page, canvas);
    await expect(page.getByText("Custom Area 2").filter({ visible: true }).first()).toBeVisible();

    await clickCanvasTool(canvas, "Add Line");
    await clickSurfaceAt(surface, 0.24, 0.74);
    await clickSurfaceAt(surface, 0.5, 0.82);
    await finishDraft(page, canvas);

    await clickCanvasTool(canvas, "Add Point");
    await clickSurfaceAt(surface, 0.78, 0.72);
    await expect.poll(async () => (await page.locator("[data-object-overlay]").count()) - beforeObjects).toBeGreaterThanOrEqual(4);

    await clickVisibleControl(page.locator('[data-object-overlay][aria-label^="Select Custom Point"]').first());
    await page.getByRole("button", { name: "Chat" }).first().click();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("make this a basin");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.locator("p.whitespace-pre-wrap").filter({ hasText: "draft geometry and still requires engineer review" })).toBeVisible();

    await expect(page.getByText(/Basin \/ Detention P/i).filter({ visible: true }).first()).toBeVisible();
    await expect(canvas).toContainText(/BASIN|USER-DRAWN|REVIEW/i);
  });

  test("mobile keeps draw controls reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundaryMobile=1", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("draw-site-boundary-toolbar-mobile")).toHaveCount(0);
    await openDrawControls(page);
    await expect(page.getByTestId("draw-site-boundary-toolbar-mobile").filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Line" }).filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Area" }).filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Box" }).filter({ visible: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Point" }).filter({ visible: true }).first()).toBeVisible();
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
    await cadTools.getByLabel("CAD command input").fill("LINE");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: LINE");
    await cadTools.getByLabel("CAD command input").fill("80,90");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("1/2+");
    await cadTools.getByLabel("CAD command input").fill("180,90");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("LINE accepted 2 points");
    await cadTools.getByLabel("CAD command input").fill("");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("LINE created manual_drawn draft_review_required geometry");
    await expect(page.getByText("Command Line").filter({ visible: true }).first()).toBeVisible();

    await cadTools.getByLabel("CAD X coordinate").fill("120");
    await cadTools.getByLabel("CAD Y coordinate").fill("120");
    await cadTools.getByRole("button", { name: "XY" }).click();
    await cadTools.getByLabel("CAD X coordinate").fill("250");
    await cadTools.getByLabel("CAD Y coordinate").fill("120");
    await cadTools.getByRole("button", { name: "XY" }).click();
    await finishDraft(page, canvas);
    await expect(page.getByText("Command Line").filter({ visible: true }).first()).toBeVisible();

    await selectObjectByName(page, "Command Line");
    await expect(cadTools).toContainText("Length");
    await expect(cadTools).toContainText("Angle");
    await expect(page.getByTestId("cad-topology-status")).toContainText("Topology");
    await cadTools.getByLabel("CAD transform value").fill("15");
    await cadTools.getByRole("button", { name: "Move selected CAD objects" }).click();
    await expect(cadTools).toContainText("Move");
    await cadTools.getByRole("button", { name: "Undo CAD command" }).click();
    await cadTools.getByRole("button", { name: "Redo CAD command" }).click();

    await cadTools.getByLabel("CAD command input").fill("OFFSET");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: OFFSET");
    await cadTools.getByLabel("CAD command input").fill("10");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("OFFSET applied 10 ft");
    await cadTools.getByLabel("CAD command input").fill("EXTEND");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: EXTEND");
    await cadTools.getByLabel("CAD command input").fill("8");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/EXTEND (applied|blocked: extend would leave the locked site extents)/);
    await cadTools.getByLabel("CAD command input").fill("TRIM");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: TRIM");
    await cadTools.getByLabel("CAD command input").fill("4");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/TRIM (applied|blocked: trim would leave the locked site extents)/);
    await cadTools.getByLabel("CAD command input").fill("fillet 4");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/FILLET (applied|blocked)/);

    const snapToggle = cadTools.getByLabel("Snap");
    if (await snapToggle.isChecked()) {
      await snapToggle.uncheck();
    }
    await clickCanvasTool(canvas, "Add Area");
    await clickSurfaceAt(surface, 0.72, 0.32);
    await clickSurfaceAt(surface, 0.86, 0.42);
    await clickSurfaceAt(surface, 0.78, 0.56);
    await finishDraft(page, canvas);
    await expect(page.getByText("Custom Area 2").filter({ visible: true }).first()).toBeVisible();
    await selectObjectByName(page, "Custom Area 2");
    await cadTools.getByLabel("CAD command input").fill("fillet 4");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/FILLET (applied|blocked)/);

    await cadTools.getByLabel("CAD layer").selectOption("C-UTIL");
    await clickVisibleControl(cadTools.getByRole("button", { name: "Layer" }));
    await expect(cadTools).toContainText("Layer");
    await cadTools.getByLabel("CAD command input").fill("SELECT NONE");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("SELECT NONE cleared");
    await cadTools.getByLabel("CAD command input").fill("SELECT LAYER C-UTIL");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/SELECT LAYER C-UTIL selected \d+/);
    await cadTools.getByLabel("CAD command input").fill("M 1");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("MOVE applied");
    await cadTools.getByLabel("CAD command input").fill("RO 5");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("ROTATE applied");
    await cadTools.getByLabel("CAD command input").fill("SC 1.01");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("SCALE applied");
    await cadTools.getByLabel("CAD command input").fill("CO 2,2");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/COPY created .*draft review copy/);
    await cadTools.getByLabel("CAD command input").fill("ARRAY 2 3 12,8");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("ARRAY created 5 draft review copies");
    await cadTools.getByLabel("CAD command input").fill("DIST 0,0 100,0");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("DIST 100.00 ft");
    await cadTools.getByLabel("CAD command input").fill("MEASURE");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/DIST selected .* ft total/);
    await cadTools.getByLabel("CAD command input").fill("MI H");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("MIRROR H applied");
    await cadTools.getByLabel("CAD command input").fill("FLIP V");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("MIRROR V applied");
    await cadTools.getByLabel("CAD dimension mode").selectOption("aligned");
    await cadTools.getByLabel("CAD dimension label").fill("130.0 ft review");
    await clickVisibleControl(cadTools.getByRole("button", { name: "Dim" }));
    const dimensionLabel = page.getByTestId("cad-dimension-label");
    if (await dimensionLabel.isVisible().catch(() => false)) {
      await expect(dimensionLabel).toContainText("130.0 ft review");
    } else {
      await expect(cadTools).toContainText(/DIM|dimension/i);
    }

    await cadTools.getByLabel("CAD command input").fill("move 5");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("MOVE applied");
    await cadTools.getByLabel("CAD command input").fill("MOVE");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: MOVE");
    await cadTools.getByLabel("CAD command input").fill("6,0");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("MOVE applied 6,0");
    await cadTools.getByLabel("CAD command input").fill("ROTATE");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: ROTATE");
    await cadTools.getByLabel("CAD command input").fill("15");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("ROTATE applied");
    await cadTools.getByLabel("CAD command input").fill("SCALE");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: SCALE");
    await cadTools.getByLabel("CAD command input").fill("1.05");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText("SCALE applied");
    await cadTools.getByLabel("CAD command input").fill("COPY");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(page.getByTestId("cad-active-command")).toContainText("Active command: COPY");
    await cadTools.getByLabel("CAD command input").fill("8,8");
    await cadTools.getByRole("button", { name: "Run" }).click();
    await expect(cadTools).toContainText(/COPY created .*draft review cop/);

    await cadTools.getByLabel("CAD X coordinate").fill("300");
    await cadTools.getByLabel("CAD Y coordinate").fill("140");
    await cadTools.getByLabel("CAD symbol", { exact: true }).selectOption("hydrant");
    await clickVisibleControl(cadTools.getByRole("button", { name: "Insert" }));
    await expect(page.getByTestId("cad-symbol").first()).toBeVisible();

    await cadTools.getByLabel("CAD object name").fill("Draft Utility Review Area");
    await cadTools.getByLabel("CAD object type").fill("custom");
    await cadTools.getByLabel("CAD object layer property").fill("C-UTIL");
    await cadTools.getByLabel("CAD source note").fill("manual field sketch");
    await cadTools.getByLabel("CAD review note").fill("verify before engineering use");
    await cadTools.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("Draft Utility Review Area").first()).toBeVisible();

    const utilityLayerToggle = cadTools.locator("button").filter({ hasText: /^C-UTIL$/ }).first();
    await utilityLayerToggle.click();
    await utilityLayerToggle.click();
    await expect(page.locator('[data-object-overlay][aria-label="Select Draft Utility Review Area"]').first()).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});

async function openDrawControls(page: Page) {
  if (await page.getByTestId("draw-cad-tools-section").isVisible().catch(() => false)) return;
  const objectManager = page.getByRole("button", { name: /^Object Manager$/ }).filter({ visible: true }).first();
  const drawStep = page.getByRole("button", { name: "Go to workflow step 2" }).filter({ visible: true }).first();
  const drawButton = page.getByRole("button", { name: /^Draw$/ }).filter({ visible: true }).first();
  if (await drawStep.isVisible().catch(() => false)) await drawStep.click();
  else if (await drawButton.isVisible().catch(() => false)) await drawButton.click();
  else if (await objectManager.isVisible().catch(() => false)) await objectManager.click();
  else await page.keyboard.press("D");
}
