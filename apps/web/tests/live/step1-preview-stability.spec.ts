import { expect, test } from "@playwright/test";

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const apiBase = process.env.PLAYWRIGHT_API_BASE_URL || "https://api.civoraai.com";
const tokenKey = "civora-ai-token";

test("step 1.1 preview stability flow", async ({ page, request, baseURL }) => {
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required.");

  const login = await request.post(`${apiBase.replace(/\/+$/, "")}/api/auth/login`, {
    data: { email, password },
  });
  expect(login.ok()).toBeTruthy();
  const loginPayload = (await login.json()) as { token?: string };
  expect(loginPayload.token).toBeTruthy();

  await page.context().addInitScript(
    ([key, token]) => window.localStorage.setItem(key, token),
    [tokenKey, loginPayload.token ?? ""] as const,
  );
  await page.goto(`${baseURL}/?debugPreview=1`, { waitUntil: "domcontentloaded" });

  await expect(page.getByText("Preview Workspace")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: "Site", exact: true }).click();
  const addressInput = page.getByPlaceholder("123 Main St, City, State");
  await addressInput.fill("20525 Margo St, Gretna, NE");
  await page.getByText("20525 Margo", { exact: false }).first().click({ timeout: 15_000 }).catch(() => null);
  await page.getByRole("button", { name: /apply address/i }).click();

  await expect(page.getByText("mapLoaded: true")).toBeVisible({ timeout: 35_000 });
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 20_000 });

  for (let index = 0; index < 10; index += 1) {
    await page.getByRole("button", { name: "Standard" }).click();
    await expect(page.getByText("quality: standard")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "High" }).click();
    await expect(page.getByText("quality: high")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("mapLoaded: true")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 10_000 });
  }

  const fullscreenTitle = page.locator("p").filter({ hasText: "Fullscreen Preview" });
  await page.getByRole("button", { name: /fullscreen preview/i }).click();
  await expect(fullscreenTitle).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 15_000 });
  await page.locator("main").getByRole("button", { name: "Close" }).click();
  await expect(fullscreenTitle).toBeHidden({ timeout: 10_000 });
  await page.getByRole("button", { name: /fullscreen preview/i }).click();
  await expect(fullscreenTitle).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 15_000 });
  await page.locator("main").getByRole("button", { name: "Close" }).click();

  await page.getByRole("button", { name: "Lock Site Apply" }).click();
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 20_000 });
  await expect(page.getByTestId("grading-readiness")).toContainText("Ready", { timeout: 20_000 });

  await page.getByRole("button", { name: /detect grading/i }).click();
  await expect(page.getByTestId("grading-result")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("grading-source-quality")).toContainText("terrain", { timeout: 10_000 });
  await expect(page.getByTestId("grading-source-detail")).toContainText("Mapbox Terrain-RGB", { timeout: 10_000 });
});
