import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1&aiRealismProvider=mock", {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Detention Basin|Office|Parking/i, {
    timeout: 30_000,
  });
}

async function openPanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible().catch(() => false)) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 10_000 });
}

test.describe("Civil review sheet deliverable", () => {
  test("renders a professional plan-sheet style review package preview", async ({ page }) => {
    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));

    await openDemoWorkspace(page);
    await openPanel(page, /^Deliver$/, /Review package/i);
    await page.getByRole("button", { name: /Make Review Package/i }).click();

    const reviewSheetDetails = page.getByTestId("deliver-review-sheet-preview");
    if (!(await reviewSheetDetails.evaluate((node) => node.hasAttribute("open")))) {
      await reviewSheetDetails.locator(":scope > summary").click();
    }

    const sheet = page.getByTestId("civil-review-sheet-preview");
    await expect(sheet).toBeVisible({ timeout: 10_000 });
    await expect(sheet).toContainText(/Civil Review Sheet/i);
    await expect(sheet).toContainText(/review only/i);
    await expect(page.getByTestId("civil-review-sheet-title-block")).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-legend")).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-plan")).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-dense-plan")).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-dense-building")).toHaveCount(9);
    await expect(page.getByTestId("civil-review-sheet-dense-parking")).toHaveCount(12);
    await expect(page.getByTestId("civil-review-sheet-dense-utilities")).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-dense-callouts")).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-profile")).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-source-summary")).toContainText(/Source candidates/i);
    await page.getByTestId("civil-review-sheet-expand").click();
    await expect(page.getByRole("button", { name: /Close full sheet/i })).toBeVisible();
    await expect(page.getByTestId("civil-review-sheet-title-block")).toBeVisible();

    const sheetText = await sheet.innerText();
    expect(sheetText).not.toMatch(/construction-ready|Civora approved|stamped by Civora|sealed by Civora|signed by Civora|engineer of record/i);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
  });
});
