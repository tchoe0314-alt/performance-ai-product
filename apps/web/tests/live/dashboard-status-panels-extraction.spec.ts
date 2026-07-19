import { expect, test, type Page } from "@playwright/test";

async function openDashboardPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=dashboard", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Project readiness", { timeout: 5_000 });
  await expect(panel).toContainText("Attention");
  return panel;
}

test("Dashboard status panels remain reachable without duplicate quick actions", async ({ page }) => {
  const panel = await openDashboardPanel(page);

  await expect(panel).toContainText("Data");
  await expect(panel).toContainText("Roadway");
  await expect(panel).toContainText("Grading");
  await expect(panel).toContainText("Takeoff snapshot");

  await expect(panel.getByRole("button", { name: "Objects" })).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "Review" })).toHaveCount(0);
  await expect(panel.getByRole("button", { name: "Deliver" })).toHaveCount(0);
});
