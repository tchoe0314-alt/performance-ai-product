import { expect, test } from "@playwright/test";
import { reviewSheetGeometry } from "../../app/utils/reviewSheetGeometry";
import type { BuildingPlacement } from "../../app/types";
import { defaultLayout } from "../../app/utils/culDeSacConcept";

test("empty review sheets never substitute an illustrative project", async ({ page }) => {
  await page.route("**/api/**", route => route.fulfill({ json: { success: true } }));
  await page.goto("/demo/workspace?debugPreview=1&chat230EmptyObjects=1&debugPanel=libraries");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByRole("button", { name: "Deliver", exact: true }).first().click();
  const details = page.getByTestId("deliver-review-sheet-preview");
  await details.locator("summary").click();
  const sheet = page.getByTestId("civil-review-sheet-preview");
  await expect(sheet).toContainText("No placed project objects");
  await expect(page.getByTestId("civil-review-sheet-plan-object")).toHaveCount(0);
});

test("small review sheets show only the imported project's objects", async ({ page }) => {
  await page.route("**/api/**", route => route.fulfill({ json: { success: true } }));
  await page.goto("/demo/workspace?debugPreview=1&chat230EmptyObjects=1&debugPanel=libraries");
  await page.getByLabel("Import cul-de-sac study into project").setInputFiles({ name: "small-fixture.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(defaultLayout())) });
  await page.getByRole("button", { name: "Deliver", exact: true }).first().click();
  await page.getByTestId("deliver-review-sheet-preview").locator("summary").click();
  await expect(page.getByTestId("civil-review-sheet-plan-object")).toHaveCount(2);
  await expect(page.getByTestId("civil-review-sheet-preview")).toContainText("Imported study building");
  await expect(page.getByTestId("civil-review-sheet-preview")).not.toContainText(/CONDOMINIUM|MATCH SHEET|22\.5/);
  await expect(page.getByTestId("civil-review-sheet-dense-plan")).toHaveCount(0);
});

test("review sheet preserves rotations, routes, out-of-site geometry and source state", () => {
  const objects: BuildingPlacement[] = [
    { id: "rotated", label: "Rotated", type: "building", x: -50, y: 100, w: 100, d: 50, rotation: 90, placed: true },
    { id: "pipe", label: "Pipe", type: "utility_corridor", x: 10, y: 20, w: 30, d: 40, geometryType: "polyline", geometry: [[10, 20], [40, 60]], placed: true },
  ];
  const before = JSON.stringify(objects);
  const result = reviewSheetGeometry(objects, 600, 500);
  expect(result.objects[0].points[0][0]).toBeCloseTo(25);
  expect(result.objects[0].points[0][1]).toBeCloseTo(75);
  expect(result.objects[1].points).toEqual(objects[1].geometry);
  expect(result.bounds.minX).toBeCloseTo(-25);
  expect(JSON.stringify(objects)).toBe(before);
});

test("invalid geometry is disclosed rather than repaired into false-looking evidence", () => {
  const result = reviewSheetGeometry([{ id: "bad", label: "Bad", x: NaN, y: 0, w: 10, d: 20, placed: true }], 600, 500);
  expect(result.objects).toEqual([]);
  expect(result.invalidIds).toEqual(["bad"]);
});
