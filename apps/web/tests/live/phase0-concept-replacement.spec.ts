import { expect, test } from "@playwright/test";
import type { BuildingPlacement } from "../../app/types";
import { canonicalConceptReplacementBlocker } from "../../app/utils/canonicalEditCommands";

for (const [mode, replacement] of [
  ["concept regeneration", "Create a complete civil site plan on an approximately 8-acre rectangular site with a 50,000 sf retail building, 220 parking spaces, 24-foot aisles, two access points, sidewalks, a rear loading and service area, detention pond, storm, sanitary, water, and fire protection."],
  ["address/program replacement", "I want the address to be 20525 Margo St Gretna NE and it is gonna be 1000ft by 1000 ft with the address as the center point and create an office building with 220 parking spaces, a basin, sidewalks and utilities"],
]) {
test(`${mode} cannot replace a protected existing program`, async ({ page }) => {
  await page.goto("/demo/workspace?debugPreview=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("region", { name: "Drawing surface" })).toBeVisible();
  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();
  const command = page.getByRole("textbox", { name: /Ask Civora to change the site plan/i });
  await command.fill("Create a complete civil site plan on an approximately 8-acre rectangular site with a 42,000 sf retail building, 190 parking spaces, 24-foot aisles, two access points, sidewalks, a rear loading and service area, detention pond, storm, sanitary, water, and fire protection.");
  await command.press("Enter");
  const originalBuilding = page.locator('[data-cad-object-id][aria-label*="Retail Building - 42,000 sf"]').first();
  await expect(originalBuilding).toBeVisible();
  const originalId = await originalBuilding.getAttribute("data-cad-object-id");
  const originalBoundary = await page.locator("main").innerText();
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const objectList = page.getByTestId("object-manager-panel");
  if (!(await objectList.evaluate(element => element.hasAttribute("open")))) await objectList.locator("summary").click();
  await page.getByTestId("object-manager-row").filter({ hasText: "Parking Field - 76 stalls" }).first().getByTestId("object-manager-inspect").click();
  await page.getByRole("button", { name: "Lock object", exact: true }).click();
  await command.fill(replacement);
  await command.press("Enter");
  await expect(originalBuilding).toBeVisible();
  await expect(originalBuilding).toHaveAttribute("data-cad-object-id", originalId!);
  await expect(page.locator('[data-cad-object-id][aria-label*="Parking Field - 76 stalls"]').first()).toBeVisible();
  await expect(page.locator('[data-cad-object-id][aria-label*="Retail Building - 50,000 sf"]')).toHaveCount(0);
  await expect(page.locator("body")).toContainText(/protected|locked/i);
  expect(originalBoundary).toMatch(/660 FT x 528 FT/i);
  await expect(page.locator("main")).toContainText(/660 FT x 528 FT/i);
});
}

test("replacement protection covers every protected control state without mutating inputs", () => {
  const base: BuildingPlacement = { id: "original", type: "building", label: "Original", w: 100, d: 50,
    meta: { dense_concept_generated: true } };
  for (const state of ["fixed", "existing", "reference"]) {
    const object = { ...base, meta: { ...base.meta, canonical_control_state: state } };
    const source = JSON.stringify(object);
    expect(canonicalConceptReplacementBlocker([object])).toContain("protected");
    expect(JSON.stringify(object)).toBe(source);
  }
  expect(canonicalConceptReplacementBlocker([{ ...base, locked: true }])).toContain("protected");
  expect(canonicalConceptReplacementBlocker([{ ...base, capabilities: { deletable: false } }])).toContain("blocked");
  expect(canonicalConceptReplacementBlocker([base])).toBeNull();
  expect(canonicalConceptReplacementBlocker([{ ...base, locked: true, type: "site" }])).toBeNull();
  expect(canonicalConceptReplacementBlocker([{ ...base, locked: true, meta: {} }])).toBeNull();
});
