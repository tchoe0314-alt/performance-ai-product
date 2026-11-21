import { expect, test } from "@playwright/test";

import { buildPreviewMarkerVisual } from "../../app/utils/previewCanvasDetail";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

test("overview markers shrink without shrinking selected evidence", () => {
  const overview = buildPreviewMarkerVisual(0.55, false);
  const standard = buildPreviewMarkerVisual(1, false);
  const detail = buildPreviewMarkerVisual(3, false);
  const selectedOverview = buildPreviewMarkerVisual(0.55, true);

  expect(overview.radius).toBeLessThan(standard.radius);
  expect(standard.radius).toBeLessThan(detail.radius);
  expect(overview.fontSize).toBeLessThan(standard.fontSize);
  expect(selectedOverview).toEqual({ radius: 1.05, fontSize: 1.55, strokeWidth: 0.22 });
});

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "narrow", width: 390, height: 844 },
]) {
  test(`${viewport.name} controls stay compact, usable, and stable`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await openWorkspaceTool(page, "Draw");

    const tools = page.getByTestId("draw-cad-tools-section");
    await expect(tools).toBeVisible();
    const select = tools.getByTestId("cad-tool-select");
    const pan = tools.getByTestId("cad-tool-pan");
    const toolBox = await select.boundingBox();
    expect(toolBox).not.toBeNull();
    expect(toolBox!.height).toBeGreaterThanOrEqual(44);
    expect(toolBox!.height).toBeLessThanOrEqual(48);

    const before = await tools.boundingBox();
    if (viewport.name === "desktop") {
      await pan.click();
      await select.click();
      const after = await tools.boundingBox();
      expect(after?.width).toBe(before?.width);
      expect(after?.height).toBe(before?.height);
    }

    await select.focus();
    await expect(select).toBeFocused();

    await page.screenshot({ path: testInfo.outputPath(`${viewport.name}-toolbar-density.png`), fullPage: true });
  });
}
