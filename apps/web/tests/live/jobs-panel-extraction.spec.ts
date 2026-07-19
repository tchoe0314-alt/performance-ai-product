import { expect, test, type Page } from "@playwright/test";

async function openJobsPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=jobs", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("async-jobs-panel");
  await expect(panel).toBeVisible({ timeout: 5_000 });
  await expect(panel).toContainText("Job workflow");
  await expect(panel).toContainText("History");
  await expect(panel).toContainText("Artifact history");
  return panel;
}

test("Jobs panel remains reachable and reports refresh blockers clearly", async ({ page }) => {
  const panel = await openJobsPanel(page);

  await expect(panel).toContainText("No active job");
  await expect(panel).toContainText("No background jobs yet.");
  await expect(panel).toContainText("No generated artifacts have been recorded yet.");

  await panel.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByTestId("jobs-refresh-status")).toContainText("Sign in/connect backend to refresh jobs.");
});
