import { expect, test } from "@playwright/test";

for (const width of [375, 768, 1024, 1280, 1440]) {
  test(`Deliver controls fit their panel at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/demo/workspace?seedDemo=1&aiRealismProvider=mock");
    await page.getByRole("button", { name: "Deliver", exact: true }).click();
    const panel = page.getByTestId("workspace-right-panel");
    await expect(panel).toBeVisible();
    const exports = page.getByTestId("deliver-export-actions");
    const actions = exports.locator("button").filter({ hasText: /^(Review PDF|DXF|Report|Quantities)$/ });
    await expect(actions).toHaveCount(4);
    await expect.poll(() => actions.evaluateAll(buttons => buttons.map(button => {
      const box = button.getBoundingClientRect();
      const parent = button.closest('[data-testid="workspace-right-panel"]')!.getBoundingClientRect();
      return { label: button.textContent?.trim(), fits: button.scrollWidth <= button.clientWidth + 1,
        contained: box.left >= parent.left && box.right <= parent.right };
    }).filter(button => !button.fits || !button.contained)), { timeout: 3000 }).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    if (width < 640) {
      const input = page.getByTestId("civora-command-input");
      await expect(input).toBeVisible();
      await expect.poll(() => input.evaluate(node => node.scrollHeight <= node.clientHeight + 1)).toBe(true);
      await expect.poll(async () => {
        const drawer = await panel.boundingBox();
        const dock = await page.getByTestId("floating-command-bar").boundingBox();
        return Boolean(drawer && dock && drawer.y + drawer.height <= dock.y);
      }).toBe(true);
    }
    await page.screenshot({ path: test.info().outputPath(`deliver-${width}.png`) });
  });

  test(`Draw layer controls fit their cards at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/demo/workspace?seedDemo=1&aiRealismProvider=mock");
    await page.getByRole("button", { name: "Draw", exact: true }).click();
    const layers = page.getByTestId("object-manager-layers");
    await layers.locator(":scope > summary").click();
    const actions = layers.getByTestId("object-manager-layer-select");
    await expect(actions.first()).toBeVisible();
    await expect.poll(() => actions.evaluateAll(buttons => buttons.filter(button => button.scrollWidth > button.clientWidth + 1)
      .map(button => button.textContent?.trim())), { timeout: 3000 }).toEqual([]);
    await page.screenshot({ path: test.info().outputPath(`draw-${width}.png`) });
  });
}
