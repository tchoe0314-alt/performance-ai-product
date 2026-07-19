import { expect, test, type Page } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";

async function installHostedMocks(page: Page, captured: { queuedRequest: Record<string, unknown> | null }) {
  await page.addInitScript(
    ([tokenKey, token]) => window.localStorage.setItem(tokenKey, token),
    [TOKEN_KEY, "drawn-context-token"] as const,
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

async function clickSurface(page: Page, xRatio: number, yRatio: number) {
  const surface = page.getByTestId("preview-drawing-surface");
  const box = await surface.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.click(box!.x + box!.width * xRatio, box!.y + box!.height * yRatio);
}

test("Generate queues drawn and placed objects as engineering context", async ({ page }) => {
  const captured: { queuedRequest: Record<string, unknown> | null } = { queuedRequest: null };
  await installHostedMocks(page, captured);

  await page.goto("/demo/workspace?debugPreview=1&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();

  await runCommand(page, "I want the address to be 20525 Margo St Gretna NE and it is gonna be 1000ft by 1000 ft with the address as the center point");
  await expect(page.getByText("SITE LOCKED").first()).toBeVisible({ timeout: 30_000 });

  await runCommand(page, "add 28000 sf office building");
  await expect(page.locator('[data-cad-object-id][aria-label*="Office Building - 28,000 sf"]').first()).toBeVisible({ timeout: 5_000 });
  await runCommand(page, "add detention basin");
  await expect(page.locator('[data-cad-object-id][aria-label*="Basin"], [data-cad-object-id][aria-label*="Detention"]').first()).toBeVisible({ timeout: 5_000 });
  await runCommand(page, "add water line");
  await expect(page.locator('[data-cad-object-id][aria-label*="Water Line"], [data-cad-object-id][aria-label*="water-line"]').first()).toBeVisible({ timeout: 5_000 });

  await page.getByRole("button", { name: /^Draw$/ }).first().click();
  const cadTools = page.getByTestId("draw-cad-tools-section");
  await cadTools.getByTestId("cad-tool-line").click();
  await clickSurface(page, 0.2, 0.35);
  await clickSurface(page, 0.42, 0.35);
  await expect(page.getByTestId("cad-command-feedback-panel")).toContainText(/LINE created|Custom Line/i);

  await page.getByRole("button", { name: /^Generate$/ }).first().click();
  await page.getByTestId("generate-main-action").click();
  await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:/i, { timeout: 8_000 });
  await expect.poll(() => captured.queuedRequest, { timeout: 8_000 }).not.toBeNull();

  const queued = captured.queuedRequest!;
  const request = queued.request as Record<string, unknown>;
  const manualFields = request.manual_fields as Record<string, unknown>;
  const siteObjects = manualFields.site_objects as Array<Record<string, unknown>>;
  const buildings = manualFields.buildings as Array<Record<string, unknown>>;
  const ponds = manualFields.ponds as Array<Record<string, unknown>>;
  const sitePlan = manualFields.site_plan as Record<string, unknown> | undefined;

  expect(Array.isArray(siteObjects)).toBeTruthy();
  expect(siteObjects.some((item) => String(item.label).includes("Office Building - 28,000 sf") && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => /Basin|Detention/i.test(String(item.label)) && item.type === "basin" && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => /water/i.test(String(item.label)) && item.type === "utility_corridor" && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => String(item.label).includes("Custom Line") && item.type === "custom" && item.placed === true)).toBeTruthy();
  expect(siteObjects.some((item) => String(item.geometry_type) === "line" || String(item.geometry_type) === "polyline")).toBeTruthy();

  expect(buildings.some((item) => String(item.label).includes("Office Building - 28,000 sf"))).toBeTruthy();
  expect(ponds.some((item) => /Basin|Detention/i.test(String(item.name)))).toBeTruthy();
  expect(sitePlan?.parking_count ?? null).not.toBe(140);

  const meta = request.meta as Record<string, unknown>;
  expect(meta.requested_system).toBe("full");
  expect(JSON.stringify(meta.auto_site_context_review_summary ?? {})).toContain("parcel/site boundary");
  expect(JSON.stringify(meta.user_layout_context_summary ?? {})).toContain("Office Building - 28,000 sf");
  expect(JSON.stringify(meta.user_layout_context_summary ?? {})).toContain("Custom Line");
  expect(JSON.stringify(meta.generate_notes ?? [])).toContain("User layout context used by Generate");
  expect(JSON.stringify(siteObjects)).toContain("passed to Generate as review context");
  expect(JSON.stringify(siteObjects)).toContain("draft_review_required");
  expect(JSON.stringify(siteObjects)).toContain('"construction_release_allowed":false');
});
