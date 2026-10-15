import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const localOnly = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1" && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);

test("website does not apply an out-of-date saved result", async ({ page, request }) => {
  test.skip(!localOnly, "Uses disposable local accounts only.");
  const registration = await request.post(`${api}/api/auth/register`, { data: {
    email: `stale-${randomUUID()}@example.test`, password: "Disposable-canonical-123", name: "Stale fixture",
  } });
  expect(registration.status()).toBe(200);
  const owner = await registration.json();
  const created = await request.post(`${api}/api/projects`, { headers: { Authorization: `Bearer ${owner.token}` },
    data: { name: "Stale Result Fixture", latest_result: { success: true, metadata: {} },
      project_input: withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", site_objects: [] } }) } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  await page.route(`**/api/projects/${project.project_id}/result`, route => route.fulfill({ json: {
    project_id: project.project_id, result_freshness_v1: { version: 1, status: "stale" },
    latest_result: { success: true, message: "OLD RESULT MUST NOT APPLY", final_plan: { actions: [], meta: {} } },
  } }));
  await page.addInitScript(token => {
    localStorage.setItem("civora-ai-token", token);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, owner.token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Stale Result Fixture" }).click();
  await expect(page.getByText("Saved results are out of date. Recalculate for this layout.", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("OLD RESULT MUST NOT APPLY", { exact: true })).toHaveCount(0);
});

test("real website opens canonical geometry, edits it, saves both projections and reloads", async ({ page, request }, testInfo) => {
  test.skip(!localOnly, "Requires explicitly enabled disposable local API; never writes hosted projects.");
  const registration = await request.post(`${api}/api/auth/register`, { data: {
    email: `canonical-${randomUUID()}@example.test`, password: "Disposable-canonical-123", name: "Canonical fixture",
  } });
  expect(registration.status()).toBe(200);
  const owner = await registration.json();
  const headers = { Authorization: `Bearer ${owner.token}` };
  const input = withCanonicalCanvasSnapshot({ input_mode: "user", allow_ai_fill_for_blanks: false,
    manual_fields: { project_name: "Canonical Geometry Fixture", units: "ft", project_type: "commercial",
      lot: { x: 0, y: 0, w: 900, h: 700 }, site_objects: [
        { id: "canonical-office", label: "Canonical Office", type: "office_building", x: 125, y: 120, w: 160, d: 90,
          source: "manual_drawn", meta: { fixture_evidence: "synthetic, not engineering evidence", retain_custom: [false, 0] } },
      ] }, meta: { site_inputs: { site_alignment_locked: true } },
  });
  input.canonical_project_v1!.client = { name: "Fixture Client" };
  // This conflicting compatibility shadow must not replace the canonical record.
  input.manual_fields!.site_objects![0].x = 999;
  const created = await request.post(`${api}/api/projects`, { headers, data: { name: "Canonical Geometry Fixture", project_input: input } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  await page.addInitScript(token => {
    localStorage.setItem("civora-ai-token", token);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, owner.token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Canonical Geometry Fixture" }).click();
  const inspect = async (expectOpened = true) => {
    if (expectOpened) await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
    await openWorkspaceTool(page, "Draw");
    const list = page.getByTestId("object-manager-panel");
    await expect(list).toBeVisible();
    if (!(await list.evaluate(element => element.hasAttribute("open")))) await list.locator("summary").click();
    const row = page.getByTestId("object-manager-row").filter({ hasText: "Canonical Office" }).first();
    await row.getByTestId("object-manager-select").click();
    await row.getByTestId("object-manager-inspect").click();
  };
  await inspect();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("125");
  await page.getByTestId("selected-object-x-input").fill("150");
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    const saved = (await response.json()).project.project_input;
    const canonicalOffice = saved.canonical_project_v1.buildings.find((item: { canvas_placement_v1?: { id?: string } }) => item.canvas_placement_v1?.id === "canonical-office").canvas_placement_v1;
    const legacyOffice = saved.manual_fields.site_objects.find((item: { id: string }) => item.id === "canonical-office");
    return { canonicalX: canonicalOffice.x, legacyX: legacyOffice.x, custom: canonicalOffice.meta.retain_custom,
      client: saved.canonical_project_v1.client.name };
  }).toEqual({ canonicalX: 150, legacyX: 150, custom: [false, 0], client: "Fixture Client" });
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  const command = page.getByTestId("civora-command-input");
  await command.fill("move the selected building 25 ft east");
  await command.press("Enter");
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    const saved = (await response.json()).project.project_input;
    const office = saved.canonical_project_v1.buildings.find((item: { canvas_placement_v1?: { id?: string } }) => item.canvas_placement_v1?.id === "canonical-office").canvas_placement_v1;
    return { x: office.x, client: saved.canonical_project_v1.client.name };
  }).toEqual({ x: 175, client: "Fixture Client" });
  await page.getByRole("button", { name: "Undo last draft change", exact: true }).click();
  await inspect(false);
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("150");
  await page.getByRole("button", { name: "Undo last draft change", exact: true }).click();
  await inspect(false);
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("125");
  await page.getByRole("button", { name: "Redo draft change", exact: true }).click();
  await inspect(false);
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("150");
  await page.getByRole("button", { name: "Redo draft change", exact: true }).click();
  await inspect(false);
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("175");
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await inspect();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("175");
  await expect(page.getByTestId("selected-object-width-input")).toHaveValue("160");
  await page.screenshot({ path: testInfo.outputPath("canonical-save-reopen.png") });
  // Continue the same direct-edit/chat/history/reopen proof into a real export.
  const checkpoint = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
  page.on("dialog", dialog => dialog.accept());
  await openWorkspaceTool(page, "Deliver");
  const drawing = page.getByTestId("current-drawing-export");
  if (!(await drawing.evaluate(element => element.hasAttribute("open")))) await drawing.locator("summary").click();
  const queuedEvent = page.waitForResponse(response => response.url().endsWith("/api/jobs/export/current-geometry") && response.request().method() === "POST");
  await drawing.getByRole("button", { name: "Drawing DXF", exact: true }).click();
  const queued = await queuedEvent;
  expect(queued.status()).toBe(200);
  const { job } = await queued.json();
  let completed: { export_manifest_v1: { source_canonical_revision: string; units: string; object_ids: string[]; calculation_results_included: boolean }; artifact: { download_path: string } };
  await expect.poll(async () => {
    const payload = await (await request.get(`${api}/api/jobs/${job.job_id}`, { headers })).json();
    completed = payload.job.result;
    return payload.job.status;
  }, { timeout: 60_000 }).toBe("completed");
  expect(completed!.export_manifest_v1).toMatchObject({ source_canonical_revision: checkpoint.revision_token, units: "ft", object_ids: ["canonical-office"], calculation_results_included: false });
  const artifact = await request.get(`${api}${completed!.artifact.download_path}`, { headers });
  expect(artifact.status()).toBe(200);
  const path = testInfo.outputPath("edited-reopened-office.dxf");
  await (await import("node:fs/promises")).writeFile(path, await artifact.body());
  const parsed = JSON.parse(execFileSync(process.env.CIVORA_TEST_PYTHON ?? "python3", ["-c", "import ezdxf,json,sys; d=ezdxf.readfile(sys.argv[1]); print(json.dumps({'units':d.header.get('$INSUNITS'),'buildings':[list(e.get_points()[0][:2]) for e in d.modelspace().query('LWPOLYLINE[layer==\"BUILDING\"]')]}))", path], { encoding: "utf8" }));
  expect(parsed).toEqual({ units: 2, buildings: [[175, 120]] });
  const after = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
  expect(after.revision_token).toBe(checkpoint.revision_token);
  // Export audit records are intentionally appended; all other canonical and
  // compatibility fields must remain exactly the same.
  const beforeInput = structuredClone(checkpoint.project_input), afterInput = structuredClone(after.project_input);
  expect(afterInput.canonical_project_v1.export_history.length).toBeGreaterThan(beforeInput.canonical_project_v1.export_history.length);
  for (const value of [beforeInput, afterInput]) {
    delete value.canonical_project_v1.export_history;
    delete value.canonical_project_v1.revisions;
  }
  expect(afterInput).toEqual(beforeInput);
  expect(after.latest_result).toEqual(checkpoint.latest_result);
});
