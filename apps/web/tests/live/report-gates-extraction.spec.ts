import { expect, test } from "@playwright/test";

test("Report truth and review gates remain visible after extraction", async ({ page }) => {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=reports", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Truth gates", { timeout: 5_000 });
  await expect(panel).toContainText("Review gates");
  await expect(panel).toContainText("Engineer review");
  await expect(panel).toContainText("Professional review");
  await expect(panel).toContainText("Standards");
  await expect(panel).toContainText("Survey / control");
  await expect(panel).toContainText("Independent review");
});
