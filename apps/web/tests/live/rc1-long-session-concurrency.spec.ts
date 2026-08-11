import { expect, test, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";
import { setPreviewQuality } from "./testUiHelpers";


const isHosted = Boolean(process.env.PLAYWRIGHT_BASE_URL && !/localhost|127\.0\.0\.1/.test(process.env.PLAYWRIGHT_BASE_URL));
const backendBase = isHosted
  ? process.env.PLAYWRIGHT_API_BASE_URL || "https://api.civoraai.com"
  : process.env.PLAYWRIGHT_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:8002";

async function registerUser(request: APIRequestContext, label: string) {
  const email = `rc1-${label}-${Date.now()}-${Math.random().toString(16).slice(2)}@example.test`;
  const response = await request.post(`${backendBase}/api/auth/register`, {
    data: { email, password: "rc1-password-123", name: `RC1 ${label}` },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as { token: string; user: { user_id: string; email: string } };
}

async function saveProject(request: APIRequestContext, token: string, name: string, marker: number, projectId?: string) {
  const response = await request.post(`${backendBase}/api/projects`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      project_id: projectId || null,
      name,
      project_input: {
        address: `${marker} RC1 Reliability Way`,
        meta: { site_inputs: { lot_width: 1000 + marker, lot_height: 1000, marker } },
      },
      metadata: { rc1_concurrency_marker: marker },
    },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()).project as { project_id: string; name: string; project_input: Record<string, unknown> };
}

async function openAuthenticatedWorkspace(context: BrowserContext, token: string) {
  await context.addInitScript((authToken) => {
    window.localStorage.setItem("civora-ai-token", authToken);
    window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  const page = await context.newPage();
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  return { page, consoleErrors, pageErrors };
}

async function openPanel(page: Page, name: RegExp | string) {
  const showSidebar = page.getByRole("button", { name: "Show left sidebar" });
  if (await showSidebar.isVisible().catch(() => false)) await showSidebar.click();
  await page.getByRole("button", { name }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
}

test.describe("RC1 long-session and concurrent-user stability", () => {
  test.skip(isHosted, "Hosted registration is intentionally controlled; hosted concurrency uses the dedicated authenticated gauntlet.");

  test("isolates two users during concurrent project writes and reads", async ({ request }) => {
    const [first, second] = await Promise.all([registerUser(request, "alpha"), registerUser(request, "beta")]);
    const [firstProject, secondProject] = await Promise.all([
      saveProject(request, first.token, "Alpha site", 1),
      saveProject(request, second.token, "Beta site", 2),
    ]);

    await Promise.all(
      Array.from({ length: 40 }, async (_, index) => {
        const owner = index % 2 === 0 ? first : second;
        const project = index % 2 === 0 ? firstProject : secondProject;
        const response = await request.post(`${backendBase}/api/projects`, {
          headers: { Authorization: `Bearer ${owner.token}` },
          data: {
            project_id: project.project_id,
            name: index % 2 === 0 ? "Alpha site" : "Beta site",
            project_input: { meta: { site_inputs: { marker: index, lot_width: 1000 + index } } },
            metadata: { concurrent_iteration: index },
          },
        });
        expect(response.status(), await response.text()).toBe(200);
      }),
    );

    const crossReads = await Promise.all([
      request.get(`${backendBase}/api/projects/${secondProject.project_id}`, {
        headers: { Authorization: `Bearer ${first.token}` },
      }),
      request.get(`${backendBase}/api/projects/${firstProject.project_id}`, {
        headers: { Authorization: `Bearer ${second.token}` },
      }),
    ]);
    expect(crossReads.map((response) => response.status())).toEqual([404, 404]);

    for (const [owner, expectedId] of [
      [first, firstProject.project_id],
      [second, secondProject.project_id],
    ] as const) {
      const response = await request.get(`${backendBase}/api/projects`, {
        headers: { Authorization: `Bearer ${owner.token}` },
      });
      expect(response.status()).toBe(200);
      const ids = ((await response.json()).projects as Array<{ project_id: string }>).map((item) => item.project_id);
      expect(ids).toEqual([expectedId]);
    }
  });

  test("stays responsive through a sustained two-window editing session", async ({ browser, request }) => {
    test.setTimeout(240_000);
    const first = await registerUser(request, "window-one");
    const second = await registerUser(request, "window-two");
    await saveProject(request, first.token, "Long session A", 10);
    await saveProject(request, second.token, "Long session B", 20);
    const contextA = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const contextB = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    try {
      const [sessionA, sessionB] = await Promise.all([
        openAuthenticatedWorkspace(contextA, first.token),
        openAuthenticatedWorkspace(contextB, second.token),
      ]);
      const heapBefore = await sessionA.page.evaluate(() => {
        const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
        return memory?.usedJSHeapSize || 0;
      });

      for (let iteration = 0; iteration < 24; iteration += 1) {
        const targetA = iteration % 4 === 0 ? /^Setup$/ : iteration % 4 === 1 ? /^Draw$/ : iteration % 4 === 2 ? /^Generate$/ : /^Deliver$/;
        const targetB = iteration % 3 === 0 ? /^Draw$/ : iteration % 3 === 1 ? /^Generate$/ : /^Setup$/;
        const started = Date.now();
        await Promise.all([openPanel(sessionA.page, targetA), openPanel(sessionB.page, targetB)]);
        expect(Date.now() - started).toBeLessThan(4000);
        await Promise.all([
          sessionA.page.getByRole("button", { name: "Minimize" }).click(),
          sessionB.page.getByRole("button", { name: "Minimize" }).click(),
        ]);
      }

      await sessionA.page.goto(`/demo/workspace?debugPreview=1&seedDemo=1&rc1LongSession=${Date.now()}`, {
        waitUntil: "domcontentloaded",
      });
      const canvasA = sessionA.page.getByTestId("workspace-canvas-shell");
      await expect(canvasA).toBeVisible({ timeout: 30_000 });
      await expect(canvasA.getByTestId("preview-mode-3d")).toBeEnabled();
      for (let iteration = 0; iteration < 6; iteration += 1) {
        await setPreviewQuality(sessionA.page, "high");
        await setPreviewQuality(sessionA.page, "standard");
        await canvasA.getByTestId("preview-mode-3d").click();
        await expect(canvasA.getByTestId("preview-mode-2d")).toBeVisible();
        await canvasA.getByTestId("preview-mode-2d").click();
      }

      const heapAfter = await sessionA.page.evaluate(() => {
        const memory = (performance as Performance & { memory?: { usedJSHeapSize: number } }).memory;
        return memory?.usedJSHeapSize || 0;
      });
      if (heapBefore && heapAfter) expect(heapAfter - heapBefore).toBeLessThan(160 * 1024 * 1024);
      for (const session of [sessionA, sessionB]) {
        expect(session.pageErrors).toEqual([]);
        expect(session.consoleErrors.filter((line) => !/favicon/i.test(line))).toEqual([]);
        const overflow = await session.page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(overflow).toBeLessThanOrEqual(1);
      }
    } finally {
      await Promise.all([contextA.close(), contextB.close()]);
    }
  });
});
