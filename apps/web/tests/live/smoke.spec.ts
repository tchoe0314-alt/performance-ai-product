import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
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
const APP_BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ||
  "https://civoraai.com";
const FALLBACK_BASE_URL =
  process.env.PLAYWRIGHT_FALLBACK_BASE_URL ||
  "https://civoraai.com";

async function ensureAppUrl(page: Page) {
  const currentUrl = page.url();
  if (currentUrl.includes("vercel.com/")) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  const vercelLogin = page.getByRole("heading", { name: "Log in to Vercel" });
  const emailLogin = page.getByRole("button", { name: "Continue with Email" });
  const deploymentProtection = page.getByText("Deployment Protection", { exact: false });
  const authRequired = page.getByText("Authentication Required", { exact: false });
  if (await vercelLogin.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  if (await emailLogin.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  if (await deploymentProtection.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  if (await authRequired.isVisible().catch(() => false)) {
    await page.goto(FALLBACK_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    return true;
  }
  return false;
}

async function ensureChatPanel(page: Page) {
  const chatControls = [
    page.getByRole("banner").getByRole("button", { name: "Chat" }),
    page.getByRole("button", { name: "Open chat from sidebar command" }),
    page.getByRole("button", { name: /^Chat$/ }),
  ];

  for (const chatButton of chatControls) {
    if (await chatButton.first().isVisible().catch(() => false)) {
      await chatButton.first().click();
      return;
    }
  }
}

async function ensureNewProject(page: Page) {
  const projectsButton = page.getByRole("button", { name: "Projects" });
  if (await projectsButton.isVisible().catch(() => false)) {
    await projectsButton.click();
  }
  const newProjectButton = page.getByRole("button", { name: /New Project/i });
  if (await newProjectButton.isVisible().catch(() => false)) {
    await newProjectButton.click();
    await page.waitForLoadState("networkidle");
  }
}

async function expectNoGenericDesignClarification(page: Page) {
  await expect(
    page.getByText(/Before I move forward, I still need the site type or land use|which systems to include/i),
  ).toHaveCount(0, { timeout: 5_000 });
}

async function waitForComposer(page: Page) {
  const composer = page.getByPlaceholder(
    "Message Civora AI with what you want to create or change...",
  );

  for (let attempt = 0; attempt < 4; attempt += 1) {
    if (await ensureAppUrl(page)) {
      continue;
    }
    await page.waitForLoadState("networkidle").catch(() => null);
    if (!(await composer.isVisible().catch(() => false))) {
      await ensureChatPanel(page);
      await page.waitForTimeout(500);
    }
    if (await composer.isVisible().catch(() => false)) {
      return composer;
    }

    if (await ensureAppUrl(page)) {
      continue;
    }

    const loadError = page.getByText("This page couldn’t load");
    if (await loadError.isVisible().catch(() => false)) {
      await page.goto(APP_BASE_URL, { waitUntil: "domcontentloaded" }).catch(() => null);
    } else {
      await page.reload({ waitUntil: "domcontentloaded" });
    }
  }

  await expect(composer).toBeVisible({ timeout: 15_000 });
  return composer;
}

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
  await waitForComposer(page);

  await page.screenshot({
    path: path.join(artifactDir, "civora-app-shell.png"),
    fullPage: true,
  });

  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await expect(page.getByRole("banner").getByRole("button", { name: "Open workspace controls" })).toBeVisible();
  await expect(page.getByTestId("header-projects-button")).toBeVisible();
  await expect(page.getByTestId("header-chat-button")).toBeVisible();
  await expect(page.getByRole("banner").getByRole("button", { name: "Help" })).toBeVisible();

  if (prompt.trim()) {
    await ensureNewProject(page);

    const composer = await waitForComposer(page);
    await composer.fill(prompt);
    await page.getByRole("button", { name: "Send" }).click();

    await expectNoGenericDesignClarification(page);
    await expect(page.getByText(/Civora AI|Next action|review-required|review context|placed|site/i).last()).toBeVisible({
      timeout: 30_000,
    });

    await page.screenshot({
      path: path.join(artifactDir, "civora-after-prompt.png"),
      fullPage: true,
    });

    await page.getByRole("button", { name: /^Generate$/ }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate|Run review concepts/i, {
      timeout: 15_000,
    });
    await page.getByTestId("generate-main-action").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|Needs input|Started/i, {
      timeout: 30_000,
    });

    await page.screenshot({
      path: path.join(artifactDir, "civora-after-generate.png"),
      fullPage: true,
    });

    await page.getByRole("button", { name: /^Deliver$/ }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Deliver|Review package/i, {
      timeout: 15_000,
    });
    await page.getByRole("button", { name: /Make Review Package/i }).click();
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(
      /Package made|Package needs input|Review package needs input|Needs input/i,
      { timeout: 30_000 },
    );
    await page.screenshot({
      path: path.join(artifactDir, "civora-after-deliver.png"),
      fullPage: true,
    });
  }
});
