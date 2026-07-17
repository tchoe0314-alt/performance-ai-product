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
  if (await page.getByTestId("draw-cad-tools-section").isVisible().catch(() => false)) {
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Object Manager|CAD Tools/);
    return;
  }
  await page.getByRole("button", { name: /Object Manager/i }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Object Manager|CAD Tools/);
  await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible();
}

async function showCadTools(page: Page) {
  await page.getByRole("button", { name: /^Draw$/ }).filter({ visible: true }).first().click();
  const cadTools = page.getByTestId("draw-cad-tools-section");
  await expect(cadTools).toBeVisible();
  return cadTools;
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
    const finish = canvas.getByTestId("canvas-quick-finish").filter({ visible: true }).first();
    await expect(finish).toBeEnabled();
    await finish.click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
  });

  test("visible Add Line CAD control is above preview hit layers and changes state", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const surface = page.getByTestId("preview-drawing-surface");
    const addLine = cadTools.getByTestId("cad-tool-line");

    await expect(cadTools).toBeVisible();
    await expectTopmost(addLine, "Add Line");
    await addLine.click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE tool active|LINE active/i);
    await clickExposedSurface(surface, 0.22, 0.34);
    await clickExposedSurface(surface, 0.42, 0.34);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE created|Custom Line/i);

    await cadTools.getByTestId("cad-tool-measure").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/DIST selected .*Custom Line.*ft total.*first angle/i);
  });

  test("draft precision HUD supports keyboard finish and cancel", async ({ page }) => {
    await startBlankSite(page);
    const surface = page.getByTestId("preview-drawing-surface");
    const drawSite = page.getByTestId("draw-site-boundary-toolbar").filter({ visible: true }).first();
    if (await drawSite.isVisible().catch(() => false)) {
      const alreadyActive = await drawSite.evaluate((element) =>
        element.className.includes("bg-slate-950") || element.getAttribute("aria-pressed") === "true",
      );
      if (!alreadyActive) await drawSite.click();
    }

    await clickExposedSurface(surface, 0.24, 0.34);
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/Draw Site Boundary|PTS 1/);
    await clickExposedSurface(surface, 0.66, 0.36);
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/SEG .* ft @ .* deg/);
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/Enter when ready/i);
    await clickExposedSurface(surface, 0.54, 0.7);
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/AREA .* sf/);
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/Enter finish/i);

    await page.keyboard.press("Enter");
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    await expect(page.getByTestId("draft-precision-readout")).toHaveCount(0);

    await openDrawPanel(page);
    const cadTools = page.getByTestId("draw-cad-tools-section");
    await cadTools.getByTestId("cad-tool-area").click();
    await clickExposedSurface(surface, 0.3, 0.56);
    await clickExposedSurface(surface, 0.42, 0.54);
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/Add Area|PTS 2/);
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("draft-precision-readout")).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: /Custom Area/ })).toHaveCount(0);
  });

  test("ortho constrains click-drawn linework before grid snap", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const surface = page.getByTestId("preview-drawing-surface");
    await page.keyboard.press("o");
    await cadTools.getByTestId("cad-tool-line").click();
    await clickExposedSurface(surface, 0.2, 0.32);
    await clickExposedSurface(surface, 0.48, 0.43);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE created|Custom Line/i);

    await cadTools.getByTestId("cad-tool-measure").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/first angle (0\.0|90\.0|180\.0|270\.0) deg/i);
  });

  test("active draw tool accepts typed coordinate and distance input", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const commandInput = page.getByLabel("CAD command input");
    await cadTools.getByTestId("cad-tool-line").click();

    await commandInput.fill("120,120");
    await commandInput.press("Enter");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("DRAW accepted point 1 at 120.0,120.0.");
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/PTS 1/);

    await commandInput.fill("80");
    await commandInput.press("Enter");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("DRAW accepted point 2 at 200.0,120.0. Press Enter/Finish to complete.");
    await expect(page.getByTestId("draft-precision-readout")).toContainText(/SEG 80\.0 ft @ 0\.0 deg/);

    await page.getByTestId("canvas-quick-finish").filter({ visible: true }).first().click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE created manual_drawn draft_review_required geometry/);
    await cadTools.getByTestId("cad-tool-measure").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/80\.00 ft total.*first angle 0\.0 deg/i);
  });

  test("visible JOIN and SPLIT combine and restore selected draft linework", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const addLine = cadTools.getByTestId("cad-tool-line");
    const surface = page.getByTestId("preview-drawing-surface");

    await addLine.click();
    await clickExposedSurface(surface, 0.2, 0.24);
    await clickExposedSurface(surface, 0.34, 0.24);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE created|Custom Line/i);

    await addLine.click();
    await clickExposedSurface(surface, 0.34, 0.24);
    await clickExposedSurface(surface, 0.48, 0.24);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: /Custom Line/ })).toHaveCount(2);

    const lineRows = page.getByTestId("object-manager-row").filter({ hasText: /Custom Line/ });
    await lineRows.nth(0).getByTestId("object-manager-bulk-select").check();
    await lineRows.nth(1).getByTestId("object-manager-bulk-select").check();
    await cadTools.getByTestId("cad-tool-join").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/JOIN created .* from 2 draft source objects/);

    const joinedRow = page.getByTestId("object-manager-row").filter({ hasText: /Join|Joined CAD Object/ }).first();
    await expect(joinedRow).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await cadTools.getByTestId("cad-tool-split").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/SPLIT restored 2 source trace objects/);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: /Join|Joined CAD Object/ })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: /Custom Line/ })).toHaveCount(2);
  });

  test("visible OPEN CLOSE and REVERSE edit selected draft area linework", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const surface = page.getByTestId("preview-drawing-surface");

    await cadTools.getByTestId("cad-tool-line").click();
    await clickExposedSurface(surface, 0.62, 0.5);
    await clickExposedSurface(surface, 0.72, 0.5);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE created|Custom Line/i);

    await cadTools.getByTestId("cad-tool-area").click();
    await clickExposedSurface(surface, 0.24, 0.52);
    await clickExposedSurface(surface, 0.42, 0.46);
    await clickExposedSurface(surface, 0.5, 0.62);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/AREA created manual_drawn draft_review_required geometry/);

    const areaRow = page.getByTestId("object-manager-row").filter({ hasText: /Custom Area/ }).first();
    await expect(areaRow).toBeVisible();
    await areaRow.getByTestId("object-manager-inspect").click();

    await showCadTools(page);
    await cadTools.getByTestId("cad-tool-open").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/OPEN converted selected draft area into open review linework/);

    await showCadTools(page);
    await cadTools.getByTestId("cad-tool-close").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/CLOSE converted selected draft linework into closed review area geometry/);

    await showCadTools(page);
    await cadTools.getByTestId("cad-tool-reverse").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/REVERSE flipped the selected draft linework vertex order/);
  });

  test("selected draft geometry exposes exact vertex coordinate editing", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const surface = page.getByTestId("preview-drawing-surface");

    await cadTools.getByTestId("cad-tool-area").click();
    await clickExposedSurface(surface, 0.24, 0.52);
    await clickExposedSurface(surface, 0.42, 0.46);
    await clickExposedSurface(surface, 0.5, 0.62);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/AREA created manual_drawn draft_review_required geometry/);

    const areaRow = page.getByTestId("object-manager-row").filter({ hasText: /Custom Area/ }).first();
    await expect(areaRow).toBeVisible();
    await areaRow.getByTestId("object-manager-inspect").click();

    const vertexEditor = page.getByTestId("selected-object-vertex-editor");
    await expect(vertexEditor).toBeVisible();
    await expect(vertexEditor).toContainText("Vertex editor");
    await expect(vertexEditor).toContainText("3 points");

    const firstVertex = page.getByTestId("selected-object-vertex-row").first();
    await firstVertex.getByTestId("selected-object-vertex-x").fill("125");
    await expect(page.getByTestId("selected-object-status")).toContainText(/Updated Custom Area .*vertex 1 X to 125/);
    await firstVertex.getByTestId("selected-object-vertex-y").fill("275");
    await expect(page.getByTestId("selected-object-status")).toContainText(/Updated Custom Area .*vertex 1 Y to 275/);
    await expect(firstVertex.getByTestId("selected-object-vertex-x")).toHaveValue("125");
    await expect(firstVertex.getByTestId("selected-object-vertex-y")).toHaveValue("275");
    await expect(page.getByTestId("selected-object-inspector-facts")).toContainText(/Dimensions|metrics/i);

    await firstVertex.getByTestId("selected-object-vertex-align-y").click();
    await expect(page.getByTestId("selected-object-status")).toContainText(/Aligned Custom Area .*vertex 1 Y to previous vertex/);
    await expect(firstVertex.getByTestId("selected-object-vertex-y")).not.toHaveValue("275");

    await firstVertex.getByTestId("selected-object-vertex-insert").click();
    await expect(page.getByTestId("selected-object-status")).toContainText(/Inserted vertex 2 on Custom Area/);
    await expect(vertexEditor).toContainText("4 points");
    await expect(page.getByTestId("selected-object-vertex-row")).toHaveCount(4);

    await page.getByTestId("selected-object-vertex-row").nth(1).getByTestId("selected-object-vertex-delete").click();
    await expect(page.getByTestId("selected-object-status")).toContainText(/Deleted vertex 2 from Custom Area/);
    await expect(vertexEditor).toContainText("3 points");
    await expect(page.getByTestId("selected-object-vertex-row")).toHaveCount(3);

    await firstVertex.getByTestId("selected-object-vertex-delete").click();
    await expect(page.getByTestId("selected-object-status")).toContainText("Delete vertex blocked: polygon geometry needs at least 3 points.");

    await firstVertex.getByTestId("selected-object-vertex-snap").click();
    await expect(page.getByTestId("selected-object-status")).toContainText(/Snapped Custom Area .*vertex 1 to .*/);
    await expect(firstVertex.getByTestId("selected-object-vertex-x")).not.toHaveValue("125");
  });

  test("visible HATCH applies and removes draft fill on closed areas", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    const cadTools = page.getByTestId("draw-cad-tools-section");
    const surface = page.getByTestId("preview-drawing-surface");

    await cadTools.getByTestId("cad-tool-area").click();
    await clickExposedSurface(surface, 0.24, 0.52);
    await clickExposedSurface(surface, 0.42, 0.46);
    await clickExposedSurface(surface, 0.5, 0.62);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/AREA created manual_drawn draft_review_required geometry/);

    const areaRow = page.getByTestId("object-manager-row").filter({ hasText: /Custom Area/ }).first();
    await expect(areaRow).toBeVisible();
    await areaRow.getByTestId("object-manager-inspect").click();

    await showCadTools(page);
    await page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-hatch").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/HATCH applied as draft review fill/);
    await expect(page.getByTestId("cad-hatch-fill").first()).toBeVisible();

    await showCadTools(page);
    await page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-hatch").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/HATCH removed from selected draft area/);
    await expect(page.getByTestId("cad-hatch-fill")).toHaveCount(0);
  });
});
