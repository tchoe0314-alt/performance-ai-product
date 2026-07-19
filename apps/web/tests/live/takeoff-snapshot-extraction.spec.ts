import { expect, test } from "@playwright/test";

test("Dashboard takeoff snapshot remains reachable after extraction", async ({ page }) => {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=dashboard", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Takeoff snapshot", { timeout: 5_000 });
  await expect(panel).toContainText(/Run systems to populate quantities|Mapped|Review|Missing cost|Untraced/i);
});
