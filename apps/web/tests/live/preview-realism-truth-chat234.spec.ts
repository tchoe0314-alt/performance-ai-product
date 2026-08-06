import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/\d+ project object\(s\)/, { timeout: 30_000 });
}

test.describe("Chat 234 preview realism truth pass", () => {
  test("source layer controls hide every proposed canvas overlay together", async ({ page }) => {
    await openDemoWorkspace(page);
    const canvas = page.getByTestId("workspace-canvas-shell");
    await canvas.getByTestId("preview-quality-standard").click();

    const overlays = page.locator("[data-object-overlay]");
    expect(await overlays.count()).toBeGreaterThan(0);
    await expect(page.getByRole("button", { name: "Select Hydrant W-12 fire-flow scenario" })).toHaveCount(0);
    await page.locator('[data-object-overlay][data-cad-object-id="demo-hydrant-1"]').click();
    await expect(page.getByTestId("selected-object-quick-toolbar")).toBeVisible();
    const layerMenu = page.getByTestId("preview-layer-menu");
    await layerMenu.locator("summary").click();
    await expect(page.getByTestId("preview-source-layer-proposed")).toBeVisible();
    await page.getByTestId("preview-source-layer-proposed").click();
    await expect(overlays).toHaveCount(0);
    await page.getByTestId("preview-source-layer-proposed").click();
    expect(await overlays.count()).toBeGreaterThan(0);
  });

  test("keeps the 2D review canvas professional without always-on source clutter", async ({ page }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    await openDemoWorkspace(page);
    const canvas = page.getByTestId("workspace-canvas-shell");

    await canvas.getByTestId("preview-quality-standard").click();
    await expect(page.getByTestId("preview-map-fallback-surface")).toHaveCount(0);
    await expect(page.getByTestId("preview-source-confidence-chip")).toHaveCount(0);
    await expect(page.getByTestId("preview-fallback-object-badge")).toHaveCount(0);
    await expect(page.getByTestId("preview-source-review-object-badge")).toHaveCount(0);

    const liveMapVisible = await page.getByRole("region", { name: "Map" }).isVisible().catch(() => false);
    if (liveMapVisible) {
      await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1);
      await expect(page.locator(".mapboxgl-canvas")).toBeVisible();
      await expect(page.getByTestId("plan-road-corridor")).toHaveCount(0);
      await expect(page.getByTestId("professional-building-footprint")).toHaveCount(0);
    } else {
      await expect(page.getByTestId("professional-building-footprint").first()).toBeVisible();
      expect(await page.locator("[data-object-overlay]").count()).toBeGreaterThan(0);
      await expect(canvas).toContainText(/SITE LOCKED/i);
    }
    await expect(page.getByTestId("plan-grading-context-lines")).toHaveCount(0);
    await expect(page.getByTestId("survey-boundary-annotation")).toHaveCount(0);
    await expect(page.getByTestId("survey-spot-elevation")).toHaveCount(0);
    await expect(canvas).not.toContainText(/PRELIMINARY BASE PLAN/i);
    await expect(page.getByTestId("selected-object-quick-toolbar")).toHaveCount(0);

    const hydrantOverlay = page.locator('div[data-object-overlay][aria-label="Select Hydrant W-12"]').first();
    const topVisibleOverlay = (await hydrantOverlay.isVisible().catch(() => false))
      ? hydrantOverlay
      : page.locator("[data-object-overlay][data-visual-kind]").first();
    await topVisibleOverlay.hover();
    await expect(page.getByTestId("selected-object-quick-toolbar")).toHaveCount(0);
    await topVisibleOverlay.click();
    await topVisibleOverlay.hover();
    await expect(page.getByTestId("selected-object-quick-toolbar")).toHaveCount(1);
    await expect(page.getByTestId("preview-fallback-object-badge")).toHaveCount(0);
    await expect(page.getByTestId("preview-source-review-object-badge")).toHaveCount(0);

    const bodyText = await canvas.innerText();
    expect(bodyText).not.toMatch(/construction-ready|\bstamp\b|\bseal\b|certify|certified|approved for construction|engineer of record/i);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
  });
});
