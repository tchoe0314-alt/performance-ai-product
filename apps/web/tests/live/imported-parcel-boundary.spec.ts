import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import { importedParcelBoundaryFromProjectInput } from "../../app/utils/importedParcelBoundary";
import { buildGenerateConceptPlacementResult, buildGenerateConceptPlacements } from "../../app/utils/dashboardGenerateConcepts";
import { layoutBoundaryViolations } from "../../app/utils/layoutBoundaryChecks";
import { searchLayoutAlternatives } from "../../app/utils/layoutAlternatives";
import { assessSiteInterference } from "../../app/utils/siteInterference";
import type { BuildingPlacement } from "../../app/types";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const featureInput = (geometry: Record<string, unknown>, units?: string, extra: Record<string, unknown>[] = []) => ({
  meta: { canonical_existing_conditions: { coordinate_system: { epsg: "EPSG:2276", units }, gis_layers: { parcels: [
    { id: "parcel-a", properties: {}, geometry }, ...extra,
  ] } } },
});

test("imported parcel validator preserves concavity and blocks ambiguous or unsafe geometry", () => {
  const ring = [[1000, 2000], [1400, 2000], [1400, 2400], [1200, 2200], [1000, 2400], [1000, 2000]];
  const ready = importedParcelBoundaryFromProjectInput(featureInput({ type: "Polygon", coordinates: [ring] }, "ft"));
  expect(ready.status).toBe("ready");
  if (ready.status === "ready") expect(ready.candidate.points).toEqual(ring.slice(0, -1));
  expect(importedParcelBoundaryFromProjectInput(featureInput({ type: "Polygon", coordinates: [ring] })).status).toBe("invalid");
  expect(importedParcelBoundaryFromProjectInput(featureInput({ type: "MultiPolygon", coordinates: [[ring]] }, "ft")).status).toBe("invalid");
  expect(importedParcelBoundaryFromProjectInput(featureInput({ type: "Polygon", coordinates: [ring, [[1100, 2100], [1150, 2100], [1100, 2150], [1100, 2100]]] }, "ft")).status).toBe("invalid");
  expect(importedParcelBoundaryFromProjectInput(featureInput({ type: "Polygon", coordinates: [ring] }, "ft", [{ id: "parcel-b", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } }])).status).toBe("ambiguous");
});

test("generated review concepts respect a concave parcel and an infeasible notch stays blocked", () => {
  const boundary: Array<[number, number]> = [
    [0, 0], [1000, 0], [1000, 700], [600, 700], [600, 620], [400, 620], [400, 700], [0, 700],
  ];
  const site: BuildingPlacement = {
    id: "concave-site",
    label: "Imported concave parcel",
    type: "site",
    x: 0,
    y: 0,
    w: 1000,
    d: 700,
    placed: true,
    locked: true,
    geometryType: "polygon",
    geometry: boundary,
    meta: { coordinate_units: "ft", imported_area_sf: 684_000, indentation: "200 ft x 80 ft" },
  };
  const generated = buildGenerateConceptPlacements({
    target: "full",
    notes: [],
    lot: { w: 1000, h: 700 },
    siteScaleLocked: true,
    buildingPlacements: [site],
    projectType: "industrial_site",
    buildingProgramSf: 14_400,
    buildingWidth: "",
    buildingDepth: "",
    parkingCount: 48,
    parkingStallWidth: 9,
    parkingStallDepth: 18,
    parkingAisleWidth: 24,
    parkingAdaAisleWidth: 8,
    parkingAdaCount: 1,
    parkingCompactCount: 0,
    parkingCompactWidth: 8,
    parkingAngle: 90,
    parkingLoading: "double",
  });
  expect(generated.find(item => item.type === "industrial_building")?.meta?.requested_area_sf).toBe(14_400);
  expect(generated.find(item => item.type === "parking")?.stallCount).toBe(48);
  expect(assessSiteInterference([site, ...generated]).filter(issue => issue.code === "outside_site_boundary")).toEqual([]);

  const deepNotchSite: BuildingPlacement = {
    ...site,
    id: "deep-notch-site",
    geometry: [[0, 0], [1000, 0], [1000, 700], [900, 700], [900, 100], [580, 100], [580, 700], [0, 700]],
    meta: { coordinate_units: "ft", imported_area_sf: 508_000, indentation: "320 ft x 600 ft" },
  };
  const requiredBuilding = generated.find(item => item.type === "industrial_building")!;
  expect(requiredBuilding).toBeTruthy();
  expect(layoutBoundaryViolations([deepNotchSite, requiredBuilding], null)).toContain("building outside current site boundary");
  const blocked = searchLayoutAlternatives([deepNotchSite, { ...requiredBuilding, locked: true }], 3, { units: "ft" });
  expect(blocked.alternatives).toEqual([]);
  expect(blocked.searchReport.accepted).toBe(0);
  expect(blocked.searchReport.rejectionReasons.some(reason => reason.includes("outside current site boundary"))).toBe(true);

  const narrowL: BuildingPlacement = {
    ...site,
    id: "narrow-l-site",
    geometry: [[0, 0], [1000, 0], [1000, 50], [50, 50], [50, 700], [0, 700]],
    meta: { coordinate_units: "ft", imported_area_sf: 82_500, indentation: "950 ft x 650 ft" },
  };
  const infeasible = buildGenerateConceptPlacementResult({
    target: "full",
    notes: [],
    lot: { w: 1000, h: 700 },
    siteScaleLocked: true,
    buildingPlacements: [narrowL],
    projectType: "industrial_site",
    buildingProgramSf: 14_400,
    buildingWidth: "",
    buildingDepth: "",
    parkingCount: 48,
    parkingStallWidth: 9,
    parkingStallDepth: 18,
    parkingAisleWidth: 24,
    parkingAdaAisleWidth: 8,
    parkingAdaCount: 1,
    parkingCompactCount: 0,
    parkingCompactWidth: 8,
    parkingAngle: 90,
    parkingLoading: "double",
  });
  expect(infeasible.blockers).toContain("Review industrial building concept - 14,400 sf cannot fit inside the active site boundary without changing its required geometry.");
});

test("explicit imported parcel action replaces only after confirmation and persists the concave canonical boundary", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable localhost only.");
  test.setTimeout(180_000);
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `parcel-${randomUUID()}@example.test`, password: "Disposable-123", name: "Imported parcel regression" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const name = `Imported parcel ${randomUUID()}`;
  const oldSite = { id: "old-site", label: "Old site", type: "site", x: 0, y: 0, w: 600, d: 500, placed: true, locked: true, geometryType: "polygon", geometry: [[0, 0], [600, 0], [600, 500], [0, 500]] as Array<[number, number]> };
  const input = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 600, h: 500 }, site_objects: [oldSite] }, meta: { site_inputs: { site_alignment_locked: true, site_boundary_source: "manual_drawn", site_boundary_state: "locked_canonical" }, system_dirty_state: { roads: "fresh", parking: "fresh", grading: "fresh", drainage: "fresh", utilities: "fresh" } } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: input } });
  expect(created.status()).toBe(200); const { project } = await created.json();
  const saved = async () => resolveCanonicalCanvasInput((await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input);
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openWorkspaceTool(page, "Setup");
  await page.getByTestId("workspace-stage-panel").selectOption("import_survey");
  const ring = [[1000, 2000], [1400, 2000], [1400, 2400], [1200, 2200], [1000, 2400], [1000, 2000]];
  const geojson = JSON.stringify({ type: "FeatureCollection", crs: { type: "name", properties: { name: "EPSG:2276", units: "ft" } }, features: [{ type: "Feature", id: "concave-parcel", properties: { layer: "parcel" }, geometry: { type: "Polygon", coordinates: [ring] } }] });
  await page.locator('input[type="file"][accept*=".geojson"]').setInputFiles({ name: "concave-parcel.geojson", mimeType: "application/geo+json", buffer: Buffer.from(geojson) });
  await expect(page.getByTestId("survey-upload-status")).toContainText("imported", { timeout: 30_000 });
  expect((await saved()).manual_fields?.site_objects?.find(item => item.type === "site")?.id).toBe("old-site");
  await expect(page.getByTestId("use-imported-site-boundary")).toBeEnabled();
  page.once("dialog", dialog => dialog.accept());
  await page.getByTestId("use-imported-site-boundary").click();
  const expected = [[0, 0], [400, 0], [400, 400], [200, 200], [0, 400]];
  await expect.poll(async () => (await saved()).meta?.site_inputs?.site_boundary_source, { timeout: 30_000 }).toBe("imported");
  const persisted = await saved();
  const site = persisted.manual_fields?.site_objects?.find(item => item.type === "site");
  expect(site?.geometry).toEqual(expected);
  expect(persisted.meta?.site_inputs?.site_boundary_geometry?.vertices.map(point => [point.x, point.y])).toEqual(expected);
  expect(persisted.meta?.site_inputs?.site_boundary_geometry?.provenance?.original_vertices.map(point => [point.x, point.y])).toEqual(ring.slice(0, -1));
  expect(persisted.meta?.system_dirty_state).toEqual({ roads: "stale", parking: "stale", grading: "stale", drainage: "stale", utilities: "stale" });
  await page.reload(); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  const reopened = await saved();
  expect(reopened.manual_fields?.site_objects?.filter(item => item.type === "site")).toHaveLength(1);
  expect(reopened.manual_fields?.site_objects?.find(item => item.type === "site")?.geometry).toEqual(expected);
  expect(reopened.meta?.site_inputs?.site_boundary_source).toBe("imported");
});
