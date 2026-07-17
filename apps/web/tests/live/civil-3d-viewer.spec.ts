import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1") {
  const params = new URLSearchParams(query);
  if (!params.has("seedDemo")) {
    params.set("seedDemo", "1");
  }
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      await page.goto(`/demo/workspace?${params.toString()}`, { waitUntil: "domcontentloaded" });
      break;
    } catch (error) {
      if (attempt === 2) throw error;
      await page.waitForTimeout(1500);
    }
  }
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Detention Basin A", { timeout: 30_000 });
}

async function open3D(page: Page) {
  const canvasShell = page.getByTestId("workspace-canvas-shell");
  await canvasShell.getByTestId("preview-mode-3d").click();
  await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("civil-3d-canvas-mount").locator("canvas")).toBeVisible({ timeout: 20_000 });
}

test.describe("Civil 3D model viewer", () => {
  test("renders a nonblank 3D workspace with terrain state and objects", async ({ page }) => {
    await openDemoWorkspace(page);
    await open3D(page);

    await expect(page.getByTestId("civil-3d-viewer")).toContainText(
      /Terrain mesh from preview elevations|Terrain source loaded|Flat site fallback/,
      { timeout: 10_000 },
    );
    await expect(page.getByTestId("civil-3d-viewer")).toContainText("visual mode does not mutate canonical geometry");
    await expect(page.getByTestId("civil-3d-object-strip")).toContainText("Detention Basin A");
    await expect(page.getByTestId("civil-3d-object-strip")).toContainText(/DRAINAGE|PARKING|ROAD|UTILITY|BUILDING/);

    const pixelSignal = await page.getByTestId("civil-3d-canvas-mount").locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
      const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true }) || canvas.getContext("webgl", { preserveDrawingBuffer: true });
      if (!gl) return { colored: 0, samples: 0 };
      const width = canvas.width;
      const height = canvas.height;
      const pixels = new Uint8Array(width * height * 4);
      gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      let colored = 0;
      let samples = 0;
      const step = Math.max(4, Math.floor(pixels.length / 4000));
      for (let i = 0; i < pixels.length; i += step * 4) {
        samples += 1;
        const r = pixels[i];
        const g = pixels[i + 1];
        const b = pixels[i + 2];
        if (Math.max(r, g, b) - Math.min(r, g, b) > 8) colored += 1;
      }
      return { colored, samples };
    });
    expect(pixelSignal.samples).toBeGreaterThan(0);
    expect(pixelSignal.colored).toBeGreaterThan(12);
  });

  test("selecting a 3D object updates the 3D inspector", async ({ page }) => {
    await openDemoWorkspace(page);
    await open3D(page);

    await page.getByTestId("civil-3d-object-strip").getByRole("button", { name: /Detention Basin A/i }).click();
    const inspector = page.getByTestId("civil-3d-selection-popover");
    await expect(inspector).toBeVisible();
    await expect(inspector).toContainText("Detention Basin A");
    await expect(inspector).toContainText(/DRAINAGE|review/i);
  });

  test("standard and high quality modes keep canonical object count stable", async ({ page }) => {
    await openDemoWorkspace(page);
    await open3D(page);

    const objectButtons = page.getByTestId("civil-3d-object-strip").getByRole("button");
    const initialCount = await objectButtons.count();
    expect(initialCount).toBeGreaterThan(0);

    await page.getByTestId("preview-quality-high").click();
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText("High Quality");
    await expect(page.getByTestId("high-quality-preview-only-label")).toContainText("Visual preview only");
    expect(await objectButtons.count()).toBe(initialCount);

    await page.getByTestId("preview-quality-standard").click();
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Standard");
    expect(await objectButtons.count()).toBe(initialCount);
  });

  test("mobile 3D mode avoids horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDemoWorkspace(page);
    await open3D(page);

    await expect(page.getByTestId("civil-3d-viewer")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("3D workspace avoids unsafe release wording", async ({ page }) => {
    await openDemoWorkspace(page);
    await open3D(page);

    const viewerText = await page.getByTestId("civil-3d-viewer").innerText();
    expect(viewerText).not.toMatch(/construction-ready|stamp|seal|sign|certify|approval/i);
  });
});
