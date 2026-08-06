import { expect, test } from "@playwright/test";

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const apiBase = (process.env.PLAYWRIGHT_API_BASE_URL || "https://api.civoraai.com").replace(/\/+$/, "");
const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

test("step 1.1 preview stability flow", async ({ page, request, baseURL }) => {
  test.setTimeout(180_000);
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required.");

  const login = await request.post(`${apiBase}/api/auth/login`, {
    data: { email, password },
  });
  expect(login.status(), "login should succeed before preview stability checks").toBe(200);
  const loginPayload = (await login.json()) as { token?: string };
  const token = String(loginPayload.token || "");
  expect(token).toBeTruthy();

  await page.addInitScript(
    ([tokenKey, restoreKey, value]) => {
      window.localStorage.setItem(tokenKey, value);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, token] as const,
  );
  await page.goto(`${baseURL}/?debugPreview=1&seedDemo=0&scenario=preview-stability-${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: /New Project/i }).filter({ visible: true }).first().click();
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();

  const addressSection = page.getByTestId("setup-address-truth");
  if (!(await addressSection.evaluate((node) => node.hasAttribute("open")))) {
    await addressSection.locator("summary").click();
  }
  await addressSection.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");
  const siteSection = page.getByTestId("setup-site-box-controls");
  if (!(await siteSection.evaluate((node) => node.hasAttribute("open")))) {
    await siteSection.locator("summary").click();
  }
  await page.getByTestId("use-1000-site-size").click();
  await addressSection.getByTestId("create-centered-site-button").click();
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 60_000 });

  const canvas = page.getByTestId("workspace-canvas-shell");
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 20_000 });
  await expect(page.locator(".mapboxgl-canvas")).toBeVisible({ timeout: 45_000 });
  await expect(canvas.getByTestId("preview-inner-map-toggle")).toContainText("Map On");

  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
  const refreshedSiteSection = page.getByTestId("setup-site-box-controls");
  await refreshedSiteSection.getByRole("button", { name: "Change Boundary" }).click();
  await expect(page.getByTestId("site-status")).toContainText("Site Editable");
  await refreshedSiteSection.getByRole("button", { name: "Lock Boundary" }).click();
  await expect(page.getByTestId("site-status")).toContainText("Site Locked");
  await page.getByTestId("workspace-right-panel").getByRole("button", { name: "Minimize" }).click();

  for (let index = 0; index < 8; index += 1) {
    await canvas.getByTestId("preview-quality-standard").first().click();
    await expect(canvas).toContainText(/Draft \/ Standard/i);
    await canvas.getByTestId("preview-quality-high").first().click();
    await expect(canvas).toContainText(/Plan Sheet \/ High Quality/i);
    await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1);
    await expect(page.locator(".mapboxgl-canvas")).toBeVisible();
  }

  await canvas.getByTestId("preview-mode-3d").first().hover();
  await canvas.getByTestId("preview-mode-3d").first().click();
  await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Open Fullscreen" }).click();
  await expect(page.getByTestId("civil-3d-fullscreen")).toBeVisible();
  await expect(page.getByTestId("civil-3d-fullscreen").locator("canvas")).toBeVisible();
  await page.getByRole("button", { name: "Close Fullscreen" }).click();
  await expect(page.getByTestId("civil-3d-fullscreen")).toHaveCount(0);
  await canvas.getByTestId("preview-mode-2d").first().click();
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 20_000 });
  await expect(page.locator(".mapboxgl-canvas")).toBeVisible({ timeout: 20_000 });
  await expect(canvas.getByTestId("preview-inner-map-toggle")).toContainText("Map On");
});
