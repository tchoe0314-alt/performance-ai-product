import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1&aiRealismProvider=mock") {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(`/demo/workspace?${query}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
  return consoleErrors;
}

async function expectNoOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("Chat 232 naming and trust copy", () => {
  test("trust panel explains what Civora does and does not do without clutter", async ({ page }) => {
    const consoleErrors = await openDemoWorkspace(page);

    await page.getByRole("button", { name: "Help" }).click();
    const panel = page.getByTestId("civora-trust-panel");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText(/what civora does/i);
    await expect(panel).toContainText("site planning and review workflows");
    await expect(panel).toContainText("source-backed context");
    await expect(panel).toContainText("layout and drafting");
    await expect(panel).toContainText("review package");
    await expect(panel).toContainText("AI visualization");
    await expect(panel).toContainText(/what civora does not do/i);
    await expect(panel).toContainText("does not replace licensed professionals");
    await expect(panel).toContainText("does not stamp, seal, sign, certify, or approve construction");
    await expect(panel).toContainText("does not submit construction documents");
    await expect(panel).toContainText("does not act as engineer of record");
    await expect(panel).toContainText("does not turn GIS, AI, PDF, satellite, or other source data into survey or control");

    const textLength = (await panel.innerText()).length;
    expect(textLength).toBeLessThan(2200);
    await expectNoOverflow(page);
    expect(consoleErrors).toEqual([]);
  });

  test("main visible labels use the cleaned naming spine", async ({ page }) => {
    await openDemoWorkspace(page);

    await expect(page.getByRole("button", { name: "Open projects from header" })).toContainText("Projects");
    await expect(page.getByRole("button", { name: "Open chat from header" })).toContainText("Chat");
    await expect(page.getByRole("button", { name: "Help" })).toBeVisible();

    const sidebar = page.getByTestId("primary-workflow-sidebar");
    await expect(sidebar).toContainText(/setup/i);
    await expect(sidebar).toContainText(/draw/i);
    await expect(sidebar).toContainText(/generate/i);
    await expect(sidebar).toContainText(/deliver/i);
    await expect(sidebar).not.toContainText(/object manager/i);
    await expect(sidebar).not.toContainText(/project health/i);
    await expect(sidebar).not.toContainText(/analyze/i);
    await expectNoOverflow(page);
  });

  test("AI Visualization remains visual-only and review package avoids repeated boundary copy", async ({ page }) => {
    await openDemoWorkspace(page);

    const canvas = page.getByTestId("workspace-canvas-shell");
    await canvas.getByTestId("preview-quality-high").click();
    await expect(page.getByTestId("high-quality-preview-only-label")).toContainText("Visual preview only");
    await expect(page.getByTestId("high-quality-preview-only-label")).toContainText("Canonical geometry unchanged");
    await expect(page.getByTestId("high-quality-preview-only-label")).toContainText("Not engineering evidence");
    await expect(canvas).toContainText("AI Visualization");

    await page.getByRole("button", { name: /^Deliver$/ }).first().click();
    await expect(page.getByTestId("deliver-review-package-flow")).toContainText(/review package/i);
    await expect(page.getByTestId("deliver-review-package-flow").getByText("Review-only and engineer-review-required.")).toHaveCount(0);

    await page.getByRole("button", { name: "Help" }).click();
    await expect(page.getByTestId("civora-trust-panel")).toContainText("Outputs are planning and review aids.");

    const unsafeClaimPattern = /construction-ready|approved for construction|certified for construction|Civora (stamps|seals|certifies|approves|submits)|Civora acts as engineer of record/i;
    const pageText = await page.locator("body").innerText();
    expect(pageText).not.toMatch(unsafeClaimPattern);
    await expectNoOverflow(page);
  });
});
