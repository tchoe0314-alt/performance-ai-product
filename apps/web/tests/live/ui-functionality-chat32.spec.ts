import { expect, test } from "@playwright/test";

async function openDemoWorkspace(page: import("@playwright/test").Page) {
  await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Detention Basin A", { timeout: 30_000 });
}

test.describe("Chat 32 UI functionality QA", () => {
  test("desktop controls are wired or truthfully blocked", async ({ page }) => {
    await openDemoWorkspace(page);

    await expect(page.getByRole("button", { name: "Search unavailable" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Undo unavailable" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Redo unavailable" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Notifications unavailable" })).toBeDisabled();

    const canvas = page.getByTestId("workspace-canvas-shell");
    await expect(canvas.getByRole("button", { name: "Export DXF" })).toBeDisabled();
    await expect(canvas.getByRole("button", { name: "Export Report" })).toBeDisabled();
    await expect(canvas).toContainText("Export blocked: authenticate with a backend session before exporting review packages");
    const initialObjectOverlayCount = await page.locator("[data-object-overlay]").count();
    expect(initialObjectOverlayCount).toBeGreaterThan(0);

    await page.getByTestId("reopen-civora-workspace").click();
    await expect(canvas.getByTestId("preview-quality-high")).toBeVisible();
    await canvas.getByTestId("preview-quality-high").click();
    await expect(canvas).toContainText("High Quality");
    await expect(canvas.getByTestId("high-quality-preview-only-label")).toContainText(
      "Visual preview only. Canonical geometry unchanged. Not engineering evidence.",
    );
    expect(await page.locator("[data-object-overlay]").count()).toBe(initialObjectOverlayCount);
    await canvas.getByTestId("preview-quality-standard").click();
    await expect(canvas).toContainText("Standard");
    expect(await page.locator("[data-object-overlay]").count()).toBe(initialObjectOverlayCount);

    await canvas.getByTestId("preview-mode-3d").click();
    await expect(canvas).toContainText("3D");
    await canvas.getByTestId("preview-mode-2d").click();
    await expect(canvas).toContainText("2D");
    expect(await page.locator("[data-object-overlay]").count()).toBe(initialObjectOverlayCount);

    await canvas.getByTestId("preview-interaction-edit").click();
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Point" })).toBeEnabled();
  });

  test("chat answers common QA commands without claiming construction readiness", async ({ page }) => {
    await openDemoWorkspace(page);

    await page.locator("header").getByRole("button", { name: "Chat" }).click();
    const composer = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
    const send = page.getByRole("button", { name: "Send" });
    const messageBodies = page.locator("p.whitespace-pre-wrap");

    await composer.fill("what should I do next");
    await send.click();
    await expect(messageBodies.filter({ hasText: /review-required|review evidence|engineer review/i })).toBeVisible();

    await composer.fill("why can't I export");
    await send.click();
    await expect(messageBodies.filter({ hasText: "Export is blocked: authenticate with a backend session before exporting review packages." })).toBeVisible();

    await composer.fill("make this a basin");
    await send.click();
    await expect(messageBodies.filter({ hasText: "This is draft geometry and still requires engineer review." })).toBeVisible();

    await composer.fill("stamp this construction-ready");
    await send.click();
    await expect(messageBodies.filter({ hasText: /Field use and professional responsibility remain outside Civora/i })).toBeVisible();
    await expect(messageBodies.last()).not.toContainText(/construction-ready|approved for construction|released for construction/i);
  });

  test("mobile workspace has no horizontal page overflow and keeps critical controls reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDemoWorkspace(page);

    await expect(page.getByTestId("floating-command-bar")).toBeVisible();
    await expect(page.getByTestId("bottom-review-panel")).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);

    const offscreenBottomTabs = await page.evaluate(() => {
      const viewportWidth = document.documentElement.clientWidth;
      return Array.from(document.querySelectorAll('[data-testid="bottom-review-panel"] button'))
        .map((button) => button.getBoundingClientRect())
        .filter((rect) => rect.width > 0 && (rect.left < -1 || rect.right > viewportWidth + 1))
        .length;
    });
    expect(offscreenBottomTabs).toBe(0);

    const canvas = page.getByTestId("workspace-canvas-shell");
    const sidebar = page.getByTestId("left-sidebar");
    const showSidebarToggle = page.getByRole("button", { name: "Show left sidebar" });
    await expect(showSidebarToggle).toBeVisible();
    await expect(canvas).toBeVisible();

    const canvasBounds = await canvas.boundingBox();
    expect(canvasBounds?.x ?? -1).toBeGreaterThanOrEqual(0);
    expect(canvasBounds?.width ?? 0).toBeGreaterThan(0);

    await showSidebarToggle.click();
    await expect(page.getByRole("button", { name: "Hide left sidebar" })).toBeVisible();
    await expect(sidebar).toBeVisible();
    await expect(sidebar).toHaveAttribute("data-motion-state", "open");

    await sidebar.getByRole("button", { name: "Open canvas from sidebar" }).click();
    await expect(page.getByRole("button", { name: "Show left sidebar" })).toBeVisible();
    await expect(canvas).toBeVisible();

    const postToggleOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(postToggleOverflow).toBeLessThanOrEqual(1);
  });
});
