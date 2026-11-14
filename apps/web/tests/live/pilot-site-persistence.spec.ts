import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot } from "../../app/utils/canonicalCanvasProject";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

test("apply rectangular site saves matching boundary and lot through reopen", async ({ page, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL || "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/127\.0\.0\.1:/.test(api), "Disposable localhost only");
  const auth = await request.post(`${api}/api/auth/register`, { data: {
    email: `site-${randomUUID()}@example.test`, password: "Disposable-123", name: "Site regression" } });
  expect(auth.status()).toBe(200);
  const { token } = await auth.json();
  const headers = { Authorization: `Bearer ${token}` };
  const name = `Rectangular site ${randomUUID()}`;
  const created = await request.post(`${api}/api/projects`, { headers, data: { name,
    project_input: withCanonicalCanvasSnapshot({ input_mode: "user", manual_fields: {
      units: "ft", lot: { x: 0, y: 0, w: 300, h: 300 },
      site_objects: [{ id: "site", type: "site", x: 0, y: 0, w: 300, d: 300, placed: true, locked: false }],
    } }) } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  await page.addInitScript(value => { sessionStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await openWorkspaceTool(page, "Setup");
  await page.getByLabel(/Site depth in feet/).fill("200");
  await page.getByTestId("create-centered-site-button").click();
  const saved = async () => (await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input.manual_fields;
  await expect.poll(async () => (await saved()).lot.h).toBe(200);
  await expect.poll(async () => (await saved()).site_objects.find((o: {type:string}) => o.type === "site").d).toBe(200);
  await page.reload();
  await openWorkspaceTool(page, "Setup");
  await expect(page.getByTestId("setup-site-box-controls")).toContainText("300 ft x 200 ft");
  expect((await saved()).lot).toMatchObject({ w: 300, h: 200 });
});
