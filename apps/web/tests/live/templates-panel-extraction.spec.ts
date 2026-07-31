import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
}

test("Templates panel remains reachable after component extraction", async ({ page }) => {
  await openDemoWorkspace(page);

  await page.getByRole("button", { name: /^Setup$/ }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Setup|Address \/ Location|Site Boundary/);

  const sources = page.getByTestId("setup-survey-terrain-card");
  if (!(await sources.evaluate((element) => element.hasAttribute("open")))) {
    await sources.locator(":scope > summary").click();
  }
  await sources.getByRole("button", { name: /^Import$/ }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Import inputs");

  await page.getByRole("button", { name: "Plan PDF" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Source hub");

  const sourceTools = page.getByText("Detailed source evidence and import tools").locator("xpath=ancestor::details[1]");
  if (!(await sourceTools.evaluate((element) => element.hasAttribute("open")))) {
    await sourceTools.locator(":scope > summary").click();
  }
  await sourceTools.getByRole("button", { name: "Templates" }).click();

  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Firm template registry");
  await expect(panel).toContainText("Registered templates");
  await expect(panel).toContainText(/Templates not loaded|Sign in to load templates|Loaded|Review/i);
  await expect(panel.getByRole("button", { name: "Use Company Template" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Export JSON" })).toBeVisible();
});
