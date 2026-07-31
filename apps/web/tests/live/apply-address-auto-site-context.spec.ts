import { expect, test } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

function candidateInbox(statuses: Record<string, "pending" | "accepted" | "rejected"> = {}) {
  const candidates = [
    {
      candidate_id: "building-1",
      candidate_type: "building_footprint",
      label: "Detected building footprint",
      source: "Test Buildings",
      provider: "Test Buildings",
      confidence: 0.88,
      object_count: 1,
    },
    {
      candidate_id: "road-1",
      candidate_type: "road_row",
      label: "Detected road / right-of-way",
      source: "Test Roads",
      provider: "Test Roads",
      confidence: 0.88,
      object_count: 1,
    },
  ].map((candidate) => ({
    ...candidate,
    status: statuses[candidate.candidate_id] ?? "pending",
    review_required: true,
    blocker_review_reason: "Confirm this source-backed candidate before using it as a project draft.",
  }));
  return {
    version: "candidate_review_inbox_v1",
    candidate_count: candidates.length,
    counts: {
      accepted: candidates.filter((candidate) => candidate.status === "accepted").length,
      rejected: candidates.filter((candidate) => candidate.status === "rejected").length,
      pending: candidates.filter((candidate) => candidate.status === "pending").length,
    },
    candidates,
    review_required: true,
  };
}

test("Apply Address automatically runs Auto Site Context", async ({ page }) => {
  let savedProjectInput: Record<string, unknown> | null = null;
  let fetchOnlineCalled = false;
  const candidateStatuses: Record<string, "pending" | "accepted" | "rejected"> = {};

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
    if (
      route.request().method() === "POST" &&
      new URL(route.request().url()).pathname === "/api/jobs/source-context"
    ) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Queue endpoint unavailable during rolling deployment." }),
      });
      return;
    }
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

  await page.route("**/api/projects/*/candidate-review", async (route) => {
    const payload = route.request().postDataJSON() as {
      candidate_ids?: string[];
      action?: "accept" | "reject" | "pending";
    };
    for (const candidateId of payload.candidate_ids ?? []) {
      candidateStatuses[candidateId] =
        payload.action === "accept" ? "accepted" : payload.action === "reject" ? "rejected" : "pending";
    }
    const projectInput = JSON.parse(JSON.stringify(savedProjectInput ?? {})) as {
      meta?: { site_inputs?: Record<string, unknown> };
    };
    projectInput.meta = projectInput.meta ?? {};
    projectInput.meta.site_inputs = {
      ...(projectInput.meta.site_inputs ?? {}),
      candidate_review_inbox_v1: candidateInbox(candidateStatuses),
      candidate_review_accepted_drafts_v1:
        candidateStatuses["building-1"] === "accepted"
          ? [
              {
                object_id: "draft_building-1",
                object_type: "building",
                source_candidate_id: "building-1",
                source_type: "official_gis",
                source_name: "Test Buildings",
                confidence: 0.88,
                geometry: {
                  type: "Polygon",
                  coordinates: [[
                    [-96.8002, 32.8002],
                    [-96.7998, 32.8002],
                    [-96.7998, 32.7998],
                    [-96.8002, 32.7998],
                    [-96.8002, 32.8002],
                  ]],
                },
              },
            ]
          : [],
    };
    savedProjectInput = projectInput as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: "Playwright Project",
          project_input: projectInput,
          latest_result: null,
          has_result: false,
        },
        candidate_review_inbox_v1: candidateInbox(candidateStatuses),
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
          candidate_count: 5,
          sources: [
            { key: "parcel_site_boundary", label: "parcel/site boundary", provider: "Test Parcels", candidate_count: 1, review_required: true, blockers: ["review-required"] },
            { key: "road_row", label: "road/ROW data", provider: "Test Roads", candidate_count: 1, review_required: true, blockers: ["review-required"] },
            { key: "building_footprints", label: "building footprints", provider: "Test Buildings", candidate_count: 1, review_required: true, blockers: ["review-required"] },
            { key: "imagery_object_detection", label: "imagery/object detection", provider: "Test Imagery Detector", candidate_count: 1, review_required: true, blockers: ["visual review only"] },
            { key: "terrain_dem_lidar", label: "terrain/DEM/LiDAR", provider: "USGS 3DEP EPQS", candidate_count: 1, review_required: true, blockers: ["not survey"] },
            {
              key: "public_utilities",
              label: "public utility layers",
              provider: "Test Stormwater, Test Water, Test Sanitary",
              candidate_count: 0,
              review_required: true,
              blockers: ["Configured utility providers checked but returned no features inside the active site."],
              child_sources: [
                { provider: "Test stormwater inlets", feature_count: 0, status: "ready_empty" },
                { provider: "Test stormwater discharge points", feature_count: 0, status: "ready_empty" },
                { provider: "Test sanitary mains", feature_count: 0, status: "ready_empty" },
                { provider: "Test waterlines", feature_count: 0, status: "ready_empty" },
              ],
            },
          ],
          missing_sources: [
            { key: "public_utilities", label: "public utility layers", missing: ["Configured utility providers checked but returned no features inside the active site."] },
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
          candidate_count: 5,
          feature_candidates: [
            { candidate_id: "parcel-1", feature_type: "parcel_or_site_boundary", source_type: "official_gis", source_name: "Test Parcels", evidence_source: "Test Parcels", confidence: 0.88, review_required: true, acceptance_status: "pending" },
            { candidate_id: "road-1", feature_type: "road_or_drive", source_type: "official_gis", source_name: "Test Roads", evidence_source: "Test Roads", confidence: 0.88, review_required: true, acceptance_status: "pending" },
            { candidate_id: "building-1", feature_type: "building_footprint", source_type: "official_gis", source_name: "Test Buildings", evidence_source: "Test Buildings", confidence: 0.88, review_required: true, acceptance_status: "pending" },
            { candidate_id: "image-building-1", feature_type: "building_footprint", source_type: "image_detected_candidate", source_name: "Test Imagery Detector", evidence_source: "Test Imagery Detector", confidence: 0.62, review_required: true, acceptance_status: "pending" },
            { candidate_id: "terrain-1", feature_type: "terrain", source_type: "official_gis", source_name: "USGS 3DEP EPQS", evidence_source: "USGS 3DEP EPQS", confidence: 0.72, review_required: true, acceptance_status: "pending" },
          ],
          imagery_object_detection_report_v1: {
            version: "imagery_object_detection_report_v1",
            status: "detected",
            provider: "Test Imagery Detector",
            detection_count: 1,
            detections: [{ detection_id: "image-building-1", kind: "building", confidence: 0.62 }],
            review_required: true,
            truth_label: "Imagery/object detection creates visual review candidates only.",
          },
        },
        candidate_review_inbox_v1: candidateInbox(),
        existing_conditions_package: { status: "review_required", production_ready: false },
        existing_conditions_summary: { production_ready: false },
      }),
    });
  });

  await page.addInitScript(
    ([tokenKey, restoreKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, "pw-token"] as const,
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

  if (process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
    await expect
      .poll(
        () => page.evaluate(() => Boolean((window as unknown as Record<string, unknown>).__civoraMapOverlayEnabled)),
        { timeout: 30_000 },
      )
      .toBe(true);
    await expect
      .poll(
        () =>
          page.evaluate(() => {
            const viewport = (window as unknown as Record<string, unknown>).__civoraMapViewport;
            if (!viewport || typeof viewport !== "object") return null;
            return Number((viewport as { lat?: unknown }).lat);
          }),
        { timeout: 30_000 },
      )
      .toBeCloseTo(32.8, 3);
    await expect
      .poll(
        () =>
          page.evaluate(() => {
            const viewport = (window as unknown as Record<string, unknown>).__civoraMapViewport;
            if (!viewport || typeof viewport !== "object") return null;
            return Number((viewport as { lng?: unknown }).lng);
          }),
        { timeout: 30_000 },
      )
      .toBeCloseTo(-96.8, 3);
  } else {
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText("Local site coordinates");
    await expect(page.getByTestId("preview-inner-map-toggle")).toBeDisabled();
  }
  await expect(page.getByTestId("local-site-bounds-overlay")).toHaveCount(0);

  await expect(page.getByTestId("auto-site-context-summary")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("auto-site-context-found")).toContainText("parcel/site boundary");
  await expect(page.getByTestId("auto-site-context-found")).toContainText("building footprints");
  await expect(page.getByTestId("auto-site-context-missing")).toContainText("public utility layers");
  await expect(page.getByTestId("auto-site-context-candidates")).toContainText("available for review");
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/Detected inside site/i);
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/parcel\/site boundary|building footprints/i);
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/missing public utility layers/i);
  await expect(page.getByTestId("auto-site-context-plain-summary")).toContainText(/not survey\/control/i);
  await expect(page.getByTestId("auto-site-context-source-table")).toBeVisible();
  await expect(page.getByTestId("auto-site-context-status-parcel")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-roads")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-buildings")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-imagery")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-detail-imagery")).toContainText(/Test Imagery Detector|1 review candidate/i);
  await expect(page.getByTestId("auto-site-context-status-terrain")).toContainText("found");
  await expect(page.getByTestId("auto-site-context-status-survey_control")).toContainText("needs source");
  await expect(page.getByTestId("auto-site-context-detail-survey_control")).toContainText("does not satisfy survey");
  await expect(page.getByTestId("auto-site-context-status-drainage")).toContainText(/needs source|assumed/);
  await expect(page.getByTestId("auto-site-context-detail-drainage")).toContainText(/stormwater|drainage|assumed/i);
  await expect(page.getByTestId("auto-site-context-status-utilities")).toContainText("needs source");
  await expect(page.getByTestId("auto-site-context-detail-utilities")).toContainText(/utility providers checked|Test stormwater/i);
  await expect(page.getByTestId("site-intelligence-summary")).toBeVisible();
  await expect(page.getByTestId("site-intelligence-one-sentence")).toContainText("Found road/ROW");
  await expect(page.getByTestId("site-intelligence-found-count")).toContainText("Found 3");
  await expect(page.getByTestId("site-intelligence-missing-count")).toContainText("Missing 1");
  await expect(page.getByTestId("site-intelligence-assumed-count")).toContainText("Assumed 1");
  await expect(page.getByTestId("site-intelligence-outside-count")).toContainText("Outside 1");
  await expect(page.getByTestId("site-intelligence-frontage")).toContainText("west side");
  await expect(page.getByTestId("site-intelligence-driveway")).toContainText("starting suggestion");
  await expect(page.getByTestId("site-intelligence-grading")).toContainText("not a grading surface");

  await page.getByTestId("review-found-context").click();
  const detectedItems = page.getByTestId("detected-items-review");
  await expect(detectedItems).toBeVisible();
  await expect(detectedItems).toContainText("Detected Items · 2 To Review");
  const buildingCandidate = detectedItems.locator('[data-candidate-id="building-1"]');
  await buildingCandidate.getByRole("button", { name: "Accept" }).click();
  await expect(detectedItems).toContainText("Detected Items · 1 To Review");
  const roadCandidate = detectedItems.locator('[data-candidate-id="road-1"]');
  await roadCandidate.getByRole("button", { name: "Reject" }).click();
  await expect(detectedItems).toContainText("Detected Items · 0 To Review");
  await expect(detectedItems).toContainText("Accepted");
  await expect(detectedItems).toContainText("Rejected");

  await page.getByRole("button", { name: "Draw" }).first().click();
  await expect(page.getByTestId("object-manager-panel")).toContainText("Test Buildings");
  await expect(
    page.getByTestId("object-manager-row").filter({ hasText: "Test Buildings" }).first(),
  ).toContainText(/Building|GIS review candidate/i);

  await page.getByTestId("header-chat-button").click();
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
  expect(JSON.stringify(savedProjectInput)).toContain("imagery_object_detection_report_v1");
});
