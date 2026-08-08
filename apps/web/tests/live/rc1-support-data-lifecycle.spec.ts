import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";

import { expect, test, type APIRequestContext, type Page } from "@playwright/test";


const backendBase =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8002";
const password = "rc1-account-lifecycle-123";

async function registerTemporaryUser(request: APIRequestContext) {
  const email = `rc1-lifecycle-${Date.now()}-${Math.random().toString(16).slice(2)}@example.test`;
  const response = await request.post(`${backendBase}/api/auth/register`, {
    data: { email, password, name: "RC1 Lifecycle User" },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as { token: string; user: { user_id: string; email: string } };
}

async function openHelp(page: Page) {
  await page.getByRole("button", { name: "Help" }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("civora-trust-panel")).toBeVisible();
}

test.describe("RC1 support and account data lifecycle", () => {
  test("submits a persisted issue, downloads an archive, and deletes a temporary account", async ({ page, request }) => {
    test.setTimeout(180_000);
    const user = await registerTemporaryUser(request);
    await page.addInitScript((token) => {
      window.localStorage.setItem("civora-ai-token", token);
      window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
    }, user.token);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await openHelp(page);

    await page.getByTestId("support-summary").click();
    await page.getByLabel("What happened?").fill("RC1 account lifecycle browser proof");
    await page.getByLabel("Details").fill("Temporary permission-cleared issue created by the automated RC1 browser test.");
    await page.getByRole("button", { name: "Send issue" }).click();
    await expect(page.getByText(/Issue received|Support request received/i)).toBeVisible();

    const supportResponse = await request.get(`${backendBase}/api/support/requests`, {
      headers: { Authorization: `Bearer ${user.token}` },
    });
    expect(supportResponse.status(), await supportResponse.text()).toBe(200);
    const supportPayload = await supportResponse.json();
    expect(supportPayload.requests).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ summary: "RC1 account lifecycle browser proof", user_id: user.user.user_id }),
      ]),
    );

    await page.getByTestId("account-data-summary").click();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download my data" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^civora-account-export-.*\.zip$/);
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    expect((await stat(downloadPath!)).size).toBeGreaterThan(200);
    const stream = createReadStream(downloadPath!);
    const signature = await new Promise<Buffer>((resolve, reject) => {
      stream.once("error", reject);
      stream.once("data", (chunk) => {
        stream.destroy();
        resolve(Buffer.from(chunk).subarray(0, 4));
      });
    });
    expect(signature.toString("hex")).toBe("504b0304");
    await expect(page.getByText("Account archive downloaded.")).toBeVisible();

    await page.getByTestId("delete-account-summary").click();
    await page.getByRole("button", { name: "Check deletion" }).click();
    await expect(page.getByText(/Deletion is available after password and exact confirmation/i)).toBeVisible();
    await page.getByLabel("Current password").fill(password);
    await page.getByLabel("Type DELETE MY CIVORA ACCOUNT").fill("DELETE MY CIVORA ACCOUNT");
    await page.getByRole("button", { name: "Permanently delete account" }).click();
    await expect(page.getByText(/Sign in|Request Pilot Access/i).first()).toBeVisible({ timeout: 30_000 });

    const expiredToken = await request.get(`${backendBase}/api/auth/me`, {
      headers: { Authorization: `Bearer ${user.token}` },
    });
    expect(expiredToken.status()).toBe(401);
  });
});
