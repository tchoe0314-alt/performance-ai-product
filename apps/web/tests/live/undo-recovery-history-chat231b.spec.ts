import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1&aiRealismProvider=mock") {
  const params = new URLSearchParams(query);
  if (!params.has("seedDemo")) {
    params.set("seedDemo", "1");
  }
  const errors: string[] = [];
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`/demo/workspace?${params.toString()}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  return errors;
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
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Objects|Tools/, { timeout: 5_000 });
}

async function openRecentChanges(page: Page) {
  if (await page.getByTestId("recent-changes-list").isVisible().catch(() => false)) return;
  const section = page.getByTestId("recent-changes-section");
  await section.getByRole("button").first().click();
  await expect(page.getByTestId("recent-changes-list")).toBeVisible();
}

test.describe("Chat 231B undo recovery and change history", () => {
  test("rename, style, type, hide/show, delete, and undo are recoverable draft UI actions", async ({ page }) => {
    const errors = await openDemoWorkspace(page);
    await runCommand(page, "add 28000 sf office building");
    await openDrawPanel(page);

    const row = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    await row.getByTestId("object-manager-select").click();
    await row.getByTestId("object-manager-inspect").click();

    await page.getByTestId("selected-object-name-input").fill("Undo HQ Office");
    await openDrawPanel(page);
    await expect(page.getByTestId("object-manager-status")).toContainText(/renamed|Undo can restore/i);
    await expect(page.getByTestId("recent-changes-section")).toContainText("Object renamed");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Office Building - 28,000 sf");

    const restored = page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" }).first();
    await restored.getByTestId("object-manager-color").fill("#0f766e");
    await expect(page.getByTestId("recent-changes-section")).toContainText("Object style changed");
    await restored.getByTestId("object-manager-type").selectOption("parking");
    await expect(page.getByTestId("recent-changes-section")).toContainText("Object type changed");

    await restored.getByTestId("object-manager-visibility").click();
    await expect(page.getByTestId("recent-changes-section")).toContainText(/hidden/i);
    await expect(page.getByTestId("object-manager-hidden-state")).toContainText("hidden object");
    await page.getByTestId("object-manager-show-all").click();
    await expect(page.getByTestId("recent-changes-section")).toContainText("All hidden objects are visible again.");

    await restored.getByTestId("object-manager-delete").click();
    await expect(page.getByTestId("object-manager-status")).toContainText(/Deleted .* Undo can restore/i);
    await expect(page.getByTestId("recent-changes-section")).toContainText("Object deleted");
    await page.getByTestId("recent-changes-undo").click();
    await expect(page.getByTestId("object-manager-row").filter({ hasText: "Office Building - 28,000 sf" })).toBeVisible();

    await openRecentChanges(page);
    await expect(page.getByTestId("recent-changes-list")).toContainText(/Object added|Object deleted|Object style changed|Object type changed/);
    await page.getByTestId("recent-changes-section").getByRole("button", { expanded: true }).click();
    await expect(page.getByTestId("recent-changes-list")).toHaveCount(0);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
  });

  test("generate, review package, and AI realism record truthful recent changes without fake undo", async ({ page }) => {
    await openDemoWorkspace(page);

    await openDrawPanel(page);
    await page.getByRole("button", { name: "Generate" }).first().click();
    await page.getByTestId("generate-main-action").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|Needs input/i, { timeout: 10_000 });
    await openDrawPanel(page);
    await expect(page.getByTestId("recent-changes-section")).toContainText(/Generate recorded|Generate needs input/);

    await page.getByRole("button", { name: /^Deliver$/ }).first().click();
    await page.getByRole("button", { name: /Make Review Package/i }).click();
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|Needs input/i);
    await openDrawPanel(page);
    await expect(page.getByTestId("recent-changes-section")).toContainText(/Review package/);

    await runCommand(page, "create AI realism");
    await page.getByRole("button", { name: "Minimize" }).click();
    await page.getByTestId("ai-realism-on").first().click();
    await expect(page.getByTestId("ai-realism-image")).toBeVisible({ timeout: 10_000 });
    await openDrawPanel(page);
    await expect(page.getByTestId("recent-changes-section")).toContainText("AI realism visualization regenerated");

    await page.getByLabel("Draft command input").fill("LINE 20,20 90,20");
    await page.getByLabel("Draft command input").press("Enter");
    await openDrawPanel(page);
    await expect(page.getByTestId("recent-changes-section")).toContainText(/AI realism visualization is stale|AI realism stale/i);

    await openRecentChanges(page);
    await page.getByTestId("recent-change-row-undo").filter({ hasText: /Why unavailable/i }).first().click();
    await expect(page.getByTestId("object-manager-status")).toContainText(/Undo not available:/);
  });
});
