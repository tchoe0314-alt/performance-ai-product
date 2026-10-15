import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

test("saved briefs reopen, switch independently and do not write project data", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable local accounts only.");
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `brief-${randomUUID()}@example.test`, password: "Disposable-123", name: "Brief audit" } });
  expect(registered.status()).toBe(200);
  const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const projects = [];
  for (const [name, width, target, use] of [["Brief site A", 435.6, 28000, "office"], ["Brief site B", 871.2, 15000, "retail"]] as const) {
    const input = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", lot: { x: 0, y: 0, w: width, h: 100 }, site_plan: { building_program_sf: target, building_type: use }, site_objects: [{ id: "site", name: "Boundary", type: "site", x: 0, y: 0, w: width, d: 100, placed: true }] } });
    const response = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: input } });
    expect(response.status()).toBe(200);
    projects.push((await response.json()).project);
  }
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/");
  const open = async (name: string) => {
    await page.getByTestId("header-projects-button").click();
    await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
    await openWorkspaceTool(page, "Setup");
  };
  const summary = page.getByTestId("active-brief-summary");
  for (const index of [0, 1, 0]) {
    await open(projects[index].name);
    await expect(summary.getByTestId("brief-value-gross-acreage")).toContainText(`${index + 1} ac`);
    await expect(summary.getByTestId("brief-value-building-area")).toContainText(index === 0 ? "28,000 sf" : "15,000 sf");
    await summary.locator(":scope > details > summary").click();
    await expect(summary.getByTestId("brief-value-building-use")).toContainText(index === 0 ? "office" : "retail");
    await summary.locator(":scope > details > summary").click();
  }
  await page.reload();
  await open(projects[1].name);
  await expect(summary.getByTestId("brief-value-building-area")).toContainText("15,000 sf");
  for (const project of projects) {
    const stored = (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project;
    expect(stored.revision_token).toBe(project.revision_token);
    expect(stored.project_input).toEqual(project.project_input);
  }
});
