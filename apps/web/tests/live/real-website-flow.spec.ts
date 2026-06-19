import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
}

async function visibleButtonCount(page: Page, name: RegExp | string) {
  const buttons = page.getByRole("button", { name });
  const count = await buttons.count();
  let visible = 0;
  for (let index = 0; index < count; index += 1) {
    if (await buttons.nth(index).isVisible()) visible += 1;
  }
  return visible;
}

async function timedOpen(page: Page, buttonName: RegExp | string, expectedPanelTitle: RegExp | string) {
  const start = Date.now();
  await page.getByRole("button", { name: buttonName }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expectedPanelTitle, { timeout: 4_000 });
  return Date.now() - start;
}

test.describe("real website workflow clarity", () => {
  test("uses one visible workflow home per major action and stays responsive", async ({ page }) => {
    await openDemoWorkspace(page);

    await expect(page.getByText("Quick actions")).toHaveCount(0);
    await expect(page.getByText("Generate Systems").first()).not.toBeVisible();
    await expect(page.getByText("Run engines with gates").first()).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Open canvas from sidebar" })).toHaveCount(1);
    expect(await visibleButtonCount(page, "Generate")).toBe(1);

    const objectOpenMs = await timedOpen(page, /^Objects$/, /Object manager|Objects/);
    const generateOpenMs = await timedOpen(page, "Generate", /Generate Systems/);
    const reviewOpenMs = await timedOpen(page, /^Review$/, /Review|Evidence|Issues/);

    expect(objectOpenMs).toBeLessThan(1_500);
    expect(generateOpenMs).toBeLessThan(1_500);
    expect(reviewOpenMs).toBeLessThan(1_500);

    await page.getByRole("button", { name: "Minimize Civora workspace controls" }).click();
    await expect(page.getByTestId("reopen-civora-workspace")).toBeVisible();
    await page.getByTestId("reopen-civora-workspace").click();
    await expect(page.getByRole("button", { name: "Minimize Civora workspace controls" })).toBeVisible();

    await page.getByRole("button", { name: /^Sections$/ }).click();
    await expect(page.locator(".civora-right-panel-sections")).toHaveAttribute("data-sections-collapsed", "true");
    await page.getByRole("button", { name: /^Expand$/ }).click();
    await expect(page.locator(".civora-right-panel-sections")).toHaveAttribute("data-sections-collapsed", "false");

    await page.getByRole("button", { name: "Hide left sidebar" }).click();
    await expect(page.getByRole("button", { name: "Show left sidebar" })).toBeVisible();
    expect(await visibleButtonCount(page, "Generate")).toBe(1);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
