import { expect, test, type Page } from "@playwright/test";

import { openCadPrecisionTools } from "./testUiHelpers";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

async function installHostedMocks(page: Page, captured: { queuedRequest: Record<string, unknown> | null }) {
  await page.addInitScript(
    ([tokenKey, restoreKey, token]) => {
      window.localStorage.setItem(tokenKey, token);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, "drawn-context-token"] as const,
  );

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
      body: JSON.stringify({ user: { user_id: "drawn-context-user", email: "drawn-context@example.com" } }),
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
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "drawn-context-project",
          name: "Drawn Context Project",
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
        },
      }),
    });
  });

  await page.route("**/api/projects-deleted", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, projects: [] }),
    });
  });

  await page.route("**/api/jobs**", async (route) => {
    const url = route.request().url();
    if (url.includes("/api/jobs/orchestrate") && route.request().method() === "POST") {
      captured.queuedRequest = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          job: {
            job_id: "job-drawn-context",
            job_type: "orchestrate",
            status: "queued",
            created_at: Date.now() / 1000,
            updated_at: Date.now() / 1000,
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

  await page.route("**/api/geocode", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        status: "ready",
        lat: 41.1514,
        lng: -96.243,
        display_name: "20525 Margo St, Gretna, NE 68028",
        provider: "test_geocoder",
        confidence: 0.95,
        crs: { epsg: "EPSG:4326", units: "degrees" },
      }),
    });
  });

  await page.route("**/api/existing-conditions/fetch-online", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        status: "ready_with_context",
        online_existing_conditions_discovery_v1: {
          version: "online_existing_conditions_discovery_v1",
          status: "candidates_found",
          candidate_count: 2,
          sources: [
            { key: "parcel_site_boundary", label: "parcel/site boundary", candidate_count: 1, review_required: true },
            { key: "terrain_dem_lidar", label: "terrain/elevation", candidate_count: 1, review_required: true },
          ],
          missing_sources: [{ key: "public_utilities", label: "public utility layers" }],
          review_required: true,
          construction_release_allowed: false,
        },
        map_feature_detection_report_v1: {
          version: "map_feature_detection_report_v1",
          candidate_count: 2,
          feature_candidates: [],
        },
      }),
    });
  });
}

async function focusCommand(page: Page) {
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  await expect(page.getByTestId("civora-command-input")).toBeFocused({ timeout: 5_000 });
}

async function runCommand(page: Page, command: string) {
  await focusCommand(page);
  await page.getByTestId("civora-command-input").fill(command);
  await page.getByTestId("civora-command-input").press("Enter");
}

async function askChat(page: Page, question: string, expected: RegExp) {
  const chatButton = page.getByTestId("header-chat-button").first();
  if (await chatButton.isVisible().catch(() => false)) {
    await chatButton.click();
  } else {
    await page.getByRole("button", { name: "Chat" }).first().click();
  }
  const input = page.getByTestId("civora-command-input");
  await input.fill(question);
  await input.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 5_000 });
}

async function openFreshMargoProject(page: Page, options: { requireFullProgramObjects?: boolean } = {}) {
  const requireFullProgramObjects = options.requireFullProgramObjects ?? true;
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();

  await runCommand(page, "create dense civil site plan with office building parking detention basin driveway sidewalks water sanitary and storm sewer");
  await expect(page.getByText("SITE LOCKED").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first()).toBeVisible({ timeout: 5_000 });
  if (requireFullProgramObjects) {
    await expect(page.locator('[data-cad-object-id][aria-label*="Basin"], [data-cad-object-id][aria-label*="Detention"]').first()).toBeVisible({ timeout: 5_000 });
    await expect(page.locator('[data-cad-object-id][aria-label*="Public Water Line"], [data-cad-object-id][aria-label*="water-line"]').first()).toBeVisible({ timeout: 5_000 });
  }
}

async function runGenerateAndCapture(page: Page, captured: { queuedRequest: Record<string, unknown> | null }) {
  captured.queuedRequest = null;
  await page.getByRole("button", { name: /^Generate$/ }).first().click();
  await page.getByTestId("generate-main-action").click();
  await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:/i, { timeout: 8_000 });
  await expect.poll(() => captured.queuedRequest, { timeout: 8_000 }).not.toBeNull();
  const queued = captured.queuedRequest!;
  return queued.request as Record<string, unknown>;
}

test("Generate queues drawn and placed objects as engineering context", async ({ page }) => {
  const captured: { queuedRequest: Record<string, unknown> | null } = { queuedRequest: null };
  await installHostedMocks(page, captured);

  await openFreshMargoProject(page, { requireFullProgramObjects: false });

  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  const precisionTools = await openCadPrecisionTools(page);
  await precisionTools.getByLabel("Draft command input").fill("LINE 20,20 220,20");
  await precisionTools.getByLabel("Draft command input").press("Enter");
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE created|Custom Line/i);

  const request = await runGenerateAndCapture(page, captured);
  await expect(page.getByTestId("generate-used-drawing-context")).toContainText(/Office Building - 28,000 sf/i);
  await expect(page.getByTestId("generate-used-drawing-context")).toContainText(/Custom Line|Command Line/i);
  await expect(page.getByTestId("generate-used-drawing-context")).toContainText(/[1-9]\d* semantic objects?/i);
  await expect(page.getByTestId("generate-used-drawing-context")).toContainText(/review context only/i);
  const manualFields = request.manual_fields as Record<string, unknown>;
  const siteObjects = manualFields.site_objects as Array<Record<string, unknown>>;
  const buildings = manualFields.buildings as Array<Record<string, unknown>>;
  const ponds = manualFields.ponds as Array<Record<string, unknown>>;
  const sitePlan = manualFields.site_plan as Record<string, unknown> | undefined;
  const utilityNetwork = manualFields.utility_network as Array<Record<string, unknown>>;
  const pipeNetwork = manualFields.pipe_network as Array<Record<string, unknown>>;
  const drainageStructures = manualFields.drainage_structures as Array<Record<string, unknown>>;
  const disciplines = manualFields.disciplines as string[];

  expect(Array.isArray(siteObjects)).toBeTruthy();
  expect(siteObjects.some((item) => String(item.label).includes("Office Building - 28,000 sf") && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => /Basin|Detention/i.test(String(item.label)) && item.type === "basin" && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => /water/i.test(String(item.label)) && item.type === "utility_corridor" && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => /Custom Line|Command Line/i.test(String(item.label)) && item.type === "custom" && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => String(item.geometry_type) === "line" || String(item.geometry_type) === "polyline")).toBeTruthy();

  expect(buildings.some((item) => String(item.label).includes("Office Building - 28,000 sf"))).toBeTruthy();
  expect(ponds.some((item) => /Basin|Detention/i.test(String(item.name)))).toBeTruthy();
  expect(sitePlan?.parking_count ?? null).toBe(140);
  expect(utilityNetwork.some((item) => item.utility_type === "water" && Array.isArray(item.points))).toBeTruthy();
  expect(utilityNetwork.some((item) => item.utility_type === "sanitary" && Array.isArray(item.points))).toBeTruthy();
  expect(pipeNetwork.some((item) => item.utility_type === "storm" && Array.isArray(item.points))).toBeTruthy();
  expect(drainageStructures.some((item) => item.structure_type === "inlet")).toBeTruthy();
  expect(disciplines).toEqual(expect.arrayContaining(["sanitary", "storm", "water"]));
  expect(JSON.stringify(utilityNetwork)).toContain('"construction_release_allowed":false');

  const meta = request.meta as Record<string, unknown>;
  expect(meta.requested_system).toBe("full");
  expect(JSON.stringify(meta.auto_site_context_review_summary ?? {})).toContain("waiting");
  expect(JSON.stringify(meta.user_layout_context_summary ?? {})).toContain("Office Building - 28,000 sf");
  expect(JSON.stringify(meta.user_layout_context_summary ?? {})).toMatch(/Custom Line|Command Line/i);
  expect(JSON.stringify(meta.generate_notes ?? [])).toContain("User layout context used by Generate");
  expect(JSON.stringify(siteObjects)).toContain("passed to Generate as review context");
  expect(JSON.stringify(siteObjects)).toContain("draft_review_required");
  expect(JSON.stringify(siteObjects)).toContain('"construction_release_allowed":false');

  await askChat(page, "what did you use from my drawing?", /Generate used these placed\/drawn objects as review context/i);
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Office Building - 28,000 sf/i);
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Custom Line|Command Line/i);
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/editable draft\/review context/i);
});

test("Generate immediately sees newly combined semantic objects", async ({ page }) => {
  const captured: { queuedRequest: Record<string, unknown> | null } = { queuedRequest: null };
  await installHostedMocks(page, captured);

  await openFreshMargoProject(page, { requireFullProgramObjects: false });
  await page.getByRole("button", { name: /^Draw$/ }).first().click();

  const officeRow = page
    .getByLabel("Rename Office Building - 28,000 sf", { exact: true })
    .locator("xpath=ancestor::*[@data-testid='object-manager-row'][1]");
  const parkingRow = page
    .getByLabel("Rename Parking Field - 84 stalls", { exact: true })
    .locator("xpath=ancestor::*[@data-testid='object-manager-row'][1]");
  await officeRow.getByTestId("object-manager-bulk-select").check();
  await parkingRow.getByTestId("object-manager-bulk-select").check();
  await page.getByTestId("object-manager-combine-name").fill("Combined Site Program");
  await page.getByTestId("object-manager-combine-type").selectOption("office_building");
  await page.getByTestId("object-manager-combine-action").click();
  await expect(page.getByTestId("object-manager-status")).toContainText("Combined", { timeout: 5_000 });

  const request = await runGenerateAndCapture(page, captured);
  await expect(page.getByTestId("generate-used-drawing-context")).toContainText(/Combined Site Program/i);
  await expect(page.getByTestId("generate-used-drawing-context")).toContainText(/semantic object/i);
  await expect(page.getByTestId("generate-roadway")).not.toContainText(/Add at least one building/i);
  await expect(page.getByTestId("generate-sanitary")).not.toContainText(/Add buildings or service/i);
  const manualFields = request.manual_fields as Record<string, unknown>;
  const siteObjects = manualFields.site_objects as Array<Record<string, unknown>>;
  const buildings = manualFields.buildings as Array<Record<string, unknown>>;
  const handoffs = manualFields.canonical_geometry_handoff_v1 as Array<Record<string, unknown>>;
  const combined = siteObjects.find((item) => String(item.label) === "Combined Site Program");
  const combinedHandoff = handoffs.find((item) => String(item.object_name) === "Combined Site Program");

  expect(combined).toBeTruthy();
  expect(combined?.type).toBe("office_building");
  expect(combined?.placed).toBe(true);
  expect(JSON.stringify(combined?.meta ?? {})).toContain("semantic_object_model");
  expect(JSON.stringify(combined?.meta ?? {})).toContain("combined_from_object_ids");
  expect(combined?.canonical_geometry_handoff_v1).toBeTruthy();
  expect(combinedHandoff?.object_type).toBe("office_building");
  expect(combinedHandoff?.canonical_object_type).toBe("office_building");
  expect(combinedHandoff?.creation_method).toBe("semantic_conversion");
  expect(combinedHandoff?.valid).toBe(true);
  expect(buildings.some((item) => String(item.label) === "Combined Site Program")).toBeTruthy();
  expect(JSON.stringify(request.meta ?? {})).toContain("Combined Site Program");

  await askChat(page, "what did you use from my drawing?", /Combined Site Program/i);
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/semantic object/i);
});
