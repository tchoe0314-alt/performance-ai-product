import { expect, test, type Locator, type Page } from "@playwright/test";

import { openCadPrecisionTools } from "./testUiHelpers";

async function openDemoWorkspace(page: Page, query = "debugPreview=1&aiRealismProvider=mock") {
  const consoleErrors: string[] = [];
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(`/demo/workspace?${query}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  return consoleErrors;
}

async function focusCommand(page: Page) {
  const chatInput = page.getByTestId("civora-chat-input");
  if (await chatInput.isVisible()) {
    await chatInput.click();
    await expect(chatInput).toBeFocused({ timeout: 5_000 });
    return chatInput;
  }
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  if (await chatInput.isVisible()) {
    await expect(chatInput).toBeFocused({ timeout: 5_000 });
    return chatInput;
  }
  const commandInput = page.getByTestId("civora-command-input");
  await expect(commandInput).toBeVisible({ timeout: 5_000 });
  const focused = await commandInput.evaluate((element) => document.activeElement === element).catch(() => false);
  if (!focused) {
    await commandInput.click({ force: true });
  }
  await expect(commandInput).toBeFocused({ timeout: 5_000 });
  return commandInput;
}

function platformShortcut(key: string) {
  return `${process.platform === "darwin" ? "Meta" : "Control"}+${key}`;
}

async function runCommand(page: Page, command: string) {
  const input = await focusCommand(page);
  await input.fill(command);
  // Focus may intentionally migrate from the compact command bar to the mounted
  // Chat composer while both surfaces share the same prompt state.
  await page.keyboard.press("Enter");
}

async function openDrawPanel(page: Page) {
  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Objects|Tools/, { timeout: 5_000 });
}

function canvasObject(page: Page, label: string) {
  return page.locator(`[data-object-overlay][data-cad-object-id][aria-label*="${label}"]`).first();
}

async function exposedObjectPoint(object: Locator) {
  return object.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    for (const xRatio of [0.35, 0.5, 0.2, 0.65]) {
      for (const yRatio of [0.5, 0.65, 0.35]) {
        const x = rect.left + rect.width * xRatio;
        const y = rect.top + rect.height * yRatio;
        const hit = document.elementFromPoint(x, y);
        const blockedControl = hit?.closest("button,input,select,textarea,a");
        if ((hit === element || element.contains(hit)) && !blockedControl) return { x, y };
      }
    }
    throw new Error("Selected object has no exposed draggable surface.");
  });
}

async function expectNoOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("Chat 230 Object Manager and inspector polish", () => {
  test("draw panel presents tools, selected object, and object list as one drafting workflow", async ({ page }) => {
    await openDemoWorkspace(page);
    await openDrawPanel(page);

    await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible();
    await expect(page.getByTestId("draw-cad-tools-section")).toContainText("Choose a tool, then draw on the canvas");
    await expect(page.getByTestId("cad-tool-line")).toBeVisible();
    await expect(page.getByTestId("cad-tool-area")).toBeVisible();
    await expect(page.getByTestId("cad-tool-box")).toBeVisible();
    await expect(page.getByTestId("draw-cad-tools-section")).toContainText("Modify");
    await expect(page.getByTestId("draw-cad-tools-section")).toContainText("Annotate / Organize");
    await expect(page.getByTestId("draw-selected-object-card")).toBeVisible();
    await expect(page.getByTestId("draw-selected-object-card")).toContainText("Selected Object");
    await expect(page.getByTestId("object-manager-panel")).toBeVisible();
    await expect(page.getByTestId("object-manager-list")).toBeVisible();
    await expect(page.getByTestId("object-manager-quick-stats")).toContainText("Visible");
    await expect(page.getByTestId("object-manager-quick-stats")).toContainText("Selected");
    await expect(page.getByTestId("object-manager-quick-stats")).toContainText("Hidden");
    await expectNoOverflow(page);
  });

  test("shows an exact empty state without console errors or overflow", async ({ page }) => {
    const consoleErrors = await openDemoWorkspace(page, "debugPreview=1&chat230EmptyObjects=1");
    await openDrawPanel(page);

    await expect(page.getByTestId("object-manager-empty-state")).toContainText(
      "No objects yet. Draw, add, or ask Civora to create one.",
    );
    await expectNoOverflow(page);
    expect(consoleErrors).toEqual([]);
  });

  test("command-created building, parking, basin, and utility objects appear as managed rows", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await runCommand(page, "add detention basin");
    await runCommand(page, "add water line");
    await openDrawPanel(page);

    const panel = page.getByTestId("object-manager-panel");
    await expect(panel).toContainText("Office Building - 28,000 sf");
    await expect(panel).toContainText("Parking Field - 140 stalls");
    await expect(panel).toContainText(/Basin|Detention/i);
    await expect(panel).toContainText("Water Line");
    await expect(panel).toContainText(/pending placement|draft/i);
  });

  test("typed layer commands hide, show, isolate, and restore draft layers", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");

    const officeOverlay = canvasObject(page, "Office Building - 28,000 sf");
    const parkingOverlay = canvasObject(page, "Parking Field - 140 stalls");
    await expect(officeOverlay).toBeVisible({ timeout: 5_000 });
    await expect(parkingOverlay).toBeVisible({ timeout: 5_000 });

    await officeOverlay.click();
    await runCommand(page, "LAYER C-BLDG");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("LAYER applied C-BLDG");

    await parkingOverlay.click();
    await runCommand(page, "LAYER C-ROAD");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("LAYER applied C-ROAD");

    await runCommand(page, "LAYER HIDE C-BLDG");
    await expect(officeOverlay).toHaveCount(0);
    await expect(parkingOverlay).toBeVisible();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("LAYER HIDE hid C-BLDG.");

    await runCommand(page, "LAYER SHOW C-BLDG");
    await expect(officeOverlay).toBeVisible();

    await runCommand(page, "LAYER OFF C-ROAD");
    await expect(parkingOverlay).toHaveCount(0);
    await expect(officeOverlay).toBeVisible();

    await runCommand(page, "LAYER ON C-ROAD");
    await expect(parkingOverlay).toBeVisible();

    await runCommand(page, "LAYER ONLY C-BLDG");
    await expect(officeOverlay).toBeVisible();
    await expect(parkingOverlay).toHaveCount(0);

    await runCommand(page, "LAYER ALL");
    await expect(officeOverlay).toBeVisible();
    await expect(parkingOverlay).toBeVisible();

    await runCommand(page, "LAYER ISOLATE C-ROAD");
    await expect(officeOverlay).toHaveCount(0);
    await expect(parkingOverlay).toBeVisible();

    await runCommand(page, "LAYER SHOWALL");
    await expect(officeOverlay).toBeVisible();
    await expect(parkingOverlay).toBeVisible();
  });

  test("canvas window selection selects visible editable objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeOverlay = canvasObject(page, "Office Building");
    const parkingOverlay = canvasObject(page, "Parking Field");
    await expect(officeOverlay).toBeVisible();
    await expect(parkingOverlay).toBeVisible();
    await page.getByRole("button", { name: /Select Pick objects/i }).click();

    const officeBox = await officeOverlay.boundingBox();
    const parkingBox = await parkingOverlay.boundingBox();
    const surfaceBox = await page.getByTestId("preview-drawing-surface").boundingBox();
    expect(officeBox).not.toBeNull();
    expect(parkingBox).not.toBeNull();
    expect(surfaceBox).not.toBeNull();
    const left = Math.max(surfaceBox!.x + 24, Math.min(officeBox!.x, parkingBox!.x) - 96);
    const top = Math.max(surfaceBox!.y + 24, Math.min(officeBox!.y, parkingBox!.y) - 96);
    const right = Math.min(
      surfaceBox!.x + surfaceBox!.width - 16,
      Math.max(officeBox!.x + officeBox!.width, parkingBox!.x + parkingBox!.width) + 24,
    );
    const bottom = Math.min(
      surfaceBox!.y + surfaceBox!.height - 16,
      Math.max(officeBox!.y + officeBox!.height, parkingBox!.y + parkingBox!.height) + 24,
    );

    await page.mouse.move(left, top);
    await page.mouse.down();
    await expect(page.getByTestId("cad-window-select-marquee")).toBeVisible();
    await page.mouse.move(right, bottom, { steps: 8 });
    await page.mouse.up();

    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("Window selected 2 editable draft objects");
    const precisionTools = await openCadPrecisionTools(page);
    await precisionTools.getByLabel("Draft command input").fill("COPY 20,0");
    await precisionTools.getByLabel("Draft command input").press("Enter");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("COPY created 2 draft review copies");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Building - 28,000 sf Copy");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Parking Field - 140 stalls Copy");
  });

  test("selected canvas object exposes quick actions without opening another panel", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const officeOverlay = canvasObject(page, "Office Building");
    await expect(officeOverlay).toBeVisible();
    await officeOverlay.click();

    const quickToolbar = () => page.getByTestId("selected-object-quick-toolbar").first();
    await expect(quickToolbar()).toBeVisible();

    await quickToolbar().getByTestId("selected-object-quick-measure").click();
    await expect(quickToolbar().getByTestId("selected-object-quick-status")).toContainText(/DIST selected .*Office Building.*ft total.*first angle/i);

    await quickToolbar().getByTestId("selected-object-quick-copy").click();
    await expect(quickToolbar().getByTestId("selected-object-quick-status")).toContainText(/COPY created 1 draft review copy/);
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Building - 28,000 sf Copy");

    await quickToolbar().getByTestId("selected-object-quick-rotate").click();
    await expect(quickToolbar().getByTestId("selected-object-quick-status")).toContainText(/ROTATE applied/);

    await quickToolbar().getByTestId("selected-object-quick-inspect").click();
    await expect(quickToolbar().getByTestId("selected-object-quick-status")).toContainText(/INSPECT selected Office Building/);

    const copiedOfficeOverlay = canvasObject(page, "Office Building - 28,000 sf Copy");
    await expect(copiedOfficeOverlay).toBeVisible();
    await copiedOfficeOverlay.click();
    await expect(quickToolbar()).toBeVisible();
    await quickToolbar().getByTestId("selected-object-quick-delete").click();
    await expect(copiedOfficeOverlay).toHaveCount(0);
  });

  test("selected canvas object can be moved and resized with visible handles", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    await page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-select").click();
    const officeOverlay = canvasObject(page, "Office Building");
    await expect(officeOverlay).toBeVisible();
    await officeOverlay.click();
    await expect(page.getByTestId("draw-selected-object-card")).toContainText("Office Building", { timeout: 5_000 });

    const beforeMove = await officeOverlay.boundingBox();
    expect(beforeMove).not.toBeNull();
    const dragStart = await exposedObjectPoint(officeOverlay);
    await page.mouse.move(dragStart.x, dragStart.y);
    await page.mouse.down();
    await page.mouse.move(dragStart.x + 48, dragStart.y + 24, { steps: 8 });
    await page.mouse.up();

    await expect
      .poll(async () => {
        const box = await officeOverlay.boundingBox();
        return Boolean(box && box.x > beforeMove!.x + 12 && box.y > beforeMove!.y + 6);
      })
      .toBeTruthy();
    const afterMove = await officeOverlay.boundingBox();
    expect(afterMove).not.toBeNull();
    expect(afterMove!.x).toBeGreaterThan(beforeMove!.x + 12);
    expect(afterMove!.y).toBeGreaterThan(beforeMove!.y + 6);

    await officeOverlay.click();
    const resizeHandle = page.getByTestId("selected-object-resize-handle");
    await expect(resizeHandle).toBeVisible();
    const beforeResize = await officeOverlay.boundingBox();
    const handleBox = await resizeHandle.boundingBox();
    expect(beforeResize).not.toBeNull();
    expect(handleBox).not.toBeNull();

    await page.mouse.move(handleBox!.x + handleBox!.width / 2, handleBox!.y + handleBox!.height / 2);
    await page.mouse.down();
    await page.mouse.move(handleBox!.x + handleBox!.width / 2 + 44, handleBox!.y + handleBox!.height / 2 + 28, { steps: 8 });
    await page.mouse.up();

    const afterResize = await officeOverlay.boundingBox();
    expect(afterResize).not.toBeNull();
    expect(afterResize!.width).toBeGreaterThan(beforeResize!.width + 10);
    expect(afterResize!.height).toBeGreaterThan(beforeResize!.height + 6);
    await expect(page.getByTestId("selected-object-resize-handle")).toBeVisible();
  });

  test("selected canvas object can be rotated and deleted with visible handles", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    await page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-select").click();
    const officeOverlay = canvasObject(page, "Office Building");
    await expect(officeOverlay).toBeVisible();
    await officeOverlay.click();

    const rotateHandle = page.getByTestId("selected-object-rotate-handle");
    await expect(rotateHandle).toBeVisible();
    const beforeTransform = await officeOverlay.evaluate((element) => getComputedStyle(element).transform);

    await rotateHandle.click();

    await expect
      .poll(async () => officeOverlay.evaluate((element) => getComputedStyle(element).transform), {
        message: "selected object should rotate from the visible handle",
      })
      .not.toBe(beforeTransform);
    await expect(page.getByTestId("selected-object-rotate-handle")).toBeVisible();

    await page.getByTestId("selected-object-delete-handle").click();
    await expect(officeOverlay).toHaveCount(0);
    await expect(page.getByTestId("selected-object-quick-toolbar")).toHaveCount(0);
  });

  test("canvas crossing selection selects touched objects while window selection requires containment", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const officeOverlay = canvasObject(page, "Office Building");
    await expect(officeOverlay).toBeVisible();
    await page.getByRole("button", { name: /Select Pick objects/i }).click();

    const officeBox = await officeOverlay.boundingBox();
    expect(officeBox).not.toBeNull();
    const left = officeBox!.x - 24;
    const top = officeBox!.y - 24;
    const right = officeBox!.x + officeBox!.width * 0.56;
    const bottom = officeBox!.y + officeBox!.height * 0.42;

    await page.mouse.move(left, top);
    await page.mouse.down();
    await expect(page.getByTestId("cad-window-select-marquee")).toHaveAttribute("data-selection-mode", "window");
    await page.mouse.move(right, bottom, { steps: 6 });
    await page.mouse.up();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("Window select found no editable draft objects.");

    await page.mouse.move(right, top);
    await page.mouse.down();
    await page.mouse.move(left, bottom, { steps: 6 });
    await expect(page.getByTestId("cad-window-select-marquee")).toHaveAttribute("data-selection-mode", "crossing");
    await page.mouse.up();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("Crossing selected 1 editable draft object.");
    await expect(page.getByTestId("preview-object-manager-list")).toHaveValue(/.+/);
  });

  test("command selection sets align and distribute editable draft objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await runCommand(page, "add detention basin");
    await openDrawPanel(page);

    await runCommand(page, "SELECT ALL");
    await expect(page.getByTestId("object-manager-multi-select")).toContainText(/3 objects selected|4 objects selected/);
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/SELECT ALL selected [34] editable draft objects/);

    await runCommand(page, "DISTRIBUTE X");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/DISTRIBUTE X spaced [34] selected draft objects evenly/);

    await runCommand(page, "ALIGN LEFT");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/ALIGN LEFT aligned [34] selected draft objects/);
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Building - 28,000 sf");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Parking Field - 140 stalls");
  });

  test("command move and copy accept relative and polar vectors", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    await runCommand(page, "SELECT ALL");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/SELECT ALL selected [23] editable draft object/);

    await runCommand(page, "MOVE selected @40,0");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/MOVE applied 40,0 to [23] selected draft object/);

    await runCommand(page, "COPY selected @40<90");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/COPY created [23] draft review cop/);
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Building - 28,000 sf Copy");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Parking Field - 140 stalls Copy");
  });

  test("selected draft objects show measurement readouts", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();

    const measurements = page.getByTestId("object-manager-measurements");
    await expect(measurements).toBeVisible();
    await expect(measurements).toContainText("Measurements");
    await expect(measurements).toContainText("2 selected");
    await expect(measurements).toContainText("Total area");
    await expect(page.getByTestId("object-manager-measure-total-area")).toContainText("sf");
    await expect(page.getByTestId("object-manager-measure-width")).toContainText("ft");
    await expect(page.getByTestId("object-manager-measurement-list")).toContainText("Office Building - 28,000 sf");
    await expect(page.getByTestId("object-manager-measurement-list")).toContainText("Parking Field - 140 stalls");
  });

  test("resizing a drawn rectangle keeps canvas geometry, type, and measurements aligned", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "Set the site to 1000 ft by 1000 ft centered at 20525 Margo St Gretna NE");
    await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 10_000 });
    await openDrawPanel(page);

    const precision = await openCadPrecisionTools(page);
    await precision.getByLabel("Draft command input").fill("RECTANGLE 100,100 200,200");
    await precision.getByLabel("Draft command input").press("Enter");

    const row = page.getByTestId("object-manager-row").filter({ hasText: "Command Rectangle" }).first();
    await expect(row).toBeVisible();
    await row.getByTestId("object-manager-select").click();
    await row.getByTestId("object-manager-type").selectOption("lot_block");
    await expect(page.getByTestId("preview-object-manager-type").filter({ visible: true }).first()).toHaveValue("lot_block");

    await row.getByTestId("object-manager-length").fill("180");
    await row.getByTestId("object-manager-width").fill("110");
    await expect(row.getByTestId("object-manager-length")).toHaveValue("180");
    await expect(row.getByTestId("object-manager-width")).toHaveValue("110");
    await expect(page.getByTestId("object-manager-measure-total-length")).toHaveText("580 ft");
    await expect(page.getByTestId("object-manager-measure-total-area")).toHaveText("19,800 sf");
    await expect(page.getByTestId("object-manager-measure-width")).toHaveText("180 ft");
    await expect(page.getByTestId("object-manager-measure-depth")).toHaveText("110 ft");
    await expect(page.getByTestId("object-manager-measurement-list")).toContainText("180 ft x 110 ft");
  });

  test("select, inspect, rename, style, type, hide, show all, copy, paste, rotate, and flip work", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    await officeRow.getByTestId("object-manager-select").click();
    await expect(officeRow).toContainText(/Office Building - 28,000 sf|Selected/i);
    await expect(page.getByTestId("floating-object-inspector")).toHaveCount(0);

    await officeRow.getByTestId("object-manager-inspect").click();
    await expect(page.getByTestId("selected-object-inspector")).toBeVisible();
    await expect(page.getByTestId("selected-object-inspector")).toContainText(/Office Building|Status|Source|Dimensions/);

    await page.getByTestId("selected-object-name-input").fill("HQ Office Test");
    await expect(page.getByTestId("selected-object-inspector")).toContainText("HQ Office Test");

    await page.getByTestId("selected-object-x-input").fill("180");
    await page.getByTestId("selected-object-y-input").fill("240");
    await page.getByTestId("selected-object-width-input").fill("260");
    await page.getByTestId("selected-object-depth-input").fill("140");
    await page.getByTestId("selected-object-rotation-input").fill("15");
    await expect(page.getByTestId("selected-object-inspector-facts")).toContainText(/260|140|15/);

    await openDrawPanel(page);
    await expect(page.getByTestId("object-manager-panel")).toContainText("HQ Office Test");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test" }).first()).toContainText(/260|140/);

    const renamedRow = page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test" }).first();
    await renamedRow.getByTestId("object-manager-lock").click();
    await expect(renamedRow).toContainText(/locked/i);
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored previous state for HQ Office Test.");
    await expect(renamedRow).toContainText(/draft placed/i);
    await renamedRow.getByTestId("object-manager-lock").click();
    await expect(renamedRow).toContainText(/locked/i);
    await renamedRow.getByTestId("object-manager-length").fill("310");
    await expect(page.getByTestId("object-manager-status")).toContainText("resize needs input: unlock HQ Office Test before changing draft geometry.");
    await renamedRow.getByTestId("object-manager-lock").click();
    await expect(renamedRow).toContainText(/draft placed/i);
    await expect(renamedRow.getByTestId("object-manager-lock")).toHaveText("Lock");
    await renamedRow.getByTestId("object-manager-length").fill("310");
    await expect(renamedRow).toContainText(/310/);
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored previous state for HQ Office Test.");
    await expect(renamedRow).toContainText(/260/);
    await renamedRow.getByTestId("object-manager-length").fill("310");
    await expect(renamedRow).toContainText(/310/);

    await renamedRow.getByTestId("object-manager-color").fill("#0f766e");
    await renamedRow.getByTestId("object-manager-type").selectOption("parking");
    await expect(renamedRow).toContainText("Parking Field");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored previous state for HQ Office Test.");
    await expect(renamedRow).toContainText("Office Building");
    await renamedRow.getByTestId("object-manager-type").selectOption("parking");
    await expect(renamedRow).toContainText("Parking Field");

    await renamedRow.getByTestId("object-manager-visibility").click();
    await expect(renamedRow.getByTestId("object-manager-visibility")).toContainText("Show");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("hidden object");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored previous state for HQ Office Test.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await renamedRow.getByTestId("object-manager-visibility").click();
    await expect(renamedRow.getByTestId("object-manager-visibility")).toContainText("Show");
    await page.getByTestId("object-manager-show-all").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");

    await renamedRow.getByTestId("object-manager-copy").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Copied HQ Office Test");
    await page.getByTestId("object-manager-paste").click();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test Copy" }).first()).toBeVisible();
    const copiedRow = page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test Copy" }).first();
    await copiedRow.getByTestId("object-manager-rotate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Rotated HQ Office Test Copy");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored previous state for HQ Office Test Copy.");
    await copiedRow.getByTestId("object-manager-rotate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Rotated HQ Office Test Copy");
    await copiedRow.getByTestId("object-manager-flip-horizontal").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Flipped horizontal HQ Office Test Copy");
    await copiedRow.getByTestId("object-manager-flip-vertical").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Flipped vertical HQ Office Test Copy");

    await copiedRow.getByTestId("object-manager-select").click();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("MOVE applied 5,0 to 1 selected draft object");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored previous state for HQ Office Test Copy.");
    await copiedRow.getByTestId("object-manager-select").click();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("MOVE applied 5,0 to 1 selected draft object");
    await page.keyboard.press("Shift+ArrowDown");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("MOVE applied 0,25 to 1 selected draft object");

    await page.keyboard.press(platformShortcut("C"));
    await expect(page.getByTestId("object-manager-status")).toContainText("Copied HQ Office Test Copy");
    await page.keyboard.press(platformShortcut("V"));
    const keyboardPastedRow = page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test Copy Copy" }).first();
    await expect(keyboardPastedRow).toBeVisible();
    await page.keyboard.press(platformShortcut("Z"));
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: removed HQ Office Test Copy Copy.");
    await expect(keyboardPastedRow).toHaveCount(0);
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: restored HQ Office Test Copy Copy.");
    await expect(keyboardPastedRow).toBeVisible();
  });

  test("multi-select supports safe bulk updates and utility hide command updates manager state", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await runCommand(page, "add water line");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    const officeLayerRow = page.getByTestId("object-manager-layer-row").filter({ hasText: "Office Building" }).first();
    const utilityLayerRow = page.getByTestId("object-manager-layer-row").filter({ hasText: "Utility Corridor" }).first();
    await expect(officeLayerRow).toContainText("1 object");
    await officeLayerRow.getByTestId("object-manager-layer-select").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Selected 1 Office Building layer object.");
    await utilityLayerRow.getByTestId("object-manager-layer-isolate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Showing only 1 Utility Corridor layer object; 2 other objects hidden.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from utility corridor layer isolate.");
    await officeLayerRow.getByTestId("object-manager-layer-visibility").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("1 hidden object");
    await expect(officeLayerRow).toContainText("1 hidden");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await officeLayerRow.getByTestId("object-manager-layer-lock").click();
    await expect(officeLayerRow).toContainText("1 locked");
    await expect(officeRow).toContainText(/locked/i);
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 1 draft objects from office building layer lock.");
    await expect(officeLayerRow).toContainText("0 locked");
    await officeLayerRow.getByTestId("object-manager-layer-lock").click();
    await officeRow.getByTestId("object-manager-color").fill("#111827");
    await expect(page.getByTestId("object-manager-status")).toContainText("style needs input: unlock Office Building - 28,000 sf before editing metadata.");
    await officeLayerRow.getByTestId("object-manager-layer-lock").click();
    await expect(officeLayerRow).toContainText("0 locked");

    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.getByTestId("object-manager-bulk-hide").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 2 draft objects from bulk hide.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 2 draft objects from bulk hide.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await page.getByTestId("object-manager-bulk-hide").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await page.getByTestId("object-manager-bulk-show").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");

    await page.getByTestId("object-manager-isolate-selected").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Isolated 2 selected objects; 1 other object hidden.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("1 hidden object");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Water Line" }).first()).toContainText("Hidden");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from isolate selected.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");

    await page.getByTestId("object-manager-bulk-type").selectOption("driveway");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Driveway");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from bulk layer/type.");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Building");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from bulk layer/type.");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Driveway");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-panel")).toContainText("Water Line");

    await utilityLayerRow.getByTestId("object-manager-layer-visibility").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText(/hidden object/);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Water Line" }).first()).toContainText("Hidden");
  });

  test("multi-select layout buttons align and distribute draft objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();

    await page.getByTestId("object-manager-bulk-align-left").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Aligned left 2 selected draft objects.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 2 draft objects from layout align left.");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 2 draft objects from layout align left.");
    await page.getByTestId("object-manager-bulk-align-top").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Aligned top 2 selected draft objects.");
    await page.getByTestId("object-manager-bulk-distribute-x").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Distributed X 2 selected draft objects.");
    await page.getByTestId("object-manager-bulk-distribute-y").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Distributed Y 2 selected draft objects.");

    await page.getByRole("button", { name: "Clear" }).click();
    const siteRow = page.getByTestId("object-manager-row").filter({ hasText: "Site" }).first();
    await siteRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-align-left").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Layout needs input: select at least two editable draft objects first.");
  });

  test("select visible draft gathers editable visible objects for bulk work", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await runCommand(page, "add detention basin");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    const basinRow = page.getByTestId("object-manager-row").filter({ hasText: /Basin|Detention/i }).first();

    await parkingRow.getByTestId("object-manager-visibility").click();
    await expect(parkingRow.getByTestId("object-manager-visibility")).toContainText("Show");

    await page.getByTestId("object-manager-select-visible").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Selected 2 visible draft objects.");
    await expect(officeRow.getByTestId("object-manager-bulk-select")).toBeChecked();
    await expect(basinRow.getByTestId("object-manager-bulk-select")).toBeChecked();
    await expect(parkingRow.getByTestId("object-manager-bulk-select")).not.toBeChecked();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.getByTestId("object-manager-bulk-hide").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("3 hidden objects");
    await page.getByRole("button", { name: "Clear" }).click();
    await page.getByTestId("object-manager-select-visible").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Select visible needs input: no visible editable draft objects are available.");
  });

  test("invert selection swaps to the other visible editable draft objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await runCommand(page, "add detention basin");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();

    await officeRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-invert-selection").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Inverted selection to 2 visible draft objects.");
    await expect(officeRow.getByTestId("object-manager-bulk-select")).not.toBeChecked();
    await expect(parkingRow.getByTestId("object-manager-bulk-select")).toBeChecked();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.getByTestId("object-manager-bulk-hide").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await page.getByRole("button", { name: "Clear" }).click();
    await officeRow.getByTestId("object-manager-visibility").click();
    await expect(officeRow.getByTestId("object-manager-visibility")).toContainText("Show");
    await page.getByTestId("object-manager-invert-selection").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Invert selection needs input: no visible editable draft objects are available.");
  });

  test("bulk lock and unlock protects selected draft objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();

    await page.getByTestId("object-manager-bulk-lock").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Locked 2 selected draft objects.");
    await expect(officeRow).toContainText(/locked/i);
    await expect(parkingRow).toContainText(/locked/i);

    await officeRow.getByTestId("object-manager-color").fill("#111827");
    await expect(page.getByTestId("object-manager-status")).toContainText("style needs input: unlock Office Building - 28,000 sf before editing metadata.");

    await page.getByTestId("object-manager-bulk-unlock").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Unlocked 2 selected draft objects.");
    await expect(officeRow.getByTestId("object-manager-lock")).toHaveText("Lock");
    await expect(parkingRow.getByTestId("object-manager-lock")).toHaveText("Lock");

    await page.getByRole("button", { name: "Clear" }).click();
    const siteRow = page.getByTestId("object-manager-row").filter({ hasText: "Site" }).first();
    await siteRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-lock").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Bulk lock needs input: selected objects are source-only or required project evidence.");
  });

  test("multi-select can combine editable objects into one named review object", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();

    await expect(page.getByTestId("object-manager-combine-selected")).toBeVisible();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();

    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await expect(combinedRow).toBeVisible();
    await expect(combinedRow).toContainText(/Office Building|Draft|Review/i);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Combined 2 drawn objects into Combined Site Program",
    );
    await expect(combinedRow).toContainText("Combined Site Program");
    await expect(page.getByTestId("floating-object-inspector")).toHaveCount(0);
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Undo: restored 2 source objects from combine objects.",
    );
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await expect(officeRow.getByTestId("object-manager-bulk-select")).toBeChecked();
    await expect(parkingRow.getByTestId("object-manager-bulk-select")).toBeChecked();

    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Combined 2 drawn objects into Combined Site Program",
    );
    const recombinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await expect(recombinedRow).toBeVisible();
    await recombinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toBeVisible();
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored Combined Site Program after explode combined object.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: exploded Combined Site Program into 2 source pieces.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
  });

  test("copied combined objects preserve source traces and explode independently", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();

    const originalCombinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await expect(originalCombinedRow).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await originalCombinedRow.getByTestId("object-manager-copy").click();
    await page.getByTestId("object-manager-paste").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Pasted Combined Site Program Copy with 2 hidden source trace pieces",
    );
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("4 hidden objects");

    const copiedCombinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Copy" }).first();
    await expect(copiedCombinedRow).toBeVisible();
    await expect(originalCombinedRow).toBeVisible();

    await copiedCombinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program Copy back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Copy" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Copy Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls Copy Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored Combined Site Program Copy after explode combined object.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Copy" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("4 hidden objects");

    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: exploded Combined Site Program Copy into 2 source pieces.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Copy" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
  });

  test("bulk duplicate preserves combined source traces independently", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByRole("button", { name: "Clear" }).click();
    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-duplicate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Duplicated 1 selected draft object with 2 hidden source trace pieces.",
    );
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("4 hidden objects");

    const duplicatedCombinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Copy" }).first();
    await expect(duplicatedCombinedRow).toBeVisible();
    await duplicatedCombinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program Copy back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Copy" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Copy Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls Copy Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
  });

  test("array preserves combined source traces for each group copy", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByRole("button", { name: "Clear" }).click();
    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-array-rows").fill("1");
    await page.getByTestId("object-manager-array-columns").fill("2");
    await page.getByTestId("object-manager-array-spacing-x").fill("90");
    await page.getByTestId("object-manager-array-spacing-y").fill("0");
    await page.getByTestId("workspace-right-panel").hover();
    await page.mouse.wheel(0, 360);
    const arrayAction = page.getByTestId("object-manager-array-action");
    await arrayAction.scrollIntoViewIfNeeded();
    await expect(arrayAction).toBeEnabled();
    await arrayAction.click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Array created 1 draft review copy with 2 hidden source trace pieces.",
    );
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("4 hidden objects");

    const arrayCombinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Array 1-2" }).first();
    await expect(arrayCombinedRow).toBeVisible();
    await arrayCombinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program Array 1-2 back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program Array 1-2" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Array Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls Array Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
  });

  test("saved draft blocks insert as traceable review groups", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();

    await page.getByTestId("object-manager-block-name").fill("Office Parking Module");
    await page.getByTestId("object-manager-save-block").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Saved Office Parking Module as a reusable draft block");
    const blockRow = page.getByTestId("object-manager-block-row").filter({ hasText: "Office Parking Module" }).first();
    await expect(blockRow).toContainText("2 source objects");
    await expect(blockRow).toContainText("rev 1");

    await blockRow.getByTestId("object-manager-block-rename").fill("Office Parking Prototype");
    await blockRow.getByTestId("object-manager-block-rename").press("Enter");
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Renamed saved block Office Parking Module to Office Parking Prototype",
    );
    const renamedBlockRow = page.getByTestId("object-manager-block-row").filter({ hasText: "Office Parking Prototype" }).first();
    await expect(renamedBlockRow).toContainText("2 source objects");
    await expect(renamedBlockRow).toContainText("rev 2");

    await runCommand(page, "add water line");
    await openDrawPanel(page);
    await page.getByTestId("object-manager-select-visible").click();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("3 objects selected");
    await renamedBlockRow.getByTestId("object-manager-update-block").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Updated Office Parking Prototype block definition from 3 draft source objects");
    await expect(renamedBlockRow).toContainText("3 source objects");
    await expect(renamedBlockRow).toContainText("rev 3");

    await renamedBlockRow.getByTestId("object-manager-insert-block").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Inserted Office Parking Prototype");
    const insertedBlock = page.getByTestId("object-manager-row").filter({ hasText: /Office Parking Prototype Insert/ }).first();
    await expect(insertedBlock).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("3 hidden objects");

    await insertedBlock.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Exploded Office Parking Prototype Insert");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Block Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls Block Source" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Water Line Block Source" }).first()).toBeVisible();

    await renamedBlockRow.getByTestId("object-manager-delete-block").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Deleted saved block Office Parking Prototype");
    await expect(page.getByTestId("object-manager-block-row").filter({ hasText: "Office Parking Prototype" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Block Source" }).first()).toBeVisible();
  });

  test("combined object edits keep hidden source traces undoable", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();

    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await expect(combinedRow).toContainText("Office Building");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await combinedRow.getByTestId("object-manager-type").selectOption("parking");
    await expect(combinedRow).toContainText("Parking Field");
    await expect(page.getByTestId("object-manager-status")).toContainText("Combined Site Program changed from Office Building to Parking Field.");

    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from combined object trace update.");
    await expect(combinedRow).toContainText("Office Building");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from combined object trace update.");
    await expect(combinedRow).toContainText("Parking Field");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await combinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
  });

  test("moving a combined object moves preserved source pieces before explode", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();

    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-inspect").click();
    const combinedOverlay = canvasObject(page, "Combined Site Program");
    await expect(combinedOverlay).toBeVisible();
    const beforeGroupBox = await combinedOverlay.boundingBox();
    expect(beforeGroupBox).not.toBeNull();

    await page.getByTestId("selected-object-x-input").fill("220");
    await openDrawPanel(page);
    await expect(page.getByTestId("object-manager-status")).toContainText("Combined Site Program geometry changed.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from combined object trace update.");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from combined object trace update.");

    const movedGroupBox = await combinedOverlay.boundingBox();
    expect(movedGroupBox).not.toBeNull();
    expect(movedGroupBox!.x).toBeGreaterThan(beforeGroupBox!.x + 10);

    await openDrawPanel(page);
    const movedCombinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await movedCombinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program back into 2 preserved source pieces",
    );

    const restoredOfficeOverlay = canvasObject(page, "Office Building - 28,000 sf");
    const restoredParkingOverlay = canvasObject(page, "Parking Field - 140 stalls");
    await expect(restoredOfficeOverlay).toBeVisible();
    await expect(restoredParkingOverlay).toBeVisible();
    const officeBox = await restoredOfficeOverlay.boundingBox();
    const parkingBox = await restoredParkingOverlay.boundingBox();
    expect(officeBox).not.toBeNull();
    expect(parkingBox).not.toBeNull();
    expect(Math.min(officeBox!.x, parkingBox!.x)).toBeGreaterThan(beforeGroupBox!.x + 10);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
  });

  test("rotating a combined object rotates preserved source pieces before explode", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();

    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-rotate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Rotated Combined Site Program.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from combined object trace update.");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from combined object trace update.");

    await combinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toContainText(/90|Visible/);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toContainText(/90|Visible/);
    const restoredOfficeOverlay = canvasObject(page, "Office Building - 28,000 sf");
    const restoredParkingOverlay = canvasObject(page, "Parking Field - 140 stalls");
    await expect(restoredOfficeOverlay).toBeVisible();
    await expect(restoredParkingOverlay).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
  });

  test("bulk transforms keep combined source traces undoable before explode", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByRole("button", { name: "Clear" }).click();
    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-move-x").fill("35");
    await page.getByTestId("object-manager-bulk-move-y").fill("-15");
    await page.getByTestId("object-manager-bulk-move-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Moved 1 selected draft object by 35,-15.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from bulk move.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("1 object selected");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from bulk move.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("1 object selected");

    await page.getByTestId("object-manager-bulk-scale-factor").fill("1.2");
    await page.getByTestId("object-manager-bulk-scale-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Scaled 1 selected draft object by 1.2.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from bulk scale.");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from bulk scale.");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByTestId("object-manager-bulk-mirror-x").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Mirrored X 1 selected draft object.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from bulk mirror X.");
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from bulk mirror X.");

    const transformedCombinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await transformedCombinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
  });

  test("show all keeps combined source trace pieces hidden until explode", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByTestId("object-manager-show-all").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "0 hidden objects shown. 2 combined source trace pieces stayed hidden until you explode the combined object.",
    );
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await expect(officeRow).toContainText("Hidden");
    await expect(parkingRow).toContainText("Hidden");

    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await expect(officeRow).toContainText("Visible");
    await expect(parkingRow).toContainText("Visible");
  });

  test("locking a combined object locks hidden source traces with undo and redo", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();

    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-lock").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Combined Site Program was locked.");
    await expect(combinedRow).toContainText(/locked/i);
    await expect(officeRow).toContainText(/locked/i);
    await expect(parkingRow).toContainText(/locked/i);

    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from combined object trace update.");
    await expect(combinedRow.getByTestId("object-manager-lock")).toHaveText("Lock");
    await expect(officeRow).not.toContainText(/locked/i);
    await expect(parkingRow).not.toContainText(/locked/i);

    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: reapplied 3 draft objects from combined object trace update.");
    await expect(combinedRow).toContainText(/locked/i);
    await expect(officeRow).toContainText(/locked/i);
    await expect(parkingRow).toContainText(/locked/i);
  });

  test("deleting a combined object removes and restores its hidden traces", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
    await page.getByTestId("object-manager-combine-type").selectOption("office_building");
    await page.getByTestId("object-manager-combine-action").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    const combinedRow = page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first();
    await combinedRow.getByTestId("object-manager-delete").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Deleted Combined Site Program and 2 hidden source trace pieces.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");

    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 3 draft objects from combined object delete.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toContainText("Hidden");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toContainText("Hidden");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");

    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: deleted 3 draft objects from combined object delete.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Combined Site Program" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
  });

  test("keyboard Delete removes selected draft object or shows blocker", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    await officeRow.getByTestId("object-manager-select").click();
    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
    });
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" })).toHaveCount(0);

    const siteRow = page.getByTestId("object-manager-row").filter({ hasText: "Site" }).first();
    await siteRow.getByTestId("object-manager-select").click();
    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
    });
    await expect(page.getByTestId("object-manager-status")).toContainText(/cannot be deleted from shortcuts|unlock .* before deleting/i);
  });

  test("keyboard Delete removes and restores multi-selected draft objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
    });
    await expect(page.getByTestId("object-manager-status")).toContainText("Deleted 2 selected draft objects.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" })).toHaveCount(0);

    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 2 draft objects from bulk delete.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toBeVisible();

    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: deleted 2 draft objects from bulk delete.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" })).toHaveCount(0);
  });

  test("keyboard copy and paste duplicates multi-selected draft objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.keyboard.press(platformShortcut("C"));
    await expect(page.getByTestId("object-manager-status")).toContainText("Copied 2 selected draft objects.");
    await expect(page.getByTestId("object-manager-paste")).toContainText("Paste 2 objects");
    await page.keyboard.press(platformShortcut("V"));
    await expect(page.getByTestId("object-manager-status")).toContainText("Pasted 2 copied draft objects.");
    const officeCopy = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Copy" }).first();
    const parkingCopy = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls Copy" }).first();
    await expect(officeCopy).toBeVisible();
    await expect(parkingCopy).toBeVisible();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.keyboard.press(platformShortcut("Z"));
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: removed 2 draft objects from multi-object paste.");
    await expect(officeCopy).toHaveCount(0);
    await expect(parkingCopy).toHaveCount(0);

    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: restored 2 draft objects from multi-object paste.");
    await expect(officeCopy).toBeVisible();
    await expect(parkingCopy).toBeVisible();
  });

  test("bulk delete removes selected draft objects and blocks protected objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-delete").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Deleted 2 selected draft objects.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" })).toHaveCount(0);
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 2 draft objects from bulk delete.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toBeVisible();
    await page.getByTestId("recent-changes-redo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Redo: deleted 2 draft objects from bulk delete.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" })).toHaveCount(0);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" })).toHaveCount(0);

    const siteRow = page.getByTestId("object-manager-row").filter({ hasText: "Site" }).first();
    await siteRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-delete").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Bulk delete needs input: selected objects are locked, source-only, or required project evidence.");
    await expect(siteRow).toBeVisible();
  });

  test("bulk duplicate copies selected draft objects and blocks protected objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-duplicate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Duplicated 2 selected draft objects.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Copy" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls Copy" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.getByRole("button", { name: "Clear" }).click();
    const siteRow = page.getByTestId("object-manager-row").filter({ hasText: "Site" }).first();
    await siteRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-duplicate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Bulk duplicate needs input: selected objects are locked, source-only, or required project evidence.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Site Copy" })).toHaveCount(0);
  });

  test("rectangular array creates traced draft copies and blocks protected objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-array-rows").fill("2");
    await page.getByTestId("object-manager-array-columns").fill("3");
    await page.getByTestId("object-manager-array-spacing-x").fill("90");
    await page.getByTestId("object-manager-array-spacing-y").fill("70");
    await page.getByTestId("workspace-right-panel").hover();
    await page.mouse.wheel(0, 360);
    const arrayAction = page.getByTestId("object-manager-array-action");
    await arrayAction.scrollIntoViewIfNeeded();
    await expect(arrayAction).toBeEnabled();
    await arrayAction.click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Array created 5 draft review copies.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Array" })).toHaveCount(5);
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("5 objects selected");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: removed 5 draft objects from array.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Array" })).toHaveCount(0);

    const siteRow = page.getByTestId("object-manager-row").filter({ hasText: "Site" }).first();
    await siteRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-array-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Array needs input: selected objects are locked, source-only, or required project evidence.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Site Array" })).toHaveCount(0);
  });

  test("numeric transform controls move and scale selected draft objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();

    await page.getByTestId("object-manager-bulk-move-x").fill("35");
    await page.getByTestId("object-manager-bulk-move-y").fill("-15");
    await page.getByTestId("object-manager-bulk-move-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Moved 2 selected draft objects by 35,-15.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 2 draft objects from bulk move.");
    await expect(officeRow.getByTestId("object-manager-bulk-select")).toBeChecked();
    await expect(parkingRow.getByTestId("object-manager-bulk-select")).toBeChecked();

    await page.getByTestId("object-manager-bulk-move-to-x").fill("25");
    await page.getByTestId("object-manager-bulk-move-to-y").fill("35");
    await page.getByTestId("object-manager-bulk-move-to-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Moved 2 selected draft objects to 25,35.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 2 draft objects from bulk move to coordinate.");

    await page.getByTestId("object-manager-bulk-copy-offset-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Copied 2 selected draft objects by 35,-15.");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf Copy" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls Copy" }).first()).toBeVisible();

    await page.getByTestId("object-manager-bulk-scale-factor").fill("1.2");
    await page.getByTestId("object-manager-bulk-scale-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Scaled 2 selected draft objects by 1.2.");
    await expect(officeRow).toContainText(/Draft|Review/i);

    await page.getByTestId("object-manager-bulk-rotate-angle").fill("22");
    await page.getByTestId("object-manager-bulk-rotate-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Rotated 2 selected draft objects by 22 degrees.");

    await page.getByTestId("object-manager-bulk-mirror-x").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Mirrored X 2 selected draft objects.");
    await page.getByTestId("object-manager-bulk-mirror-y").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Mirrored Y 2 selected draft objects.");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Undo: restored 2 draft objects from bulk mirror Y.");

    await page.getByRole("button", { name: "Clear" }).click();
    const siteRow = page.getByTestId("object-manager-row").filter({ hasText: "Site" }).first();
    await siteRow.getByTestId("object-manager-bulk-select").check();
    await page.getByTestId("object-manager-bulk-move-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Move needs input: selected objects are locked, source-only, or required project evidence.");
    await page.getByTestId("object-manager-bulk-copy-offset-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Copy by offset needs input: selected objects are locked, source-only, or required project evidence.");
    await page.getByTestId("object-manager-bulk-move-to-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Move to coordinate needs input: selected objects are locked, source-only, or required project evidence.");
    await page.getByTestId("object-manager-bulk-rotate-action").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Rotate needs input: selected objects are locked, source-only, or required project evidence.");
    await page.getByTestId("object-manager-bulk-mirror-x").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Mirror needs input: selected objects are locked, source-only, or required project evidence.");
  });
});
