import { expect, test, type Page } from "@playwright/test";
import type { ConceptLayout } from "../../app/utils/culDeSacConcept";
import { defaultLayout } from "../../app/utils/culDeSacConcept";

const storageKey = "civora.cul-de-sac-study.v1";
async function layout(page: Page) {
  return page.evaluate(() => (window as unknown as { designSnapshot: () => ConceptLayout }).designSnapshot());
}
async function screenPoint(page: Page, x: number, y: number) {
  await page.locator("canvas").scrollIntoViewIfNeeded();
  return page.evaluate(({ x, y }) => {
    const w = window as unknown as { worldToCanvas: (p: { x: number; y: number }) => { x: number; y: number } };
    const rect = document.querySelector("canvas")!.getBoundingClientRect();
    const p = w.worldToCanvas({ x, y });
    return { x: p.x + rect.left, y: p.y + rect.top };
  }, { x, y });
}
async function dragObject(page: Page, from: [number, number], to: [number, number]) {
  const start = await screenPoint(page, ...from), end = await screenPoint(page, ...to);
  await page.mouse.move(start.x, start.y); await page.mouse.down();
  await page.mouse.move(end.x, end.y, { steps: 8 }); await page.mouse.up();
}
async function setSlider(page: Page, id: string, value: number) {
  await page.locator(`#${id}`).evaluate((el, value) => {
    (el as HTMLInputElement).value = String(value); el.dispatchEvent(new Event("input", { bubbles: true }));
  }, value);
}

test("road and building drag independently with grouped undo/redo", async ({ page }) => {
  await page.goto("/concepts/cul-de-sac.html");
  await dragObject(page, [70, 10], [50, 50]);
  let s = await layout(page);
  expect(s.building.x).toBeCloseTo(40, 1); expect(s.building.y).toBeCloseTo(40, 1);
  expect(s.position).toEqual({ x: 0, y: 0 });
  await expect(page.locator("#calculationStatus")).toContainText("No pavement or island contact");
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  expect((await layout(page)).building).toEqual(defaultLayout().building);
  await expect(page.getByRole("button", { name: "Undo", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Redo", exact: true }).click();
  expect((await layout(page)).building.x).toBeCloseTo(40, 1);
  await dragObject(page, [0, 0], [10, -10]);
  s = await layout(page);
  expect(s.position.x).toBeCloseTo(10, 1); expect(s.position.y).toBeCloseTo(-10, 1);
  expect(s.building.x).toBeCloseTo(40, 1);
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  expect((await layout(page)).position).toEqual({ x: 0, y: 0 });
  await setSlider(page, "width", 40);
  await expect(page.getByRole("button", { name: "Redo", exact: true })).toBeDisabled();
});

test("cancelled drag restores the starting layout and does not add history", async ({ page }) => {
  await page.goto("/concepts/cul-de-sac.html");
  const start = await screenPoint(page, 70, 10), end = await screenPoint(page, 40, 10);
  await page.mouse.move(start.x, start.y); await page.mouse.down(); await page.mouse.move(end.x, end.y);
  await page.locator("canvas").dispatchEvent("pointercancel", { pointerId: 1, pointerType: "mouse" });
  await page.mouse.up();
  expect(await layout(page)).toEqual(defaultLayout());
  await expect(page.getByRole("button", { name: "Undo", exact: true })).toBeDisabled();
});

test("device save restores exact fractional positions and drawing after reload", async ({ page }) => {
  await page.goto("/concepts/cul-de-sac.html");
  await setSlider(page, "width", 40); await setSlider(page, "roadX", 12.25); await setSlider(page, "roadY", -4.5);
  await setSlider(page, "buildingX", 65.125);
  await expect(page.locator("canvas")).toHaveAttribute("data-stale", "false");
  const before = await layout(page);
  const image = await page.locator("canvas").screenshot();
  await page.getByRole("button", { name: "Save on this device" }).click();
  const saved = await page.evaluate(key => localStorage.getItem(key), storageKey);
  expect(JSON.parse(saved!)).toEqual(before); expect(saved).not.toContain("isStale");
  await page.reload();
  await expect(page.locator("#storageStatus")).toContainText("Restored device-saved study");
  await expect(page.locator("canvas")).toHaveAttribute("data-stale", "false");
  expect(await layout(page)).toEqual(before);
  expect(await page.locator("canvas").screenshot()).toEqual(image);
});

test("export/import round trips and rejects malformed or oversized JSON without mutation", async ({ page }) => {
  await page.goto("/concepts/cul-de-sac.html");
  await setSlider(page, "radius", 62);
  const before = await layout(page);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON" }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream();
  const chunks = []; for await (const chunk of stream!) chunks.push(chunk);
  const json = Buffer.concat(chunks).toString("utf8");
  expect(JSON.parse(json)).toEqual(before);
  await setSlider(page, "radius", 40);
  await page.locator("#fileInput").setInputFiles({ name: "study.json", mimeType: "application/json", buffer: Buffer.from(json) });
  await expect(page.locator("#storageStatus")).toContainText("JSON imported");
  expect(await layout(page)).toEqual(before);
  for (const bad of ["{", JSON.stringify({ ...before, units: "m" }), "x".repeat(8193)]) {
    await page.locator("#fileInput").setInputFiles({ name: "invalid.json", mimeType: "application/json", buffer: Buffer.from(bad) });
    await expect(page.locator("#storageStatus")).toContainText("Import rejected");
    expect(await layout(page)).toEqual(before);
  }
});

test("storage errors and corrupt saved data do not overwrite user data", async ({ page }) => {
  await page.addInitScript(key => {
    localStorage.setItem(key, "broken saved study");
    Storage.prototype.setItem = () => { throw new Error("Storage unavailable"); };
  }, storageKey);
  await page.goto("/concepts/cul-de-sac.html");
  await expect(page.locator("#storageStatus")).toContainText("not overwritten");
  expect(await layout(page)).toEqual(defaultLayout());
  await page.getByRole("button", { name: "Save on this device" }).click();
  await expect(page.locator("#storageStatus")).toContainText("storage unavailable");
  expect(await page.evaluate(key => localStorage.getItem(key), storageKey)).toBe("broken saved study");
});

test("geometry retry recovers after a failed server check", async ({ page }) => {
  let fail = true;
  await page.route("**/api/concepts/cul-de-sac/check", route => fail ? route.abort() : route.continue());
  await page.goto("/concepts/cul-de-sac.html");
  await expect(page.locator("#calculationStatus")).toContainText("results stale");
  fail = false;
  await page.getByRole("button", { name: "Recheck geometry" }).click();
  await expect(page.locator("canvas")).toHaveAttribute("data-stale", "false");
  await expect(page.locator("#calculationStatus")).toContainText("No pavement or island contact");
});

test("road widening updates current contact warnings immediately", async ({ page }) => {
  await page.goto("/concepts/cul-de-sac.html");
  await setSlider(page, "buildingX", 18); await setSlider(page, "buildingY", 100);
  await expect(page.locator("#calculationStatus")).toContainText("No pavement or island contact");
  await setSlider(page, "width", 40);
  await expect(page.locator("canvas")).toHaveAttribute("data-pavement-conflict", "true");
  await expect(page.locator("#calculationStatus")).toContainText("Building touches or overlaps the asphalt");
  await setSlider(page, "width", 30);
  await expect(page.locator("canvas")).toHaveAttribute("data-pavement-conflict", "false");
  await expect(page.locator("#calculationStatus")).toContainText("No pavement or island contact");
});

test("layout API rejects invalid and oversized requests without accepting cached checks", async ({ request }) => {
  for (const data of [null, { ...defaultLayout(), revision: -1 }, { ...defaultLayout(), units: "m", revision: 0 },
    { ...defaultLayout(), roadWidth: 500, revision: 0 }, { padding: "x".repeat(8193) }]) {
    expect((await request.post("/api/concepts/cul-de-sac/check", { data })).status()).toBe(400);
  }
  const response = await request.post("/api/concepts/cul-de-sac/check", { data: { ...defaultLayout(), revision: 99, isStale: false, issues: ["fake conflict"] } });
  expect(response.status()).toBe(200);
  expect(response.headers()["cache-control"]).toBe("no-store");
  expect(await response.json()).toEqual({ revision: 99, issues: [], check: "analytic-pavement-and-island" });
});

test("touch drag uses pointer capture and updates world coordinates", async ({ browser }) => {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  try {
    await page.goto(`${test.info().project.use.baseURL}/concepts/cul-de-sac.html`);
    const start = await screenPoint(page, 70, 10), end = await screenPoint(page, 40, 10);
    const session = await page.context().newCDPSession(page);
    await session.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: start.x, y: start.y }] });
    await session.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: end.x, y: end.y }] });
    await session.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    expect((await layout(page)).building.x).toBeCloseTo(30, 1);
    await expect(page.locator("#calculationStatus")).toContainText("Building touches or overlaps the asphalt");
  } finally { await page.close(); }
});
