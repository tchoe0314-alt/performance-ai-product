import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { writeFile } from "node:fs/promises";
import original from "../fixtures/q01-office-brief-v1.json";
import nondefault from "../fixtures/q01-office-brief-nondefault-v1.json";
import { resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";
import type { ProjectRecord } from "../../app/types";
import { openWorkspaceTool, workspaceCommandButton } from "./helpers/workspaceNavigation";

const api = (process.env.PLAYWRIGHT_API_BASE_URL ?? "").replace(/\/+$/, "");
const email = process.env.CIVORA_EMAIL ?? "";
const password = process.env.CIVORA_PASSWORD ?? "";
const failureReceipts = new WeakMap<object, { writes: unknown[]; receipts: Promise<void>[] }>();
test.afterEach(async ({ page }, info) => {
  const trace = failureReceipts.get(page);
  if (!trace) return; // Hosted/unqualified/skipped and neighboring tests stay untouched.
  await Promise.all(trace.receipts);
  const leases = await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith("civora-project-tab-v1:"))).catch(() => null);
  const branchDialogVisible = await page.getByTestId("project-tab-branch-dialog").isVisible().catch(() => null);
  await writeFile(info.outputPath("final-write-boundary.json"), JSON.stringify({ writes: trace.writes, leases, branchDialogVisible }, null, 2));
});
function loopback(value: string) {
  try { const url = new URL(value); return url.protocol === "http:" &&
    ["127.0.0.1", "localhost"].includes(url.hostname) && !!url.port && !url.username && !url.password; }
  catch { return false; }
}

for (const brief of [original, nondefault]) test(`${brief.id} saves and reopens exact program and objects`, async ({ page, request, baseURL }, info) => {
  test.skip(process.env.CIVORA_RUN_DISPOSABLE_FIXTURE !== "1" || !loopback(api) || !loopback(baseURL ?? "") ||
    !email.endsWith("@example.test") || !password, "Explicit disposable loopback API/frontend and authored synthetic account required; never hosted.");
  const writes: Array<{ path: string; method: string; status: number; at: number; expectedRevision?: string; returnedRevision?: string; detail?: string }> = [];
  const receipts: Promise<void>[] = [];
  failureReceipts.set(page, { writes, receipts });
  page.on("response", response => {
    const req = response.request(); const url = new URL(response.url());
    if (url.origin === api && url.pathname.startsWith("/api/projects")) {
      const entry: (typeof writes)[number] = { path: url.pathname, method: req.method(), status: response.status(), at: Date.now() };
      if (req.method() === "POST" && url.pathname === "/api/projects") entry.expectedRevision = req.postDataJSON()?.expected_revision;
      writes.push(entry);
      receipts.push(response.json().then(body => {
        entry.returnedRevision = body.project?.revision_token;
        if (typeof body.detail === "string") entry.detail = body.detail;
      }).catch(() => { entry.detail = "Response body unavailable"; }));
    }
  });
  info.attachments.push({ name: "write-events-note", contentType: "text/plain", body: Buffer.from("Project-write responses only; no tokens or request bodies collected.") });
  const login = await request.post(`${api}/api/auth/login`, { data: { email, password } });
  expect(login.status()).toBe(200);
  const { token } = await login.json(); expect(typeof token).toBe("string"); expect(token.length).toBeGreaterThan(0);
  const headers = { Authorization: `Bearer ${token}` };
  const name = `${brief.id}-${randomUUID()}`;
  const created = await request.post(`${api}/api/projects`, { headers,
    data: { name, project_input: { manual_fields: { units: "ft" } } } });
  expect(created.status()).toBe(200);
  const projectId = ((await created.json()).project as ProjectRecord).project_id;
  const saved = async () => {
    const response = await request.get(`${api}/api/projects/${encodeURIComponent(projectId)}`, { headers });
    expect(response.status()).toBe(200); return (await response.json()).project as ProjectRecord;
  };
  const snapshot = (project: ProjectRecord) => {
    if (!project.project_input) throw new Error("Saved project has no input document");
    const input = resolveCanonicalCanvasInput(project.project_input);
    const objects = [...(input.manual_fields?.site_objects ?? [])];
    for (const object of objects) {
      if (typeof object.id !== "string" || !object.id) throw new Error("Saved object has no stable identity");
    }
    return { units: input.manual_fields?.units, lot: input.manual_fields?.lot,
      sitePlan: input.manual_fields?.site_plan,
      objects: objects.sort((a, b) => a.id!.localeCompare(b.id!)) };
  };
  const assertTargets = (current: ReturnType<typeof snapshot>) => {
    expect(current.units).toBe(brief.expected.units);
    expect(current.lot).toMatchObject({ w: brief.expected.lot_width_ft, h: brief.expected.lot_height_ft });
    expect(current.sitePlan).toMatchObject({ building_program_sf: brief.expected.building_program_sf,
      parking_count: brief.expected.parking_count, building_type: "office" });
    const objects = current.objects.filter(item => item.meta?.command_source === "site_setup_program_command");
    expect(objects.length).toBeGreaterThan(0);
    expect(current.objects.some(item => item.meta?.command_source === "site_setup_subdivision_cad_command")).toBe(false);
    expect(objects.every(item => item.meta?.construction_release_allowed === false)).toBe(true);
  };
  await page.addInitScript(value => {
    sessionStorage.setItem("civora-ai-token", value);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/?debugPreview=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await page.getByTestId("civora-command-input").fill(brief.command);
  await workspaceCommandButton(page).click();
  await expect(async () => assertTargets(snapshot(await saved()))).toPass({ timeout: 10000 });
  await openWorkspaceTool(page, "Generate");
  await page.getByTestId("generate-main-action").click();
  await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|Needs input|Started|review/i);
  await openWorkspaceTool(page, "Deliver");
  await page.getByRole("button", { name: /Make Review Package/i }).click();
  await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|needs input/i);
  await expect(page.getByTestId("header-save-status")).toHaveText("Saved");
  // The command preserves the unique saved identity. Do not add an unrelated
  // metadata write merely to locate the project again; assert that identity.
  await expect(async () => { const current = await saved(); expect(current.name).toBe(name); assertTargets(snapshot(current)); }).toPass({ timeout: 10000 });
  const before = snapshot(await saved());
  await writeFile(info.outputPath("saved-before-reload.json"), JSON.stringify({ fixture: brief.id, before }, null, 2));
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}`, exact: true }).click();
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  const after = snapshot(await saved()); assertTargets(after); expect(after).toEqual(before);
  await writeFile(info.outputPath("saved-and-reopened.json"), JSON.stringify({ fixture: brief.id, before, after }, null, 2));
  const leases = await page.evaluate(() => Object.keys(localStorage).filter(key => key.startsWith("civora-project-tab-v1:")));
  await Promise.all(receipts);
  await writeFile(info.outputPath("reopen-write-boundary.json"), JSON.stringify({ writes, leases }, null, 2));
  // A single-page reopen must not silently start a conflicting save. Preserve a
  // clear failure instead of force-clicking through the branch-protection modal.
  await expect(page.getByTestId("project-tab-branch-dialog")).toBeHidden();
  await openWorkspaceTool(page, "Setup");
  await expect(page.getByTestId("brief-value-building-area")).toContainText(`${brief.expected.building_program_sf.toLocaleString("en-US")} sf`);
  await expect(page.getByTestId("brief-value-required-parking")).toContainText(`${brief.expected.parking_count} spaces`);
  await expect(page.getByTestId("header-save-status")).toHaveText("Saved");
});
