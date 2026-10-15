import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { buildActiveBriefSummary } from "../../app/utils/activeBriefSummary";
import { changeBriefClassification, classificationFor, validateBriefClassifications } from "../../app/utils/briefClassification";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { liveInputFingerprint } from "../../app/utils/liveCalculationFreshness";
import type { ProjectInput } from "../../app/types";
import { preserveExplicitBriefProgram } from "../../app/utils/briefProgramPreservation";

test("program preservation never restores parking, overrides explicit live targets or mutates inputs", () => {
  const fields = { site_plan: { parking_count: 140 } };
  const saved: ProjectInput = { manual_fields: { site_plan: { parking_count: 999, building_program_sf: 28000, building_type: "office" } } };
  expect(preserveExplicitBriefProgram(fields, saved).site_plan).toEqual({ parking_count: 140, building_program_sf: 28000, building_type: "office" });
  expect(fields).toEqual({ site_plan: { parking_count: 140 } });
  expect(preserveExplicitBriefProgram({ site_plan: { building_program_sf: 0, building_type: "" } }, saved).site_plan).toEqual({ building_program_sf: 0, building_type: "" });
});

test("explicit choices and confirmation bind to exact values and do not survive changed inputs", () => {
  const input: ProjectInput = { manual_fields: { units: "ft", setback: 20 } };
  const row = buildActiveBriefSummary(input).find(item => item.id === "setbacks")!;
  expect(classificationFor(row, undefined).priority).toBe("unknown");
  const required = changeBriefClassification(row, undefined, "required");
  expect(classificationFor(row, required).trust).toBe("unverified");
  const confirmed = changeBriefClassification(row, required, "required", true);
  expect(classificationFor(row, confirmed).trust).toBe("user_confirmed");
  input.manual_fields!.setback = 20.001;
  const edited = buildActiveBriefSummary(input).find(item => item.id === "setbacks")!;
  expect(edited.value).toBe(row.value);
  expect(classificationFor(edited, confirmed)).toMatchObject({ priority: "unknown", trust: "unverified", needsReview: true });
});

test("unknown values cannot be classified and sourced statuses require evidence references", () => {
  const absent = buildActiveBriefSummary({}).find(item => item.id === "height")!;
  expect(() => changeBriefClassification(absent, undefined, "required")).toThrow();
  for (const invalid of [{ version: 2, fields: {} }, { version: 1, fields: { height: { priority: "required", trust: "externally_verified", value_key: "x" } } }]) expect(() => validateBriefClassifications(invalid)).toThrow();
});

test("classification changes are calculation inputs, not invisible presentation settings", () => {
  const input: ProjectInput = { manual_fields: { units: "ft", setback: 20 } };
  const before = liveInputFingerprint(input);
  const row = buildActiveBriefSummary(input).find(item => item.id === "setbacks")!;
  input.meta = { site_inputs: { active_brief_classifications_v1: changeBriefClassification(row, undefined, "preferred") } };
  expect(liveInputFingerprint(input)).not.toBe(before);
});

test("classification controls ask explicitly, retain choices and require review after live edits", async ({ page }) => {
  await page.goto("/demo/workspace?seedDemo=1&chat230EmptyObjects=1");
  await openWorkspaceTool(page, "Setup");
  const summary = page.getByTestId("active-brief-summary");
  const acreage = summary.getByTestId("brief-value-gross-acreage");
  await expect(acreage).toContainText("16.07 ac");
  await acreage.locator("summary").click();
  const priority = acreage.getByRole("combobox", { name: "Gross acreage requirement" });
  await expect(priority).toHaveValue("unknown");
  await priority.selectOption("required");
  await expect(priority).toHaveValue("required");
  await acreage.getByRole("button", { name: "Confirm this value" }).click();
  await expect(acreage.getByTestId("brief-trust")).toContainText("user confirmed");
  const boundary = page.getByTestId("setup-site-box-controls");
  if (!(await boundary.evaluate(element => element.hasAttribute("open")))) await boundary.locator("summary").click();
  if (await boundary.getByRole("spinbutton", { name: /Width \(ft\)/ }).isDisabled()) await page.getByTestId("create-centered-site-button").click();
  await boundary.getByRole("spinbutton", { name: /Width \(ft\)/ }).fill("1100");
  await expect(priority).toHaveValue("unknown");
  await expect(acreage).toContainText("review change");
  await expect(acreage.getByTestId("brief-trust")).toContainText("calculated");
  const violations = (await new AxeBuilder({ page }).include('[data-testid="active-brief-summary"]').analyze()).violations;
  expect(violations.filter(item => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
});
