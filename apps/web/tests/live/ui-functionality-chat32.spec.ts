import { expect, test } from "@playwright/test";

async function openDemoWorkspace(page: import("@playwright/test").Page) {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Detention Basin A", { timeout: 30_000 });
}

test.describe("Chat 32 UI functionality QA", () => {
  test("desktop controls are wired or truthfully blocked", async ({ page }) => {
    await openDemoWorkspace(page);

    await expect(page.getByRole("button", { name: "Search unavailable" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Undo unavailable" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Redo unavailable" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Notifications unavailable" })).toHaveCount(0);
    await expect(page.locator("header").getByRole("button", { name: "Projects" })).toBeVisible();
    await expect(page.locator("header").getByRole("button", { name: "Chat" })).toBeVisible();
    await expect(page.locator("header").getByRole("button", { name: "Workspace" })).toBeVisible();

    const canvas = page.getByTestId("workspace-canvas-shell");
    await page.getByRole("button", { name: /^Deliver$/ }).filter({ visible: true }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Make Review Package|Deliver/i);
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Export|review package|blocked/i);
    const initialObjectOverlayCount = await page.locator("[data-object-overlay]").count();
    expect(initialObjectOverlayCount).toBeGreaterThan(0);

    await page.locator("header").getByRole("button", { name: "Workspace" }).click();
    await expect(canvas.getByTestId("preview-quality-high")).toBeVisible();
    await canvas.getByTestId("preview-quality-high").click();
    await expect(canvas).toContainText("High Quality");
    await expect(canvas.getByTestId("high-quality-preview-only-label")).toContainText(/Visual preview only/i);
    await expect(canvas.getByTestId("high-quality-preview-only-label")).toContainText(/Canonical geometry unchanged/i);
    await expect(canvas.getByTestId("high-quality-preview-only-label")).toContainText(/Not engineering evidence/i);
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
    await page.getByTestId("left-sidebar").getByRole("button", { name: "Draw", exact: true }).click();
    const drawTools = page.getByTestId("draw-cad-tools-section");
    await expect(drawTools).toBeVisible();
    await expect(drawTools.getByTestId("cad-tool-pan")).toBeEnabled();
    await expect(drawTools.getByTestId("cad-tool-line")).toBeEnabled();
    await expect(drawTools.getByTestId("cad-tool-area")).toBeEnabled();
    await expect(drawTools.getByTestId("cad-tool-box")).toBeEnabled();
    await expect(drawTools.getByTestId("cad-tool-point")).toBeEnabled();
  });

  test("chat answers common QA commands without claiming construction readiness", async ({ page }) => {
    await openDemoWorkspace(page);

    await page.locator("header").getByRole("button", { name: "Chat" }).click();
    const composer = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
    const send = page.getByRole("button", { name: "Send" });
    const chatPanel = page.getByTestId("workspace-right-panel");

    await composer.fill("what should I do next");
    await send.click();
    await expect(chatPanel).toContainText(/review-required|review evidence|engineer review|review drafts/i);

    await composer.fill("why can't I export");
    await send.click();
    await expect(chatPanel).toContainText("Export needs input: authenticate with a backend session before exporting review packages.");

    await composer.fill("make this a basin");
    await send.click();
    await expect(chatPanel).toContainText("This is draft geometry and still requires engineer review.");

    await composer.fill("stamp this construction-ready");
    await send.click();
    await expect(chatPanel).toContainText(/can't stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record/i);
    await expect(chatPanel).toContainText(/review-only draft materials/i);
    await expect(chatPanel.locator("p").last()).not.toContainText(/approved for construction|released for construction/i);
  });

  test("mobile workspace has no horizontal page overflow and keeps critical controls reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDemoWorkspace(page);

    await expect(page.getByTestId("floating-command-bar")).toHaveCount(0);
    await expect(page.getByTestId("bottom-review-panel")).toHaveCount(0);

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
    const hideSidebarToggle = page.getByRole("button", { name: "Hide left sidebar" });
    const showSidebarToggle = page.getByRole("button", { name: "Show left sidebar" });
    await expect(hideSidebarToggle).toBeVisible();
    await expect(canvas).toBeVisible();

    const canvasBounds = await canvas.boundingBox();
    expect(canvasBounds?.x ?? -1).toBeGreaterThanOrEqual(0);
    expect(canvasBounds?.width ?? 0).toBeGreaterThan(0);

    await hideSidebarToggle.click();
    await expect(showSidebarToggle).toBeVisible();
    await expect(sidebar).toHaveAttribute("data-motion-state", "closed");
    await page.keyboard.press("/");
    await expect(page.getByTestId("floating-command-bar")).toBeVisible();

    await showSidebarToggle.click();
    await expect(hideSidebarToggle).toBeVisible();
    await expect(sidebar).toBeVisible();
    await expect(sidebar).toHaveAttribute("data-motion-state", "open");

    await sidebar.getByRole("button", { name: /^Draw$/ }).click();
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeVisible();
    await expect(canvas.getByRole("button", { name: "Add Area" })).toBeVisible();
    await expect(canvas).toBeVisible();

    const postToggleOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(postToggleOverflow).toBeLessThanOrEqual(1);
  });
});
