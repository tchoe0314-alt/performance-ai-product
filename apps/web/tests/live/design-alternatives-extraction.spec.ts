import { expect, test } from "@playwright/test";

test("Design alternatives panel remains reachable after extraction", async ({ page }) => {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=reports", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  const panel = page.getByTestId("workspace-right-panel");
  const alternatives = panel.getByTestId("design-alternatives-panel");
  await expect(alternatives).toBeVisible({ timeout: 5_000 });
  await expect(alternatives).toContainText("Design Alternatives");
  await expect(alternatives).toContainText("Review required");
  await expect(alternatives).toContainText("Options");
  await expect(alternatives).toContainText("Accepted inputs");
  await expect(alternatives.getByRole("button", { name: "Show 3 Options" })).toBeVisible();
  await expect(alternatives.getByRole("button", { name: "Compare" })).toBeDisabled();
  await expect(alternatives).toContainText(/concept alternatives|review only|review-required/i);
});
