import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1&aiRealismProvider=mock") {
  const params = new URLSearchParams(query);
  if (!params.has("seedDemo")) {
    params.set("seedDemo", "1");
  }
  const consoleErrors: string[] = [];
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(`/demo/workspace?${params.toString()}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
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
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Object Manager|CAD Tools/, { timeout: 5_000 });
}

test.describe("Chat 229 command power layer and shortcuts", () => {
  test("keeps one command surface and focuses it with shortcuts", async ({ page }) => {
    const consoleErrors = await openDemoWorkspace(page);

    await expect(page.getByTestId("floating-command-bar")).toHaveCount(0);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(0);

    await page.keyboard.press("/");
    await expect(page.getByTestId("floating-command-bar")).toHaveCount(1);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(1);
    await expect(page.getByTestId("civora-command-input")).toBeFocused();

    await page.locator("body").click({ position: { x: 20, y: 20 } });
    await page.keyboard.press("?");
    await expect(page.getByTestId("shortcuts-help-overlay")).toBeVisible();
    await expect(page.getByTestId("shortcuts-help-overlay")).toContainText("Cmd/Ctrl S");
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("shortcuts-help-overlay")).toHaveCount(0);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(consoleErrors).toEqual([]);
  });

  test("commands create real pending office and parking objects", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "add 28000 sf office building");
    await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first()).toBeVisible({ timeout: 5_000 });

    await runCommand(page, "add 140 parking spaces");
    await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field - 140 stalls"]').first()).toBeVisible({ timeout: 5_000 });

    await openDrawPanel(page);
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Office Building - 28,000 sf");
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Parking Field - 140 stalls");
  });

  test("commands open generate, deliver, blocker view, layers, and AI realism mode", async ({ page }) => {
    await openDemoWorkspace(page);

    await runCommand(page, "hide utilities");
    await expect(page.getByText("Utility and drainage layers are hidden in the preview.")).toBeVisible();

    await runCommand(page, "show only blockers");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Review|Issue|blocker/i);

    await runCommand(page, "generate");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate Systems/i);

    await runCommand(page, "make review package");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Review package|Plan Sheets|Deliver/i);
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(/construction-ready|approved for construction/i);

    await runCommand(page, "create AI realism");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText("High Quality", { timeout: 5_000 });
    await expect(page.getByTestId("ai-realism-toggle").first()).toBeVisible();

    await runCommand(page, "turn AI realism off");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Standard", { timeout: 5_000 });
  });

  test("shortcuts open panels, cancel tools, delete selected objects, save truthfully, and refuse unsafe commands", async ({ page }) => {
    await openDemoWorkspace(page);

    await page.keyboard.press("G");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate Systems/i);
    await page.keyboard.press("D");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Object Manager|CAD Tools/i);
    await page.keyboard.press("P");
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("projects-drawer")).toHaveCount(0);

    await runCommand(page, "draw site boundary");
    await expect(page.getByTestId("draw-site-boundary-toolbar")).toBeVisible();

    await runCommand(page, "add 28000 sf office building");
    const officeOverlay = page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first();
    await expect(officeOverlay).toBeVisible({ timeout: 5_000 });
    await officeOverlay.click();
    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", bubbles: true }));
    });
    await expect(page.getByText(/Deleted Office Building - 28,000 sf|DELETE removed Office Building - 28,000 sf/i)).toBeVisible({ timeout: 5_000 });

    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true, ctrlKey: true, bubbles: true }));
    });
    await expect(page.getByText(/Undo: restored Office Building - 28,000 sf/)).toBeVisible();

    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "s", metaKey: true, ctrlKey: true, bubbles: true }));
    });
    await expect(page.getByText(/Demo workspace changes stay local|Sign in\/connect backend to save projects|Saved project/)).toBeVisible();

    await runCommand(page, "stamp this");
    await expect(page.getByText(/can't stamp, seal, sign, certify/i)).toBeVisible();
    await runCommand(page, "act as engineer of record");
    await expect(page.getByText(/can't stamp, seal, sign, certify/i)).toBeVisible();
  });
});
