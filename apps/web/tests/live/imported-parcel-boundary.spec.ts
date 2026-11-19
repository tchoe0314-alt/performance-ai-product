import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import { importedParcelBoundaryFromProjectInput } from "../../app/utils/importedParcelBoundary";
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
