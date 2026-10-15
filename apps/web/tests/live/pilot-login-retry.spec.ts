import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { retryTransientLogin, withLoginDeadline } from "../../app/utils/loginRetry";

test("closed public registration shows sign-in and support, never an account creation action", async ({ page }) => {
  await page.route("**/api/auth/status", route => route.fulfill({ status: 200, json: {
    success: true, auth_enabled: true, account_setup: "configured", public_registration_enabled: false,
  } }));
  let registrations = 0;
  page.on("request", request => { if (request.url().endsWith("/api/auth/register")) registrations++; });
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Sign In", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Request Access/i })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Contact support", exact: true })).toHaveAttribute("href", "/support");
  expect(registrations).toBe(0);
});

test("stalled login is bounded, aborted and never retried automatically", async () => {
  let attempts = 0, signal: AbortSignal | undefined;
  await expect(retryTransientLogin(() => withLoginDeadline(async current => {
    attempts++; signal = current;
    return new Promise<never>(() => {});
  }, 20), async () => {})).rejects.toThrow("Sign-in took too long.");
  expect(attempts).toBe(1);
  expect(signal?.aborted).toBe(true);
});

test("deadline preserves success and failure and cannot abort a finished login", async () => {
  let signal: AbortSignal | undefined;
  expect(await withLoginDeadline(async current => { signal = current; return "accepted"; }, 20)).toBe("accepted");
  await new Promise(resolve => setTimeout(resolve, 40));
  expect(signal?.aborted).toBe(false);
  const rejected = Object.assign(new Error("Invalid email or password"), { status: 401 });
  await expect(withLoginDeadline(async () => { throw rejected; })).rejects.toBe(rejected);
  for (const value of [0, -1, NaN, Infinity]) await expect(withLoginDeadline(async () => "unused", value)).rejects.toThrow("Invalid sign-in deadline");
});

test("a late transport success cannot replace the timeout", async () => {
  let finish: ((value: string) => void) | undefined;
  const attempt = withLoginDeadline(() => new Promise<string>(resolve => { finish = resolve; }), 20);
  await expect(attempt).rejects.toThrow("Sign-in took too long.");
  finish!("late token");
  await expect(attempt).rejects.toThrow("Sign-in took too long.");
});

test("website stalled login clears its busy state without creating a session", async ({ page }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Local fault injection only.");
  let attempts = 0;
  await page.route(`${api}/api/auth/login`, async route => {
    attempts++;
    await new Promise(resolve => setTimeout(resolve, 18_000));
    await route.abort().catch(() => {});
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Sign In Mode", exact: true }).click();
  await page.getByLabel("Email", { exact: true }).fill("timeout@example.test");
  await page.getByLabel("Password", { exact: true }).fill("Disposable-123");
  const button = page.getByRole("button", { name: "Sign In", exact: true });
  await button.click();
  await expect(page.getByText("Sign-in took too long. Try again shortly.", { exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(button).toBeEnabled();
  expect(attempts).toBe(1);
  expect(await page.evaluate(() => sessionStorage.getItem("civora-ai-token"))).toBeNull();
  await expect(page.getByTestId("workspace-canvas-shell")).toHaveCount(0);
});

for (const status of [401, 403, 409, 422, 429, 500]) {
  test(`login does not retry status ${status}`, async () => {
    let attempts = 0, pauses = 0;
    const failure = Object.assign(new Error("Rejected"), { status });
    await expect(retryTransientLogin(async () => { attempts++; throw failure; }, async () => { pauses++; })).rejects.toBe(failure);
    expect([attempts, pauses]).toEqual([1, 0]);
  });
}
for (const status of [502, 503, 504]) {
  test(`login recovers once from status ${status}`, async () => {
    let attempts = 0, pauses = 0;
    const result = await retryTransientLogin(async () => { if (++attempts === 1) throw Object.assign(new Error("Temporary"), { status }); return "accepted"; }, async () => { pauses++; });
    expect(result).toBe("accepted"); expect([attempts, pauses]).toEqual([2, 1]);
  });
}
test("login cannot loop, and cancellation is never retried", async () => {
  let attempts = 0;
  const failure = Object.assign(new Error("Temporary"), { status: 502 });
  await expect(retryTransientLogin(async () => { attempts++; throw failure; }, async () => {})).rejects.toBe(failure);
  expect(attempts).toBe(2);
  attempts = 0;
  await expect(retryTransientLogin(async () => { attempts++; throw Object.assign(new Error("Cancelled"), { name: "AbortError" }); }, async () => {})).rejects.toThrow("Cancelled");
  expect(attempts).toBe(1);
});
test("login network recovery preserves a successful result without extra requests", async () => {
  let attempts = 0;
  expect(await retryTransientLogin(async () => { if (++attempts === 1) throw new Error("Could not reach the backend"); return "accepted"; }, async () => {})).toBe("accepted");
  expect(attempts).toBe(2);
  attempts = 0;
  expect(await retryTransientLogin(async () => { attempts++; return "accepted"; }, async () => {})).toBe("accepted");
  expect(attempts).toBe(1);
});

test("website recovers from one injected gateway failure and signs in against the real local backend", async ({ page, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable localhost only.");
  const email = `login-retry-${randomUUID()}@example.test`, password = "Disposable-123";
  expect((await request.post(`${api}/api/auth/register`, { data: { email, password, name: "Login recovery regression" } })).status()).toBe(200);
  let attempts = 0;
  await page.route(`${api}/api/auth/login`, async route => { attempts++; if (attempts === 1) await route.fulfill({ status: 502, json: { detail: "Temporary upstream failure" } }); else await route.continue(); });
  await page.goto("/");
  await page.getByRole("button", { name: "Sign In Mode", exact: true }).click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  expect(attempts).toBe(2);
  const token = await page.evaluate(() => sessionStorage.getItem("civora-ai-token"));
  expect(token).toBeTruthy();
  const me = await request.get(`${api}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
  expect(me.status()).toBe(200); expect((await me.json()).user.email).toBe(email);
});

for (const scenario of [
  { mode: "login", status: 401, attempts: 1, message: "Invalid email or password." },
  { mode: "login", status: 429, attempts: 1, message: "Too many sign-in attempts." },
  { mode: "login", status: 502, attempts: 2, message: "Sign-in is temporarily unavailable. Try again shortly." },
  { mode: "register", status: 502, attempts: 1, message: "Temporary upstream failure" },
]) {
  test(`website ${scenario.mode} status ${scenario.status} retains its bounded failure and no session`, async ({ page }) => {
    const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
    test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Local fault injection only.");
    let attempts = 0;
    await page.route(`${api}/api/auth/${scenario.mode}`, async route => { attempts++; await route.fulfill({ status: scenario.status, json: { detail: scenario.status === 502 ? "Temporary upstream failure" : scenario.message } }); });
    await page.goto("/");
    if (scenario.mode === "login") await page.getByRole("button", { name: "Sign In Mode", exact: true }).click();
    else await page.getByLabel("Name", { exact: true }).fill("Synthetic signup fault");
    await page.getByLabel("Email", { exact: true }).fill("fault@example.test");
    await page.getByLabel("Password", { exact: true }).fill("Disposable-123");
    await page.getByRole("button", { name: scenario.mode === "login" ? "Sign In" : "Request Access", exact: true }).click();
    await expect(page.getByText(scenario.message, { exact: true })).toBeVisible();
    expect(attempts).toBe(scenario.attempts);
    expect(await page.evaluate(() => sessionStorage.getItem("civora-ai-token"))).toBeNull();
    await expect(page.getByTestId("workspace-canvas-shell")).toHaveCount(0);
  });
}
