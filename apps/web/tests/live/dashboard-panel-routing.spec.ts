import { expect, test } from "@playwright/test";
import { sidePanelCopy } from "../../app/utils/workspaceShell";

// Route coverage is intentionally shallow; existing panel suites exercise actions.
// Check the body separately so a correct drawer title cannot hide missing content.
for (const [key, copy] of Object.entries(sidePanelCopy)) {
  test(`dashboard route ${key} renders its panel body`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: false, message: "Synthetic route test: no external data", projects: [], jobs: [] }),
      });
    });
    await page.goto(`/demo/workspace?debugPreview=1&debugPanel=${key}`, { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
    const drawer = page.getByTestId("workspace-right-panel");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText(copy.title, { exact: true }).first()).toBeVisible();
    const body = drawer.locator(".civora-right-panel-sections");
    await expect(body).toBeVisible();
    const content = body.locator(":scope > *").filter({
      hasNot: page.getByText("Discipline controls", { exact: true }),
    });
    await expect.poll(() => content.count()).toBeGreaterThan(0);
    await expect.poll(async () => (await content.allInnerTexts()).join(" ").trim().length).toBeGreaterThan(0);
    expect(errors).toEqual([]);
  });
}
