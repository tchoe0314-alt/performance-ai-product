import { expect, test } from "@playwright/test";
import fs from "node:fs/promises";
import path from "node:path";

const email = process.env.CIVORA_EMAIL || "";
const password = process.env.CIVORA_PASSWORD || "";
const prompt = process.env.CIVORA_PROMPT || "";
const TOKEN_KEY = "civora-ai-token";
const API_BASE_URL =
  process.env.PLAYWRIGHT_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "https://api.civoraai.com";

async function ensureArtifactDir(): Promise<string> {
  const dir = path.resolve(process.cwd(), "playwright-artifacts");
  await fs.mkdir(dir, { recursive: true });
  return dir;
}

test("live civora flow", async ({ page, request, baseURL }) => {
  test.skip(!baseURL, "PLAYWRIGHT_BASE_URL is required.");
  test.skip(!email || !password, "CIVORA_EMAIL and CIVORA_PASSWORD are required.");

  const artifactDir = await ensureArtifactDir();
  const loginResponse = await request.post(`${API_BASE_URL.replace(/\/+$/, "")}/api/auth/login`, {
    data: {
      email,
      password,
    },
  });

  expect(loginResponse.ok()).toBeTruthy();

  const loginPayload = (await loginResponse.json()) as { token?: string };
  const token = String(loginPayload?.token || "");
  expect(token).toBeTruthy();

  await page.addInitScript(
    ([tokenKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
    },
    [TOKEN_KEY, token] as const,
  );

  await page.goto(baseURL!, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle");
  await expect(
    page.getByPlaceholder("Message Civora AI with what you want to create or change..."),
  ).toBeVisible();

  await page.screenshot({
    path: path.join(artifactDir, "civora-app-shell.png"),
    fullPage: true,
  });

  await expect(page.getByText("What You Need")).toBeVisible();

  if (prompt.trim()) {
    const newProjectButton = page.getByRole("button", { name: "New Project" });
    if (await newProjectButton.isVisible().catch(() => false)) {
      await newProjectButton.click();
      await page.waitForLoadState("networkidle");
    }

    const composer = page.getByPlaceholder(
      "Message Civora AI with what you want to create or change...",
    );
    await composer.fill(prompt);
    await page.getByRole("button", { name: "Send" }).click();

    const approvalCard = page.getByText("Awaiting Approval", { exact: true });
    await expect(approvalCard).toBeVisible({ timeout: 60_000 });

    const previewImage = page.getByAltText("Generated plan preview");
    await previewImage.waitFor({ state: "visible", timeout: 12_000 }).catch(() => null);

    await page.screenshot({
      path: path.join(artifactDir, "civora-after-prompt.png"),
      fullPage: true,
    });

    const approveButton = page.getByRole("button", { name: /Approve & Continue/i });
    if (await approveButton.isVisible().catch(() => false)) {
      await approveButton.scrollIntoViewIfNeeded();
      await approveButton.click({ force: true });
      await expect(
        page.getByText(/Proposed grading surface built\.|2\/5 phases complete/i),
      ).toBeVisible({ timeout: 60_000 });
      await previewImage.waitFor({ state: "visible", timeout: 12_000 }).catch(() => null);
      await page.screenshot({
        path: path.join(artifactDir, "civora-after-approve.png"),
        fullPage: true,
      });
    }
  }
});
