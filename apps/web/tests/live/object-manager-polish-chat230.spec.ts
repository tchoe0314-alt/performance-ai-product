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
    await openDrawPanel(page);
    await expect(page.getByTestId("object-manager-panel")).toContainText("HQ Office Test");

    const renamedRow = page.getByTestId("object-manager-row").filter({ hasText: "HQ Office Test" }).first();
    await renamedRow.getByTestId("object-manager-color").fill("#0f766e");
    await renamedRow.getByTestId("object-manager-type").selectOption("parking");
    await expect(renamedRow).toContainText("Parking Field");

    await renamedRow.getByTestId("object-manager-visibility").click();
    await expect(renamedRow.getByTestId("object-manager-visibility")).toContainText("Show");
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("hidden object");
    await page.getByTestId("object-manager-show-all").click();
    await expect(page.getByTestId("object-manager-hidden-state")).toHaveCount(0);

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
    await expect(page.getByTestId("object-manager-hidden-state")).toHaveCount(0);

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
