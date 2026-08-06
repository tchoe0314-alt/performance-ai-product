import { expect, test } from "@playwright/test";

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";
const apiBase = (
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://api.civoraai.com"
).replace(/\/+$/, "");

test("phase 2 site setup workflow", async ({ page, request, baseURL }) => {
  test.setTimeout(180_000);
  test.skip(!baseURL, "PLAYWRIGHT_BASE_URL is required.");
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required.");

  const loginResponse = await request.post(`${apiBase}/api/auth/login`, {
    data: { email, password },
  });
  expect(loginResponse.status(), "login should succeed before the setup flow").toBe(200);
  const loginPayload = (await loginResponse.json()) as { token?: string };
  const token = String(loginPayload.token || "");
  expect(token).toBeTruthy();

  await page.addInitScript(
    ([tokenKey, restoreKey, value]) => {
      window.localStorage.setItem(tokenKey, value);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, token] as const,
  );

  await page.goto(`/?debugPreview=1&seedDemo=0&scenario=phase2-${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("header-projects-button").click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible();
  await page.getByRole("button", { name: /New Project/i }).filter({ visible: true }).first().click();

  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Address \/ Location|Site Boundary/i);

  const addressSection = page.getByTestId("setup-address-truth");
  if (!(await addressSection.evaluate((node) => node.hasAttribute("open")))) {
    await addressSection.locator("summary").click();
  }
  await addressSection.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");

  const siteSection = page.getByTestId("setup-site-box-controls");
  if (!(await siteSection.evaluate((node) => node.hasAttribute("open")))) {
    await siteSection.locator("summary").click();
  }
  await page.getByLabel("Site width in feet").fill("1000");
  await page.getByLabel("Site depth in feet").fill("1000");
  await addressSection.getByTestId("create-centered-site-button").click();

  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 60_000 });
  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
  const refreshedAddressSection = page.getByTestId("setup-address-truth");
  const refreshedSiteSection = page.getByTestId("setup-site-box-controls");
  await expect(refreshedSiteSection).toContainText("1000 ft x 1000 ft");
  await expect(refreshedAddressSection).toContainText(/Applied|Local/i);

  await refreshedSiteSection.getByRole("button", { name: "Change Boundary" }).click();
  await expect(page.getByTestId("site-status")).toContainText("Site Open");
  await refreshedSiteSection.getByRole("button", { name: "Lock Boundary" }).click();
  await expect(page.getByTestId("site-status")).toContainText("Site Locked");

  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
  const surveySection = page.getByTestId("setup-survey-terrain-card");
  await expect(surveySection).toBeVisible({ timeout: 15_000 });
  if (!(await surveySection.evaluate((node) => node.hasAttribute("open")))) {
    await surveySection.locator("summary").first().click();
  }
  await surveySection.locator('input[accept="image/*"]').setInputFiles({
    name: "phase2-site.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64",
    ),
  });
  await expect(page.getByTestId("image-upload-status")).toContainText(
    /Uploading image|Detecting site features|Detection complete|No detections found|Image uploaded|Detection failed/i,
    { timeout: 60_000 },
  );

  await page.getByRole("button", { name: /^Generate$/ }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("generate-main-action")).toBeVisible();
  await page.getByTestId("generate-main-action").click();
  await expect(page.getByTestId("generate-flow-summary")).toContainText(
    /Ran:|Needs input|Started|review|queued/i,
    { timeout: 60_000 },
  );
});
