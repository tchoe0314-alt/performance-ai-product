import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

import { setPreviewQuality } from "./testUiHelpers";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

async function collectPageFailures(page: Page) {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  return { pageErrors, consoleErrors };
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

async function measureVisible(
  page: Page,
  label: string,
  action: () => Promise<void>,
  visible: Locator,
  thresholdMs = 3_000,
) {
  const startedAt = Date.now();
  await action();
  await expect(visible).toBeVisible({ timeout: thresholdMs });
  const durationMs = Date.now() - startedAt;
  console.info(`[chat222b-timing] ${label}: ${durationMs}ms`);
  expect(durationMs).toBeLessThanOrEqual(thresholdMs);
  return durationMs;
}

async function openDemoWorkspace(page: Page) {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.route("**/api/plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        final_plan: {
          actions: [],
          meta: {
            grading: { export_validation: { ready: false, reasons: ["review_only_assumption"] } },
            convergence_summary: { blocked_exports: [], blocked_reasons: [] },
          },
        },
        explanation: { summary: "Generated review draft." },
      }),
    });
  });
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await expect.poll(() => page.locator("[data-object-overlay]").count(), { timeout: 30_000 }).toBeGreaterThan(0);
}

async function openWorkspacePanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 5_000 });
}

async function mockProjectsBackend(page: Page) {
  const project = {
    project_id: "chat222b-project",
    name: "Responsive Project",
    description: "Timing fixture",
    updated_at: Math.floor(Date.now() / 1000),
    has_result: false,
    project_input: {
      full_design_mode: true,
      input_mode: "user",
      manual_fields: {
        project_name: "Responsive Project",
        lot: { w: 800, h: 520 },
        building: { w: 120, d: 80, count: 1 },
        parking: { count: 24 },
        setback: 25,
      },
      meta: { site_inputs: {} },
    },
    latest_result: null,
  };
  const store = new Map([[project.project_id, project]]);

  await page.addInitScript(
    ([tokenKey, restoreKey, token]) => {
      window.localStorage.setItem(tokenKey, token);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, "chat222b-token"] as const,
  );
  await page.route("**/api/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.route("**/api/auth/status", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user: { user_id: "chat222b", email: "chat222b@example.com", name: "Chat 222B" } }),
    });
  });
  await page.route("**/api/jobs**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [] }) });
  });
  await page.route("**/api/projects**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const detailMatch = url.pathname.match(/^\/api\/projects\/([^/]+)$/);
    if (url.pathname === "/api/projects" && request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, projects: Array.from(store.values()) }),
      });
      return;
    }
    if (url.pathname === "/api/projects" && request.method() === "POST") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, project }) });
      return;
    }
    if (detailMatch && request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, project: store.get(detailMatch[1]) ?? project }),
      });
      return;
    }
    if (detailMatch && request.method() === "DELETE") {
      store.delete(detailMatch[1]);
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, latest_result: {} }) });
  });
}

test.describe("Chat 222B performance and responsiveness", () => {
  test("workspace controls respond without overflow or browser errors", async ({ page }) => {
    const failures = await collectPageFailures(page);
    await openDemoWorkspace(page);
    await expectNoHorizontalOverflow(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    await measureVisible(
      page,
      "panel open generate",
      () => openWorkspacePanel(page, "Generate", /Generate project systems/i),
      page.getByTestId("generate-main-action"),
    );
    await measureVisible(
      page,
      "generate response visible",
      () => page.getByTestId("generate-main-action").click(),
      page.getByTestId("generate-flow-summary"),
      5_000,
    );
    await measureVisible(
      page,
      "panel open deliver",
      () => openWorkspacePanel(page, /^Deliver$/, /Review package/i),
      page.getByTestId("deliver-review-package-flow"),
    );
    const closeStartedAt = Date.now();
    await page.getByTestId("workspace-right-panel").getByRole("button", { name: "Minimize" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0, { timeout: 3_000 });
    console.info(`[chat222b-timing] panel close: ${Date.now() - closeStartedAt}ms`);
    const hideSidebar = page.getByRole("button", { name: "Hide left sidebar" });
    if (await hideSidebar.isVisible().catch(() => false)) {
      await hideSidebar.click();
      await expect(page.getByRole("button", { name: "Show left sidebar" })).toBeVisible({ timeout: 3_000 });
    }

    const backgroundRefreshesBeforeQuality = await page.evaluate(() => {
      const perf = (window as typeof window & { __civoraPerf?: { entries?: Array<{ label: string }> } }).__civoraPerf;
      return perf?.entries?.filter((entry) => entry.label === "preview.background_refresh.debounced").length ?? 0;
    });
    await measureVisible(
      page,
      "quality high visible",
      () => setPreviewQuality(page, "high"),
      canvas.getByTestId("preview-quality-high"),
    );
    await expect(page.getByTestId("high-quality-preview-only-label")).toContainText("Visual preview only");
    await measureVisible(
      page,
      "quality standard visible",
      () => setPreviewQuality(page, "standard"),
      canvas.getByTestId("preview-quality-standard"),
    );
    await expect.poll(async () => {
      const perf = await page.evaluate(() => {
        const store = (window as typeof window & { __civoraPerf?: { entries?: Array<{ label: string }> } }).__civoraPerf;
        return store?.entries?.filter((entry) => entry.label === "preview.background_refresh.debounced").length ?? 0;
      });
      return perf;
    }, { timeout: 1_000 }).toBe(backgroundRefreshesBeforeQuality);
    const mode3DStartedAt = Date.now();
    await canvas.getByTestId("preview-mode-3d").click();
    const mode3DFeedback = page
      .getByTestId("civil-3d-viewer-loading")
      .or(page.getByTestId("civil-3d-viewer"));
    await expect(mode3DFeedback).toBeVisible({ timeout: 750 });
    const mode3DFeedbackMs = Date.now() - mode3DStartedAt;
    console.info(`[chat222b-timing] mode 3d feedback: ${mode3DFeedbackMs}ms`);
    expect(mode3DFeedbackMs).toBeLessThanOrEqual(750);
    await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId("civil-3d-canvas-mount").locator("canvas")).toBeVisible({ timeout: 1_000 });
    const mode3DReadyMs = Date.now() - mode3DStartedAt;
    console.info(`[chat222b-timing] mode 3d ready: ${mode3DReadyMs}ms`);
    expect(mode3DReadyMs).toBeLessThanOrEqual(5_000);
    await measureVisible(
      page,
      "mode 2d visible",
      () => canvas.getByTestId("preview-mode-2d").click(),
      page.locator("[data-object-overlay]").first(),
      5_000,
    );
    await measureVisible(
      page,
      "mode 3d warm visible",
      () => canvas.getByTestId("preview-mode-3d").click(),
      page.getByTestId("civil-3d-canvas-mount").locator("canvas"),
      2_000,
    );
    await measureVisible(
      page,
      "mode 2d warm visible",
      () => canvas.getByTestId("preview-mode-2d").click(),
      page.locator("[data-object-overlay]").first(),
      2_000,
    );
    await measureVisible(
      page,
      "draw controls clickable",
      async () => {
        await canvas.getByTestId("preview-interaction-edit").click();
        await page.keyboard.press("D");
      },
      page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-line"),
    );
    await expect(page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-line")).toBeEnabled();
    await page.getByTestId("draw-cad-tools-section").getByTestId("cad-tool-pan").click();
    const drawingSurface = page.getByTestId("preview-drawing-surface");
    await expect(drawingSurface).toHaveAttribute("data-draw-mode", "pan");
    const mapCanvas = page.locator(".mapboxgl-canvas").filter({ visible: true });
    const mapPanActive = (await mapCanvas.count()) > 0;
    await expect(drawingSurface).toHaveCSS("pointer-events", mapPanActive ? "none" : "auto");
    const panSurface = mapPanActive ? mapCanvas.first() : drawingSurface;
    const drawingSurfaceBox = await panSurface.boundingBox();
    expect(drawingSurfaceBox).toBeTruthy();
    const beforeMapViewport = mapPanActive
      ? await page.evaluate(() => {
          const value = (window as unknown as Record<string, unknown>).__civoraMapViewport;
          return value as { lat: number; lng: number } | null;
        })
      : null;
    if (drawingSurfaceBox) {
      const viewport = page.viewportSize();
      expect(viewport).toBeTruthy();
      const visibleLeft = Math.max(drawingSurfaceBox.x, 0);
      const visibleTop = Math.max(drawingSurfaceBox.y, 0);
      const visibleRight = Math.min(drawingSurfaceBox.x + drawingSurfaceBox.width, viewport?.width ?? Infinity);
      const visibleBottom = Math.min(drawingSurfaceBox.y + drawingSurfaceBox.height, viewport?.height ?? Infinity);
      expect(visibleRight - visibleLeft).toBeGreaterThan(100);
      expect(visibleBottom - visibleTop).toBeGreaterThan(100);
      const dragStart = {
        x: visibleLeft + (visibleRight - visibleLeft) * 0.52,
        y: visibleTop + (visibleBottom - visibleTop) * 0.52,
      };
      const hitTarget = await page.evaluate(({ x, y }) => {
        const element = document.elementFromPoint(x, y) as HTMLElement | null;
        return {
          testId: element?.closest<HTMLElement>("[data-testid]")?.dataset.testid ?? null,
          mapCanvas: Boolean(element?.closest(".mapboxgl-canvas")),
        };
      }, dragStart);
      if (mapPanActive) expect(hitTarget.mapCanvas).toBe(true);
      else expect(["preview-drawing-surface", "preview-drawing-overlays"]).toContain(hitTarget.testId);
      await page.mouse.move(dragStart.x, dragStart.y);
      await page.mouse.down();
      await page.mouse.move(
        Math.min(dragStart.x + Math.min(drawingSurfaceBox.width * 0.1, 100), visibleRight - 10),
        Math.min(dragStart.y + Math.min(drawingSurfaceBox.height * 0.06, 50), visibleBottom - 10),
        { steps: 12 },
      );
      await page.mouse.up();
    }
    if (mapPanActive) {
      expect(beforeMapViewport).not.toBeNull();
      await expect.poll(async () => {
        const viewport = await page.evaluate(() => {
          const value = (window as unknown as Record<string, unknown>).__civoraMapViewport;
          return value as { lat: number; lng: number } | null;
        });
        if (!viewport || !beforeMapViewport) return 0;
        return Math.hypot(viewport.lat - beforeMapViewport.lat, viewport.lng - beforeMapViewport.lng);
      }).toBeGreaterThan(0.000001);
    } else {
      await expect.poll(
        async () =>
          page.evaluate(() => {
            const perf = (window as typeof window & { __civoraPerf?: { last?: Record<string, { durationMs: number }> } }).__civoraPerf;
            return perf?.last?.["preview.pan.drag"]?.durationMs ?? null;
          }),
        { timeout: 3_000 },
      ).not.toBeNull();
    }

    await expectNoHorizontalOverflow(page);
    expect(failures.pageErrors).toEqual([]);
    expect(failures.consoleErrors).toEqual([]);
  });

  test("projects drawer opens, restores, creates, and deletes responsively", async ({ page }) => {
    const failures = await collectPageFailures(page);
    await mockProjectsBackend(page);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

    await measureVisible(
      page,
      "projects drawer open",
      () => page.getByTestId("header-projects-button").click(),
      page.getByTestId("projects-drawer"),
    );
    await measureVisible(
      page,
      "projects open saved project",
      () => page.getByRole("button", { name: "Open project Responsive Project" }).click(),
      page.getByTestId("project-drawer-state").filter({ hasText: "Saved" }),
      5_000,
    );
    await measureVisible(
      page,
      "projects new project",
      async () => {
        await page.getByRole("button", { name: "New Project" }).first().click();
        await page.getByTestId("header-projects-button").click();
      },
      page.getByTestId("project-drawer-state").filter({ hasText: "Unsaved draft" }),
      5_000,
    );
    page.once("dialog", async (dialog) => {
      await dialog.accept();
    });
    await page.getByTestId("header-projects-button").click();
    await measureVisible(
      page,
      "projects delete project",
      () => page.getByRole("button", { name: "Delete project Responsive Project" }).click({ force: true }),
      page.getByTestId("project-drawer-detail").filter({ hasText: "Project deleted." }),
      5_000,
    );

    await expectNoHorizontalOverflow(page);
    expect(failures.pageErrors).toEqual([]);
    expect(failures.consoleErrors).toEqual([]);
  });
});
