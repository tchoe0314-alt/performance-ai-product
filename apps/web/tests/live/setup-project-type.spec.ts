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
  await createProject("Setup Type B", "legacy_custom_campus", 24_000);
  type GenerateQueueRequest = { request?: { manual_fields?: { project_type?: string; site_plan?: { building_area_sf?: number; required_parking?: number } } } };
  let generateRequest: GenerateQueueRequest | null = null;
  await page.route("**/api/jobs/orchestrate", async (route) => {
    generateRequest = route.request().postDataJSON() as GenerateQueueRequest;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      success: true,
      job: { job_id: "setup-type-generate", job_type: "orchestrate", status: "queued", progress: 0 },
    }) });
  });

  await page.addInitScript((value) => {
    localStorage.setItem("civora-ai-token", value);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Setup Type A" }).click();
  const selector = page.getByLabel("Project type");
  await expect(selector).toHaveValue("");
  await selector.selectOption("industrial_site");
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${first.project_id}`, { headers });
    const saved = (await response.json()).project.project_input.manual_fields;
    return { type: saved.project_type, area: saved.site_plan?.building_area_sf, parking: saved.site_plan?.required_parking };
  }).toEqual({ type: "industrial_site", area: 14_400, parking: 48 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Project type")).toHaveValue("industrial_site");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Setup Type B" }).click();
  await expect(page.getByLabel("Project type")).toHaveValue("legacy_custom_campus");
  await expect(page.getByLabel("Project type").locator("option:checked")).toHaveText("Existing type: legacy_custom_campus");
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Setup Type A" }).click();
  await expect(page.getByLabel("Project type")).toHaveValue("industrial_site");

  await page.getByRole("button", { name: "Generate", exact: true }).click();
  await page.getByTestId("generate-main-action").click();
  await expect.poll(() => generateRequest).not.toBeNull();
  const capturedRequest = generateRequest as GenerateQueueRequest | null;
  expect(capturedRequest?.request?.manual_fields?.project_type).toBe("industrial_site");
  expect(capturedRequest?.request?.manual_fields?.site_plan).toMatchObject({ building_area_sf: 14_400, required_parking: 48 });
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${first.project_id}`, { headers });
    const saved = (await response.json()).project.project_input.manual_fields;
    return { type: saved.project_type, area: saved.site_plan?.building_area_sf, parking: saved.site_plan?.required_parking };
  }).toEqual({ type: "industrial_site", area: 14_400, parking: 48 });
});

test("synthetic geocode persists confirmed provenance and rejects an uncertain replacement without provider traffic", async ({ page, request }) => {
  test.skip(!explicitlyLocal, "Synthetic regression only; it does not verify Mapbox configuration, terms, cost, or release readiness.");
  const registration = await request.post(`${api}/api/auth/register`, { data: {
    email: `setup-geocode-${randomUUID()}@example.test`, password: "Disposable-geocode-123", name: "Synthetic geocode fixture",
  } });
  expect(registration.status()).toBe(200);
  const { token } = await registration.json();
  const headers = { Authorization: `Bearer ${token}` };
  const created = await request.post(`${api}/api/projects`, { headers, data: {
    name: "Synthetic Geocode Persistence",
    project_input: { input_mode: "user", allow_ai_fill_for_blanks: false, manual_fields: {
      units: "ft", lot: { x: 0, y: 0, w: 600, h: 400 },
    }, meta: { site_inputs: { site_alignment_locked: true } } },
  } });
  expect(created.status()).toBe(200);
  const project = (await created.json()).project;
  let geocodeMode: "success" | "uncertain" | "not_found" = "success";
  let providerTraffic = 0;
  await page.route("https://api.mapbox.com/**", async (route) => { providerTraffic += 1; await route.abort("blockedbyclient"); });
  await page.route("**/api/geocode", async (route) => {
    const body = geocodeMode === "success" ? {
      success: true, status: "ready", lat: 35.123456, lng: -80.654321,
      display_name: "100 SYNTHETIC WAY, TEST CITY, NC", provider: "mapbox", confidence: 0.93,
      crs: { epsg: "EPSG:4326", units: "degrees", source: "mapbox_geocoder" },
      location_context: { coordinates: { lat: 35.123456, lng: -80.654321 }, evidence_source: "mapbox_geocoder", truth_label: "Synthetic location context only." },
    } : geocodeMode === "uncertain" ? {
      success: false, status: "uncertain_match", blocked: true,
      message: "Address lookup returned an uncertain or unrelated match.",
      blockers: [{ area: "geocode", code: "address_match_uncertain", message: "Address lookup returned an uncertain or unrelated match." }],
    } : {
      success: false, status: "not_found", blocked: true,
      message: "Address could not be geocoded by the configured provider.",
      blockers: [{ area: "geocode", code: "address_not_found", message: "Address could not be geocoded by the configured provider." }],
    };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/api/jobs/source-context", async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic test blocks downstream source discovery." }) });
  });
  await page.addInitScript((value) => {
    localStorage.setItem("civora-ai-token", value);
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  }, token);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Synthetic Geocode Persistence" }).click();
  const address = page.getByLabel("Type project address");
  await address.fill("100 Synthetic Way, Test City, NC");
  await page.getByRole("button", { name: "Apply address" }).click();
  await expect.poll(async () => {
    const response = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
    return (await response.json()).project.project_input.meta.site_inputs.geocode;
  }).toMatchObject({ lat: 35.123456, lng: -80.654321, provider: "mapbox", confidence: 0.93, crs: { epsg: "EPSG:4326" } });
  expect(providerTraffic).toBe(0);

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByLabel("Type project address")).toHaveValue("100 Synthetic Way, Test City, NC");
  geocodeMode = "uncertain";
  await page.getByLabel("Type project address").fill("Unrelated ambiguous location");
  await page.getByRole("button", { name: "Apply address" }).click();
  await expect(page.getByTestId("apply-address-status")).toContainText("uncertain or unrelated match");
  const after = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
  expect((await after.json()).project.project_input.meta.site_inputs.geocode).toMatchObject({ lat: 35.123456, lng: -80.654321, provider: "mapbox" });
  geocodeMode = "not_found";
  await page.getByLabel("Type project address").fill("No-result synthetic location");
  await page.getByRole("button", { name: "Apply address" }).click();
  await expect(page.getByTestId("apply-address-status")).toContainText("could not be geocoded");
  const afterNoResult = await request.get(`${api}/api/projects/${project.project_id}`, { headers });
  expect((await afterNoResult.json()).project.project_input.meta.site_inputs.geocode).toMatchObject({ lat: 35.123456, lng: -80.654321, provider: "mapbox" });
  expect(providerTraffic).toBe(0);
});
