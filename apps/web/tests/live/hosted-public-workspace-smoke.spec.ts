import { expect, test, type Page } from "@playwright/test";

const ignoredConsoleError = /favicon|401|unauthorized|auth\/status/i;

async function openWorkspace(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  const failedRequests: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error" && !ignoredConsoleError.test(message.text())) {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    const url = request.url();
    if (!ignoredConsoleError.test(url)) {
      failedRequests.push(`${request.method()} ${url} ${request.failure()?.errorText || "failed"}`);
    }
  });

  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });

  return { consoleErrors, pageErrors, failedRequests };
}

async function visibleButtonCount(page: Page, name: RegExp | string) {
  const buttons = page.getByRole("button", { name });
  const count = await buttons.count();
  let visible = 0;
  for (let index = 0; index < count; index += 1) {
    if (await buttons.nth(index).isVisible()) visible += 1;
  }
  return visible;
}

async function openPanel(page: Page, name: RegExp | string, expectedText: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expectedText, { timeout: 6_000 });
}

test.describe("hosted/public workspace smoke", () => {
  test("loads the current workspace shell and core controls without auth", async ({ page }) => {
    const browserHealth = await openWorkspace(page);

    await expect(page.getByRole("button", { name: "Open projects from header" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open chat from header" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Setup$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Draw$/ })).toBeVisible();
    expect(await visibleButtonCount(page, "Generate")).toBe(1);
    expect(await visibleButtonCount(page, /^Deliver$/)).toBe(1);

    await expect(page.getByTestId("preview-mode-2d").first()).toBeVisible();
    await page.getByTestId("preview-quality-high").first().click();
    await expect(page.getByTestId("ai-realism-on").first()).toBeVisible();
    await page.getByTestId("ai-realism-on").first().click();
    await expect(page.getByTestId("ai-realism-watermark").first()).toContainText(/visual concept only/i);
    await page.getByTestId("preview-mode-3d").first().click();
    await expect(page.getByTestId("preview-mode-2d").first()).toBeVisible();
    await page.getByTestId("preview-mode-2d").first().click();

    await openPanel(page, /^Setup$/, /Setup|Address \/ Location|Site Boundary/);
    await expect(page.getByTestId("setup-address-truth")).toContainText(/Address \/ Location/i);
    await expect(page.getByTestId("setup-site-box-controls")).toContainText(/Site Boundary/i);

    await openPanel(page, /^Draw$/, /Draw & Objects|Tools/);
    await expect(page.getByTestId("cad-tool-line")).toBeVisible();
    await page.getByTestId("cad-tool-line").click();
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE tool active|LINE active/i);

    await openPanel(page, "Generate", /Generate Systems/);
    await expect(page.getByTestId("generate-main-action")).toBeVisible();
    await expect(page.getByTestId("generate-system-details")).toContainText(/Advanced/i);

    await openPanel(page, /^Deliver$/, /Review package|Deliver/);
    await expect(page.getByTestId("deliver-review-package-flow").getByRole("button", { name: /Make Review Package/i })).toHaveCount(1);
    await expect(page.getByTestId("deliver-review-sheet-preview")).toContainText(/Review sheet preview/i);

    await page.getByRole("button", { name: "Open projects from header" }).click();
    await expect(page.getByTestId("projects-drawer")).toBeVisible();
    await page.getByRole("button", { name: "Minimize" }).click();

    await page.getByRole("button", { name: "Open chat from header" }).click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toBeVisible();

    await expect(page.getByText(/construction-ready|Civora approved|stamped by Civora|sealed by Civora|engineer of record/i)).toHaveCount(0);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(browserHealth.pageErrors).toEqual([]);
    expect(browserHealth.consoleErrors).toEqual([]);
    expect(browserHealth.failedRequests).toEqual([]);
  });
});
