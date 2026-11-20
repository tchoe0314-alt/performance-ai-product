import { expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

const api = process.env.PLAYWRIGHT_API_BASE_URL ?? "";
const explicitlyLocal = process.env.CIVORA_PHASE0_LOCAL_TESTS === "1" && /^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(api);

test("Setup project type persists per project without replacing the saved program", async ({ page, request }) => {
  test.skip(!explicitlyLocal, "Requires the disposable localhost backend; never runs against hosted projects.");
  const registration = await request.post(`${api}/api/auth/register`, { data: {
    email: `setup-project-type-${randomUUID()}@example.test`,
    password: "Disposable-project-type-123",
    name: "Setup project type fixture",
  } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json();
  const headers = { Authorization: `Bearer ${token}` };
  const createProject = async (name: string, projectType: string, buildingAreaSf: number) => {
    const response = await request.post(`${api}/api/projects`, { headers, data: {
      name,
      project_input: {
        input_mode: "user",
        allow_ai_fill_for_blanks: false,
        manual_fields: {
          units: "ft",
          project_type: projectType,
          lot: { x: 0, y: 0, w: 600, h: 400 },
          site_plan: { building_area_sf: buildingAreaSf, required_parking: 48 },
        },
        meta: { site_inputs: { site_alignment_locked: true } },
      },
    } });
    expect(response.status()).toBe(200);
    return (await response.json()).project;
  };
  const first = await createProject("Setup Type A", "", 14_400);
  await createProject("Setup Type B", "industrial_site", 24_000);

  await page.addInitScript((value) => {
    localStorage.setItem("civora-ai-token", value);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Setup Type A" }).click();
  const selector = page.getByLabel("Project type");
  await expect(selector).toHaveValue("");
  await selector.selectOption("mixed_use");
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${first.project_id}`, { headers });
    const saved = (await response.json()).project.project_input.manual_fields;
    return { type: saved.project_type, area: saved.site_plan?.building_area_sf, parking: saved.site_plan?.required_parking };
  }).toEqual({ type: "mixed_use", area: 14_400, parking: 48 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Project type")).toHaveValue("mixed_use");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Setup Type B" }).click();
  await expect(page.getByLabel("Project type")).toHaveValue("industrial_site");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Setup Type A" }).click();
  await expect(page.getByLabel("Project type")).toHaveValue("mixed_use");

  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${first.project_id}`, { headers });
    const saved = (await response.json()).project.project_input.manual_fields;
    return { type: saved.project_type, area: saved.site_plan?.building_area_sf, parking: saved.site_plan?.required_parking };
  }).toEqual({ type: "mixed_use", area: 14_400, parking: 48 });
});
