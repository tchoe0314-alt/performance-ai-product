import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

const api = "https://api.civoraai.com";
const enabled = process.env.CIVORA_PRODUCTION_SAFE_TESTS === "1"
  && process.env.PLAYWRIGHT_BASE_URL === "https://civoraai.com";

test("current hosted website: isolated test-account editing, save/reopen and protected API", async ({ page, request }, testInfo) => {
  test.skip(!enabled, "Explicit approval and exact current website target required.");
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
  const blockedWrites: string[] = [];
  const pageErrors: string[] = [];
  page.on("pageerror", error => pageErrors.push(error.message));
  // Never queue generation/imagery/export work or mutate another project.
  // This is a safety boundary, not a mocked successful backend response.
  await page.route(`${api}/**`, async route => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    if (["GET", "HEAD", "OPTIONS"].includes(req.method())) return route.continue();
    const ownedSave = path === "/api/projects" && req.method() === "POST"
      && req.postDataJSON()?.project_id === project.project_id;
    const ownedPresence = path === `/api/projects/${project.project_id}/presence`;
    if (ownedSave || ownedPresence) return route.continue();
    blockedWrites.push(`${req.method()} ${path}`);
    await route.fulfill({ status: 409, json: { detail: "Live QA guard: this action is outside the authorized test project." } });
  });
  await page.addInitScript(authToken => {
    localStorage.setItem("civora-ai-token", authToken);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: `Open project ${name}` }).click();
  const inspect = async () => {
    await page.getByRole("button", { name: "Draw", exact: true }).first().click();
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
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await inspect();
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("125");
  await expect(page.getByTestId("selected-object-width-input")).toHaveValue("160");
  await expect(page.getByTestId("selected-object-depth-input")).toHaveValue("90");
  for (const panel of ["Setup", "Generate", "Review", "Deliver"]) {
    await page.getByRole("button", { name: panel, exact: true }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).toBeVisible();
  }
  expect(blockedWrites, "UI must not attempt unapproved background writes").toEqual([]);
  expect(pageErrors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath("current-hosted-test-project.png") });
  await testInfo.attach("safe-qa-scope", { body: JSON.stringify({
    website: "https://civoraai.com", api, project_id: project.project_id, project_name: name,
    synthetic: true, no_deletion: true, no_generation: true, no_deployment: true,
  }), contentType: "application/json" });
});
