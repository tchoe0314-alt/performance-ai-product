import { expect, test, type Page } from "@playwright/test";

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
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await expect(page.getByTestId("civora-command-input")).toBeFocused({ timeout: 5_000 });
}

async function runCommand(page: Page, command: string) {
  await focusCommand(page);
  await page.getByTestId("civora-command-input").fill(command);
  await page.getByTestId("civora-command-input").press("Enter");
}

async function openDrawPanel(page: Page) {
  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Object Manager|Draw & Object Manager|CAD Tools/, { timeout: 5_000 });
}

async function expectNoOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("Chat 230 Object Manager and inspector polish", () => {
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

  test("canvas window selection selects visible editable objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await openDrawPanel(page);

    const officeOverlay = page.locator('[data-cad-object-id][aria-label*="Office Building"]').first();
    const parkingOverlay = page.locator('[data-cad-object-id][aria-label*="Parking Field"]').first();
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
    await page.getByLabel("CAD command input").fill("COPY 20,0");
    await page.getByLabel("CAD command input").press("Enter");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("COPY created 2 draft review copies");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Building - 28,000 sf Copy");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Parking Field - 140 stalls Copy");
  });

  test("canvas crossing selection selects touched objects while window selection requires containment", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const officeOverlay = page.locator('[data-cad-object-id][aria-label*="Office Building"]').first();
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

  test("select, inspect, rename, style, type, hide, show all, copy, paste, rotate, and flip work", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    await officeRow.getByTestId("object-manager-select").click();
    await expect(page.getByTestId("floating-object-inspector")).toContainText("Office Building - 28,000 sf");

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
    await renamedRow.getByTestId("object-manager-length").fill("310");
    await expect(page.getByTestId("object-manager-status")).toContainText("resize blocked: unlock HQ Office Test before changing draft geometry.");
    await renamedRow.getByTestId("object-manager-lock").click();
    await expect(renamedRow).toContainText(/draft placed/i);
    await expect(renamedRow.getByTestId("object-manager-lock")).toHaveText("Lock");
    await renamedRow.getByTestId("object-manager-length").fill("310");
    await expect(renamedRow).toContainText(/310/);

    await renamedRow.getByTestId("object-manager-color").fill("#0f766e");
    await renamedRow.getByTestId("object-manager-type").selectOption("parking");
    await expect(renamedRow).toContainText("Parking Field");

    await renamedRow.getByTestId("object-manager-visibility").click();
    await expect(renamedRow.getByTestId("object-manager-visibility")).toContainText("Show");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("hidden object");
    await page.getByTestId("object-manager-show-all").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");

    await renamedRow.getByTestId("object-manager-copy").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Copied HQ Office Test");
    await page.getByTestId("object-manager-paste").click();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test Copy" }).first()).toBeVisible();
    const copiedRow = page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test Copy" }).first();
    await copiedRow.getByTestId("object-manager-rotate").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Rotated HQ Office Test Copy");
    await copiedRow.getByTestId("object-manager-flip-horizontal").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Flipped horizontal HQ Office Test Copy");
    await copiedRow.getByTestId("object-manager-flip-vertical").click();
    await expect(page.getByTestId("object-manager-status")).toContainText("Flipped vertical HQ Office Test Copy");

    await copiedRow.getByTestId("object-manager-select").click();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("MOVE applied 5,0 to 1 selected draft object");
    await page.keyboard.press("Shift+ArrowDown");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("MOVE applied 0,25 to 1 selected draft object");

    await page.keyboard.press("Control+C");
    await expect(page.getByTestId("object-manager-status")).toContainText("Copied HQ Office Test Copy");
    await page.keyboard.press("Control+V");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test Copy Copy" }).first()).toBeVisible();
  });

  test("multi-select supports safe bulk updates and utility hide command updates manager state", async ({ page }) => {
    await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await runCommand(page, "add 140 parking spaces");
    await runCommand(page, "add water line");
    await openDrawPanel(page);

    const officeRow = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    const parkingRow = page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first();
    await officeRow.getByTestId("object-manager-bulk-select").check();
    await parkingRow.getByTestId("object-manager-bulk-select").check();
    await expect(page.getByTestId("object-manager-multi-select")).toContainText("2 objects selected");

    await page.getByTestId("object-manager-bulk-hide").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("2 hidden objects");
    await page.getByTestId("object-manager-bulk-show").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");

    await page.getByTestId("object-manager-bulk-type").selectOption("driveway");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Driveway");

    await runCommand(page, "hide utilities");
    await openDrawPanel(page);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText(/hidden object/);
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Water Line" }).first()).toContainText("Hidden");
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
    await expect(page.getByTestId("floating-object-inspector")).toContainText("Combined Site Program");
    await combinedRow.getByTestId("object-manager-explode-combined").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(
      "Exploded Combined Site Program back into 2 preserved source pieces",
    );
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("0 hidden objects");
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first()).toBeVisible();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 140 stalls" }).first()).toBeVisible();
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
    await expect(page.getByText(/Delete blocked: .*cannot be deleted|Delete blocked: locked site boundary/i)).toBeVisible();
  });
});
