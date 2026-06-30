import { expect, test, type Page } from "@playwright/test";

async function openWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
}

async function openPanel(page: Page, name: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible()) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
}

test.describe("Chat 227 Apple-clean workspace polish", () => {
  test("desktop is preview-first with minimal mode rail and reachable drawers", async ({ page }) => {
    await openWorkspace(page);

    const canvasBox = await page.getByTestId("workspace-canvas-shell").boundingBox();
    const railBox = await page.getByTestId("left-sidebar").boundingBox();
    expect(canvasBox?.width ?? 0).toBeGreaterThan(900);
    expect(railBox?.width ?? 999).toBeLessThanOrEqual(120);

    await openPanel(page, /^Draw$/);
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Object Manager|Canvas Objects|CAD Tools/i);
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Add objects or ask Civora to generate|Placed|Unplaced|No objects yet/i);
    await expect(page.getByTestId("workspace-right-panel").getByRole("button", { name: /Minimize/i })).toBeVisible();

    await openPanel(page, /^Dashboard$/);
    await expect(page.getByTestId("workspace-right-panel").locator("[data-sections-collapsed='true']")).toBeVisible();

    await page.getByRole("button", { name: "Open chat from header" }).click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toBeVisible();
    await page.getByRole("button", { name: "Open projects" }).click();
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
  });

  test("setup, generate, deliver keep one obvious primary action each", async ({ page }) => {
    await openWorkspace(page);

    await openPanel(page, /^Setup$/);
    await expect(page.getByTestId("setup-address-truth")).toContainText(/Type project address/i);
    await expect(page.getByTestId("setup-site-box-controls")).toContainText(/Lock site|Unlock site/i);

    await openPanel(page, /^Generate$/);
    await expect(page.getByTestId("generate-main-action")).toBeVisible();
    await expect(page.getByTestId("generate-main-action")).toContainText(/^Generate/i);

    await openPanel(page, /^Deliver$/);
    await expect(page.getByRole("button", { name: /Make Review Package/i })).toBeVisible();
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(/construction-ready|Civora approved|stamped by Civora|sealed by Civora|signed by Civora/i);
  });

  test("mobile has no horizontal overflow and canvas controls stay reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openWorkspace(page);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);

    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    const canvasBox = await page.getByTestId("workspace-canvas-shell").boundingBox();
    expect(canvasBox?.width ?? 0).toBeLessThanOrEqual(390);
    expect(canvasBox?.height ?? 0).toBeGreaterThan(500);
  });
});
