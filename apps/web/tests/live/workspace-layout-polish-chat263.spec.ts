import { expect, test, type Page } from "@playwright/test";

type Rect = { left: number; right: number; top: number; bottom: number; width: number; height: number };

type ShellMetrics = {
  viewport: { width: number; height: number };
  pageOverflowX: number;
  header: Rect | null;
  rail: Rect | null;
  canvas: Rect | null;
  panel: Rect | null;
  controls: Rect | null;
  siteStatus: Rect | null;
  drawingSurface: Rect | null;
  commandBar: Rect | null;
  panelOverflowX: number;
  railOverflowX: number;
  panelState: { motion: string | null; commandBar: string | null; mobileNavigation: string | null; transform: string } | null;
};

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
}

async function openRailPanel(page: Page, name: "Setup" | "Draw" | "Generate" | "Deliver") {
  const button = page.getByTestId("left-sidebar").getByRole("button", { name, exact: true });
  await expect(button).toHaveCount(1);
  await button.click();
  await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
  return button;
}

async function readShellMetrics(page: Page): Promise<ShellMetrics> {
  return page.evaluate(() => {
    const rectFor = (selector: string) => {
      const element = document.querySelector<HTMLElement>(selector);
      if (!element) return null;
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") return null;
      const rect = element.getBoundingClientRect();
      return {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
      };
    };
    const panel = document.querySelector<HTMLElement>('[data-testid="workspace-right-panel"]');
    const rail = document.querySelector<HTMLElement>('[data-testid="left-sidebar"]');
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      pageOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      header: rectFor("header"),
      rail: rectFor('[data-testid="left-sidebar"]'),
      canvas: rectFor('[data-testid="workspace-canvas-frame"]'),
      panel: rectFor('[data-testid="workspace-right-panel"]'),
      controls: rectFor(".civora-preview-view-toolbar"),
      siteStatus: rectFor('[data-testid="site-status"]'),
      drawingSurface: rectFor('[aria-label="Drawing surface"]'),
      commandBar: rectFor('[data-testid="floating-command-bar"]'),
      panelOverflowX: panel ? panel.scrollWidth - panel.clientWidth : 0,
      railOverflowX: rail ? rail.scrollWidth - rail.clientWidth : 0,
      panelState: panel
        ? {
            motion: panel.getAttribute("data-motion-state"),
            commandBar: panel.getAttribute("data-command-bar-visible"),
            mobileNavigation: panel.getAttribute("data-mobile-navigation-visible"),
            transform: window.getComputedStyle(panel).transform,
          }
        : null,
    };
  });
}

function expectContained(inner: Rect | null, outer: Rect | null) {
  expect(inner).not.toBeNull();
  expect(outer).not.toBeNull();
  if (!inner || !outer) return;
  expect(inner.left).toBeGreaterThanOrEqual(outer.left - 1);
  expect(inner.right).toBeLessThanOrEqual(outer.right + 1);
  expect(inner.top).toBeGreaterThanOrEqual(outer.top - 1);
  expect(inner.bottom).toBeLessThanOrEqual(outer.bottom + 1);
}

test.describe("Chat 263 workspace visual geometry", () => {
  test("desktop panels overlay the fixed canvas without covering its active controls", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openDemoWorkspace(page);

    const initial = await readShellMetrics(page);
    expect(initial.pageOverflowX).toBeLessThanOrEqual(1);
    expect(initial.panel).toBeNull();
    expect(initial.header?.bottom).toBeLessThanOrEqual((initial.canvas?.top ?? 0) + 65);
    expect(initial.rail?.right).toBeLessThanOrEqual((initial.canvas?.left ?? 0) + 1);
    expectContained(initial.controls, initial.canvas);
    expectContained(initial.siteStatus, initial.controls);

    for (const panelName of ["Setup", "Draw", "Generate", "Deliver"] as const) {
      const railButton = await openRailPanel(page, panelName);
      const metrics = await readShellMetrics(page);
      expect(metrics.pageOverflowX).toBeLessThanOrEqual(1);
      expect(metrics.panelOverflowX).toBeLessThanOrEqual(1);
      expect(metrics.header?.bottom).toBeLessThanOrEqual((metrics.panel?.top ?? 0) + 1);
      expect(metrics.canvas?.right).toBeGreaterThan(metrics.panel?.left ?? 0);
      expect(metrics.canvas?.right).toBeLessThanOrEqual(metrics.viewport.width + 1);
      expect(metrics.controls?.right).toBeLessThanOrEqual((metrics.panel?.left ?? 0) - 8);
      expectContained(metrics.controls, metrics.canvas);
      expectContained(metrics.siteStatus, metrics.controls);
      expect(await railButton.getAttribute("aria-current")).toBe("page");
    }

    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await expect(page.getByTestId("floating-command-bar")).toBeVisible();
    const withCommand = await readShellMetrics(page);
    expect(withCommand.commandBar?.right).toBeLessThanOrEqual((withCommand.panel?.left ?? 0) - 8);
    expect(withCommand.commandBar?.left).toBeGreaterThanOrEqual((withCommand.canvas?.left ?? 0) + 8);
  });

  test("constrained desktop keeps the fixed canvas controls clear of every primary drawer", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await openDemoWorkspace(page);

    for (const panelName of ["Setup", "Draw", "Generate", "Deliver"] as const) {
      await openRailPanel(page, panelName);
      const metrics = await readShellMetrics(page);
      expect(metrics.pageOverflowX).toBeLessThanOrEqual(1);
      expect(metrics.canvas?.width).toBeGreaterThanOrEqual(panelName === "Deliver" ? 300 : 500);
      expect(metrics.drawingSurface?.height).toBeGreaterThanOrEqual(220);
      expect(metrics.canvas?.right).toBeGreaterThan(metrics.panel?.left ?? 0);
      expect(metrics.controls?.right).toBeLessThanOrEqual((metrics.panel?.left ?? 0) - 8);
      expectContained(metrics.controls, metrics.canvas);
    }
  });

  test("mobile drawer, navigation, and canvas never cover one another", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDemoWorkspace(page);

    for (const panelName of ["Setup", "Draw", "Generate", "Deliver"] as const) {
      await openRailPanel(page, panelName);
      const metrics = await readShellMetrics(page);
      expect(metrics.pageOverflowX).toBeLessThanOrEqual(1);
      expect(metrics.panelOverflowX).toBeLessThanOrEqual(1);
      expect(metrics.railOverflowX).toBeLessThanOrEqual(1);
      expect(metrics.header?.bottom).toBeLessThanOrEqual((metrics.panel?.top ?? 0) + 1);
      expect(
        metrics.panel?.bottom,
        `${panelName} drawer state: ${JSON.stringify(metrics.panelState)}`,
      ).toBeLessThanOrEqual((metrics.rail?.top ?? 0) - 8);
    }

    const minimize = page.getByTestId("workspace-right-panel").getByRole("button", { name: "Minimize", exact: true });
    await expect(minimize).toHaveCount(1);
    await minimize.click();
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
    const canvasOnly = await readShellMetrics(page);
    expect(canvasOnly.canvas?.bottom).toBeLessThanOrEqual((canvasOnly.rail?.top ?? 0) - 1);
    expect(canvasOnly.pageOverflowX).toBeLessThanOrEqual(1);
  });
});
