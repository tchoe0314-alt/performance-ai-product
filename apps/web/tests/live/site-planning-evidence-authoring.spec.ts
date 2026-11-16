import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const local = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1" && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);

async function inspect(page: Page, name: string) {
  await openWorkspaceTool(page, "Draw");
  const panel = page.getByTestId("object-manager-panel");
  if (!(await panel.evaluate(element => element.hasAttribute("open")))) await panel.locator("summary").click();
  const row = page.getByTestId("object-manager-row").filter({ hasText: name }).first();
  await row.getByTestId("object-manager-select").click();
  await row.getByTestId("object-manager-inspect").click();
}

test("user authors site-planning evidence, persists, edits adverse input and calculates without approval claims", async ({ page, request }) => {
  test.skip(!local, "Disposable localhost accounts only.");
  test.setTimeout(180_000);
  const authResponse = await request.post(`${api}/api/auth/register`, { data: {
    email: `site-evidence-${randomUUID()}@example.test`, password: "Disposable-site-123", name: "Site evidence fixture",
  } });
  expect(authResponse.status()).toBe(200);
  const auth = await authResponse.json();
  const headers = { Authorization: `Bearer ${auth.token}` };
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name: "Site evidence authoring fixture",
    project_input: withCanonicalCanvasSnapshot({ input_mode: "assisted", allow_ai_fill_for_blanks: true, manual_fields: {
      units: "ft", project_name: "Site evidence authoring fixture", project_type: "commercial_pad",
      terrain: "2% slope north to south", setback: 12, lot: { x: 0, y: 0, w: 240, h: 180 },
      building_width: 60, building_depth: 40,
      site_plan: { parking_count: 12 },
      site_objects: [
        { id: "site", label: "Site boundary", type: "site", x: 0, y: 0, w: 240, d: 180, placed: true, source: "manual_drawn" },
        { id: "office", label: "Office", type: "office_building", x: 80, y: 40, w: 60, d: 40, placed: true, source: "manual_drawn" },
        { id: "parking", label: "Parking court", type: "parking", x: 60, y: 115, w: 120, d: 50, stall_count: 12, placed: true, source: "manual_drawn", meta: { requested_stalls: 12 } },
        { id: "route", label: "Accessible route", type: "sidewalk", x: 74.5, y: 80, w: 35.5, d: 72, placed: true, source: "manual_drawn", geometry_type: "polyline", geometry: [[74.5,152],[74.5,131],[74.5,105],[110,80]] },
        { id: "access", label: "Site access", type: "driveway", x: 0, y: 128, w: 60, d: 24, placed: true, source: "manual_drawn", geometry_type: "polyline", geometry: [[0,140],[30,140],[60,140]] },
      ],
    }, meta: { site_inputs: { site_alignment_locked: true } } }),
  } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  const objects = async () => (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields.site_objects;
  const object = async (id: string) => (await objects()).find((item: { id: string }) => item.id === id);
  await page.addInitScript(token => { sessionStorage.setItem("civora-ai-token", token); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, auth.token);
  await page.goto("/");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Site evidence authoring fixture" }).click();

  await inspect(page, "Parking court");
  const parkingEditor = page.getByTestId("parking-design-evidence-editor");
  await parkingEditor.getByLabel("Stall width (ft)").fill("9");
  await parkingEditor.getByLabel("Stall depth (ft)").fill("18");
  await parkingEditor.getByLabel("Drive aisle (ft)").fill("24");
  await parkingEditor.getByLabel("Accessible stalls").fill("1");
  await parkingEditor.getByLabel("Accessible stall width").fill("8");
  await parkingEditor.getByLabel("Access aisle width").fill("5");
  await parkingEditor.getByTestId("parking-evidence-source").fill("Synthetic adopted parking criteria v1");
  await parkingEditor.getByTestId("parking-evidence-source").blur();
  await expect(page.getByTestId("parking-evidence-status")).toContainText("legal compliance remains unverified");
  await parkingEditor.getByTestId("apply-parking-evidence").click();

  await inspect(page, "Accessible route");
  const routeEditor = page.getByTestId("accessible-route-evidence-editor");
  for (const [label, value] of [["Route width (ft)","5"],["Minimum width (ft)","4"],["Measured running slope (%)","2.5"],["Maximum running slope (%)","5"],["Measured cross slope (%)","1.2"],["Maximum cross slope (%)","2"],["Entrance X","110"],["Entrance Y","80"],["Vehicle crossings","1"]]) await routeEditor.getByLabel(label).fill(value);
  await routeEditor.getByLabel("Route geometry source").fill("Synthetic route survey v1");
  await routeEditor.getByLabel("Criteria source").fill("Synthetic accessibility criteria v1");
  await routeEditor.getByLabel("Crossing treatment source").fill("Synthetic marked crossing detail v1");
  await routeEditor.getByLabel("Crossing treatment source").blur();
  await expect(page.getByTestId("accessible-route-evidence-status")).toContainText("approval remains unverified");
  await routeEditor.getByTestId("apply-accessible-route-evidence").click();

  await inspect(page, "Site access");
  const accessEditor = page.getByTestId("circulation-evidence-editor");
  for (const [label, value] of [["Route width (ft)","24"],["Entrance X","0"],["Entrance Y","140"],["Overall length (ft)","30"],["Overall width (ft)","8.5"],["Wheelbase (ft)","20"]]) await accessEditor.getByLabel(label).fill(value);
  await accessEditor.getByLabel("Minimum width (ft)").first().fill("20");
  await accessEditor.getByLabel("Route geometry source").fill("Synthetic access survey v1");
  await accessEditor.getByLabel("Circulation criteria source").fill("Synthetic circulation criteria v1");
  await accessEditor.getByLabel("Vehicle name").fill("Synthetic single-unit vehicle");
  await accessEditor.getByLabel("Vehicle record/source").fill("Synthetic vehicle record v1");
  await accessEditor.getByLabel("Study/source").fill("Synthetic swept study v1");
  await accessEditor.getByLabel("Maneuvering area polygon").fill("[[0,110],[190,110],[190,175],[0,175]]");
  await accessEditor.getByLabel("Maneuvering area polygon").blur();
  await accessEditor.getByLabel("Swept envelope polygon").fill("[[4,124],[180,124],[180,158],[4,158]]");
  await accessEditor.getByLabel("Swept envelope polygon").blur();
  for (const [label, value] of [["Clear width (ft)","24"],["Vertical clearance (ft)","14"],["Minimum clearance (ft)","13.5"],["Measured max grade (%)","5"],["Maximum grade (%)","10"],["Surface capacity (tons)","40"],["Minimum capacity (tons)","36"],["Dead end length (ft)","60"],["Max without turnaround (ft)","150"]]) await accessEditor.getByLabel(label).fill(value);
  await accessEditor.getByLabel("Minimum width (ft)").last().fill("20");
  await accessEditor.getByLabel("Fire criteria source").fill("Synthetic fire criteria v1");
  await accessEditor.getByLabel("Pavement capacity source").fill("Synthetic pavement record v1");
  await accessEditor.getByLabel("Gate/access-control source").fill("Synthetic access-control record v1");
  await accessEditor.getByLabel("Gate/access-control source").blur();
  await expect(page.getByTestId("circulation-evidence-status")).toContainText("approval remain required");
  await accessEditor.getByTestId("apply-circulation-evidence").click();

  await expect.poll(async () => Boolean((await object("access")).meta?.circulation_design_basis?.swept_path_evidence?.swept_envelope_polygon)).toBe(true);
  await page.reload();
  await inspect(page, "Site access");
  await expect(page.getByLabel("Route width (ft)")).toHaveValue("24");
  await page.getByLabel("Route width (ft)").fill("16");
  await page.getByTestId("apply-circulation-evidence").click();
  await expect.poll(async () => (await object("access")).meta?.circulation_design_basis?.route_width_ft).toBe(16);

  await openWorkspaceTool(page, "Generate");
  const response = page.waitForResponse(value => value.request().method() === "POST" && /\/api\/(?:jobs\/)?orchestrate$/.test(value.url()));
  await page.getByTestId("generate-parking").click();
  expect((await response).status()).toBe(200);
  await expect.poll(async () => Boolean((await (await request.get(`${api}/api/projects/${project.project_id}/result`, { headers })).json()).latest_result?.final_plan)).toBe(true);
  const latest = (await (await request.get(`${api}/api/projects/${project.project_id}/result`, { headers })).json()).latest_result.final_plan.meta.parking_program;
  expect(latest.jurisdictional_compliance_verified).toBe(false);
  expect(latest.circulation_access_evidence.verified).toBe(false);
  expect(latest.circulation_access_evidence.missing_evidence).toContain("circulation_width_design_basis");
  await page.getByTestId("workspace-stage-analyze").click();
  await page.getByTestId("workspace-stage-panel").selectOption("quantities");
  const downloadEvent = page.waitForEvent("download");
  await page.getByTestId("workspace-right-panel").getByRole("button", { name: "Export report", exact: true }).click();
  const download = await downloadEvent;
  const reportPath = test.info().outputPath("authored-site-planning-review.json");
  await download.saveAs(reportPath);
  const report = JSON.parse(await readFile(reportPath, "utf8"));
  expect(report).toMatchObject({ review_only: true, engineer_review_required: true });
});
