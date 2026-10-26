import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const css = readFileSync(path.join(__dirname, "../../app/globals.css"), "utf8");

test("panels fade without sliding and stay hidden with reduced motion", async ({ page }) => {
  await page.setContent('<aside class="civora-motion-right-panel" data-motion-state="closed" inert><button>Hidden control</button></aside>');
  await page.addStyleTag({ content: css });
  const panel = page.locator("aside");
  await expect(panel).toHaveCSS("opacity", "0");
  await expect(panel).toHaveCSS("transform", "none");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(panel).toHaveCSS("opacity", "0");
  await expect(panel).toHaveCSS("transition-duration", "0s");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Hidden control", includeHidden: true })).not.toBeFocused();
});

test("dialog opens and closes with opacity transitions only", async ({ page }) => {
  await page.setContent('<dialog class="civora-dialog"><button>Continue</button></dialog>');
  await page.addStyleTag({ content: css });
  await page.locator("dialog").evaluate((element: HTMLDialogElement) => element.showModal());
  await expect(page.locator("dialog")).toHaveCSS("opacity", "1");
  await expect(page.locator("dialog")).toHaveCSS("transform", "none");
  await page.locator("dialog").evaluate((element: HTMLDialogElement) => element.close());
  await expect(page.locator("dialog")).toHaveCSS("opacity", "0");
  await expect(page.locator("dialog")).not.toBeVisible();
});
