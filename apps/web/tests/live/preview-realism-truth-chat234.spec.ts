import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Detention Basin A", { timeout: 30_000 });
}

test.describe("Chat 234 preview realism truth pass", () => {
  test("keeps the 2D review canvas professional without always-on source clutter", async ({ page }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    await openDemoWorkspace(page);
    const canvas = page.getByTestId("workspace-canvas-shell");

    await canvas.getByTestId("preview-quality-high").click();
    await expect(page.getByTestId("preview-map-fallback-surface")).toHaveCount(0);
    await expect(page.getByTestId("preview-source-confidence-chip")).toHaveCount(0);
    await expect(page.getByTestId("preview-fallback-object-badge")).toHaveCount(0);
    await expect(page.getByTestId("preview-source-review-object-badge")).toHaveCount(0);

    await expect(page.getByTestId("plan-road-corridor").first()).toBeVisible();
    await expect(page.getByTestId("plan-basin-shelf-cues").first()).toBeVisible();
    await expect(page.getByTestId("plan-parking-stall-cues").first()).toBeVisible();

    const hydrantOverlay = page.locator('div[data-object-overlay][aria-label="Select Hydrant W-12"]').first();
    const topVisibleOverlay = (await hydrantOverlay.isVisible().catch(() => false))
      ? hydrantOverlay
      : page.locator("[data-object-overlay][data-visual-kind]").first();
    await topVisibleOverlay.hover();
    await expect(page.getByTestId("preview-fallback-object-badge").or(page.getByTestId("preview-source-review-object-badge")).first()).toBeVisible();

    const bodyText = await canvas.innerText();
    expect(bodyText).not.toMatch(/construction-ready|\bstamp\b|\bseal\b|certify|certified|approved for construction|engineer of record/i);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
  });
});
