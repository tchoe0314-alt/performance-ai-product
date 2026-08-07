import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true }),
    });
  });
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked");
}

async function runCommand(page: Page, command: string) {
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  const input = page.getByTestId("civora-command-input");
  await expect(input).toBeVisible();
  await input.fill(command);
  await input.press("Enter");
}

test.describe("Preview height and geometry fidelity", () => {
  test("edits canonical building height and roof, then renders the same value in 3D", async ({ page }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    await openDemoWorkspace(page);
    await page.getByRole("button", { name: /^Draw$/ }).first().click();
    const initialObjectCount = await page.getByTestId("object-manager-row").count();
    const buildingRow = page
      .getByTestId("object-manager-row")
      .filter({ hasText: "Multifamily Building A" })
      .first();
    await buildingRow.getByTestId("object-manager-select").click();

    const height = page.getByTestId("selected-object-height-input");
    await expect(height).toHaveValue("36");
    await height.fill("72");
    await expect(height).toHaveValue("72");
    await page.getByTestId("selected-object-roof-select").selectOption("gable");
    await expect(buildingRow).toContainText("72 ft high");

    await page.getByTestId("preview-quality-high").click();
    await page.getByTestId("preview-mode-3d").click();
    const viewer = page.getByTestId("civil-3d-viewer");
    await expect(viewer).toBeVisible({ timeout: 20_000 });
    const objectStrip = page.getByTestId("civil-3d-object-strip");
    await expect(objectStrip).toContainText("BUILDING | 72 ft");
    await objectStrip.getByRole("button", { name: /Multifamily Building A/i }).click();
    await expect(page.getByTestId("civil-3d-selected-height")).toContainText("72 ft");

    await runCommand(page, "make Multifamily Building A 84 feet tall");
    await expect(viewer).toBeVisible({ timeout: 20_000 });
    await expect(objectStrip).toContainText("BUILDING | 84 ft");

    const pixelSignal = await page
      .getByTestId("civil-3d-canvas-mount")
      .locator("canvas")
      .evaluate((canvas: HTMLCanvasElement) => {
        const gl =
          canvas.getContext("webgl2", { preserveDrawingBuffer: true }) ||
          canvas.getContext("webgl", { preserveDrawingBuffer: true });
        if (!gl) return { colored: 0, samples: 0 };
        const pixels = new Uint8Array(canvas.width * canvas.height * 4);
        gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        let colored = 0;
        let samples = 0;
        const step = Math.max(4, Math.floor(pixels.length / 6000));
        for (let index = 0; index < pixels.length; index += step * 4) {
          samples += 1;
          const red = pixels[index];
          const green = pixels[index + 1];
          const blue = pixels[index + 2];
          if (Math.max(red, green, blue) - Math.min(red, green, blue) > 8) colored += 1;
        }
        return { colored, samples };
      });
    expect(pixelSignal.samples).toBeGreaterThan(0);
    expect(pixelSignal.colored).toBeGreaterThan(18);

    await page.getByTestId("preview-mode-2d").click();
    const mapCanvas = page.locator(".mapboxgl-canvas").filter({ visible: true });
    if ((await mapCanvas.count()) > 0) {
      await expect(mapCanvas.first()).toBeVisible();
      await expect(page.locator('[data-object-overlay][aria-label*="Multifamily Building A"]').first()).toBeVisible();
    } else {
      await expect(page.getByTestId("professional-building-footprint").first()).toHaveJSProperty("tagName", "polygon");
    }
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Plan Sheet mode/i);
    await page.getByRole("button", { name: /^Draw$/ }).first().click();
    expect(await page.getByTestId("object-manager-row").count()).toBe(initialObjectCount);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
  });
});
