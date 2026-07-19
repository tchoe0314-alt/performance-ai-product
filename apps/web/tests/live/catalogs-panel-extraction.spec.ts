import { expect, test, type Page } from "@playwright/test";

async function openCatalogsPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=catalogs", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Utility catalog manager", { timeout: 5_000 });
  await expect(panel).toContainText("Pipe material / size catalogs");
  await expect(panel).toContainText("Structures / valves / fittings");
  return panel;
}

test("Catalogs panel remains reachable and keeps review-source filtering", async ({ page }) => {
  const panel = await openCatalogsPanel(page);

  await expect(panel).toContainText("Catalog entries require explicit source and workspace review metadata");
  await expect(panel.getByRole("button", { name: "all" })).toBeVisible();
  await panel.getByRole("button", { name: "storm" }).click();
  await expect(panel.getByRole("button", { name: "storm" })).toHaveClass(/bg-slate-950/);
  await expect(panel).toContainText(/No pipe catalogs match this filter|storm|Source/i);

  await panel.getByRole("button", { name: "water" }).click();
  await expect(panel.getByRole("button", { name: "water" })).toHaveClass(/bg-slate-950/);
  await expect(panel).toContainText(/do not claim standards compliance/i);
});
