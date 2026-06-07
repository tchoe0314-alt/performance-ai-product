import { expect, type Page, type Locator, test } from "@playwright/test";

async function clickSurfaceAt(surface: Locator, xRatio: number, yRatio: number) {
  await surface.scrollIntoViewIfNeeded();
  const box = await surface.boundingBox();
  expect(box).not.toBeNull();
  await surface.page().mouse.click(box!.x + box!.width * xRatio, box!.y + box!.height * yRatio);
}

async function openBlankWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundary=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Detention Basin A").first()).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Open setup from sidebar command" }).click();
  await page.getByRole("button", { name: "Start a blank site and clear address map evidence" }).click({ noWaitAfter: true });
  await expect(page.getByTestId("site-status")).toContainText("Selecting Site");
  await expect(page.getByText("Detention Basin A")).toHaveCount(0);
  await expect(page.getByText("Multifamily Building A")).toHaveCount(0);
  const close = page.getByRole("button", { name: "Close" });
  if (await close.isVisible().catch(() => false)) {
    await close.click();
  }
}

test.describe("drawn site boundary Finish workflow", () => {
  test("locks a blank drawn boundary and enables draft manual objects", async ({ page }) => {
    await openBlankWorkspace(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    const surface = page.getByTestId("preview-drawing-surface");
    await canvas.getByRole("button", { name: "Draw Site Boundary" }).click();

    await clickSurfaceAt(surface, 0.22, 0.42);
    await clickSurfaceAt(surface, 0.72, 0.44);
    await clickSurfaceAt(surface, 0.62, 0.78);
    await expect(canvas.getByRole("button", { name: "Finish" })).toBeEnabled();
    await canvas.getByRole("button", { name: "Finish" }).click();

    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    await expect(canvas).toContainText("Locked canonical site");
    await expect(canvas.getByRole("button", { name: "Draw Site Boundary" })).toBeVisible();
    await expect(canvas.getByRole("button", { name: "Change Site Boundary" })).toBeVisible();
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Point" })).toBeEnabled();

    await canvas.getByRole("button", { name: "Change Site Boundary" }).click();
    await expect(page.getByTestId("site-status")).toContainText("Selecting Site");
    await page.getByRole("button", { name: "Open setup from sidebar command" }).click();
    await page.getByRole("button", { name: "Lock current site boundary for engineer review" }).click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    const relockClose = page.getByRole("button", { name: "Close" });
    if (await relockClose.isVisible().catch(() => false)) {
      await relockClose.click();
    }
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Area" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Box" })).toBeEnabled();
    await expect(canvas.getByRole("button", { name: "Add Point" })).toBeEnabled();

    const beforeObjects = await page.locator("[data-object-overlay]").count();
    await canvas.getByRole("button", { name: "Add Box" }).click();
    await clickSurfaceAt(surface, 0.28, 0.5);
    await clickSurfaceAt(surface, 0.44, 0.66);
    await expect(page.getByText("Custom Rectangle 1").first()).toBeVisible();

    await canvas.getByRole("button", { name: "Add Area" }).click();
    await clickSurfaceAt(surface, 0.5, 0.52);
    await clickSurfaceAt(surface, 0.66, 0.58);
    await clickSurfaceAt(surface, 0.58, 0.72);
    await canvas.getByRole("button", { name: "Finish" }).click();
    await expect(page.getByText("Custom Area 2").first()).toBeVisible();

    await canvas.getByRole("button", { name: "Add Line" }).click();
    await clickSurfaceAt(surface, 0.24, 0.74);
    await clickSurfaceAt(surface, 0.5, 0.82);
    await canvas.getByRole("button", { name: "Finish" }).click();

    await canvas.getByRole("button", { name: "Add Point" }).click();
    await clickSurfaceAt(surface, 0.78, 0.72);
    await expect.poll(async () => (await page.locator("[data-object-overlay]").count()) - beforeObjects).toBeGreaterThanOrEqual(4);

    await page.getByRole("button", { name: "Open chat from sidebar command" }).click();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("make this a basin");
    await page.getByRole("button", { name: "Send" }).click();
    await expect(page.locator("p.whitespace-pre-wrap").filter({ hasText: "draft geometry and still requires engineer review" })).toBeVisible();

    await page.getByRole("button", { name: "Open canvas from sidebar command" }).click();
    await page.getByRole("button", { name: "Selected Details" }).click();
    const rightPanel = page.getByTestId("workspace-right-panel");
    await expect(rightPanel.locator("p").filter({ hasText: /^Basin \/ Detention Pond \d+$/ })).toBeVisible();
    await expect(rightPanel.locator('input[value="manual_drawn"]')).toBeVisible();
    await expect(
      rightPanel.locator("button", { hasText: /Basin \/ Detention Pond \d+/ }).filter({
        hasText: "Canonical geometry · Draft review required",
      }),
    ).toBeVisible();
  });

  test("mobile keeps draw controls reachable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/demo/workspace?debugPreview=1&chat7DrawnBoundaryMobile=1", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Draw Site Boundary" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Line" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Area" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Box" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Add Point" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
