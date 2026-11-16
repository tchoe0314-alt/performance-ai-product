import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";

function siteObjects(valid: boolean) {
  return [
    { id: "parcel", type: "site", x: 0, y: 0, w: 240, d: 180, placed: true },
    { id: "office", type: "office_building", x: 80, y: 40, w: 60, d: 40, placed: true },
    { id: "parking", type: "parking", x: 60, y: 115, w: 120, d: 50, placed: true,
      meta: { requested_stalls: 12, parking_design_basis: {
        stall_width_ft: 9, stall_depth_ft: 18, aisle_width_ft: 24,
        accessible_stall_count: 1, accessible_stall_width_ft: 8,
        access_aisle_width_ft: 5, source: "synthetic_candidate_basis_v1",
      } } },
    { id: "accessible-route", type: "sidewalk", x: 74.5, y: 80, w: 35.5, d: 72, placed: true,
      geometry_type: "polyline" as const,
      geometry: [[74.5, 152], [74.5, 131], [74.5, 105], [110, 80]] as [number, number][],
      meta: { accessible_route_design_basis: {
        route_geometry_source: "synthetic_route_survey_v1",
        criteria_source: "synthetic_accessibility_basis_v1", building_entrance_xy: [110, 80],
        route_width_ft: 5, minimum_route_width_ft: 4, measured_running_slope_pct: valid ? 2.5 : 7,
        maximum_running_slope_pct: 5, measured_cross_slope_pct: 1.2, maximum_cross_slope_pct: 2,
        vehicle_crossing_count: 1,
        ...(valid ? { vehicle_crossing_controls_source: "synthetic_marked_crossing_v1" } : {}),
      } } },
    { id: "site-access", type: "driveway", x: valid ? 0 : 10, y: 128, w: 60, d: 24, placed: true,
      geometry_type: "polyline" as const,
      geometry: [[valid ? 0 : 10, 140], [30, 140], [60, 140]] as [number, number][],
      meta: { circulation_design_basis: {
        route_geometry_source: "synthetic_access_survey_v1",
        criteria_source: "synthetic_circulation_basis_v1", site_entrance_xy: [valid ? 0 : 10, 140],
        route_width_ft: valid ? 24 : 16, minimum_route_width_ft: 20,
        design_vehicle: { name: "Synthetic SU", overall_length_ft: 30, overall_width_ft: 8.5,
          wheelbase_ft: 20, source: "synthetic_vehicle_record_v1" },
        swept_path_evidence: { source: "synthetic_envelope_v1",
          maneuvering_area_polygon: [[0, 110], [190, 110], [190, 175], [0, 175]],
          swept_envelope_polygon: [[4, 124], [180, 124], [180, 158], [4, 158]] },
        fire_access_design_basis: { criteria_source: "synthetic_fire_basis_v1",
          clear_width_ft: 24, minimum_clear_width_ft: 20, vertical_clearance_ft: 14,
          minimum_vertical_clearance_ft: 13.5, measured_max_grade_pct: 5, maximum_grade_pct: 10,
          surface_capacity_tons: 40, minimum_surface_capacity_tons: 36, dead_end_length_ft: 60,
          maximum_dead_end_without_turnaround_ft: 150,
          surface_capacity_source: "synthetic_pavement_record_v1",
          access_control_source: "synthetic_access_control_v1" },
      } } },
  ];
}

async function openCandidate(page: Page, request: APIRequestContext, valid: boolean) {
  const name = `Site planning candidate ${valid ? "positive" : "adverse"} ${randomUUID()}`;
  const registration = await request.post(`${api}/api/auth/register`, { data: {
    email: `site-plan-${randomUUID()}@example.test`, name: "Synthetic site planning candidate",
    password: "Disposable-123",
  } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json();
  const headers = { Authorization: `Bearer ${token}` };
  const created = await request.post(`${api}/api/projects`, { headers, data: { name,
    project_input: withCanonicalCanvasSnapshot({ input_mode: "assisted", allow_ai_fill_for_blanks: true,
      manual_fields: { project_name: name, units: "ft", project_type: "commercial_pad",
        building_width: 60, building_depth: 40, terrain: "2% slope north to south", setback: 12,
        lot: { x: 0, y: 0, w: 240, h: 180 },
        site_plan: { building_program_sf: 2400, building_count: 1, building_type: "office", parking_count: 12 },
        site_objects: siteObjects(valid),
      }, meta: { site_inputs: { site_alignment_locked: true }, system_dirty_state: { parking: "stale" } },
    }),
  } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  await page.addInitScript(value => {
    localStorage.setItem("civora-ai-token", value);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openWorkspaceTool(page, "Generate");
  const execution = page.waitForResponse(value => value.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(value.url()));
  await page.getByTestId("generate-parking").click();
  const response = await execution;
  expect(response.status()).toBe(200);
  const result = await response.json();
  expect(result.success, result.message).toBe(true);
  const saved = async () => {
    const record = await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json();
    const latest = await (await request.get(`${api}/api/projects/${project.project_id}/result`, { headers })).json();
    return { project: record.project, latest };
  };
  await expect.poll(async () => Boolean((await saved()).latest.latest_result?.final_plan)).toBe(true);
  return { ...(await saved()), headers };
}

test.beforeEach(() => {
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api),
    "Disposable localhost only; never runs hosted generation.");
});

test("supported site planning persists and exports truthful review data", async ({ page, request }, info) => {
  test.setTimeout(120_000);
  const result = await openCandidate(page, request, true);
  const program = result.latest.latest_result.final_plan.meta.parking_program;
  expect(program).toMatchObject({ geometry_stall_count: 12, accessible_route_verified: true,
    vehicle_access_route_verified: true, jurisdictional_compliance_verified: false });
  expect(program.circulation_access_evidence).toMatchObject({ turning_movement_verified: true,
    fire_access_geometry_verified: true, fire_access_verified: false,
    jurisdictional_compliance_verified: false });
  await page.reload();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await openWorkspaceTool(page, "Generate");
  await expect(page.getByTestId("generate-parking")).toContainText("Current");
  await page.getByTestId("workspace-stage-analyze").click();
  await page.getByTestId("workspace-stage-panel").selectOption("quantities");
  const downloadEvent = page.waitForEvent("download");
  await page.getByTestId("workspace-right-panel").getByRole("button", { name: "Export report", exact: true }).click();
  const download = await downloadEvent;
  const path = info.outputPath("site-planning-quantity-review.json");
  await download.saveAs(path);
  const exported = JSON.parse(await readFile(path, "utf8"));
  expect(exported).toMatchObject({ review_only: true, engineer_review_required: true,
    quantity_success: true,
    cost_estimate_reference: { pricing_source: "civora_concept_default_unit_prices" } });
  expect(exported.cost_estimate_reference.price_book_hash).toBe("");
});

test("adverse access persists explicit missing evidence", async ({ page, request }) => {
  test.setTimeout(120_000);
  const result = await openCandidate(page, request, false);
  const program = result.latest.latest_result.final_plan.meta.parking_program;
  expect(program.accessible_route_verified).toBe(false);
  expect(program.accessible_route_missing_evidence).toEqual(expect.arrayContaining([
    "route_width_and_slope_design_basis", "vehicle_crossing_treatment",
  ]));
  expect(program.vehicle_access_route_verified).toBe(false);
  expect(program.circulation_access_evidence.missing_evidence).toEqual(expect.arrayContaining([
    "site_entrance_to_parking_geometry", "circulation_width_design_basis",
  ]));
  await page.reload();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await openWorkspaceTool(page, "Generate");
  await expect(page.getByTestId("generate-parking")).toContainText("Current");
});
