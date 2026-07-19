import { expect, test, type Page } from "@playwright/test";

async function openLibrariesPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=libraries", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Buildings & Program", { timeout: 5_000 });
  await expect(panel).toContainText("Access & Parking");
  await expect(panel).toContainText("Drainage & Water");
  return panel;
}

test("Libraries panel remains reachable and can add an object", async ({ page }) => {
  const panel = await openLibrariesPanel(page);

  await panel.getByRole("button", { name: "Office Building" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Office Building|Needs placement/i, { timeout: 5_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Office Building|Add objects|Place/i);
});
