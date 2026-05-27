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

  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Site & Existing" }).click();
  await page.getByRole("button", { name: "Edit site data" }).click();
  const addressInput = page.getByPlaceholder("123 Main St, City, State");
  await addressInput.fill("20525 Margo St, Gretna, NE");
  await page.getByText("20525 Margo", { exact: false }).first().click({ timeout: 15_000 }).catch(() => null);
  await page.getByRole("button", { name: /apply address/i }).click();

  await expect(page.getByText("mapLoaded: true")).toBeVisible({ timeout: 35_000 });
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 20_000 });

  await page.getByRole("button", { name: "Site & Existing" }).click();
  await page.getByRole("button", { name: "Edit site data" }).click();
  await page.getByRole("button", { name: "Lock Site" }).click();
  await expect(page.getByRole("button", { name: "Change Site" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Change Site" }).click();
  await expect(page.getByRole("button", { name: "Lock Site" })).toBeVisible({ timeout: 20_000 });

  await page.getByRole("button", { name: "Design" }).click();
  for (let index = 0; index < 10; index += 1) {
    await page.getByRole("button", { name: /^standard$/i }).nth(0).click();
    await expect(page.getByText("quality: standard")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: /^high$/i }).nth(0).click();
    await expect(page.getByText("quality: high")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("mapLoaded: true")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 10_000 });
  }

  const fullscreenTitle = page.locator("p").filter({ hasText: "Fullscreen Preview" });
  await page.getByRole("button", { name: "Fullscreen" }).click();
  await expect(fullscreenTitle).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 15_000 });
  await page.locator("main").getByRole("button", { name: "Close" }).click();
  await expect(fullscreenTitle).toBeHidden({ timeout: 10_000 });
  await page.getByRole("button", { name: "Fullscreen" }).click();
  await expect(fullscreenTitle).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 15_000 });
  await page.locator("main").getByRole("button", { name: "Close" }).click();

  await page.goto(`${baseURL}/?demo=workspace&debugPreview=1`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Site & Existing" }).click();
  await page.getByRole("button", { name: "Edit site data" }).click();
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 20_000 });
  await page.getByRole("button", { name: /detect grading/i }).click();
  await expect(page.getByTestId("grading-result")).toHaveCount(1, { timeout: 45_000 });
  await expect(page.getByTestId("grading-source-quality")).toContainText("terrain", { timeout: 10_000 });
  await expect(page.getByTestId("grading-source-detail")).toContainText("Mapbox Terrain-RGB", { timeout: 10_000 });
  await expect(page.getByTestId("grading-sample-count")).toContainText("sample_count =");
  await expect(page.getByTestId("grading-missing-count")).toContainText("missing_count =");
  await expect(page.getByTestId("grading-high-points")).toContainText("high_points =");
  await expect(page.getByTestId("grading-low-points")).toContainText("low_points =");
  await expect(page.getByTestId("grading-slope-summary")).toContainText("slope summary =");
});
