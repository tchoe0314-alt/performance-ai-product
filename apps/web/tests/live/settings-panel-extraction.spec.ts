import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
}

async function openSettingsPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Workspace settings", { timeout: 5_000 });
  await expect(panel).toContainText("Run defaults");
  return panel;
}

test("Settings panel remains functional after component extraction", async ({ page }) => {
  await openDemoWorkspace(page);

  let panel = await openSettingsPanel(page);
  await expect(panel).toContainText("Appearance");
  await expect(panel).toContainText("AI behavior");

  const roadsToggle = panel.getByLabel("Roads");
  await expect(roadsToggle).toBeVisible();
  const initialRoadsValue = await roadsToggle.isChecked();
  await roadsToggle.click();
  await expect(roadsToggle).toBeChecked({ checked: !initialRoadsValue });

  await panel.getByRole("button", { name: "Standards" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Standards source registry");

  panel = await openSettingsPanel(page);
  await panel.getByRole("button", { name: "Export settings" }).click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Deliver|Plan Sheets|Make Review Package/i);
});
