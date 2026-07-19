import { expect, test, type Page } from "@playwright/test";

async function openReportsPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=reports", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel.getByTestId("review-issue-tracker-panel")).toBeVisible({ timeout: 5_000 });
  return panel;
}

test("Review issue tracker remains visible and routes commands to chat", async ({ page }) => {
  let panel = await openReportsPanel(page);
  const tracker = panel.getByTestId("review-issue-tracker-panel");

  await expect(tracker).toContainText("Issue Tracker");
  await expect(tracker).toContainText("Open");
  await expect(tracker).toContainText("Engineer review");
  await expect(tracker).toContainText("Drainage");
  await expect(tracker).toContainText("Waived");

  await tracker.getByRole("button", { name: "Ask Open" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Chat|what issues are open/i);

  panel = await openReportsPanel(page);
  await panel.getByRole("button", { name: "show drainage blockers" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Chat|show drainage blockers/i);
});
