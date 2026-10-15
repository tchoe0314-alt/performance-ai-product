import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { buildActiveBriefSummary } from "../../app/utils/activeBriefSummary";
import type { ProjectInput } from "../../app/types";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const row = (input: ProjectInput, id: string) => buildActiveBriefSummary(input).find(item => item.id === id)!;
const rectangle = { id: "site", name: "Site", type: "site", x: 0, y: 0, w: 435.6, d: 100, placed: true };

test("complete summary leaves absent requirements unknown without modifying inputs", () => {
  const input: ProjectInput = { manual_fields: { units: "ft" } };
  const before = JSON.stringify(input);
  const rows = buildActiveBriefSummary(input);
  expect(rows).toHaveLength(18);
  expect(new Set(rows.map(item => item.id)).size).toBe(18);
  expect(rows.filter(item => item.known).map(item => item.id)).toEqual(["protected"]);
  expect(row(input, "usable-acreage").value).toBe("Not set");
  expect(JSON.stringify(input)).toBe(before);
});

test("site outline overrides its bounding box and old source acreage", () => {
  const input: ProjectInput = { manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 1000, h: 1000 }, site_objects: [
    { ...rectangle, geometry_type: "polygon", geometry: [[0, 0], [435.6, 0], [0, 200]] },
  ] }, meta: { site_inputs: { site_boundary_acres: 999 } } };
  expect(row(input, "gross-acreage").value).toBe("1 ac");
  input.manual_fields!.site_objects![0].geometry![2] = [0, 400];
  expect(row(input, "gross-acreage").value).toBe("2 ac");
  expect(row(input, "usable-acreage").known).toBe(false);
});

test("invalid, ambiguous and unknown-unit boundaries do not produce acreage", () => {
  for (const input of [
    { manual_fields: { units: "yards", site_objects: [rectangle] } },
    { manual_fields: { units: "ft", site_objects: [rectangle, { ...rectangle, id: "site-two" }] } },
    { manual_fields: { units: "ft", site_objects: [{ ...rectangle, geometry_type: "polygon", geometry: [[0, 0], [20, 20], [0, 20], [20, 0]] }] } },
    { manual_fields: { units: "ft", lot: { x: 0, y: 0, w: Infinity, h: 100 } } },
  ] as ProjectInput[]) expect(row(input, "gross-acreage").known).toBe(false);
});

test("metric dimensions convert correctly without assuming missing units", () => {
  expect(row({ manual_fields: { units: "m", lot: { x: 0, y: 0, w: 100, h: 40.468564224 } } }, "gross-acreage").value).toBe("1 ac");
  expect(row({ manual_fields: { lot: { x: 0, y: 0, w: 435.6, h: 100 } } }, "gross-acreage").known).toBe(false);
});

test("program targets are distinct from drawn results and blank controls stay unknown", () => {
  const input: ProjectInput = { manual_fields: { units: "ft", site_plan: { building_program_sf: 28000, building_type: "office", parking_count: 140 }, setback: 0 }, meta: { edit_controls_v1: { parkingCount: "" } } };
  expect(row(input, "building-area").value).toBe("28,000 sf");
  expect(row(input, "building-use").value).toBe("office");
  expect(row(input, "required-parking").known).toBe(false);
  expect(row(input, "setbacks").value).toBe("0 ft");
  input.meta!.edit_controls_v1 = { parkingCount: "0" };
  expect(row(input, "required-parking").value).toBe("0 spaces");
  input.meta!.edit_controls_v1 = { parkingCount: "12.5" };
  expect(row(input, "required-parking").known).toBe(false);
});

test("lists fixed and existing geometry without treating hidden objects as unprotected", () => {
  const input: ProjectInput = { manual_fields: { site_objects: [
    { ...rectangle, type: "building", name: "Fixed office", locked: true, meta: { ui_hidden: true } },
    { ...rectangle, id: "existing", type: "road", name: "Existing road", source: "detected_from_gis" },
    { ...rectangle, id: "pending", name: "Pending", locked: true, placed: false },
  ] } };
  expect(row(input, "protected").value).toBe("Fixed office, Existing road");
});

test("saved program fallback preserves explicit targets but never restores stale geometry or overrides live values", () => {
  const saved: ProjectInput = { manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 1000, h: 1000 }, site_plan: { building_program_sf: 28000, building_type: "office", parking_count: 999 } } };
  const live: ProjectInput = { manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 435.6, h: 100 } }, meta: { edit_controls_v1: { parkingCount: "140" } } };
  const rows = buildActiveBriefSummary(live, saved);
  expect(rows.find(item => item.id === "building-area")!.value).toBe("28,000 sf");
  expect(rows.find(item => item.id === "gross-acreage")!.value).toBe("1 ac");
  expect(rows.find(item => item.id === "required-parking")!.value).toBe("140 spaces");
  live.manual_fields!.site_plan = { building_program_sf: 0, building_type: "" };
  expect(buildActiveBriefSummary(live, saved).filter(item => ["building-area", "building-use"].includes(item.id)).every(item => !item.known)).toBe(true);
});

for (const [width, height] of [[320, 568], [844, 390], [1280, 720]]) {
  test(`brief summary is reachable, read-only and contained at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    const writes: string[] = [];
    page.on("request", request => { if (/\/api\/projects(?:\/|$)/.test(new URL(request.url()).pathname) && ["POST", "PUT", "DELETE", "PATCH"].includes(request.method())) writes.push(request.url()); });
    await page.goto("/demo/workspace?debugPreview=1&seedDemo=1");
    await openWorkspaceTool(page, "Setup");
    const summary = page.getByTestId("active-brief-summary");
    await expect(summary).toBeVisible();
    await expect(summary.getByTestId("brief-value-gross-acreage")).toContainText("16.07 ac");
    await summary.locator(":scope > details > summary").click();
    await expect(summary.locator("dt")).toHaveCount(18);
    await expect(summary.getByTestId("brief-value-usable-acreage")).toContainText("Not set");
    await expect(summary.locator("input, textarea")).toHaveCount(0);
    expect(await summary.evaluate(element => element.scrollWidth - element.clientWidth)).toBeLessThanOrEqual(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    const violations = (await new AxeBuilder({ page }).include('[data-testid="active-brief-summary"]').analyze()).violations;
    expect(violations.filter(item => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
    await page.screenshot({ path: test.info().outputPath(`brief-${width}.png`) });
    await page.reload();
    await openWorkspaceTool(page, "Setup");
    await expect(page.getByTestId("active-brief-summary")).toBeVisible();
    expect(writes).toEqual([]);
  });
}

test("live dimensions update both brief views without creating a second state store", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1&chat230EmptyObjects=1");
  await openWorkspaceTool(page, "Setup");
  const summary = page.getByTestId("active-brief-summary");
  await expect(summary.getByTestId("brief-value-gross-acreage")).toContainText("16.07 ac");
  const boundary = page.getByTestId("setup-site-box-controls");
  if (!(await boundary.evaluate(element => element.hasAttribute("open")))) await boundary.locator("summary").click();
  const width = boundary.getByRole("spinbutton", { name: /Width \(ft\)/ });
  if (await width.isDisabled()) await page.getByTestId("create-centered-site-button").click();
  await width.fill("435.6");
  await boundary.getByRole("spinbutton", { name: /Depth \(ft\)/ }).fill("100");
  await expect(summary.getByTestId("brief-value-gross-acreage")).toContainText("1 ac");
  const controls = page.getByTestId("workspace-layout-controls");
  await controls.locator("summary").click();
  await page.getByLabel("Workspace mode", { exact: true }).selectOption("professional");
  const docked = page.getByTestId("active-brief-summary-docked");
  await expect(docked).toBeVisible();
  await expect(docked.getByTestId("brief-value-gross-acreage")).toContainText("1 ac");
  await controls.locator("summary").click();
  await page.getByTestId("workspace-brief-chat").getByRole("button", { name: "Edit brief", exact: true }).click();
  await expect(summary).toBeVisible();
  await boundary.getByRole("spinbutton", { name: /Width \(ft\)/ }).fill("871.2");
  await expect(summary.getByTestId("brief-value-gross-acreage")).toContainText("2 ac");
  await expect(docked.getByTestId("brief-value-gross-acreage")).toContainText("2 ac");
});
