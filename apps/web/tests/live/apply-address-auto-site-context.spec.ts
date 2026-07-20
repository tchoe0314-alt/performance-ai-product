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
          site_intelligence_summary_v1: {
            version: "site_intelligence_summary_v1",
            one_sentence: "Found road/ROW, building footprints, and parcel candidates near the address; review missing and assumed items before generating.",
            found: [
              { feature_type: "building_footprint", label: "building footprint", count: 1, confidence: "source-backed" },
              { feature_type: "road_or_drive", label: "road/ROW", count: 1, confidence: "source-backed" },
              { feature_type: "parcel_or_site_boundary", label: "parcel/site boundary", count: 1, confidence: "source-backed" },
            ],
            missing: [{ source_type: "existing_utilities", label: "public utility layers", status: "missing_source" }],
            assumed: [{ key: "terrain_direction", label: "Terrain/drainage direction", status: "single_point_context" }],
            outside_site: [{ candidate_id: "offsite-building", label: "building footprint" }],
            road_frontage: { status: "candidate", likely_frontage_side: "west", message: "Likely road frontage is on the west side based on source candidates." },
            driveway_suggestions: [{ status: "candidate", frontage_side: "west", message: "Use this as a starting suggestion only; confirm access spacing, sight distance, and jurisdiction standards." }],
            grading_context: { status: "single_point_elevation", message: "Public point elevation gives vertical context, not a grading surface or drainage direction." },
            review_required: true,
            survey_control_satisfied: false,
            construction_release_allowed: false,
          },
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
  const addressSection = page.getByTestId("setup-address-truth");
  if (!(await addressSection.evaluate((node) => node.hasAttribute("open")))) {
    await addressSection.locator("summary").click();
  }
  await page.getByLabel("Type project address").fill("1 Main St, Test City, TX");
  await page.getByRole("button", { name: "Apply address" }).click();

  await expect(page.getByTestId("auto-site-context-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("auto-site-context-found")).toContainText("parcel/site boundary");
  await expect(page.getByTestId("auto-site-context-found")).toContainText("building footprints");
  await expect(page.getByTestId("auto-site-context-missing")).toContainText("public utility layers");
  await expect(page.getByTestId("auto-site-context-candidates")).toContainText("review required");
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/Detected inside site/i);
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/parcel\/site boundary|building footprints/i);
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/missing public utility layers/i);
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/not survey\/control/i);
  await expect(page.getByTestId("auto-site-context-source-table")).toBeVisible();
  await expect(page.getByTestId("auto-site-context-status-parcel")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-roads")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-buildings")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-terrain")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-utilities")).toContainText("missing");
  await expect(page.getByTestId("auto-site-context-detail-utilities")).toContainText("No existing utilities GIS source is configured");
  await expect(page.getByTestId("site-intelligence-summary")).toBeVisible();
  await expect(page.getByTestId("site-intelligence-one-sentence")).toContainText("Found road/ROW");
  await expect(page.getByTestId("site-intelligence-found-count")).toContainText("Found 3");
  await expect(page.getByTestId("site-intelligence-missing-count")).toContainText("Missing 1");
  await expect(page.getByTestId("site-intelligence-assumed-count")).toContainText("Assumed 1");
  await expect(page.getByTestId("site-intelligence-outside-count")).toContainText("Outside 1");
  await expect(page.getByTestId("site-intelligence-frontage")).toContainText("west side");
  await expect(page.getByTestId("site-intelligence-driveway")).toContainText("starting suggestion");
  await expect(page.getByTestId("site-intelligence-grading")).toContainText("not a grading surface");

  await page.getByRole("button", { name: "Open chat from header" }).click();
  const composer = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
  await composer.fill("what did you find here?");
  await composer.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Found inside the site");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Buildings");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Utilities");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("not survey/control");

  await composer.fill("why didn't it detect utilities and grading?");
  await composer.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Missing or unavailable");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Utilities");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Terrain / elevation");
  await expect(page.getByTestId("workspace-right-panel")).toContainText("not survey/control");

  expect(fetchOnlineCalled).toBeTruthy();
  expect(JSON.stringify(savedProjectInput)).toContain("online_existing_conditions_discovery_v1");
  expect(JSON.stringify(savedProjectInput)).toContain("site_intelligence_summary_v1");
});
