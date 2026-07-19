import { expect, test, type Page } from "@playwright/test";

async function openStandardsPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=standards", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Active criteria", { timeout: 5_000 });
  await expect(panel).toContainText("Standards source registry");
  return panel;
}

test("Standards panel remains reachable and links to source/review panels", async ({ page }) => {
  let panel = await openStandardsPanel(page);

  await expect(panel).toContainText("Min slope");
  await expect(panel).toContainText("Parking angle");
  await expect(panel).toContainText("Candidate standards review");

  await panel.getByRole("button", { name: "Source data" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Existing Conditions|Online Sources|Source/i);

  panel = await openStandardsPanel(page);
  await panel.getByRole("button", { name: "Review gates" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Reports|Capability|Review/i);
});
