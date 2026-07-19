import { expect, test, type Page } from "@playwright/test";

async function openQuantitiesPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=quantities", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Quantity takeoff", { timeout: 5_000 });
  await expect(panel).toContainText("Traceable canonical quantities");
  return panel;
}

test("Quantities panel remains reachable and keeps review export state", async ({ page }) => {
  const panel = await openQuantitiesPanel(page);

  await expect(panel).toContainText("Rows");
  await expect(panel).toContainText("Missing cost");
  await expect(panel).toContainText("Untraced");
  await expect(panel).toContainText("Deltas");
  await expect(panel.getByRole("button", { name: "Export report" })).toBeDisabled();
  await expect(panel).toContainText("Run systems to populate quantities.");
});
