import { expect, test } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

test("fresh setup creates a centered 1000 by 1000 site from an address", async ({ page }) => {
  let geocodeCalled = false;
  let fetchOnlineCalled = false;
  let savedProjectInput = "";

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
      body: JSON.stringify({ user: { user_id: "chat239-user", email: "chat239@example.com" } }),
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
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    savedProjectInput = JSON.stringify(payload.project_input ?? {});
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "chat239-project",
          name: "Margo Centered Site",
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
        },
      }),
    });
  });

  await page.route("**/api/geocode", async (route) => {
    geocodeCalled = true;
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
    fetchOnlineCalled = true;
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    expect(JSON.stringify(payload)).toContain("20525 Margo St");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        status: "ready_with_context",
        online_existing_conditions_discovery_v1: {
          version: "online_existing_conditions_discovery_v1",
          status: "candidates_found",
          candidate_count: 3,
          sources: [
            { key: "parcel_site_boundary", label: "parcel/site boundary", candidate_count: 1, review_required: true },
            { key: "road_row", label: "road/ROW data", candidate_count: 1, review_required: true },
            { key: "terrain_dem_lidar", label: "terrain/elevation", candidate_count: 1, review_required: true },
          ],
          missing_sources: [{ key: "public_utilities", label: "public utility layers" }],
          review_required: true,
          construction_release_allowed: false,
        },
        map_feature_detection_report_v1: {
          version: "map_feature_detection_report_v1",
          candidate_count: 3,
          feature_candidates: [
            { candidate_id: "parcel-1", feature_type: "parcel_or_site_boundary", source_name: "Test Parcels", confidence: 0.88, review_required: true },
            { candidate_id: "road-1", feature_type: "road_or_drive", source_name: "Test Roads", confidence: 0.84, review_required: true },
            { candidate_id: "terrain-1", feature_type: "terrain", source_name: "Test Terrain", confidence: 0.72, review_required: true },
          ],
        },
      }),
    });
  });

  await page.addInitScript(
    ([tokenKey, restoreKey, token]) => {
      window.localStorage.setItem(tokenKey, token);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, "chat239-token"] as const,
  );

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

  await page.getByRole("button", { name: "Setup" }).first().click();
  await expect(page.getByTestId("setup-address-truth")).toBeVisible();
  await page.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");
  const siteBoxSection = page.getByTestId("setup-site-box-controls");
  if (!(await siteBoxSection.evaluate((node) => node.hasAttribute("open")))) {
    await siteBoxSection.locator("summary").click();
  }
  await page.getByLabel("Site width in feet").fill("1000");
  await page.getByLabel("Site depth in feet").fill("1000");
  await page.getByTestId("create-centered-site-button").click();

  await page.getByRole("button", { name: "Setup" }).first().click();
  await expect(page.getByTestId("setup-site-box-controls")).toContainText("1000 ft x 1000 ft");
  await expect(page.getByTestId("setup-site-box-controls")).toContainText("Locked");
  await expect(page.getByTestId("auto-site-context-found")).toContainText("parcel/site boundary", { timeout: 30_000 });
  await expect(page.getByTestId("auto-site-context-found")).toContainText("terrain/elevation");
  await expect(page.getByTestId("auto-site-context-missing")).toContainText("public utility layers");

  expect(geocodeCalled).toBeTruthy();
  expect(fetchOnlineCalled).toBeTruthy();
  expect(savedProjectInput).toContain("\"w\":1000");
  expect(savedProjectInput).toContain("\"h\":1000");
  expect(savedProjectInput).toContain("20525 Margo St");
});

test("chat can create the same centered site from natural language", async ({ page }) => {
  let geocodeCalled = false;
  let fetchOnlineCalled = false;
  let savedProjectInput = "";

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
      body: JSON.stringify({ user: { user_id: "chat239-user", email: "chat239@example.com" } }),
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
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    savedProjectInput = JSON.stringify(payload.project_input ?? {});
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "chat239-project",
          name: "Margo Centered Site",
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
        },
      }),
    });
  });

  await page.route("**/api/geocode", async (route) => {
    geocodeCalled = true;
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
    fetchOnlineCalled = true;
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    expect(JSON.stringify(payload)).toContain("20525 Margo St");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        status: "ready_with_context",
        online_existing_conditions_discovery_v1: {
          version: "online_existing_conditions_discovery_v1",
          status: "candidates_found",
          candidate_count: 3,
          sources: [
            { key: "parcel_site_boundary", label: "parcel/site boundary", candidate_count: 1, review_required: true },
            { key: "road_row", label: "road/ROW data", candidate_count: 1, review_required: true },
            { key: "terrain_dem_lidar", label: "terrain/elevation", candidate_count: 1, review_required: true },
          ],
          missing_sources: [{ key: "public_utilities", label: "public utility layers" }],
          review_required: true,
          construction_release_allowed: false,
        },
        map_feature_detection_report_v1: {
          version: "map_feature_detection_report_v1",
          candidate_count: 3,
          feature_candidates: [
            { candidate_id: "parcel-1", feature_type: "parcel_or_site_boundary", source_name: "Test Parcels", confidence: 0.88, review_required: true },
            { candidate_id: "road-1", feature_type: "road_or_drive", source_name: "Test Roads", confidence: 0.84, review_required: true },
            { candidate_id: "terrain-1", feature_type: "terrain", source_name: "Test Terrain", confidence: 0.72, review_required: true },
          ],
        },
      }),
    });
  });

  await page.addInitScript(
    ([tokenKey, restoreKey, token]) => {
      window.localStorage.setItem(tokenKey, token);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, "chat239-token"] as const,
  );

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("button", { name: "Projects" }).first().click();
  await page.getByRole("button", { name: "New Project" }).first().click();
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

  await page.getByRole("button", { name: "Chat" }).first().click();
  const composer = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
  await composer.fill(
    "I want the address to be 20525 Margo St Gretna NE and it is gonna be 1000ft by 1000 ft with the address as the center point",
  );
  await composer.press("Enter");

  await expect(page.getByText("SITE LOCKED").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("workspace-canvas-shell")).toContainText("1000 FT x 1000 FT");

  await page.getByRole("button", { name: "Chat" }).first().click();
  const chatPanel = page.getByTestId("workspace-right-panel");
  await expect(chatPanel).toContainText("1000 ft by 1000 ft", { timeout: 30_000 });
  await expect(chatPanel).toContainText("20525 Margo St");
  await expect(chatPanel).not.toContainText(/Before I move forward|site type or land use/i);

  await page.getByRole("button", { name: "Setup" }).first().click();
  await expect(page.getByTestId("setup-site-box-controls")).toContainText("1000 ft x 1000 ft");
  await expect(page.getByTestId("setup-site-box-controls")).toContainText("Locked");
  await expect(page.getByTestId("auto-site-context-found")).toContainText("parcel/site boundary", { timeout: 30_000 });
  await expect(page.getByTestId("auto-site-context-found")).toContainText("terrain/elevation");

  expect(geocodeCalled).toBeTruthy();
  expect(fetchOnlineCalled).toBeTruthy();
  expect(savedProjectInput).toContain("\"w\":1000");
  expect(savedProjectInput).toContain("\"h\":1000");
  expect(savedProjectInput).toContain("20525 Margo St");
});
