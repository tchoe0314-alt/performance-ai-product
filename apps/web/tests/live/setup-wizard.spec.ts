import { expect, test } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const API_BASE_URL =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://api.civoraai.com";
const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";

test("setup wizard surfaces current step and blocker text", async ({ page, request, baseURL }) => {
  test.skip(!baseURL, "PLAYWRIGHT_BASE_URL is required.");
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required.");

  const loginResponse = await request.post(`${API_BASE_URL.replace(/\/+$/, "")}/api/auth/login`, {
    data: { email, password },
  });
  expect(loginResponse.ok()).toBeTruthy();
  const loginPayload = (await loginResponse.json()) as { token?: string };
  const token = String(loginPayload.token || "");
  expect(token).toBeTruthy();

  await page.addInitScript(
    ([tokenKey, authToken]) => window.localStorage.setItem(tokenKey, authToken),
    [TOKEN_KEY, token] as const,
  );

  await page.goto(baseURL!, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Setup" }).first().click();

  await expect(page.getByTestId("setup-wizard-sidebar-card")).toContainText("Auto Setup Wizard");
  await expect(page.getByTestId("setup-wizard-current-step")).toContainText("Auto Setup Wizard");
  await expect(page.getByTestId("setup-wizard-current-step")).toContainText(/Enter an address|Set dimensions|Review/i);
  await expect(page.getByText("Wizard steps")).toBeVisible();
  await expect(page.getByText("Online Sources / Candidates")).toBeVisible();
  await expect(page.getByText("Survey / Terrain / Control")).toBeVisible();
  await expect(page.getByText("Standards")).toBeVisible();
});
