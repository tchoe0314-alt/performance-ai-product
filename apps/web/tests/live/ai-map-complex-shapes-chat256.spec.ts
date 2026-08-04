import { expect, test, type Locator, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";

async function clickExposedSurface(surface: Locator, siteFrame: Locator, xRatio: number, yRatio: number) {
  await surface.scrollIntoViewIfNeeded();
  const point = await siteFrame.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      const clamp = (value: number) => Math.max(0.08, Math.min(0.9, value));
      return {
        x: rect.left + rect.width * clamp(ratios.xRatio),
        y: rect.top + rect.height * clamp(ratios.yRatio),
      };
    },
    { xRatio, yRatio },
  );
  await surface.page().mouse.click(point.x, point.y);
}

async function drawArea(page: Page, points: Array<[number, number]>) {
  await page.getByTestId("cad-tool-area").click();
  const surface = page.getByTestId("preview-drawing-surface").filter({ visible: true }).first();
  const siteFrame = page.getByTestId("preview-plan-canvas-svg").first();
  await expect(siteFrame).toBeVisible();
  for (const [x, y] of points) await clickExposedSurface(surface, siteFrame, x, y);
  const finish = page.getByTestId("canvas-quick-finish").filter({ visible: true }).first();
  await expect(finish).toBeEnabled();
  await finish.click();
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/AREA created editable draft geometry/i);
}

test("keeps the live map visible and preserves complex building and parking polygons", async ({ page }) => {
  await mkdir("test-results/chat256-preview", { recursive: true });
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });

  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1&aiRealismProvider=mock", {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible();

  await drawArea(page, [
    [0.15, 0.2],
    [0.34, 0.2],
    [0.34, 0.31],
    [0.27, 0.31],
    [0.27, 0.43],
    [0.15, 0.43],
  ]);
  await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill("L-Shaped Research Building");
  await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("office_building");
  await page.getByTestId("selected-object-height-input").filter({ visible: true }).first().fill("64");

  await drawArea(page, [
    [0.42, 0.2],
    [0.7, 0.24],
    [0.74, 0.37],
    [0.64, 0.47],
    [0.43, 0.43],
    [0.38, 0.31],
  ]);
  await page.getByTestId("preview-object-manager-rename").filter({ visible: true }).first().fill("Angled Visitor Parking");
  await page.getByTestId("preview-object-manager-type").filter({ visible: true }).first().selectOption("parking");

  await expect(page.getByTestId("object-manager-row").filter({ hasText: "L-Shaped Research Building" }).first()).toBeVisible();
  await expect(page.getByTestId("object-manager-row").filter({ hasText: "Angled Visitor Parking" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Minimize", exact: true }).click();
  await page.getByRole("button", { name: "Plan Sheet", exact: true }).click();
  const mapToggle = page.getByTestId("preview-inner-map-toggle");
  const liveMapAvailable = await mapToggle.isEnabled();
  if (liveMapAvailable && (await mapToggle.textContent())?.includes("Off")) await mapToggle.click();
  if (liveMapAvailable) await expect(page.getByRole("region", { name: "Map" })).toBeVisible();
  await page.getByTestId("ai-realism-on").click();

  await expect(page.getByTestId("ai-realism-image")).toBeVisible();
  await expect(page.getByTestId("ai-realism-preview-badge")).toContainText(
    liveMapAvailable ? "Live map + current layout" : "Current site layout",
  );
  await expect(page.getByTestId("ai-realism-site-frame")).toContainText(
    liveMapAvailable ? /ft × .* ft.*registered over live map context/i : /ft × .* ft.*local site coordinates/i,
  );
  const imageSource = await page.getByTestId("ai-realism-image").getAttribute("src");
  expect(imageSource).toBeTruthy();
  const artifactSvg = decodeURIComponent(String(imageSource).split(",").slice(1).join(","));
  expect(artifactSvg).toContain('data-map-grounded="true"');
  expect(artifactSvg).toContain('data-ai-object-type="office_building"');
  expect(artifactSvg).toContain('data-ai-object-type="parking"');
  expect(artifactSvg).toContain("L-Shaped Research Building");
  expect(artifactSvg).toContain("Angled Visitor Parking");
  expect((artifactSvg.match(/data-geometry-kind="polygon"/g) || []).length).toBeGreaterThanOrEqual(2);
  expect(artifactSvg).toContain("ai-parking-clip");
  expect(artifactSvg).not.toContain('<rect width="1200" height="760" fill="#f8fafc"');
  await page.screenshot({ path: "test-results/chat256-preview/ai-map-complex-shapes.png", fullPage: true });

  await page.getByTestId("ai-realism-off").click();
  if (liveMapAvailable && (await mapToggle.textContent())?.includes("On")) await mapToggle.click();
  await page.getByRole("button", { name: "3D", exact: true }).click();
  await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("civil-3d-object-strip")).toContainText("L-Shaped Research Building");
  await expect(page.getByTestId("civil-3d-object-strip")).toContainText(/BUILDING \| 64 ft/i);
  await expect(page.getByTestId("civil-3d-object-strip")).toContainText("Angled Visitor Parking");

  const pixels = await page.getByTestId("civil-3d-canvas-mount").locator("canvas").evaluate((canvas: HTMLCanvasElement) => {
    const gl = canvas.getContext("webgl2", { preserveDrawingBuffer: true }) || canvas.getContext("webgl", { preserveDrawingBuffer: true });
    if (!gl) return 0;
    const sample = new Uint8Array(canvas.width * canvas.height * 4);
    gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, sample);
    let signal = 0;
    for (let index = 0; index < sample.length; index += Math.max(16, Math.floor(sample.length / 8000))) {
      if (sample[index] !== sample[index + 1] || sample[index + 1] !== sample[index + 2]) signal += 1;
    }
    return signal;
  });
  expect(pixels).toBeGreaterThan(20);
  await page.screenshot({ path: "test-results/chat256-preview/complex-shapes-3d.png", fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
});
