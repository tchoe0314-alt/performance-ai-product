import { expect, test, type Page } from "@playwright/test";

async function openReportsPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=reports", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Source confidence", { timeout: 5_000 });
  return panel;
}

test("Source confidence report card remains visible after extraction", async ({ page }) => {
  const panel = await openReportsPanel(page);

  await expect(panel).toContainText("Entries");
  await expect(panel).toContainText("Low confidence");
  await expect(panel).toContainText("User drawn");
  await expect(panel).toContainText("Need control");
  await expect(panel).toContainText(/Verification status visible|Review|Missing|candidate/i);
});
