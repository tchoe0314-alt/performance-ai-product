import { expect, test, type Page, type Route } from "@playwright/test";

const appUrl = process.env.CIVORA_APP_FLOW_URL ?? "/concepts/cul-de-sac.html";

async function setSlider(page: Page, selector: string, value: number) {
  await page.locator(selector).evaluate((element, nextValue) => {
    const input = element as HTMLInputElement;
    input.value = String(nextValue);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
}

async function delayedEngineeringResponse(route: Route, delayMs: number) {
  const state = route.request().postDataJSON() as {
    revision: number;
    building: { x: number; y: number; w: number; d: number };
  };
  await new Promise(resolve => setTimeout(resolve, delayMs));
  const collides = state.building.x <= 50 && state.building.x + state.building.w >= 50 &&
    state.building.y <= 20 && state.building.y + state.building.d >= -20;
  await route.fulfill({
    contentType: "application/json",
    json: {
      revision: state.revision,
      check: "analytic-pavement-and-island",
      issues: collides
        ? [{ code: "pavement_contact", objectIds: ["concept-road", "test-building"], message: "Building touches or overlaps the asphalt pavement boundary." }]
        : [],
    },
  }).catch(() => {
    // Rapid edits intentionally abort obsolete requests before they reach the server.
  });
}

test("Civora preserves engineering state through a complete interactive workflow", async ({ page }) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  let racing = false;

  page.on("console", message => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", error => pageErrors.push(error.message));

  await page.route("**/api/concepts/cul-de-sac/check", async route => {
    const requestState = route.request().postDataJSON() as { roadWidth?: number } | null;
    const width = requestState?.roadWidth;
    const delay = racing ? (width === 40 ? 40 : 650) : 250;
    await delayedEngineeringResponse(route, delay);
  });

  // 1. Initialization: use the explicit local integration server, not a hosted fallback.
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });
  const canvas = page.locator("canvas#plan");
  const status = page.locator("#calculationStatus");
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveAttribute("data-radius", "50");
  await expect(canvas).toHaveAttribute("data-road-width", "30");
  await expect(canvas).toHaveAttribute("data-revision", "0");
  await expect(status).toContainText(/recalculation required|checks remain unverified/i);
  await expect(status).toContainText(/checking current layout|engineering checks remain unverified/i);

  // 2. Parametric edit: stale state and revision must survive a responsive repaint.
  const initialRevision = Number(await canvas.getAttribute("data-revision"));
  await setSlider(page, "#width", 40);
  await expect(canvas).toHaveAttribute("data-road-width", "40");
  await expect(canvas).toHaveAttribute("data-stale", "true");
  await expect(status).toContainText(/recalculation required/i);
  const editedRevision = Number(await canvas.getAttribute("data-revision"));
  expect(editedRevision).toBeGreaterThan(initialRevision);

  await page.setViewportSize({ width: 820, height: 780 });
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveAttribute("data-road-width", "40");
  await expect(canvas).toHaveAttribute("data-revision", String(editedRevision));
  await expect(canvas).toHaveAttribute("data-stale", "true");
  await expect(status).toContainText(/recalculation required/i);
  await expect(canvas).toHaveAttribute("data-stale", "false");

  // 3. Collision is computed locally at once and remains authoritative across
  // an unrelated radius edit while server verification catches up.
  await setSlider(page, "#buildingX", 50);
  await setSlider(page, "#buildingY", 0);
  await expect(canvas).toHaveAttribute("data-pavement-conflict", "true");
  await expect(status).toHaveClass(/warning/);
  await expect(canvas).toHaveAttribute("data-stale", "false");
  await expect(status).toContainText(/touches or overlaps the asphalt pavement boundary/i);

  const redStrokePixels = await canvas.evaluate(element => {
    const context = (element as HTMLCanvasElement).getContext("2d", { willReadFrequently: true })!;
    const { data } = context.getImageData(0, 0, context.canvas.width, context.canvas.height);
    let matches = 0;
    for (let index = 0; index < data.length; index += 4) {
      if (Math.abs(data[index] - 197) <= 8 && Math.abs(data[index + 1] - 43) <= 8 && Math.abs(data[index + 2] - 53) <= 8 && data[index + 3] > 180) matches++;
    }
    return matches;
  });
  expect(redStrokePixels).toBeGreaterThan(0);

  await setSlider(page, "#radius", 51);
  await expect(canvas).toHaveAttribute("data-radius", "51");
  await expect(canvas).toHaveAttribute("data-pavement-conflict", "true");
  await expect(status).toHaveClass(/warning/);
  await expect(canvas).toHaveAttribute("data-stale", "false");
  await expect(status).toContainText(/touches or overlaps/i);

  // 4. Force several requests into flight. Earlier widths resolve after 40 ft,
  // proving abort/generation/revision guards reject obsolete responses.
  racing = true;
  for (const width of [31, 34, 37, 39, 40]) {
    await setSlider(page, "#width", width);
    await page.waitForTimeout(90);
  }
  const finalRaceRevision = Number(await canvas.getAttribute("data-revision"));
  await expect(canvas).toHaveAttribute("data-road-width", "40");
  await expect(page.locator("#width")).toHaveValue("40");
  await expect(canvas).toHaveAttribute("data-stale", "false");
  await page.waitForTimeout(800);
  await expect(canvas).toHaveAttribute("data-road-width", "40");
  await expect(canvas).toHaveAttribute("data-revision", String(finalRaceRevision));
  await expect(canvas).toHaveAttribute("data-pavement-conflict", "true");
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);

  // 5. Reset is idempotent for dimensions and must not erase an unresolved
  // building/road dependency. The building position is intentionally retained.
  racing = false;
  const reset = page.getByRole("button", { name: "Reset to 50 ft / 30 ft" });
  await reset.click();
  await expect(canvas).toHaveAttribute("data-radius", "50");
  await expect(canvas).toHaveAttribute("data-road-width", "30");
  await expect(canvas).toHaveAttribute("data-pavement-conflict", "true");
  await expect(canvas).toHaveAttribute("data-stale", "false");
  await expect(status).toHaveClass(/warning/);
  await expect(status).toContainText(/touches or overlaps/i);

  const resetRevision = await canvas.getAttribute("data-revision");
  await reset.click();
  await expect(canvas).toHaveAttribute("data-revision", resetRevision!);
  await expect(canvas).toHaveAttribute("data-pavement-conflict", "true");
  await expect(status).toContainText(/touches or overlaps/i);
});
