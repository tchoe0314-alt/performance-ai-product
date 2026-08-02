import { expect, test, type Locator } from "@playwright/test";
import { readFile } from "node:fs/promises";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

async function clickExposedSurface(surface: Locator, xRatio: number, yRatio: number) {
  await surface.scrollIntoViewIfNeeded();
  const point = await surface.evaluate(
    (element, ratios) => {
      const rect = element.getBoundingClientRect();
      const clamp = (value: number) => Math.max(0.08, Math.min(0.92, value));
      const candidates: Array<{ x: number; y: number; distance: number }> = [];
      for (const xOffset of [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24]) {
        for (const yOffset of [0, -0.08, 0.08, -0.16, 0.16, -0.24, 0.24]) {
          const nextXRatio = clamp(ratios.xRatio + xOffset);
          const nextYRatio = clamp(ratios.yRatio + yOffset);
          const x = rect.left + rect.width * nextXRatio;
          const y = rect.top + rect.height * nextYRatio;
          const hit = document.elementFromPoint(x, y);
          const blocked = hit?.closest?.(
            '[data-object-overlay],button,input,select,textarea,aside,header,[data-testid="cad-precision-tools"],[data-testid="workspace-right-panel"]',
          );
          if ((hit === element || element.contains(hit)) && !blocked) {
            candidates.push({
              x,
              y,
              distance: Math.abs(nextXRatio - ratios.xRatio) + Math.abs(nextYRatio - ratios.yRatio),
            });
          }
        }
      }
      candidates.sort((a, b) => a.distance - b.distance);
      return candidates[0] ?? {
        x: rect.left + rect.width * clamp(ratios.xRatio),
        y: rect.top + rect.height * clamp(ratios.yRatio),
      };
    },
    { xRatio, yRatio },
  );
  await surface.page().mouse.click(point.x, point.y);
}

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
    {
      candidate_id: "image-building-1",
      candidate_type: "building_footprint",
      label: "Detected imagery building footprint",
      source: "Civora Vision",
      provider: "Civora Vision",
      confidence: 0.62,
      object_count: 1,
      source_record: {
        candidate_id: "image-building-1",
        feature_type: "building_footprint",
        source_type: "image_detected_candidate",
        source_name: "Civora Vision",
        source_feature_id: "vision-detection-1",
        properties: {
          vision_detection_id: "vision-detection-1",
          imagery_frame_id: "frame-1",
          source_rights: { training_use_allowed: true },
        },
      },
    },
    ...Array.from({ length: 30 }, (_, index) => ({
      candidate_id: `parcel-extra-${index + 1}`,
      candidate_type: "parcel_site_boundary",
      label: `Additional parcel candidate ${index + 1}`,
      source: "Test Parcels",
      provider: "Test Parcels",
      confidence: 0.75,
      object_count: 1,
    })),
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
  let fetchOnlineRequest: Record<string, unknown> | null = null;
  let lastVisionCorrectionPayload: Record<string, unknown> | null = null;
  const candidateStatuses: Record<string, "pending" | "accepted" | "rejected"> = {};
  let markOnlineFetchStarted: () => void = () => undefined;
  let releaseOnlineFetch: () => void = () => undefined;
  let markCandidateDecisionStarted: () => void = () => undefined;
  let releaseCandidateDecision: () => void = () => undefined;
  let delayNextCandidateDecision = true;
  const onlineFetchStarted = new Promise<void>((resolve) => {
    markOnlineFetchStarted = resolve;
  });
  const onlineFetchRelease = new Promise<void>((resolve) => {
    releaseOnlineFetch = resolve;
  });
  const candidateDecisionStarted = new Promise<void>((resolve) => {
    markCandidateDecisionStarted = resolve;
  });
  const candidateDecisionRelease = new Promise<void>((resolve) => {
    releaseCandidateDecision = resolve;
  });

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
          jurisdiction: {
            country: "United States",
            country_code: "US",
            region: "Texas",
            place: "Test City",
          },
          truth_label: "Address/geocode is location context only.",
        },
      }),
    });
  });

  await page.route("**/api/projects/*/candidate-review", async (route) => {
    const payload = route.request().postDataJSON() as {
      candidate_ids?: string[];
      action?: "accept" | "reject" | "pending" | "correct";
      corrected_feature_type?: string;
      corrected_geometry?: Record<string, unknown>;
      correction_coordinate_space?: string;
    };
    if ((payload.candidate_ids ?? []).includes("image-building-1")) {
      lastVisionCorrectionPayload = payload as Record<string, unknown>;
    }
    for (const candidateId of payload.candidate_ids ?? []) {
      candidateStatuses[candidateId] =
        payload.action === "accept" || payload.action === "correct"
          ? "accepted"
          : payload.action === "reject"
            ? "rejected"
            : "pending";
    }
    if (delayNextCandidateDecision) {
      delayNextCandidateDecision = false;
      markCandidateDecisionStarted();
      await candidateDecisionRelease;
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
    const responseProjectInput = JSON.parse(JSON.stringify(projectInput)) as {
      meta?: { site_inputs?: Record<string, unknown> };
    };
    responseProjectInput.meta = responseProjectInput.meta ?? {};
    responseProjectInput.meta.site_inputs = {
      ...(responseProjectInput.meta.site_inputs ?? {}),
      // Simulate an older backend project shell racing the current browser
      // workspace. Candidate review state is authoritative, but this stale
      // lock flag must not replace the user's newer locked site.
      site_alignment_locked: false,
      // The top-level inbox is the authoritative decision response. Keep the
      // project snapshot stale here to prove the UI reconciles both payloads.
      candidate_review_inbox_v1: candidateInbox(),
    };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: "Playwright Project",
          project_input: responseProjectInput,
          latest_result: null,
          has_result: false,
        },
        candidate_review_inbox_v1: candidateInbox(candidateStatuses),
        civora_vision_training_dataset_v1: {
          version: "civora_vision_training_dataset_v1",
          example_count: 1,
          reviewed_example_count: candidateStatuses["image-building-1"] === "accepted" ? 1 : 0,
          training_eligible_example_count:
            candidateStatuses["image-building-1"] === "accepted" && payload.correction_coordinate_space !== "project_local" ? 1 : 0,
          counts: {
            accepted: 0,
            rejected: 0,
            corrected: candidateStatuses["image-building-1"] === "accepted" ? 1 : 0,
            pending: candidateStatuses["image-building-1"] === "accepted" ? 0 : 1,
          },
          contains_image_bytes: false,
        },
        civora_vision_quality_report_v1: {
          version: "civora_vision_quality_report_v1",
          evaluation_status: "ground_truth_not_attached",
          precision: null,
          recall: null,
          quality_claim_allowed: false,
        },
      }),
    });
  });

  await page.route("**/api/projects/*/vision-learning", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project_id: "pw-project",
        civora_vision_training_dataset_v1: {
          version: "civora_vision_training_dataset_v1",
          example_count: 1,
          reviewed_example_count: 1,
          training_eligible_example_count: 1,
          contains_image_bytes: false,
        },
        civora_vision_quality_report_v1: {
          version: "civora_vision_quality_report_v1",
          evaluation_status: "ground_truth_not_attached",
          precision: null,
          recall: null,
          quality_claim_allowed: false,
        },
      }),
    });
  });

  await page.route("**/api/existing-conditions/fetch-online", async (route) => {
    fetchOnlineCalled = true;
    fetchOnlineRequest = route.request().postDataJSON() as Record<string, unknown>;
    markOnlineFetchStarted();
    await onlineFetchRelease;
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
            {
              key: "road_row",
              label: "road/ROW data",
              provider: "OpenStreetMap",
              candidate_count: 1,
              source_tier: "community_global",
              authoritative: false,
              attribution: "OpenStreetMap contributors, ODbL 1.0",
              review_required: true,
              blockers: ["Community-mapped road context; not authoritative ROW."],
            },
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

  await onlineFetchStarted;
  await page.getByRole("button", { name: "Draw" }).first().click();
  await expect(page.getByTestId("object-manager-panel")).toBeVisible();
  const cadTools = page.getByTestId("draw-cad-tools-section");
  const drawingSurface = page.getByTestId("preview-drawing-surface").filter({ visible: true }).first();
  await page.getByTestId("draw-site-boundary-toolbar").filter({ visible: true }).first().click();
  await clickExposedSurface(drawingSurface, 0.2, 0.25);
  await clickExposedSurface(drawingSurface, 0.72, 0.28);
  await clickExposedSurface(drawingSurface, 0.68, 0.78);
  await clickExposedSurface(drawingSurface, 0.24, 0.75);
  await expect(page.getByTestId("site-status")).toContainText("Site Locked");
  await cadTools.getByTestId("cad-tool-area").filter({ visible: true }).first().click();
  await clickExposedSurface(drawingSurface, 0.25, 0.52);
  await clickExposedSurface(drawingSurface, 0.38, 0.47);
  await clickExposedSurface(drawingSurface, 0.44, 0.62);
  await expect(page.getByTestId("canvas-quick-finish").filter({ visible: true }).first()).toBeEnabled();
  await page.getByTestId("canvas-quick-finish").filter({ visible: true }).first().click();
  await expect(page.getByTestId("object-manager-row").filter({ hasText: /Custom Area/ }).first()).toBeVisible();
  releaseOnlineFetch();
  await expect
    .poll(() => JSON.stringify(savedProjectInput), { timeout: 30_000 })
    .toContain("online_existing_conditions_discovery_v1");
  await expect.poll(() => JSON.stringify(savedProjectInput), { timeout: 30_000 }).toContain('"site_alignment_locked":true');
  await expect.poll(() => JSON.stringify(savedProjectInput), { timeout: 30_000 }).toContain("site_boundary_geometry");
  await expect(page.getByTestId("object-manager-panel")).toBeVisible();
  await page.getByRole("button", { name: "Setup" }).first().click();

  const runtimeMapToggle = page.getByTestId("preview-inner-map-toggle");
  if (await runtimeMapToggle.isEnabled()) {
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

    const canvas = page.getByTestId("workspace-canvas-shell");
    await canvas.getByTestId("preview-quality-high").click();
    await expect(page.getByText("Creating AI realism", { exact: true })).toHaveCount(0);
    for (let cycle = 0; cycle < 3; cycle += 1) {
      await canvas.getByTestId("preview-mode-3d").click();
      await expect(canvas).toContainText(/3D Model|3D geometry not ready yet/i);
      await canvas.getByTestId("preview-mode-2d").click();
      await expect(page.locator(".mapboxgl-canvas")).toHaveCount(1, { timeout: 20_000 });
      await expect(page.locator(".mapboxgl-canvas")).toBeVisible({ timeout: 20_000 });
    }
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
    await expect(page.getByTestId("local-site-bounds-overlay")).toHaveCount(0);
  } else {
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(/Local (site coordinates|drawing scale|review canvas site extent)/i);
    await expect(page.getByTestId("preview-inner-map-toggle")).toBeDisabled();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    await expect(page.getByTestId("local-site-bounds-overlay")).toHaveCount(0);
  }

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
  await expect(page.getByTestId("auto-site-context-detail-roads")).toContainText(/community mapped.*OpenStreetMap contributors/);
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
  await expect(detectedItems).toContainText("Detected Items · 33 To Review");
  await expect(detectedItems.getByTestId("detected-items-page-summary")).toHaveText("Showing 1-12 of 33");
  await expect(detectedItems.getByTestId("detected-item-candidate")).toHaveCount(12);
  await detectedItems.getByRole("tab", { name: "Vision 1" }).click();
  await expect(detectedItems.getByTestId("detected-item-candidate")).toHaveCount(1);
  await expect(detectedItems.getByTestId("detected-items-page-summary")).toHaveText("Showing 1-1 of 1");
  await detectedItems.getByRole("tab", { name: "All" }).click();
  await expect(detectedItems.getByTestId("detected-item-candidate")).toHaveCount(12);
  const buildingCandidate = detectedItems.locator('[data-candidate-id="building-1"]');
  await buildingCandidate.getByRole("button", { name: "Accept" }).click();
  await candidateDecisionStarted;
  await expect(buildingCandidate.getByRole("button", { name: "Saving..." })).toBeVisible();
  await expect(detectedItems.getByRole("button", { name: "Reject" }).first()).toBeDisabled();
  releaseCandidateDecision();
  await expect(detectedItems).toContainText("Detected Items · 32 To Review");
  await expect(page.getByTestId("site-status")).toContainText("Site Locked");
  await expect(buildingCandidate).toContainText(/accepted/i);
  await expect(buildingCandidate.getByRole("button", { name: "Accept" })).toBeDisabled();
  const roadCandidate = detectedItems.locator('[data-candidate-id="road-1"]');
  await roadCandidate.getByRole("button", { name: "Reject" }).click();
  await expect(detectedItems).toContainText("Detected Items · 31 To Review");
  await expect(detectedItems).toContainText("Accepted");
  await expect(detectedItems).toContainText("Rejected");
  const visionCandidate = detectedItems.locator('[data-candidate-id="image-building-1"]');
  await expect(visionCandidate.getByTestId("vision-candidate-correction")).toBeVisible();
  await visionCandidate
    .getByLabel("Correct detected type for Detected imagery building footprint")
    .selectOption("parking_area");
  await expect(visionCandidate).toContainText(/Selected outline: Custom Area/i);
  await visionCandidate.getByRole("button", { name: "Use selected outline" }).click();
  await expect(detectedItems).toContainText("Detected Items · 30 To Review");
  await expect(visionCandidate).toContainText(/accepted/i);
  await expect.poll(() => lastVisionCorrectionPayload?.correction_coordinate_space).toBe("project_local");
  await expect.poll(() => (lastVisionCorrectionPayload?.corrected_geometry as { type?: string } | undefined)?.type).toBe("Polygon");
  await expect(page.getByTestId("site-status")).toContainText("Site Locked");
  await expect(detectedItems.getByTestId("vision-learning-summary")).toContainText("1 reviewed");
  await expect(detectedItems.getByTestId("vision-learning-summary")).toContainText("0 rights-cleared");
  await expect(detectedItems.getByTestId("vision-learning-summary")).toContainText("Accuracy is not claimed");
  await expect(detectedItems.getByTestId("vision-inference-source-summary")).toContainText("external/other");
  const learningDownload = page.waitForEvent("download");
  await detectedItems.getByRole("button", { name: "Export feedback" }).click();
  const downloadedManifest = await learningDownload;
  await expect(downloadedManifest.suggestedFilename()).toBe("pw-project_civora_vision_learning.json");
  const downloadedManifestPath = await downloadedManifest.path();
  expect(downloadedManifestPath).toBeTruthy();
  const manifestText = await readFile(downloadedManifestPath!, "utf8");
  const manifest = JSON.parse(manifestText) as Record<string, unknown>;
  const exportedDataset = manifest.civora_vision_training_dataset_v1 as Record<string, unknown>;
  const exportedQuality = manifest.civora_vision_quality_report_v1 as Record<string, unknown>;
  expect(exportedDataset.contains_image_bytes).toBe(false);
  expect(exportedQuality.precision).toBeNull();
  expect(manifestText).not.toContain("access_token");

  await page.getByRole("button", { name: "Draw" }).first().click();
  await cadTools.getByTestId("cad-tool-box").filter({ visible: true }).first().click();
  await clickExposedSurface(drawingSurface, 0.52, 0.4);
  await clickExposedSurface(drawingSurface, 0.64, 0.55);
  await expect(page.getByTestId("object-manager-row").filter({ hasText: /Custom Rectangle/ }).first()).toBeVisible();
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
  expect(fetchOnlineRequest).toMatchObject({
    include_worldwide_context: true,
    geocode_context: {
      lat: 32.8,
      lng: -96.8,
      provider: "test_geocoder",
      location_context: {
        jurisdiction: { country_code: "US", region: "Texas", place: "Test City" },
      },
    },
  });
  expect(JSON.stringify(savedProjectInput)).toContain("online_existing_conditions_discovery_v1");
  expect(JSON.stringify(savedProjectInput)).toContain("site_intelligence_summary_v1");
  expect(JSON.stringify(savedProjectInput)).toContain("imagery_object_detection_report_v1");
});

test("Apply Address recovers when a background source status poll is transiently rate limited", async ({ page }) => {
  let pollCount = 0;

  await page.route("**/api/auth/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, user_count: 1, registration_allowed: true }),
    });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user: { user_id: "pw-user", email: "pw@example.com", name: "Playwright" } }),
    });
  });
  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [] }) });
      return;
    }
    const payload = route.request().postDataJSON() as { project_input?: Record<string, unknown> };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: "Transient Poll Project",
          project_input: payload.project_input ?? {},
          latest_result: null,
          has_result: false,
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
        lat: 41.2587,
        lng: -95.9378,
        display_name: "1600 DODGE ST, OMAHA, NE",
        provider: "test_geocoder",
      }),
    });
  });
  await page.route("**/api/jobs**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (route.request().method() === "POST" && pathname === "/api/jobs/source-context") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            job_id: "job-transient-source",
            job_type: "source_context",
            status: "queued",
            progress: 0,
          },
        }),
      });
      return;
    }
    if (route.request().method() === "GET" && pathname === "/api/jobs/job-transient-source") {
      pollCount += 1;
      if (pollCount === 1) {
        await route.fulfill({
          status: 429,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Temporary polling rate limit" }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            job_id: "job-transient-source",
            job_type: "source_context",
            status: "completed",
            progress: 100,
            result: {
              success: true,
              status: "ready_with_context",
              online_existing_conditions_discovery_v1: {
                version: "online_existing_conditions_discovery_v1",
                status: "candidates_found",
                candidate_count: 1,
                sources: [
                  {
                    key: "building_footprints",
                    label: "building footprints",
                    provider: "Test Buildings",
                    candidate_count: 1,
                    review_required: true,
                    blockers: ["review-required"],
                  },
                ],
                missing_sources: [],
                review_required: true,
                acceptance_status: "candidate",
              },
              map_feature_detection_report_v1: {
                version: "map_feature_detection_report_v1",
                candidate_count: 1,
                feature_candidates: [],
              },
            },
          },
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, jobs: [] }),
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
  await page.getByLabel("Type project address").fill("1600 Dodge St, Omaha, NE");
  await page.getByRole("button", { name: "Apply address" }).click();

  await expect(page.getByTestId("auto-site-context-candidates")).toContainText("1 source candidate available for review", {
    timeout: 30_000,
  });
  await expect(page.getByTestId("auto-site-context-found")).toContainText("building footprints");
  expect(pollCount).toBeGreaterThanOrEqual(2);
});
