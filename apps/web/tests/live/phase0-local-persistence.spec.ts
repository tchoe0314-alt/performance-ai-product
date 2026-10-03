import { expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const explicitlyLocal = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1" && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);

async function inspectBuilding(page: Page) {
  await expect(page.getByTestId("project-status-summary")).toContainText("Project opened");
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const list = page.getByTestId("object-manager-panel");
  await expect(list).toBeVisible();
  if (!(await list.evaluate(element => element.hasAttribute("open")))) await list.locator("summary").click();
  await expect(list).toHaveAttribute("open", "");
  const row = page.getByTestId("object-manager-row").filter({ hasText: "Persistence Office" }).first();
  await row.getByTestId("object-manager-select").click();
  await row.getByTestId("object-manager-inspect").click();
}

test("real local authentication preserves manual geometry across save and reload and isolates owners", async ({ page, request }) => {
  test.skip(!explicitlyLocal, "Requires explicitly enabled disposable localhost backend; never runs against hosted data.");
  const register = async (suffix: string) => {
    const response = await request.post(`${api}/api/auth/register`, { data: {
      email: `phase0-${randomUUID()}-${suffix}@example.test`, password: "Disposable-phase0-123", name: "Phase 0 fixture",
    } });
    expect(response.status()).toBe(200);
    return response.json();
  };
  const owner = await register("owner");
  const stranger = await register("stranger");
  const headers = { Authorization: `Bearer ${owner.token}` };
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name: "Phase 0 Persistence Fixture",
    project_input: {
      input_mode: "user", strict_mode: false, allow_ai_fill_for_blanks: false,
      manual_fields: { units: "ft", project_type: "commercial", lot: { x: 0, y: 0, w: 900, h: 700 },
        site_objects: [{ id: "persistence-office", label: "Persistence Office", type: "office_building", x: 100, y: 120, w: 160, d: 90, placed: true, source: "manual_drawn", meta: { fixture_evidence: "synthetic, not engineering evidence" } }],
      }, meta: { site_inputs: { site_alignment_locked: true } },
    },
  } });
  expect(created.status()).toBe(200);
  const { project } = await created.json();
  const forbidden = await request.get(`${api}/api/projects/${project.project_id}`, { headers: { Authorization: `Bearer ${stranger.token}` } });
  expect([403, 404]).toContain(forbidden.status());
  const anonymous = await request.get(`${api}/api/projects/${project.project_id}`);
  expect(anonymous.status()).toBe(401);
  await page.addInitScript(token => {
    localStorage.setItem("civora-ai-token", token);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, owner.token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Phase 0 Persistence Fixture" }).click();
  await inspectBuilding(page);
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("100");
  await expect(page.getByTestId("selected-object-width-input")).toHaveValue("160");
  await expect(page.getByTestId("selected-object-depth-input")).toHaveValue("90");
  await page.getByTestId("selected-object-x-input").fill("125");
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    const payload = await response.json();
    const fields = payload.project.project_input.manual_fields;
    const objects = fields.site_objects ?? fields.buildings ?? [];
    return objects.find((item: { id: string }) => item.id === "persistence-office")?.x;
  }).toBe(125);
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await inspectBuilding(page);
  await expect(page.getByTestId("selected-object-x-input")).toHaveValue("125");
  await expect(page.getByTestId("selected-object-width-input")).toHaveValue("160");
  await expect(page.getByTestId("selected-object-depth-input")).toHaveValue("90");
});
