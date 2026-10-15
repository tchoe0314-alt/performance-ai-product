import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { regenerateCulDeSac, defaultCulDeSacParameters } from "../../app/utils/parametricRoad";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { resolveDashboardExportBlockReason } from "../../app/utils/dashboardExportActions";

test("drawing-only readiness never waives units, representation, acknowledgement or construction gates", () => {
  const source = { token: "fixture", backendResultPresent: false, projectId: "pilot", systemStatuses: { grading: "stale" as const }, staleOutputs: ["grading"], exportScope: "review" as const, exportSource: "current_geometry_only" as const, geometryIsCurrent: true, geometryValid: true, unitsKnown: true, preliminaryAcknowledged: true };
  expect(resolveDashboardExportBlockReason(source)).toBe("");
  for (const flag of ["geometryIsCurrent", "geometryValid", "unitsKnown", "preliminaryAcknowledged"] as const) expect(resolveDashboardExportBlockReason({ ...source, [flag]: false })).not.toBe("");
  expect(resolveDashboardExportBlockReason({ ...source, exportScope: "construction" })).not.toBe("");
  expect(resolveDashboardExportBlockReason({ ...source, exportSource: undefined, backendResultPresent: true })).toContain("rerun");
});

test("website edits a road and exports only the current drawing while old calculations stay stale", async ({ page, context, request }, info) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  test.setTimeout(120_000);
  const register = async (name: string) => {
    const response = await request.post(`${api}/api/auth/register`, { data: { email: `drawing-${name}-${randomUUID()}@example.test`, password: "Disposable-123", name } });
    expect(response.status()).toBe(200); return response.json();
  };
  const owner = await register("owner"), stranger = await register("stranger");
  const headers = { Authorization: `Bearer ${owner.token}` };
  const road = regenerateCulDeSac({ id: "road", label: "Pilot access road", type: "road", x: 350, y: 120, w: 100, d: 250, rotation: 20, source: "manual_drawn", placed: true, meta: { cul_de_sac_v1: defaultCulDeSacParameters() } });
  const input = withCanonicalCanvasSnapshot({ input_mode: "user", manual_fields: { units: "ft", project_name: "Drawing pilot", lot: { x: 0, y: 0, w: 900, h: 700 }, setback: 20, site_plan: { parking_count: 140, building_program_sf: 12000, building_type: "office" }, site_objects: [
    { id: "parcel", label: "Pilot parcel", type: "site", x: 0, y: 0, w: 900, d: 700, source: "manual_drawn", placed: true },
    { id: "office", label: "Office footprint", type: "office_building", x: 100, y: 120, w: 160, d: 90, source: "manual_drawn", placed: true },
    { ...road, geometry_type: road.geometryType },
    { id: "parking", label: "Parking footprint", type: "parking", x: 660, y: 350, w: 180, d: 180, meta: { requested_stalls: 35 }, source: "manual_drawn", placed: true },
  ] }, meta: { system_dirty_state: { grading: "stale", roads: "stale", parking: "stale" } } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Drawing pilot", project_input: input, latest_result: { success: true, final_plan: { project_name: "Old calculation", units: "ft", actions: [{ task: "rectangle", layer: "BUILDING", origin: [999, 999], width: 80, height: 40 }], meta: { reactive_update_report: { stale_outputs: ["grading"] }, assumptions: ["Old result; not the current drawing."] } } } } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  const saved = async () => (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, owner.token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click(); await page.getByRole("button", { name: "Open project Drawing pilot", exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await openWorkspaceTool(page, "Draw");
  const manager = page.getByTestId("object-manager-panel");
  if (!(await manager.evaluate(element => element.hasAttribute("open")))) await manager.locator("summary").click();
  const row = page.getByTestId("object-manager-row").filter({ hasText: "Pilot access road" });
  await row.getByTestId("object-manager-select").click();
  const width = page.getByRole("slider", { name: "Project cul-de-sac road width" });
  await expect(width).toHaveValue("30");
  for (let n = 0; n < 10; n++) await width.press("ArrowRight");
  await expect(width).toHaveValue("40");
  await expect.poll(async () => (await saved()).project_input.manual_fields.site_objects.find((item: { id: string }) => item.id === "road").meta.cul_de_sac_v1.roadWidthFt).toBe(40);
  expect((await saved()).project_input.manual_fields.site_plan.parking_count).toBe(140);
  const oldResult = (await saved()).latest_result;
  await page.getByRole("button", { name: "Deliver", exact: true }).first().click();
  await expect(page.getByTestId("deliver-export-blocker")).toBeVisible();
  let calculatedRequests = 0;
  page.on("request", event => { if (event.url().endsWith("/api/jobs/export/dxf") && event.method() === "POST") calculatedRequests++; });
  await page.getByRole("button", { name: "Export DXF", exact: true }).first().click();
  await expect(page.getByTestId("deliver-export-status")).toContainText("input");
  expect(calculatedRequests).toBe(0);
  page.on("dialog", dialog => dialog.accept());
  for (const format of ["dxf", "pdf"] as const) {
    await page.getByRole("button", { name: "Deliver", exact: true }).first().click();
    const drawing = page.getByTestId("current-drawing-export");
    if (!(await drawing.evaluate(element => element.hasAttribute("open")))) await drawing.locator("summary").click();
    const responseEvent = page.waitForResponse(response => response.url().endsWith("/api/jobs/export/current-geometry") && response.request().method() === "POST");
    await drawing.getByRole("button", { name: `Drawing ${format.toUpperCase()}`, exact: true }).click();
    const queued = await responseEvent;
    expect(queued.status()).toBe(200);
    const { job } = await queued.json();
    let artifact: { filename: string; download_path: string };
    await expect.poll(async () => {
      const payload = await (await request.get(`${api}/api/jobs/${job.job_id}`, { headers })).json();
      artifact = payload.job.result?.artifact;
      return payload.job.status;
    }, { timeout: 60_000 }).toBe("completed");
    const url = `${api}${artifact!.download_path}`;
    expect((await request.get(url)).status()).toBe(401);
    expect([403, 404]).toContain((await request.get(url, { headers: { Authorization: `Bearer ${stranger.token}` } })).status());
    await page.getByRole("button", { name: "Downloads", exact: true }).click();
    const fileRow = page.getByTestId("async-jobs-panel").locator("div.flex.items-center.justify-between").filter({ hasText: artifact!.filename });
    const downloadEvent = page.waitForEvent("download");
    await fileRow.getByRole("button", { name: "Download", exact: true }).first().click();
    const download = await downloadEvent, path = info.outputPath(`current-drawing.${format}`);
    await download.saveAs(path); expect(await download.failure()).toBeNull();
    await info.attach(`current-drawing-${format}`, { path, contentType: format === "pdf" ? "application/pdf" : "application/dxf" });
    const bytes = await readFile(path);
    if (format === "pdf") expect(bytes.subarray(0, 4).toString()).toBe("%PDF");
    else {
      const detail = JSON.parse(execFileSync(process.env.CIVORA_TEST_PYTHON ?? "python3", ["-c", "import ezdxf,json,sys; d=ezdxf.readfile(sys.argv[1]); m=d.modelspace(); print(json.dumps({'units':d.header.get('$INSUNITS'),'islands':len(list(m.query('CIRCLE[layer==\"LANDSCAPE\"]'))),'markings':len(list(m.query('LWPOLYLINE[layer==\"ROAD_MARKING\"]'))),'buildings':[list(e.get_points()[0][:2]) for e in m.query('LWPOLYLINE[layer==\"BUILDING\"]')]}))", path], { encoding: "utf8" }));
      expect(detail.units).toBe(2);
      expect(detail.islands).toBe(1); expect(detail.markings).toBe(2); expect(detail.buildings).toContainEqual([100, 120]); expect(detail.buildings).not.toContainEqual([999, 999]);
      expect(bytes.toString()).toContain("NOT FOR CONSTRUCTION");
    }
    expect((await saved()).latest_result).toEqual(oldResult);
  }
});

test("metric parametric road exports through the real API with metre units and a 4.572 m island", async ({ request }, info) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `metric-drawing-${randomUUID()}@example.test`, password: "Disposable-123", name: "Metric drawing fixture" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const road = regenerateCulDeSac({ id: "metric-road", label: "Metric access road", type: "road", x: 60, y: 40, w: 30, d: 70, rotation: 90, source: "manual_drawn", placed: true, meta: { cul_de_sac_v1: defaultCulDeSacParameters("m") } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Metric drawing", project_input: withCanonicalCanvasSnapshot({ manual_fields: { units: "m", site_objects: [{ ...road, geometry_type: road.geometryType }] } }) } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  const queued = await request.post(`${api}/api/jobs/export/current-geometry`, { headers, data: { project_id: project.project_id, expected_revision: project.revision_token, export_format: "dxf", acknowledgement: true } });
  expect(queued.status()).toBe(200);
  const { job } = await queued.json();
  let downloadPath = "";
  await expect.poll(async () => {
    const payload = await (await request.get(`${api}/api/jobs/${job.job_id}`, { headers })).json();
    downloadPath = payload.job.result?.artifact?.download_path ?? "";
    return payload.job.status;
  }, { timeout: 60_000 }).toBe("completed");
  const artifact = await request.get(`${api}${downloadPath}`, { headers }); expect(artifact.status()).toBe(200);
  await info.attach("metric-drawing-dxf", { body: await artifact.body(), contentType: "application/dxf" });
  // Reuse the private artifact path in the Python reader, with no shell interpolation.
  const artifactFile = info.outputPath("metric-current.dxf");
  const fs = await import("node:fs/promises");
  await fs.writeFile(artifactFile, await artifact.body());
  const parsed = JSON.parse(execFileSync(process.env.CIVORA_TEST_PYTHON ?? "python3", ["-c", "import ezdxf,json,sys; d=ezdxf.readfile(sys.argv[1]); print(json.dumps({'units':d.header.get('$INSUNITS'),'radii':[e.dxf.radius for e in d.modelspace().query('CIRCLE[layer==\"LANDSCAPE\"]')]}))", artifactFile], { encoding: "utf8" }));
  expect(parsed.units).toBe(6); expect(parsed.radii).toEqual([4.572]);
});
