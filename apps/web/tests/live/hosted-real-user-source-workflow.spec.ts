import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";
import path from "node:path";

import { setPreviewQuality } from "./testUiHelpers";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";
const DEFAULT_APP_URL = "https://civoraai.com/?debugPreview=1&aiRealismProvider=mock";
const DEFAULT_API_URL = "https://api.civoraai.com";
const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const appUrl = process.env.PLAYWRIGHT_BASE_URL || DEFAULT_APP_URL;
const apiBaseUrl = (process.env.PLAYWRIGHT_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_URL).replace(/\/+$/, "");
const fixtureDir = path.resolve(__dirname, "../../../../backend/fixtures/real_input_benchmarks");

async function login(request: APIRequestContext) {
  const response = await request.post(`${apiBaseUrl}/api/auth/login`, {
    data: { email, password },
  });
  expect(response.status(), "hosted login should succeed").toBe(200);
  const payload = (await response.json()) as { token?: string };
  const token = String(payload.token || "");
  expect(token, "hosted login returned a bearer token").toBeTruthy();
  return token;
}

async function seedAuth(page: Page, token: string) {
  await page.addInitScript(
    ([tokenKey, restoreKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, token] as const,
  );
}

async function shot(page: Page, testInfo: TestInfo, name: string) {
  await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
}

async function openPanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 20_000 });
}

async function uploadSource(page: Page, filename: string, expected: RegExp) {
  await openPanel(page, /^Setup$/, /Address \/ Location|Site Boundary|Survey \/ Terrain/i);
  const surveySection = page.getByTestId("setup-survey-terrain-card");
  await expect(surveySection).toBeVisible({ timeout: 20_000 });
  if (!(await surveySection.evaluate((node) => node.hasAttribute("open")))) {
    await surveySection.locator("summary").first().click();
  }
  await page.locator('input[accept*=".las"]').first().setInputFiles(path.join(fixtureDir, filename));
  await expect(page.getByTestId("survey-upload-status").first()).toContainText(/imported|review/i, { timeout: 60_000 });
  await expect(page.getByTestId("source-effects-summary").filter({ visible: true }).first()).toContainText(expected, { timeout: 20_000 });
  await expect(page.getByTestId("source-effects-summary").filter({ visible: true }).first()).toContainText(/Does not replace survey control/i);
}

test("hosted real user can set up site, upload real sources, generate, and deliver review package", async ({ page, request }, testInfo) => {
  test.setTimeout(6 * 60_000);
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required for hosted real user source workflow proof.");

  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (requestInfo) => {
    failedRequests.push(`${requestInfo.method()} ${requestInfo.url()} ${requestInfo.failure()?.errorText || "request failed"}`);
  });

  const token = await login(request);
  await seedAuth(page, token);
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByTestId("header-projects-button").click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible();
  await page.getByRole("button", { name: /New Project/i }).filter({ visible: true }).first().click();
  await shot(page, testInfo, "01-new-project");

  await openPanel(page, /^Setup$/, /Address \/ Location|Site Boundary|Survey \/ Terrain/i);
  const addressSection = page.getByTestId("setup-address-truth");
  if (!(await addressSection.evaluate((node) => node.hasAttribute("open")))) {
    await addressSection.locator("summary").click();
  }
  await addressSection.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");
  const siteBox = page.getByTestId("setup-site-box-controls");
  if (!(await siteBox.evaluate((node) => node.hasAttribute("open")))) {
    await siteBox.locator("summary").click();
  }
  await page.getByLabel("Site width in feet").fill("1000");
  await page.getByLabel("Site depth in feet").fill("1000");
  await siteBox.getByTestId("create-centered-site-button").click();
  await expect(page.getByTestId("site-status")).toContainText(/Site Locked/i, { timeout: 30_000 });
  await shot(page, testInfo, "02-site-locked");

  await uploadSource(page, "surface_grid.tif", /GeoTIFF terrain|Terrain surface/i);
  await shot(page, testInfo, "03-geotiff-source-effects");
  await uploadSource(page, "surface_points.las", /LAS\/LiDAR point cloud|LiDAR \/ point-cloud terrain evidence/i);
  await shot(page, testInfo, "04-las-source-effects");
  await uploadSource(page, "surface_pipe.landxml", /LandXML exchange|Surface metadata|Pipe-network metadata/i);
  await shot(page, testInfo, "05-landxml-source-effects");

  await setPreviewQuality(page, "high");
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/SOURCE|REVIEW|Terrain/i, { timeout: 20_000 });

  await openPanel(page, /^Generate$/, /Generate project systems/i);
  await page.getByTestId("generate-main-action").click();
  await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|Needs input|Started|review/i, { timeout: 60_000 });
  await shot(page, testInfo, "06-generate");

  await openPanel(page, /^Deliver$/, /Review package|Make Review Package/i);
  await page.getByRole("button", { name: /Make Review Package/i }).click();
  await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|Package needs input|Review package needs input|Needs input/i, {
    timeout: 60_000,
  });
  await shot(page, testInfo, "07-deliver");

  await expect(page.locator("body")).not.toContainText(/construction-ready|approved for construction|stamped by Civora|sealed by Civora|signed by Civora/i);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((line) => !/401|auth|favicon|rate limit/i.test(line))).toEqual([]);
  expect(
    failedRequests.filter((line) => !/401|auth|favicon|rate limit|api\.mapbox\.com\/.*ERR_ABORTED/i.test(line)),
  ).toEqual([]);
});
