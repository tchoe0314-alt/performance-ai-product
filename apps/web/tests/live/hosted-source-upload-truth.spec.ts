import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import path from "node:path";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";
const DEFAULT_APP_URL = "https://civoraai.com/?debugPreview=1&aiRealismProvider=mock";
const DEFAULT_API_URL = "https://api.civoraai.com";
const SURVEY_FIXTURE = path.resolve(__dirname, "../../../../backend/fixtures/real_input_benchmarks/survey_points.csv");

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const appUrl = process.env.PLAYWRIGHT_BASE_URL || DEFAULT_APP_URL;
const apiBaseUrl = (process.env.PLAYWRIGHT_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_URL).replace(/\/+$/, "");

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

async function openPanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 15_000 });
}

test("hosted survey upload drives source-backed preview marks without fake topo", async ({ page, request }) => {
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required for hosted source upload proof.");

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
  await page.getByTestId("use-1000-site-size").click();
  await expect(addressSection.getByTestId("create-centered-site-button")).toBeEnabled({ timeout: 10_000 });
  await addressSection.getByTestId("create-centered-site-button").click();
  await expect(page.getByTestId("site-status")).toContainText(/Site Locked/i, { timeout: 30_000 });
  const mapToggle = page.getByTestId("workspace-canvas-shell").getByTestId("preview-inner-map-toggle");
  await expect(mapToggle).toBeEnabled({ timeout: 60_000 });
  await openPanel(page, /^Setup$/, /Address \/ Location|Site Boundary|Survey \/ Terrain/i);

  const surveySection = page.getByTestId("setup-survey-terrain-card");
  if (!(await surveySection.evaluate((node) => node.hasAttribute("open")))) {
    await surveySection.locator("summary").first().click();
  }
  await page.locator('input[accept*=".csv"]').first().setInputFiles(SURVEY_FIXTURE);
  await expect(page.getByTestId("survey-upload-status").first()).toContainText(/Survey\/topo imported|Existing conditions imported|ready for review/i, {
    timeout: 60_000,
  });
  await expect(page.getByTestId("best-survey-source-label")).toContainText(/uploaded survey\/control points/i, { timeout: 15_000 });

  const canvas = page.getByTestId("workspace-canvas-shell");
  await canvas.getByTestId("preview-quality-high").click();
  await expect(page.getByTestId("source-survey-point").first()).toBeVisible({ timeout: 15_000 });
  if ((await mapToggle.textContent())?.includes("Map On")) await mapToggle.click();
  await expect(mapToggle).toContainText("Map Off");
  await expect(page.getByTestId("survey-spot-elevation").first()).toBeVisible();
  await expect(canvas).toContainText(/SOURCE EXHIBIT/i);
  await expect(canvas).toContainText(/SOURCE REVIEW/i);
  await expect(canvas).not.toContainText(/NO SURVEY \/ TOPO SOURCE/i);
  await expect(canvas).not.toContainText(/N 89°58|S 89°58|N 00°01|S 00°01/i);

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((line) => !/401|auth|favicon/i.test(line))).toEqual([]);
  expect(
    failedRequests.filter((line) => !/401|auth|favicon|api\.mapbox\.com\/.*ERR_ABORTED/i.test(line)),
  ).toEqual([]);
});
