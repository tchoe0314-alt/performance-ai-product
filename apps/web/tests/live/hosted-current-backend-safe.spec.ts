import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

function isLocalOrigin(value: string | undefined) {
  try {
    const url = new URL(value ?? "");
    return url.protocol === "http:" && ["127.0.0.1", "localhost"].includes(url.hostname)
      && Boolean(url.port) && url.origin === value;
  } catch {
    return false;
  }
}

const liveEnabled = process.env.CIVORA_PRODUCTION_SAFE_TESTS === "1"
  && process.env.PLAYWRIGHT_BASE_URL === "https://civoraai.com";
const localEnabled = process.env.CIVORA_LOCAL_SAFE_TESTS === "1"
  && isLocalOrigin(process.env.PLAYWRIGHT_BASE_URL)
  && isLocalOrigin(process.env.PLAYWRIGHT_API_BASE_URL);
const api = localEnabled && !liveEnabled ? process.env.PLAYWRIGHT_API_BASE_URL! : "https://api.civoraai.com";
const enabled = liveEnabled || localEnabled;

// Live runs must not record credentials in video or trace artifacts.
test.use({ video: "off", trace: "off" });

test("current hosted website: isolated test-account editing, save/reopen and protected API", async ({ page, request }, testInfo) => {
  test.skip(!enabled, "Explicit live approval or disposable localhost website/API opt-in required.");
  const suffix = randomUUID();
  const password = `Synthetic-${randomUUID()}-123`;
  const email = `civora-safe-qa-${suffix}@example.test`;
  const name = `CIVORA TEST ONLY ${suffix.slice(0, 8)}`;
  const registered = await request.post(`${api}/api/auth/register`, { data: {
    email, password, name: "Civora synthetic website QA",
  } });
  expect(registered.status()).toBe(200);
  const loggedIn = await request.post(`${api}/api/auth/login`, { data: { email, password } });
  expect(loggedIn.status()).toBe(200);
  const { token } = await loggedIn.json();
  expect(token).toBeTruthy();
  const headers = { Authorization: `Bearer ${token}` };
  expect((await request.get(`${api}/api/jobs`)).status()).toBe(401);
  expect((await request.get(`${api}/api/jobs`, { headers })).status()).toBe(200);
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name,
    description: "Authorized non-destructive website test. Synthetic geometry, not a customer design.",
    project_input: { input_mode: "user", strict_mode: false, allow_ai_fill_for_blanks: false,
      manual_fields: { units: "ft", project_type: "commercial", lot: { x: 0, y: 0, w: 900, h: 700 },
        site_objects: [{ id: "safe-qa-office", label: "Synthetic QA Office", type: "office_building", x: 100, y: 120,
          w: 160, d: 90, placed: true, source: "manual_drawn" }],
      }, meta: { site_inputs: { site_alignment_locked: true } },
    },
    metadata: { synthetic_qa: true, test_only: true },
  } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  expect((await request.get(`${api}/api/projects/${project.project_id}`)).status()).toBe(401);
  // Prove authenticated isolation too: rejecting an anonymous request alone
  // does not establish separation between two valid customer accounts.
  const outsiderRegistered = await request.post(`${api}/api/auth/register`, { data: {
    email: `civora-safe-outsider-${randomUUID()}@example.test`,
    password: `Synthetic-${randomUUID()}-123`, name: "Civora synthetic isolation QA",
  } });
  expect(outsiderRegistered.status()).toBe(200);
  const outsider = await outsiderRegistered.json();
  expect(outsider.token).toBeTruthy();
  const outsiderHeaders = { Authorization: `Bearer ${outsider.token}` };
  const outsiderList = await request.get(`${api}/api/projects`, { headers: outsiderHeaders });
  expect(outsiderList.status()).toBe(200);
  const outsiderProjects = await outsiderList.json();
  expect((outsiderProjects.projects ?? []).some((item: { project_id: string }) => item.project_id === project.project_id)).toBe(false);
  expect([403, 404]).toContain((await request.get(`${api}/api/projects/${project.project_id}`, { headers: outsiderHeaders })).status());
  const blockedWrites: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  // Never queue generation/imagery/export work or mutate another project.
  // This is a safety boundary, not a mocked successful backend response.
  await page.route(`${api}/**`, async route => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    if (["GET", "HEAD", "OPTIONS"].includes(req.method())) return route.continue();
    const ownLogin = path === "/api/auth/login" && req.method() === "POST"
      && req.postDataJSON()?.email === email;
    const ownedSave = path === "/api/projects" && req.method() === "POST"
      && req.postDataJSON()?.project_id === project.project_id;
    const ownedPresence = path === `/api/projects/${project.project_id}/presence`;
    const ownLogout = path === "/api/auth/logout" && req.method() === "POST";
    if (ownLogin || ownLogout || ownedSave || ownedPresence) return route.continue();
    blockedWrites.push(`${req.method()} ${path}`);
    await route.fulfill({ status: 409, json: { detail: "Live QA guard: this action is outside the authorized test project." } });
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Sign In Mode", exact: true }).click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}` }).click();
  const inspect = async () => {
    await openWorkspaceTool(page, "Draw");
    const list = page.getByTestId("object-manager-panel");
    const row = page.getByTestId("object-manager-row").filter({ hasText: "Synthetic QA Office" }).first();
    const reveal = async (control: "object-manager-select" | "object-manager-inspect") => {
      await expect.poll(async () => {
        if (await row.getByTestId(control).isVisible()) return true;
        if (!(await list.evaluate(node => node.hasAttribute("open")))) await list.locator(":scope > summary").click();
        return row.getByTestId(control).isVisible();
      }).toBe(true);
    };
    await reveal("object-manager-select");
    await row.getByTestId("object-manager-select").click();
    await reveal("object-manager-inspect");
    await row.getByTestId("object-manager-inspect").click();
  };
  await inspect();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("100");
  await expect(page.getByTestId("selected-object-width-input")).toHaveValue("160");
  await expect(page.getByTestId("selected-object-depth-input")).toHaveValue("90");
  await page.getByTestId("selected-object-x-input").fill("125");
  await expect.poll(async () => {
    const saved = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    expect(saved.status()).toBe(200);
    const payload = await saved.json();
    const fields = payload.project.project_input.manual_fields;
    return (fields.site_objects ?? fields.buildings ?? []).find((item: { id: string }) => item.id === "safe-qa-office")?.x;
  }).toBe(125);
  await page.getByTestId("selected-object-width-input").fill("175");
  const savedWidth = async () => {
    const saved = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    expect(saved.status()).toBe(200);
    const fields = (await saved.json()).project.project_input.manual_fields;
    return (fields.site_objects ?? fields.buildings ?? []).find((item: { id: string }) => item.id === "safe-qa-office")?.w;
  };
  await expect.poll(savedWidth).toBe(175);
  await page.getByRole("button", { name: "Undo last draft change", exact: true }).click();
  await expect.poll(savedWidth).toBe(160);
  await page.getByRole("button", { name: "Redo draft change", exact: true }).click();
  await expect.poll(savedWidth).toBe(175);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await inspect();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("125");
  await expect(page.getByTestId("selected-object-width-input")).toHaveValue("175");
  await expect(page.getByTestId("selected-object-depth-input")).toHaveValue("90");
  for (const panel of ["Setup", "Generate", "Review", "Deliver"] as const) {
    await openWorkspaceTool(page,panel);
    await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
  }
  expect(blockedWrites, "UI must not attempt unapproved background writes").toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("current-hosted-test-project.png") });
  const browserToken = await page.evaluate(() => sessionStorage.getItem("civora-ai-token") || localStorage.getItem("civora-ai-token"));
  expect(browserToken).toBeTruthy();
  await page.getByRole("button", { name: `Sign out ${email}`, exact: true }).click();
  await expect(page.getByTestId("workspace-canvas-shell")).toHaveCount(0);
  await page.getByRole("button", { name: "Sign In Mode", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign In", exact: true })).toBeVisible();
  expect((await request.get(`${api}/api/auth/me`, { headers: { Authorization: `Bearer ${browserToken}` } })).status()).toBe(401);
  expect(blockedWrites).toEqual([]);
  expect(pageErrors).toEqual([]);
  await testInfo.attach("safe-qa-scope", { body: JSON.stringify({
    website: process.env.PLAYWRIGHT_BASE_URL, api, project_id: project.project_id, project_name: name,
    synthetic: true, real_sign_in_form: true, saved_undo_redo: true, sign_out_revokes_browser_session: true,
    authenticated_cross_account_read_denied: true, no_deletion: true, no_generation: true, no_deployment: true,
  }), contentType: "application/json" });
});
