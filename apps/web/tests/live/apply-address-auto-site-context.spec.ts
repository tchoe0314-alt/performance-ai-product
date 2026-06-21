import { expect, test } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";

test("Apply Address automatically runs Auto Site Context", async ({ page }) => {
  let savedProjectInput: Record<string, unknown> | null = null;
  let fetchOnlineCalled = false;

  await page.route("**/api/auth/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        user_count: 1,
        registration_allowed: true,
      }),
    });
  });

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: { user_id: "pw-user", email: "pw@example.com", name: "Playwright" },
      }),
    });
  });

  await page.route("**/api/jobs**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, jobs: [] }),
    });
  });

  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, projects: [] }),
      });
      return;
    }
    const payload = route.request().postDataJSON() as {
      project_input?: Record<string, unknown>;
      latest_result?: Record<string, unknown> | null;
    };
    savedProjectInput = payload.project_input ?? null;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: "Playwright Project",
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
        },
      }),
    });
  });

  await page.route("**/api/geocode", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        status: "ready",
        lat: 32.8,
        lng: -96.8,
        display_name: "1 MAIN ST, TEST CITY, TX",
        provider: "test_geocoder",
        confidence: 0.95,
        crs: { epsg: "EPSG:4326", units: "degrees" },
        location_context: {
          address: "1 MAIN ST, TEST CITY, TX",
          coordinates: { lat: 32.8, lng: -96.8 },
          truth_label: "Address/geocode is location context only.",
        },
      }),
    });
  });

  await page.route("**/api/existing-conditions/fetch-online", async (route) => {
    fetchOnlineCalled = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        status: "ready_with_context",
        online_existing_conditions_discovery_v1: {
          version: "online_existing_conditions_discovery_v1",
          status: "candidates_found",
          candidate_count: 4,
          sources: [
            { key: "parcel_site_boundary", label: "parcel/site boundary", provider: "Test Parcels", candidate_count: 1, review_required: true, blockers: ["review-required"] },
            { key: "road_row", label: "road/ROW data", provider: "Test Roads", candidate_count: 1, review_required: true, blockers: ["review-required"] },
            { key: "building_footprints", label: "building footprints", provider: "Test Buildings", candidate_count: 1, review_required: true, blockers: ["review-required"] },
            { key: "terrain_dem_lidar", label: "terrain/DEM/LiDAR", provider: "USGS 3DEP EPQS", candidate_count: 1, review_required: true, blockers: ["not survey"] },
            { key: "public_utilities", label: "public utility layers", provider: "", candidate_count: 0, review_required: true, blockers: ["No existing utilities GIS source is configured."] },
          ],
          missing_sources: [
            { key: "public_utilities", label: "public utility layers", missing: ["No existing utilities GIS source is configured."] },
          ],
          survey_control: { survey_control_satisfied: false },
          review_required: true,
          acceptance_status: "candidate",
          construction_release_allowed: false,
        },
        map_feature_detection_report_v1: {
          version: "map_feature_detection_report_v1",
          candidate_count: 4,
          feature_candidates: [
            { candidate_id: "parcel-1", feature_type: "parcel_or_site_boundary", source_type: "official_gis", source_name: "Test Parcels", evidence_source: "Test Parcels", confidence: 0.88, review_required: true, acceptance_status: "pending" },
            { candidate_id: "road-1", feature_type: "road_or_drive", source_type: "official_gis", source_name: "Test Roads", evidence_source: "Test Roads", confidence: 0.88, review_required: true, acceptance_status: "pending" },
            { candidate_id: "building-1", feature_type: "building_footprint", source_type: "official_gis", source_name: "Test Buildings", evidence_source: "Test Buildings", confidence: 0.88, review_required: true, acceptance_status: "pending" },
            { candidate_id: "terrain-1", feature_type: "terrain", source_type: "official_gis", source_name: "USGS 3DEP EPQS", evidence_source: "USGS 3DEP EPQS", confidence: 0.72, review_required: true, acceptance_status: "pending" },
          ],
        },
        existing_conditions_package: { status: "review_required", production_ready: false },
        existing_conditions_summary: { production_ready: false },
      }),
    });
  });

  await page.addInitScript(
    ([tokenKey, authToken]) => window.localStorage.setItem(tokenKey, authToken),
    [TOKEN_KEY, "pw-token"] as const,
  );

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Setup" }).first().click();
  await page.getByTestId("setup-address-truth").locator("summary").click();
  await page.getByLabel("Type project address").fill("1 Main St, Test City, TX");
  await page.getByRole("button", { name: "Apply address" }).click();

  await expect(page.getByTestId("auto-site-context-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("auto-site-context-found")).toContainText("parcel/site boundary");
  await expect(page.getByTestId("auto-site-context-found")).toContainText("building footprints");
  await expect(page.getByTestId("auto-site-context-missing")).toContainText("public utility layers");
  await expect(page.getByTestId("auto-site-context-candidates")).toContainText("review required");

  expect(fetchOnlineCalled).toBeTruthy();
  expect(JSON.stringify(savedProjectInput)).toContain("online_existing_conditions_discovery_v1");
});
