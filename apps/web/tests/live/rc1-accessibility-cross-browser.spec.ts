import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";


async function openFreshWorkspace(page: Page) {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto(`/demo/workspace?debugPreview=1&seedDemo=0&rc1=${Date.now()}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const projects = page.getByRole("button", { name: "Projects" }).filter({ visible: true }).first();
  await projects.click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible();
  await page.getByRole("button", { name: "New Project" }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("site-status")).toContainText("Site Editable");
  return {
    assertClean() {
      expect(pageErrors).toEqual([]);
      expect(consoleErrors.filter((line) => !/401|api\/auth|favicon|ERR_CONNECTION_REFUSED/i.test(line))).toEqual([]);
    },
  };
}

async function openPanel(page: Page, name: RegExp | string) {
  const showSidebar = page.getByRole("button", { name: "Show left sidebar" });
  if (await showSidebar.isVisible().catch(() => false)) await showSidebar.click();
  await page.getByRole("button", { name }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
}

test.describe("RC1 accessibility and browser/device contract", () => {
  test("fresh-project shell has no serious WCAG violations and all visible buttons are named", async ({ page }) => {
    const runtime = await openFreshWorkspace(page);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    const serious = results.violations.filter((item) => item.impact === "serious" || item.impact === "critical");
    expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);

    const unnamed = await page.locator("button:visible").evaluateAll((buttons) =>
      buttons.flatMap((button) => {
        const name =
          button.getAttribute("aria-label")?.trim() ||
          button.getAttribute("title")?.trim() ||
          (button.textContent || "").trim();
        return name ? [] : [button.outerHTML.slice(0, 240)];
      }),
    );
    expect(unnamed).toEqual([]);
    runtime.assertClean();
  });

  test("keyboard and touch-sized navigation reaches the one natural home for core actions", async ({ page, isMobile }) => {
    const runtime = await openFreshWorkspace(page);
    const help = page.getByRole("button", { name: "Help" }).filter({ visible: true }).first();
    await expect(help).toBeVisible();
    await help.click();
    await expect(page.getByTestId("civora-trust-panel")).toBeVisible();
    await page.getByTestId("support-summary").click();
    await expect(page.getByLabel("What happened?")).toBeVisible();
    await page.getByTestId("account-data-summary").click();
    await expect(page.getByRole("button", { name: "Download my data" })).toBeVisible();
    await page.getByRole("button", { name: "Minimize" }).click();

    await openPanel(page, /^Draw$/);
    await expect(page.getByRole("button", { name: "Select and edit objects" })).toBeVisible();
    await page.getByRole("button", { name: "Select and edit objects" }).focus();
    await page.keyboard.press("Tab");
    const focusedName = await page.evaluate(() => {
      const element = document.activeElement as HTMLElement | null;
      return element?.getAttribute("aria-label") || element?.getAttribute("title") || element?.textContent || "";
    });
    expect(focusedName.trim()).not.toBe("");
    await page.keyboard.press("Escape");

    const targets = await page.locator("button:visible").evaluateAll((buttons) =>
      buttons.flatMap((button) => {
        const rect = button.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return [];
        const name = button.getAttribute("aria-label") || button.textContent || "button";
        const tooSmall = rect.width < 24 || rect.height < 24;
        return tooSmall ? [{ name: name.trim(), width: rect.width, height: rect.height }] : [];
      }),
    );
    expect(targets, JSON.stringify(targets, null, 2)).toEqual([]);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(await page.getByTestId("workspace-canvas-shell").count()).toBe(1);
    if (isMobile) {
      await expect(page.getByTestId("header-chat-button-mobile")).toBeVisible();
      await expect(page.getByTestId("header-projects-button-mobile")).toBeVisible();
    }
    runtime.assertClean();
  });
});
