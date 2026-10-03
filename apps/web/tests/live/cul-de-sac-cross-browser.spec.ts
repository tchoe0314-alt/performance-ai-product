import { chromium, firefox, webkit, expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import path from "node:path";

for (const [name, engine, mobile] of [
  ["Chrome", chromium, false], ["Firefox", firefox, false], ["Safari", webkit, false],
  ["mobile Chrome", chromium, true], ["mobile Safari", webkit, true],
] as const) {
  test(`isolated editor works in ${name}`, async ({ baseURL }) => {
    let browser;
    try { browser = await engine.launch({ timeout: 15000 }); }
    catch (error) {
      const message = String(error);
      if (name === "Firefox" && /RenderCompositorSWGL|sandbox_extension_issue_file_to_process/.test(message)) {
        test.skip(true, "Local Firefox cannot start its graphics/content process; this browser remains unverified.");
        return;
      }
      throw error;
    }
    try {
      const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1280, height: 800 }, hasTouch: mobile });
      const page = await context.newPage();
      const errors: string[] = [];
      page.on("pageerror", e => errors.push(e.message));
      await page.goto(`${baseURL}/concepts/cul-de-sac.html`);
      await expect(page.locator("canvas")).toHaveAttribute("data-stale", "false");
      await page.getByRole("slider", { name: /Approach road width/ }).press("ArrowRight");
      await expect(page.locator("canvas")).toHaveAttribute("data-road-width", "31");
      // This scenario verifies a completed calculation and persisted layout.
      // Width rendering is immediate; server calculation completion is not.
      await expect(page.locator("canvas")).toHaveAttribute("data-stale", "false");
      await page.getByRole("button", { name: "Save on this device" }).click();
      await page.reload();
      await expect(page.locator("canvas")).toHaveAttribute("data-road-width", "31");
      await expect(page.locator("canvas")).toHaveAttribute("data-stale", "false");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      expect(errors).toEqual([]);
    } finally { await browser.close(); }
  });
}

test("standalone file has working geometry and device persistence without a server", async ({ browser }) => {
  const page = await browser.newPage();
  try {
    await page.goto(`file://${path.resolve("public/concepts/cul-de-sac.html")}`);
    await expect(page.locator("#calculationStatus")).toContainText("standalone mode");
    await page.getByRole("slider", { name: /Approach road width/ }).press("ArrowRight");
    await expect(page.locator("canvas")).toHaveAttribute("data-road-width", "31");
    await page.getByRole("button", { name: "Save on this device" }).click();
    await page.reload();
    await expect(page.locator("canvas")).toHaveAttribute("data-road-width", "31");
    await expect(page.locator("#calculationStatus")).toContainText("standalone mode");
  } finally { await page.close(); }
});
