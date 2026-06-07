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

  await page.goto(`${baseURL}/?demo=1`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByRole("banner").getByRole("button", { name: "Dashboard" }).click();
  const rightPanel = page.getByTestId("workspace-right-panel");
  await expect(rightPanel.getByText("Onboarding checklist")).toBeVisible();
  await expect(rightPanel.getByText("What do statuses mean?")).toBeVisible();
  await expect(rightPanel.getByText("Report issue")).toBeVisible();
  await rightPanel.getByText("Report issue", { exact: true }).click();
  await expect(rightPanel.getByText("Diagnostic summary", { exact: true })).toBeVisible();
  await expect(rightPanel.getByText("Pilot docs")).toBeVisible();

  await page.locator("button").filter({ hasText: "Deliver" }).filter({ hasText: "Sheets and exports" }).first().click();
  await expect(rightPanel.getByText("What is the review package?")).toBeVisible();
  await expect(rightPanel.getByText("External licensed engineer approval is required")).toBeVisible();
});
