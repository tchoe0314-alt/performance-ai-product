import { expect, test } from "@playwright/test";

test("design state drives rendering and preserves engineering staleness", async ({ page }) => {
  await page.goto("/concepts/cul-de-sac.html");
  const canvas = page.locator("canvas");
  await expect(canvas).toHaveAttribute("data-stale", "false");
  await page.getByRole("slider", { name: /Approach road width/ }).focus();
  for (let i = 0; i < 10; i++) await page.keyboard.press("ArrowRight");
  await expect(canvas).toHaveAttribute("data-road-width", "40");
  await expect(canvas).toHaveAttribute("data-revision", "10");
  await expect(canvas).toHaveAttribute("data-stale", "true");
  await expect(page.locator("#calculationStatus")).toContainText("recalculation required");
  // A DOM-only change must not become a design change on repaint.
  await page.evaluate(() => {
    (document.getElementById("width") as HTMLInputElement).value = "20";
    (window as unknown as { renderSite: () => void }).renderSite();
  });
  await expect(page.locator("#width")).toHaveValue("40");
  await expect(canvas).toHaveAttribute("data-road-width", "40");
  await page.setViewportSize({ width: 700, height: 800 });
  await expect(canvas).toHaveAttribute("data-stale", "true");
  await expect(canvas).toHaveAttribute("data-revision", "10");
  await page.getByRole("slider", { name: /Bulb radius/ }).press("ArrowRight");
  await expect(canvas).toHaveAttribute("data-radius", "51");
  await expect(page.locator("#pavementValue")).toHaveText("36 ft");
  await page.getByRole("button", { name: "Reset to 50 ft / 30 ft" }).click();
  await expect(canvas).toHaveAttribute("data-radius", "50");
  await expect(canvas).toHaveAttribute("data-road-width", "30");
  await expect(canvas).toHaveAttribute("data-revision", "12");
  await expect(canvas).toHaveAttribute("data-stale", "true");
  await page.getByRole("button", { name: "Reset to 50 ft / 30 ft" }).click();
  await expect(canvas).toHaveAttribute("data-revision", "12");
});

test("cul-de-sac sliders preserve tangent pavement joins over their full ranges", async ({ page }, testInfo) => {
  await page.goto("/concepts/cul-de-sac.html");
  const canvas = page.locator("canvas");
  await expect(canvas).toHaveAttribute("data-radius", "50");
  await expect(canvas).toHaveAttribute("data-road-width", "30");
  const errors = await page.evaluate(() => {
    const calculate = (window as unknown as { geometry: (r: number, w: number) => {
      x: number; y: number; tx: number; ty: number; f: number; a: number;
    } }).geometry;
    const errors: string[] = [];
    for (let r = 35; r <= 80; r++) for (let w = 20; w <= 48; w++) {
      const g = calculate(r, w);
      // Shared tangency point lies on both circles; radii are collinear.
      const bulbError = Math.abs(Math.hypot(g.tx, g.ty) - r);
      const filletError = Math.abs(Math.hypot(g.tx - g.x, g.ty - g.y) - g.f);
      const cross = Math.abs(g.tx * (g.ty - g.y) - g.ty * (g.tx - g.x));
      const roadError = Math.abs(g.x - g.f - w / 2);
      if (![g.x, g.y, g.tx, g.ty].every(Number.isFinite) ||
          Math.max(bulbError, filletError, cross, roadError) > 1e-8) errors.push(`${r}/${w}`);
    }
    return errors;
  });
  expect(errors).toEqual([]);
  await page.getByRole("slider", { name: /Bulb radius/ }).press("End");
  await page.getByRole("slider", { name: /Approach road width/ }).press("End");
  await expect(canvas).toHaveAttribute("data-radius", "80");
  await expect(canvas).toHaveAttribute("data-road-width", "48");
  await page.getByRole("button", { name: "Reset to 50 ft / 30 ft" }).click();
  await expect(canvas).toHaveAttribute("data-radius", "50");
  await expect(canvas).toHaveAttribute("data-road-width", "30");
  await page.screenshot({ path: testInfo.outputPath("cul-de-sac.png"), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("slider", { name: /Bulb radius/ }).press("Home");
  await page.getByRole("slider", { name: /Approach road width/ }).press("End");
  await expect(canvas).toHaveAttribute("data-radius", "35");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const painted = await canvas.evaluate((element) => {
    const c = element as HTMLCanvasElement;
    const pixels = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
    return pixels.some((value, index) => index % 4 === 3 && value > 0);
  });
  expect(painted).toBe(true);
});
