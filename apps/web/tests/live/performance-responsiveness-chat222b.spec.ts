import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";

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
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Detention Basin A", { timeout: 30_000 });
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
    ([tokenKey, token]) => window.localStorage.setItem(tokenKey, token),
    [TOKEN_KEY, "chat222b-token"] as const,
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
      () => openWorkspacePanel(page, "Generate", /Generate systems/i),
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

    await measureVisible(
      page,
      "quality high visible",
      () => canvas.getByTestId("preview-quality-high").click(),
      canvas.getByTestId("preview-quality-high"),
    );
    await expect(page.getByTestId("high-quality-preview-only-label")).toContainText("Visual preview only");
    await measureVisible(
      page,
      "quality standard visible",
      () => canvas.getByTestId("preview-quality-standard").click(),
      canvas.getByTestId("preview-quality-standard"),
    );
    await measureVisible(
      page,
      "mode 3d visible",
      () => canvas.getByTestId("preview-mode-3d").click(),
      page.getByTestId("civil-3d-viewer"),
      8_000,
    );
    await measureVisible(
      page,
      "mode 2d visible",
      () => canvas.getByTestId("preview-mode-2d").click(),
      page.locator("[data-object-overlay]").first(),
      5_000,
    );
    await measureVisible(
      page,
      "draw controls clickable",
      () => canvas.getByTestId("preview-interaction-edit").click(),
      canvas.getByRole("button", { name: "Add Line" }),
    );
    await expect(canvas.getByRole("button", { name: "Add Line" })).toBeEnabled();

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
      () => page.getByRole("button", { name: "Open projects from header" }).click(),
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
        await page.getByRole("button", { name: "Open projects from header" }).click();
      },
      page.getByTestId("project-drawer-state").filter({ hasText: "Unsaved draft" }),
      5_000,
    );
    page.once("dialog", async (dialog) => {
      await dialog.accept();
    });
    await page.getByRole("button", { name: "Open projects from header" }).click();
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
