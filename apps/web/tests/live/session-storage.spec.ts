import { expect, test } from "@playwright/test";

test("sign-in stays tab-scoped, survives reload, and clears on sign-out", async ({ page, request, context }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL || "http://127.0.0.1:8002";
  const email = `session-${Date.now()}@example.test`;
  const password = "session-test-pass-123";
  const registered = await request.post(`${api}/api/auth/register`, {
    data: { email, password, name: "Session Test" },
  });
  expect(registered.ok()).toBe(true);
  await page.goto("/");
  await page.getByRole("button", { name: "Sign In Mode" }).click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByRole("button", { name: `Sign out ${email}` })).toBeVisible();
  const storageState = () => page.evaluate(() => ({
    persistent: Boolean(localStorage.getItem("civora-ai-token") || localStorage.getItem("performance-ai-token")),
    session: Boolean(sessionStorage.getItem("civora-ai-token")),
  }));
  expect(await storageState()).toEqual({ persistent: false, session: true });
  await page.reload();
  await expect(page.getByRole("button", { name: `Sign out ${email}` })).toBeVisible();
  const separateTab = await context.newPage();
  await separateTab.goto("/");
  await expect(separateTab.getByRole("button", { name: `Sign out ${email}` })).toHaveCount(0);
  expect(await separateTab.evaluate(() => Boolean(sessionStorage.getItem("civora-ai-token")))).toBe(false);
  await separateTab.close();
  await page.getByRole("button", { name: `Sign out ${email}` }).click();
  await expect.poll(storageState).toEqual({ persistent: false, session: false });
  await page.reload();
  await expect(page.getByRole("button", { name: `Sign out ${email}` })).toHaveCount(0);
});
