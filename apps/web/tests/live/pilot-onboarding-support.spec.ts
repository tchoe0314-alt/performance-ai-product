import { expect, test } from "@playwright/test";

test("pilot onboarding and support surfaces render", async ({ page, baseURL }) => {
  test.skip(!baseURL, "PLAYWRIGHT_BASE_URL is required.");

  await page.goto(baseURL!, { waitUntil: "domcontentloaded" });
  await expect(page.getByText("private-pilot planning and review workspace")).toBeVisible();
  await expect(page.getByRole("link", { name: "Pilot limits" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Responsibility" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Support" })).toBeVisible();

  await page.goto(`${baseURL}/pilot`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Civora Pilot Onboarding And Support" })).toBeVisible();
  await expect(page.locator("#onboarding")).toBeVisible();
  await expect(page.locator("#limitations")).toBeVisible();
  await expect(page.locator("#operations")).toBeVisible();
  await expect(page.locator("#responsibility")).toBeVisible();

  await page.goto(`${baseURL}/demo/workspace?debugPreview=1&debugPanel=dashboard`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  const rightPanel = page.getByTestId("workspace-right-panel");
  await expect(rightPanel.getByText("Onboarding checklist")).toHaveCount(0);
  await expect(rightPanel.getByText("What do statuses mean?")).toHaveCount(0);
  await expect(rightPanel.getByText("Report issue")).toBeVisible();
  await rightPanel.getByText("Report issue", { exact: true }).click();
  await expect(rightPanel.getByText("Diagnostic summary", { exact: true })).toBeVisible();

  await page.getByTestId("primary-workflow-sidebar").getByRole("button", { name: /^Deliver\b/i }).click();
  await expect(page.getByTestId("deliver-review-package-flow")).toContainText(/Make a review package/i);
  await expect(page.getByTestId("deliver-review-package-flow").getByText("Review-only and engineer-review-required.")).toHaveCount(0);
});
