import { expect, test, type Locator, type Page } from "@playwright/test";

async function openCleanWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
}

function overlap(a: { x: number; y: number; width: number; height: number }, b: { x: number; y: number; width: number; height: number }) {
  const width = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
  const height = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  return width * height;
}

async function box(locator: Locator) {
  const value = await locator.boundingBox();
  expect(value).not.toBeNull();
  return value!;
}

async function clickSitePoint(page: Page, xRatio: number, yRatio: number) {
  const point = await page.getByTestId("canonical-site-boundary").evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      return {
        x: rect.left + rect.width * ratios.xRatio,
        y: rect.top + rect.height * ratios.yRatio,
      };
    },
    { xRatio, yRatio },
  );
  await page.mouse.click(point.x, point.y);
}

test.describe("canvas-first workspace redesign", () => {
  test("desktop has one clear shell and a drawer that minimizes and reopens", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openCleanWorkspace(page);

    await expect(page.getByTestId("primary-workflow-sidebar").getByRole("button")).toHaveCount(5);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(1);
    await expect(page.getByTestId("preview-object-manager-overlay")).toHaveCount(0);
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);

    await page.getByRole("button", { name: "Setup", exact: true }).click();
    const drawer = page.getByTestId("workspace-right-panel");
    const toolbar = page.getByTestId("preview-control-stack").locator(".civora-preview-view-toolbar");
    await expect(drawer).toBeVisible();
    await expect(page.getByTestId("setup-address-truth")).toBeVisible();
    expect((await box(toolbar)).x + (await box(toolbar)).width).toBeLessThanOrEqual((await box(drawer)).x);

    await page.getByRole("button", { name: "Minimize", exact: true }).click();
    await expect(drawer).toBeHidden();
    await page.getByRole("button", { name: "Setup", exact: true }).click();
    await expect(drawer).toBeVisible();

    const deliverMode = page.getByRole("button", { name: "Deliver", exact: true });
    await deliverMode.click();
    await expect(deliverMode).toHaveAttribute("aria-current", "page");
    await page.getByTestId("header-chat-button").click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Conversation and assisted workflow control");
    await expect(deliverMode).toHaveAttribute("aria-current", "page");
  });

  test("mobile keeps the drawer, command input, and workflow rail separate", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openCleanWorkspace(page);
    await page.getByRole("button", { name: "Setup", exact: true }).click();

    const drawer = await box(page.getByTestId("workspace-right-panel"));
    const command = await box(page.getByTestId("floating-command-bar"));
    const rail = await box(page.getByTestId("left-sidebar"));
    expect(overlap(drawer, command)).toBe(0);
    expect(overlap(drawer, rail)).toBe(0);
    expect(overlap(command, rail)).toBe(0);
    await expect(page.locator(".civora-preview-mobile-draw-toolbar")).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);

    await page.getByRole("button", { name: "Draw", exact: true }).click();
    await page.getByTestId("cad-tool-line").click();
    await expect(page.getByTestId("workspace-right-panel")).toBeHidden();
    const mobileTools = page.locator(".civora-preview-mobile-draw-toolbar");
    await expect(mobileTools).toBeVisible();
    expect(overlap(await box(mobileTools), await box(page.getByTestId("floating-command-bar")))).toBe(0);
    await mobileTools.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(mobileTools).toHaveCount(0);
  });

  test("site setup, drawing, drawer clearance, and 3D mode use real state", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 720 });
    await openCleanWorkspace(page);

    await page.getByRole("button", { name: "Setup", exact: true }).click();
    await page.getByTestId("use-1000-site-size").click();
    await page.getByRole("button", { name: "Use this site", exact: true }).click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    await expect(page.getByTestId("canonical-site-boundary")).toBeVisible();

    const siteBox = await box(page.getByTestId("canonical-site-boundary"));
    expect(Math.abs(siteBox.width - siteBox.height)).toBeLessThan(2);

    await page.getByRole("button", { name: "Draw", exact: true }).click();
    await page.getByTestId("cad-tool-line").click();
    const drawer = page.getByTestId("workspace-right-panel");
    const drawHud = page.getByTestId("active-draw-hud");
    await expect(drawer).toBeVisible();
    await expect(drawHud).toBeVisible();
    expect((await box(drawHud)).x + (await box(drawHud)).width).toBeLessThanOrEqual((await box(drawer)).x);

    const beforeObjects = await page.locator("[data-object-overlay]").count();
    await clickSitePoint(page, 0.25, 0.3);
    await clickSitePoint(page, 0.62, 0.3);
    await expect.poll(() => page.locator("[data-object-overlay]").count()).toBeGreaterThan(beforeObjects);

    await page.getByTestId("cad-tool-line").click();
    await expect(drawHud).toBeVisible();
    await page.getByTestId("preview-mode-3d").click();
    await expect(drawHud).toHaveCount(0);
    await expect(page.getByTestId("preview-mode-3d")).toHaveAttribute("aria-pressed", "true").catch(async () => {
      await expect(page.getByTestId("preview-mode-3d")).toHaveClass(/bg-slate-950/);
    });
    await page.getByTestId("preview-mode-2d").click();
    await expect(page.getByTestId("preview-plan-canvas-svg")).toBeVisible();

    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
    await expect(page.getByTestId("cad-command-feedback-panel")).toHaveCount(0);
  });
});
