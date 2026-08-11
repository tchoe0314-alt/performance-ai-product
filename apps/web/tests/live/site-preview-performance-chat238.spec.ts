import { expect, test, type Page } from "@playwright/test";

import { setPreviewQuality } from "./testUiHelpers";

async function collectFailures(page: Page) {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (url.includes("mapbox")) failedRequests.push(`${request.method()} ${url}`);
  });
  return { pageErrors, consoleErrors, failedRequests };
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

async function openNewProject(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByTestId("header-projects-button").click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible();
  await page.getByRole("button", { name: /new project/i }).first().click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0, { timeout: 5_000 });
}

async function createBlankSite(page: Page) {
  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toBeVisible({ timeout: 5_000 });
  const boundary = panel.getByTestId("setup-site-box-controls");
  const boundaryOpen = await boundary.evaluate((element) => element.hasAttribute("open"));
  if (!boundaryOpen) await boundary.locator("summary").click();
  await boundary.getByLabel("Width (ft)").fill("1000");
  await boundary.getByLabel("Depth (ft)").fill("1000");
  await boundary.getByRole("button", { name: "Use this site" }).click();
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 5_000 });
  if (await panel.isVisible()) {
    await panel.getByRole("button", { name: "Minimize" }).click();
  }
  await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0, { timeout: 5_000 });
}

async function timed(label: string, action: () => Promise<void>, thresholdMs = 2_500) {
  const startedAt = Date.now();
  await action();
  const duration = Date.now() - startedAt;
  console.info(`[chat238-timing] ${label}: ${duration}ms`);
  expect(duration).toBeLessThanOrEqual(thresholdMs);
}

test.describe("Chat 238 site preview performance", () => {
  test("demo workspace starts clean unless seeded data is explicitly requested", async ({ page }) => {
    const failures = await collectFailures(page);
    await page.goto("/demo/workspace?debugPreview=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Pinecrest Mixed-Use Demo Site")).toHaveCount(0);
    await expect(page.getByText("Pinecrest Mixed-Use")).toHaveCount(0);
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
    await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
    await expect(page.getByLabel("Type project address")).toBeVisible();
    await page.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");
    await page.getByRole("button", { name: /apply address/i }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(
      /Address saved locally|Live geocode and source lookup need sign-in|Online geocode\/source lookup/i,
    );
    expect(failures.pageErrors).toEqual([]);
    expect(failures.consoleErrors).toEqual([]);
  });

  test("new project preview switches modes without loading map unless requested", async ({ page }) => {
    const failures = await collectFailures(page);
    await openNewProject(page);
    await createBlankSite(page);
    await expectNoHorizontalOverflow(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    await setPreviewQuality(page, "standard");
    await expect(canvas).toContainText(/Local site coordinates/i);
    const coordinateReadout = canvas.getByTestId("canvas-coordinate-readout");
    await expect(coordinateReadout).toContainText("SITE 1000 ft x 1000 ft");
    await expect(coordinateReadout.getByTestId("canvas-scale-source")).toContainText("LOCAL SITE SCALE");
    const zoomBeforeText = await coordinateReadout.textContent();
    const zoomBefore = Number(zoomBeforeText?.match(/ZOOM\s+(\d+)%/)?.[1] ?? NaN);
    expect(Number.isFinite(zoomBefore)).toBeTruthy();

    const surface = canvas.getByTestId("preview-drawing-surface");
    const surfaceBox = await surface.boundingBox();
    expect(surfaceBox).not.toBeNull();
    await page.mouse.move(surfaceBox!.x + surfaceBox!.width / 2, surfaceBox!.y + surfaceBox!.height / 2);
    await page.mouse.wheel(0, -360);
    await expect
      .poll(async () => {
        const text = await coordinateReadout.textContent();
        return Number(text?.match(/ZOOM\s+(\d+)%/)?.[1] ?? NaN);
      })
      .toBeGreaterThan(zoomBefore);
    await expect(coordinateReadout).toContainText("SITE 1000 ft x 1000 ft");

    await timed("high quality from new project", async () => {
      await setPreviewQuality(page, "high");
      await expect(canvas.getByTestId("preview-quality-high")).toHaveAttribute("aria-pressed", "true", { timeout: 2_500 });
    });
    await expect(page.evaluate(() => (window as unknown as { __civoraShowMap?: boolean }).__civoraShowMap)).resolves.toBeFalsy();

    await timed("3d from new project", async () => {
      await canvas.getByTestId("preview-mode-3d").first().click();
      await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 6_000 });
    }, 6_000);

    await timed("back to 2d from new project", async () => {
      await canvas.getByTestId("preview-mode-2d").first().click();
      await expect(canvas.getByTestId("preview-mode-2d").first()).toBeVisible({ timeout: 2_500 });
    });

    expect(failures.pageErrors).toEqual([]);
    expect(failures.consoleErrors).toEqual([]);
    expect(failures.failedRequests).toEqual([]);
  });
});
