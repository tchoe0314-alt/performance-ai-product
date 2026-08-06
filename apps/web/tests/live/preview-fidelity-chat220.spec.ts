import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&mapDebug=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/\d+ project object\(s\)/, { timeout: 30_000 });
}

test.describe("Chat 220 preview fidelity", () => {
  test("2D standard and high quality have clear visual states without cluttered labels", async ({ page }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    await openDemoWorkspace(page);
    const canvas = page.getByTestId("workspace-canvas-shell");

    await canvas.getByTestId("preview-quality-standard").click();
    await expect(canvas.getByTestId("preview-quality-standard")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("preview-map-fallback-surface")).toHaveCount(0);
    await expect(page.getByTestId("preview-source-confidence-summary")).toHaveCount(0);
    await expect(page.getByTestId("preview-fallback-object-badge")).toHaveCount(0);

    await canvas.getByTestId("preview-quality-high").click();
    await expect(canvas.getByTestId("preview-quality-high")).toHaveAttribute("aria-pressed", "true");
    await expect(canvas.getByTestId("high-quality-preview-only-label")).toContainText("Visual preview only");
    await expect(canvas.getByTestId("high-quality-preview-only-label")).toContainText("Canonical geometry unchanged");
    await expect(page.getByTestId("preview-source-confidence-summary")).toHaveCount(0);

    const bodyText = await canvas.innerText();
    expect(bodyText).not.toMatch(/construction-ready|stamp|seal|certify|approved for construction/i);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
  });

  test("renders professional geometry primitives rather than only box overlays", async ({ page }) => {
    await openDemoWorkspace(page);
    const canvas = page.getByTestId("workspace-canvas-shell");
    await canvas.getByTestId("preview-quality-high").click();

    const visibleMapCanvas = page.locator(".mapboxgl-canvas").filter({ visible: true });
    if ((await visibleMapCanvas.count()) === 1) {
      await expect(visibleMapCanvas).toBeVisible();
      const mapGeometryReady = async () =>
        page.evaluate(() => {
          const summary = (
            window as Window & {
              __civoraMapLayerSummary?: {
                featureCounts?: Record<string, number>;
                layersReady?: Record<string, boolean>;
              };
            }
          ).__civoraMapLayerSummary;
          if (!summary?.featureCounts || !summary.layersReady) return false;
          return (
            (summary.featureCounts.buildings ?? 0) > 0 &&
            (summary.featureCounts.roads ?? 0) > 0 &&
            (summary.featureCounts.parking ?? 0) > 0 &&
            (summary.featureCounts.basins ?? 0) > 0 &&
            (summary.featureCounts.polygons ?? 0) > 0 &&
            (summary.featureCounts.polylines ?? 0) > 0 &&
            summary.layersReady.buildings === true &&
            summary.layersReady.roads === true &&
            summary.layersReady.parking === true &&
            summary.layersReady.basins === true
          );
        });
      await expect.poll(mapGeometryReady).toBe(true);
      return;
    }

    await expect(page.getByTestId("plan-polyline-object").first()).toBeVisible();
    await expect(page.getByTestId("plan-rect-object").first()).toBeVisible();
    await expect(page.getByTestId("plan-road-corridor").first()).toBeVisible();
    await expect(page.getByTestId("plan-basin-shelf-cues").first()).toBeVisible();
    await expect(page.getByTestId("plan-parking-stall-cues").first()).toBeVisible();

    const linePointCount = await page.getByTestId("plan-polyline-object").first().evaluate((node) => {
      const points = node.getAttribute("points") || "";
      return points.trim().split(/\s+/).filter(Boolean).length;
    });
    expect(linePointCount).toBeGreaterThan(1);
  });

  test("3D high quality canvas is nonblank and selectable", async ({ page }) => {
    await openDemoWorkspace(page);
    const canvas = page.getByTestId("workspace-canvas-shell");
    await canvas.getByTestId("preview-quality-high").click();
    await canvas.getByTestId("preview-mode-3d").click();

    await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("civil-3d-canvas-mount").locator("canvas")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("civil-3d-massing-summary")).toContainText(/3D massing:/);
    await expect(page.getByTestId("civil-3d-massing-summary")).toContainText(/detailed buildings/i);
    await page.getByTestId("civil-3d-object-strip").getByRole("button", { name: /Detention Basin A/i }).click();
    await expect(page.getByTestId("civil-3d-selection-popover")).toContainText("Detention Basin A");

    const pixelSignal = await page.getByTestId("civil-3d-canvas-mount").locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
      const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true }) || canvas.getContext("webgl", { preserveDrawingBuffer: true });
      if (!gl) return 0;
      const pixels = new Uint8Array(canvas.width * canvas.height * 4);
      gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      let colored = 0;
      const step = Math.max(4, Math.floor(pixels.length / 3600));
      for (let i = 0; i < pixels.length; i += step * 4) {
        if (Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) - Math.min(pixels[i], pixels[i + 1], pixels[i + 2]) > 8) colored += 1;
      }
      return colored;
    });
    expect(pixelSignal).toBeGreaterThan(12);
  });
});
