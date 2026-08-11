import { expect, test } from "@playwright/test";

test("setup opens clean sections and direct setup actions", async ({ page, baseURL }) => {
  test.skip(!baseURL, "PLAYWRIGHT_BASE_URL is required.");

  await page.goto(`${baseURL!.replace(/\/+$/, "")}/demo/workspace?debugPreview=1`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Setup" }).first().click();

  await expect(page.getByTestId("setup-wizard-sidebar-card")).toHaveCount(0);
  await expect(page.getByTestId("setup-address-truth")).toContainText("Address / Location");
  await expect(page.getByTestId("setup-site-box-controls")).toContainText("Site Boundary");
  await expect(page.getByTestId("setup-survey-terrain-card")).toContainText("Survey / Terrain / Sources");
  await expect(page.getByTestId("setup-detect-inside-site")).toContainText("Site Context");
  await expect(
    page.getByRole("button", { name: /Apply Address|Start a blank site|Draw Site Boundary|Detect again/i }).first(),
  ).toBeVisible();
});
