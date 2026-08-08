import { expect, test, type APIRequestContext } from "@playwright/test";


const backendBase =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8002";

async function registerTemporaryUser(request: APIRequestContext) {
  const email = `rc1-support-route-${Date.now()}-${Math.random().toString(16).slice(2)}@example.test`;
  const response = await request.post(`${backendBase}/api/auth/register`, {
    data: { email, password: "rc1-support-route-123", name: "RC1 Support Route" },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as { token: string };
}

test.describe("standalone support route", () => {
  test("requires sign-in without failing silently", async ({ page }) => {
    await page.goto("/support?category=bug", { waitUntil: "domcontentloaded" });
    await expect(page.getByRole("heading", { name: "Report a Civora problem" })).toBeVisible();
    await expect(page.getByText("Sign in to Civora before sending an issue.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Civora to sign in" })).toBeVisible();
  });

  test("submits and lists a redacted authenticated issue", async ({ page, request }) => {
    const user = await registerTemporaryUser(request);
    await page.addInitScript((token) => {
      window.localStorage.setItem("civora-ai-token", token);
      window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
    }, user.token);
    await page.goto("/support?category=bug", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Your signed-in session is ready.")).toBeVisible();
    await expect(page.getByLabel("Category")).toHaveValue("workflow");
    await page.getByLabel("What happened?").fill("Standalone support route proof");
    await page.getByLabel("Details").fill("A drawing action did not match the expected result. password=do-not-store");
    await page.getByRole("button", { name: "Send issue" }).click();
    await expect(page.getByTestId("support-request-status")).toContainText("Issue received as support_");
    await expect(page.getByTestId("recent-support-requests")).toContainText("Standalone support route proof");

    const listed = await request.get(`${backendBase}/api/support/requests`, {
      headers: { Authorization: `Bearer ${user.token}` },
    });
    expect(listed.status(), await listed.text()).toBe(200);
    const serialized = JSON.stringify(await listed.json());
    expect(serialized).toContain("Standalone support route proof");
    expect(serialized).not.toContain("do-not-store");
    await expect(page.locator("body")).toHaveJSProperty("scrollWidth", await page.locator("body").evaluate((body) => body.clientWidth));
  });
});
