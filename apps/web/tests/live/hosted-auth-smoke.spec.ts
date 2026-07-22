import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const DEFAULT_APP_URL = "https://civoraai.com/demo/workspace?debugPreview=1&aiRealismProvider=mock";
const DEFAULT_API_URL = "https://api.civoraai.com";

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
    ([tokenKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
    },
    [TOKEN_KEY, token] as const,
  );
}

async function openWorkspace(page: Page) {
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
}

async function askChat(page: Page, prompt: string, expected: RegExp) {
  await page.getByTestId("header-chat-button").click();
  const input = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
  await input.fill(prompt);
  await input.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 10_000 });
}

test.describe("hosted authenticated smoke", () => {
  test("proves auth, projects, workflow panels, chat, API gates, and browser health", async ({ page, request }) => {
    test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required for hosted authenticated smoke.");

    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    const failedRequests: string[] = [];

    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("requestfailed", (requestInfo) => {
      const failure = requestInfo.failure()?.errorText || "request failed";
      failedRequests.push(`${requestInfo.method()} ${requestInfo.url()} ${failure}`);
    });

    const token = await login(request);

    const authenticatedJobs = await request.get(`${apiBaseUrl}/api/jobs`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(authenticatedJobs.status(), "authenticated jobs endpoint should be reachable").toBe(200);

    const unauthenticatedJobs = await request.get(`${apiBaseUrl}/api/jobs`);
    expect(unauthenticatedJobs.status(), "unauthenticated jobs endpoint should stay protected").toBe(401);

    await seedAuth(page, token);
    await openWorkspace(page);

    await expect(page.getByRole("banner").getByRole("button", { name: "Open workspace controls" })).toBeVisible();
    await expect(page.getByTestId("header-projects-button")).toBeVisible();
    await expect(page.getByTestId("header-chat-button")).toBeVisible();
    await expect(page.getByRole("banner").getByRole("button", { name: "Help" })).toBeVisible();

    await page.getByTestId("header-projects-button").click();
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await page.getByRole("button", { name: /New Project/i }).filter({ visible: true }).first().click();
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

    await page.getByRole("button", { name: "Open workspace controls" }).click();
    await page.getByRole("button", { name: /^Setup$/ }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Setup|Address \/ Location|Site Boundary/i);

    await page.getByRole("button", { name: "Generate" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate Systems/i);
    await page.getByTestId("generate-main-action").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|Needs input/i, { timeout: 10_000 });

    await page.getByRole("button", { name: /^Deliver$/ }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Deliver|Review package/i);
    await page.getByRole("button", { name: /Make Review Package/i }).click();
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|Package needs input|Review package needs input/i, { timeout: 10_000 });

    await askChat(page, "what changed?", /What changed|Last Generate|Recent changes|Auto Site Context/i);
    await askChat(page, "what is blocked?", /Needs input|review-required|Outputs remain review-required/i);
    await askChat(page, "can I export?", /export|review package|blocked/i);

    await expect(page.getByTestId("workspace-canvas-shell")).not.toContainText(
      /construction-ready|Civora approved|stamped by Civora|sealed by Civora|signed by Civora/i,
    );

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors).toEqual([]);
    expect(failedRequests).toEqual([]);
  });
});
