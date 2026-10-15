import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { readFileSync } from "node:fs";

const api = process.env.CIVORA_IDENTITY_FIXTURE_API || "";
const mailbox = process.env.CIVORA_IDENTITY_FIXTURE_MAILBOX || "";
const enabled = process.env.CIVORA_DISPOSABLE_IDENTITY_UI === "1"
  && /^http:\/\/127\.0\.0\.1:\d+$/.test(api)
  && /^\/(private\/)?tmp\/.+\/civora-ui-fixture-[^/]+\/mailbox\.json$/.test(mailbox);

function codeFor(email: string) {
  const messages = JSON.parse(readFileSync(mailbox, "utf8")) as Array<{ recipient: string; text: string }>;
  const message = messages.filter(row => row.recipient === email).at(-1);
  if (!message) throw new Error("No synthetic message for the fixture identity.");
  return message.text.split("\n")[0].split(": ")[1];
}

test("real private signup, mailbox recovery, verification, invitation and session controls", async ({ page, request }) => {
  test.skip(!enabled, "Explicit newly created local identity fixture required; never hosted/customer targets.");
  test.setTimeout(180_000);
  const pageErrors: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message.slice(0, 300)));
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    const localPage = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:49321";
    if (["http:", "https:"].includes(url.protocol) && ![new URL(localPage).origin, api].includes(url.origin)) return route.abort("blockedbyclient");
    return route.continue();
  });
  const ownerLogin = await request.post(`${api}/api/auth/login`, { data: { email: "owner@example.test", password: "Synthetic-only-123" } });
  expect(ownerLogin.status()).toBe(200);
  const ownerToken = (await ownerLogin.json()).token;
  const headers = { Authorization: `Bearer ${ownerToken}` };
  const projects = await request.get(`${api}/api/projects`, { headers });
  const projectId = (await projects.json()).projects[0].project_id;
  const invitationCodes: Record<string, string> = {};
  for (const email of ["new@example.test", "recipient@example.test"]) {
    const invitation = await request.post(`${api}/api/projects/${projectId}/admin/invites`, { headers, data: { email } });
    expect(invitation.status()).toBe(200);
    invitationCodes[email] = codeFor(email);
  }

  await page.goto("/");
  await expect(page.getByRole("button", { name: "Sign In", exact: true })).toBeVisible();
  await page.locator("#civora-auth-email").fill("owner@example.test");
  await page.locator("#civora-auth-password").fill("Synthetic-only-123");
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-help-button").click();
  const security = page.getByTestId("identity-security");
  await security.locator("summary").click();
  await security.getByRole("button", { name: "Send verification code", exact: true }).click();
  await expect(security.getByRole("status")).toContainText("Verification code sent");
  await security.getByLabel("Email verification code").fill(codeFor("owner@example.test"));
  await security.getByRole("button", { name: "Verify email", exact: true }).click();
  await expect(security.getByText("Email verified", { exact: true })).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).include('[data-testid="identity-security"]').analyze();
  expect(accessibility.violations.filter(row => ["serious", "critical"].includes(row.impact || ""))).toEqual([]);
  await security.getByLabel("Current password", { exact: true }).fill("Synthetic-only-123");
  await security.getByRole("button", { name: "Sign out all devices" }).click();
  await expect(page.getByRole("button", { name: "Sign In", exact: true })).toBeVisible();
  expect((await request.get(`${api}/api/auth/me`, { headers })).status()).toBe(401);

  await page.getByRole("button", { name: "Use invitation", exact: true }).click();
  await expect(page.getByRole("button", { name: "Create account", exact: true })).toBeDisabled();
  await page.locator("#civora-auth-name").fill("Synthetic new recipient");
  await page.locator("#civora-auth-email").fill("new@example.test");
  await page.locator("#civora-auth-password").fill("New-synthetic-password");
  await page.getByLabel("Invitation code", { exact: true }).fill(invitationCodes["new@example.test"]);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-help-button").click();
  await security.locator("summary").click();
  await expect(security.getByText("Email verified", { exact: true })).toBeVisible();
  await security.getByLabel("Current password", { exact: true }).fill("New-synthetic-password");
  await security.getByRole("button", { name: "Sign out all devices" }).click();
  await expect(page.getByRole("button", { name: "Sign In", exact: true })).toBeVisible();

  const recovery = page.getByTestId("password-recovery");
  await recovery.locator("summary").click();
  await recovery.getByLabel("Recovery email").fill("recipient@example.test");
  await recovery.getByRole("button", { name: "Send reset code" }).click();
  await expect(recovery.getByRole("status")).toContainText("a code was sent");
  await recovery.getByLabel("Reset code", { exact: true }).fill(codeFor("recipient@example.test"));
  await recovery.getByLabel("New password", { exact: true }).fill("Recovered-synthetic-password");
  await recovery.getByRole("button", { name: "Reset password", exact: true }).click();
  await expect(recovery.getByRole("status")).toContainText("Password changed");
  await page.locator("#civora-auth-password").fill("Recovered-synthetic-password");
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-help-button").click();
  await security.locator("summary").click();
  await security.getByLabel("Invitation code", { exact: true }).fill(invitationCodes["recipient@example.test"]);
  await security.getByRole("button", { name: "Accept invitation", exact: true }).click();
  await expect(security.getByRole("status")).toContainText("Invitation accepted");
  expect(pageErrors).toEqual([]);
});

test("responsive security controls and workflow rail remain usable and legible", async ({ page }) => {
  test.skip(!enabled, "Disposable local identity fixture only.");
  test.setTimeout(120_000);
  await page.route("**/*", route => {
    const url=new URL(route.request().url());
    if (["http:","https:"].includes(url.protocol) && !["http://127.0.0.1:49321",api].includes(url.origin)) return route.abort("blockedbyclient");
    return route.continue();
  });
  await page.goto("/");
  await page.locator("#civora-auth-email").fill("owner@example.test");
  await page.locator("#civora-auth-password").fill("Synthetic-only-123");
  await page.getByRole("button",{name:"Sign In",exact:true}).click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  for (const [width,height] of [[1280,800],[844,390],[390,844]]) {
    await page.setViewportSize({width,height});
    for (const stage of ["brief","explore","analyze","review","deliver"]) {
      const button=page.getByTestId(`workspace-stage-${stage}`);
      await button.click();
      await expect(button).toHaveAttribute("aria-current","page");
    }
    const rail=await new AxeBuilder({page}).include('[data-testid="left-sidebar"]').analyze();
    expect(rail.violations.filter(row=>["serious","critical"].includes(row.impact||""))).toEqual([]);
    await page.getByTestId("header-help-button").click();
    const security=page.getByTestId("identity-security");
    await security.locator("summary").click();
    await expect(security.getByLabel("Invitation code",{exact:true})).toBeVisible();
    const box=await security.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(-1);
    expect(box!.x+box!.width).toBeLessThanOrEqual(width+1);
    const scan=await new AxeBuilder({page}).include('[data-testid="identity-security"]').analyze();
    expect(scan.violations.filter(row=>["serious","critical"].includes(row.impact||""))).toEqual([]);
    await page.screenshot({path:test.info().outputPath(`security-${width}x${height}.png`)});
  }
});
