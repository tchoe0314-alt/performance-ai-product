import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { withCanonicalCanvasSnapshot, resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import { resolveDashboardObjectTarget } from "../../app/utils/dashboardObjectTargetResolver";
import type { BuildingPlacement } from "../../app/types";

const objects: BuildingPlacement[] = [
  { id: "site", label: "Site", type: "site", x: 0, y: 0, w: 900, d: 700, placed: true, locked: true },
  { id: "north", label: "North Office", type: "office_building", x: 100, y: 100, w: 100, d: 60, placed: true },
  { id: "south", label: "South Office", type: "office_building", x: 350, y: 100, w: 100, d: 60, placed: true },
  { id: "annex", label: "North Office Annex", type: "office_building", x: 600, y: 100, w: 100, d: 60, placed: true },
];

test("object target resolution prefers explicit identity and never guesses ambiguity", () => {
  expect(resolveDashboardObjectTarget({ objects, selectedId: "south", targetText: "North Office" })).toMatchObject({ status: "resolved", object: { id: "north" } });
  expect(resolveDashboardObjectTarget({ objects, selectedId: "south", targetText: "north" })).toMatchObject({ status: "resolved", object: { id: "north" } });
  expect(resolveDashboardObjectTarget({ objects, selectedId: "south", targetText: "office" }).status).toBe("ambiguous");
  expect(resolveDashboardObjectTarget({ objects, selectedId: "missing", targetText: "selected building" }).status).toBe("not_found");
});

test("named chat move outranks selection; ambiguous and missing targets are no-ops across reload", async ({ page, context, request }) => {
  const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
  test.skip(process.env.CIVORA_PHASE0_LOCAL_TESTS !== "1" || !/^http:\/\/(127\.0\.0\.1|localhost):/.test(api), "Disposable localhost only.");
  const registered = await request.post(`${api}/api/auth/register`, { data: { email: `chat-target-${randomUUID()}@example.test`, password: "Disposable-123", name: "Chat target regression" } });
  expect(registered.status()).toBe(200); const { token } = await registered.json(), headers = { Authorization: `Bearer ${token}` };
  const name = `Chat targeting ${randomUUID()}`;
  const input = withCanonicalCanvasSnapshot({ manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 900, h: 700 }, site_objects: objects } });
  const created = await request.post(`${api}/api/projects`, { headers, data: { name, project_input: input } });
  expect(created.status()).toBe(200); const { project } = await created.json();
  const saved = async () => resolveCanonicalCanvasInput((await (await request.get(`${api}/api/projects/${project.project_id}`, { headers })).json()).project.project_input);
  const positions = async () => Object.fromEntries(((await saved()).manual_fields?.site_objects ?? []).map(item => [item.id, item.x]));
  await context.addInitScript(value => { localStorage.setItem("civora-ai-token", value); sessionStorage.setItem("civora-ai-session-auth-restore", "1"); }, token);
  await page.goto("/"); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  const command = page.getByTestId("civora-command-input");
  const send = async (text: string) => { await command.fill(text); await command.press("Enter"); };
  await send("select South Office");
  await send("move North Office 25 ft east");
  await expect(page.getByText("Moved North Office 25 ft east.", { exact: false })).toBeVisible();
  await expect.poll(positions).toMatchObject({ north: 125, south: 350, annex: 600 });
  await page.getByRole("button", { name: "Undo last draft change", exact: true }).click();
  await expect.poll(positions).toMatchObject({ north: 100, south: 350, annex: 600 });
  await page.getByRole("button", { name: "Redo draft change", exact: true }).click();
  await expect.poll(positions).toMatchObject({ north: 125, south: 350, annex: 600 });
  const beforeNoOps = await positions();
  await send("move office 10 ft east");
  await expect(page.getByText(/Which object should I move\? Matches:/)).toBeVisible();
  expect(await positions()).toEqual(beforeNoOps);
  await send("move Missing Office 10 ft east");
  await expect(page.getByText(/couldn't find that object/i)).toBeVisible();
  expect(await positions()).toEqual(beforeNoOps);
  await page.reload(); await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  expect(await positions()).toEqual(beforeNoOps);
});
