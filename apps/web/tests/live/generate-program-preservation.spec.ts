import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import { buildGenerateConceptPlacements, isReplaceableGeneratedReviewConcept } from "../../app/utils/dashboardGenerateConcepts";
import { resolveDashboardGenerationTarget } from "../../app/utils/dashboardGenerateIntent";

const conceptArgs = (overrides: Partial<Parameters<typeof buildGenerateConceptPlacements>[0]> = {}) => ({
  target: "full" as const,
  notes: [],
  lot: { w: 1000, h: 1000 },
  siteScaleLocked: true,
  buildingPlacements: [],
  projectType: "office_site",
  buildingProgramSf: 28_800,
  buildingWidth: "229",
  buildingDepth: "126",
  parkingCount: 12,
  parkingStallWidth: 9,
  parkingStallDepth: 18,
  parkingAisleWidth: 24,
  parkingAdaAisleWidth: 8,
  parkingAdaCount: 1,
  parkingCompactCount: 0,
  parkingCompactWidth: 8,
  parkingAngle: 90,
  parkingLoading: "double" as const,
  ...overrides,
});

test("Generate respects the explicitly selected project type without changing the program", () => {
  const industrial = buildGenerateConceptPlacements(conceptArgs({ projectType: "industrial_site", buildingProgramSf: 14_400 }));
  const industrialBuilding = industrial.find(item => item.type === "industrial_building");
  expect(industrialBuilding?.label).toContain("industrial building");
  expect(industrialBuilding?.meta?.requested_area_sf).toBe(14_400);
  expect(industrialBuilding?.meta?.requested_project_type).toBe("industrial_site");
  expect(industrialBuilding?.meta?.building_use).toBe("industrial");
  expect(industrial.some(item => item.type === "office_building")).toBe(false);

  const commercial = buildGenerateConceptPlacements(conceptArgs({ projectType: "commercial_pad" }));
  expect(commercial.some(item => item.type === "retail_building")).toBe(true);

  const existingIndustrial = buildGenerateConceptPlacements(conceptArgs({
    projectType: "industrial_site",
    buildingPlacements: [{ id: "existing", label: "Existing industrial", type: "industrial_building", x: 1, y: 1, w: 100, d: 80, placed: true }],
  }));
  expect(existingIndustrial.some(item => item.meta?.generated_program_object)).toBe(false);

  const editedGenerated = buildGenerateConceptPlacements(conceptArgs({
    projectType: "industrial_site",
    buildingPlacements: [{
      id: "edited-generated",
      label: "Authored industrial footprint",
      type: "industrial_building",
      x: 1,
      y: 1,
      w: 179,
      d: 85,
      placed: true,
      source: "manual_drawn",
      meta: { generated_review_concept: true, requested_area_sf: 14_400 },
    }],
  }));
  expect(editedGenerated.some(item => item.meta?.generated_program_object)).toBe(false);
  expect(isReplaceableGeneratedReviewConcept({
    id: "untouched", label: "Untouched", type: "industrial_building", source: "generated", w: 100, d: 80,
    meta: { generated_review_concept: true },
  })).toBe(true);
  expect(isReplaceableGeneratedReviewConcept({
    id: "authored", label: "Authored", type: "industrial_building", source: "manual_drawn", w: 100, d: 80,
    meta: { generated_review_concept: true },
  })).toBe(false);
});

test("combined Generate intent preserves canonical program and never invents a missing building", () => {
  expect(resolveDashboardGenerationTarget("Generate an office site with a 28,800 sf building and 12 parking spaces")).toBe("full");
  expect(resolveDashboardGenerationTarget("generate parking")).toBe("parking");
  expect(resolveDashboardGenerationTarget("run drainage and utilities")).toBe("full");

  const concepts = buildGenerateConceptPlacements(conceptArgs());
  const building = concepts.find(item => item.type === "office_building");
  const parking = concepts.find(item => item.type === "parking");
  expect(building?.meta?.requested_area_sf).toBe(28_800);
  expect((building?.w ?? 0) * (building?.d ?? 0)).toBe(28_800);
  expect(parking?.stallCount).toBe(12);

  // Conflicting restored display dimensions must not override the canonical brief.
  expect(buildGenerateConceptPlacements(conceptArgs({ buildingProgramSf: 31_750, buildingWidth: 100, buildingDepth: 100 }))
    .find(item => item.type === "office_building")?.meta?.requested_area_sf).toBe(31_750);
  expect(buildGenerateConceptPlacements(conceptArgs({ buildingProgramSf: null, buildingWidth: "", buildingDepth: "" }))
    .some(item => item.type === "office_building")).toBe(false);
});

test("exact audited Generate command creates and persists the 28,800 sf building and 12 stalls", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable localhost only.");
  test.setTimeout(180_000);
  const name = `Generate program ${randomUUID()}`;
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `generate-program-${randomUUID()}@example.test`, password: "Disposable-123", name: "Generate program regression" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json();
  const headers = { Authorization: `Bearer ${token}` };
  const input = withCanonicalCanvasSnapshot({
    input_mode: "assisted",
    allow_ai_fill_for_blanks: true,
    manual_fields: {
      units: "ft",
      project_type: "commercial_pad",
      terrain: "2% synthetic review slope west to east",
      lot: { x: 0, y: 0, w: 1000, h: 1000 },
      site_plan: { building_program_sf: 28_800, building_count: 1, building_type: "office", parking_count: 12 },
      site_objects: [{ id: "parcel", label: "Synthetic parcel", type: "site", x: 0, y: 0, w: 1000, d: 1000, placed: true, locked: true }],
    },
    meta: { site_inputs: { site_alignment_locked: true } },
  });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: input } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  const saved = async () => resolveCanonicalCanvasInput((await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input);
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");

  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await page.getByTestId("civora-command-input").fill("Generate an office site with a 28,800 sf building and 12 parking spaces");
  await page.getByTestId("civora-command-input").press("Enter");
  await expect.poll(async () => {
    const items = (await saved()).manual_fields?.site_objects ?? [];
    return items.some(item => item.type === "office_building" && item.meta?.requested_area_sf === 28_800)
      && items.some(item => item.type === "parking" && item.label?.includes("12 stalls"));
  }, { timeout: 30_000 }).toBe(true);
  const persisted = await saved();
  const objects = persisted.manual_fields?.site_objects ?? [];
  expect(objects.find(item => item.type === "office_building")?.meta?.requested_area_sf).toBe(28_800);
  expect(objects.find(item => item.type === "parking")?.label).toContain("12 stalls");
  expect(persisted.manual_fields?.site_plan?.building_program_sf).toBe(28_800);
  expect(persisted.manual_fields?.site_plan?.parking_count).toBe(12);

  const conflictDialog = page.getByRole("dialog", { name: "Keep these edits separate?" });
  if (await conflictDialog.isVisible()) await conflictDialog.getByRole("button", { name: "Keep editing" }).click();
  await page.reload();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  const reopened = await saved();
  expect(reopened.manual_fields?.site_objects?.find(item => item.type === "office_building")?.meta?.requested_area_sf).toBe(28_800);
  expect(reopened.manual_fields?.site_objects?.find(item => item.type === "parking")?.label).toContain("12 stalls");
  expect(reopened.manual_fields?.site_plan?.parking_count).toBe(12);
});
