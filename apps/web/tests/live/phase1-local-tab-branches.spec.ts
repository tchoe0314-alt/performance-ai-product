import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const local = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1" && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);

for (const choice of ["copy", "replace", "cancel"] as const) {
  test(`second tab asks on first edit and supports ${choice}`, async ({ page, context, request }) => {
    test.skip(!local, "Disposable local projects only.");
    const registered = await request.post(`${api}/api/auth/register`, { data: {
      email: `tabs-${randomUUID()}@example.test`, password: "Disposable-123", name: "Tabs",
    } });
    expect(registered.status()).toBe(200);
    const { token } = await registered.json();
    const headers = { Authorization: `Bearer ${token}` };
    const name = `Two tabs ${randomUUID()}`;
    const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input:
      withCanonicalCanvasSnapshot({ input_mode: "user", allow_ai_fill_for_blanks: false, manual_fields: {
        project_name: name, units: "ft", project_type: "commercial", lot: { x: 0, y: 0, w: 900, h: 700 }, site_objects: [
          { id: "office", label: "Office", type: "office_building", x: 125, y: 120, w: 160, d: 90, source: "manual_drawn" },
        ] } }), latest_result: { success: true, final_plan: { units: "ft", actions: [], meta: { quantities: { area: 123 } } } } } });
    expect(created.status()).toBe(200);
    const { project } = await created.json();
    await context.addInitScript(value => {
      if (!location.href.startsWith("http")) return;
      localStorage.setItem("civora-ai-token", value);
      sessionStorage.setItem("civora-ai-session-auth-restore", "1");
    }, token);
    const open = async (tab: typeof page) => {
      await tab.goto("/");
      await expect(tab.getByTestId("workspace-canvas-shell")).toBeVisible();
      await tab.getByTestId("header-projects-button").click();
      await tab.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
      await expect(tab.getByTestId("project-status-summary")).toContainText("Project opened");
    };
    await open(page);
    const second = await context.newPage();
    await open(second);
    const dialog = second.getByTestId("project-tab-branch-dialog");
    await expect(dialog).not.toBeVisible();
    await openWorkspaceTool(second, "Draw");
    const list = second.getByTestId("object-manager-panel");
    if (!(await list.evaluate(element => element.hasAttribute("open")))) await list.locator("summary").click();
    const row = second.getByTestId("object-manager-row").filter({ hasText: "Office" }).first();
    await row.getByTestId("object-manager-select").click();
    await row.getByTestId("object-manager-inspect").click();
    await second.getByTestId("selected-object-x-input").fill("175");
    await expect(dialog).toBeVisible();
    const before = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
    expect(before.project_input.manual_fields.site_objects[0].x).toBe(125);
    await dialog.getByRole("button", { name: choice === "copy" ? "Save as a copy" : choice === "replace" ? "Replace original" : "Keep editing", exact: true }).click();
    await expect(dialog).not.toBeVisible();
    if (choice === "cancel") {
      await expect(second.getByTestId("selected-object-x-input")).toHaveValue("175");
      expect((await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields.site_objects[0].x).toBe(125);
    } else {
      await expect.poll(async () => {
        const projects = (await (await request.get(`${api}/api/projects`, { headers })).json()).projects;
        if (choice === "copy") {
          const copy = projects.find((item: { project_id: string }) => item.project_id !== project.project_id);
          if (!copy) return null;
          return (await (await request.get(`${api}/api/projects/${copy.project_id}`, { headers })).json()).project.project_input.manual_fields.site_objects[0].x;
        }
        return (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields.site_objects[0].x;
      }).toBe(175);
      const original = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
      expect(original.project_input.manual_fields.site_objects[0].x).toBe(choice === "copy" ? 125 : 175);
      if (choice === "replace") expect(original.metadata.branch_recovery_v1[0].project.project_input.manual_fields.site_objects[0].x).toBe(125);
      if (choice === "copy") {
        const projects = (await (await request.get(`${api}/api/projects`, { headers })).json()).projects;
        const copy = projects.find((item: { project_id: string }) => item.project_id !== project.project_id);
        expect(copy.name).toBe(`${name} Copy`);
        await second.getByTestId("selected-object-x-input").fill("225");
        await expect.poll(async () => (await (await request.get(`${api}/api/projects/${copy.project_id}`, { headers })).json()).project.project_input.manual_fields.site_objects[0].x).toBe(225);
        await expect(dialog).not.toBeVisible();
        await page.reload();
        await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
        expect((await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields.site_objects[0].x).toBe(125);
        const persistedCopy = (await (await request.get(`${api}/api/projects/${copy.project_id}`, { headers })).json()).project;
        expect(persistedCopy.name).toBe(`${name} Copy`);
        const copiedResult = (await (await request.get(`${api}/api/projects/${copy.project_id}/result`, { headers })).json()).latest_result;
        expect(copiedResult.final_plan.meta.quantities.area).toBe(123);
        const exported = await request.get(`${api}/api/projects/${copy.project_id}/document`, { headers });
        expect(exported.status()).toBe(200);
        expect((await exported.json()).document.buildings[0].canvas_placement_v1.x).toBe(225);
      }
    }
    await second.close();
  });
}
