import { expect, type Page } from "@playwright/test";

// Synthetic project at an explicit geographic anchor. Uses the real Mapbox
// canvas, but mocks project/auth APIs and never writes customer data.
export async function openMapAnchoredFixture(page: Page) {
  let project = {
    project_id: "map-interaction-fixture", name: "Map Interaction Fixture",
    updated_at: 1, latest_result: null,
    project_input: {
      manual_fields: { units: "ft", lot: { x: 0, y: 0, w: 1000, h: 1000 },
        buildings: [{ id: "map-office", name: "Map Office", type: "office_building",
          x: 350, y: 300, w: 100, d: 80, placed: true, source: "user" }] },
      meta: { site_inputs: { address: "Synthetic map interaction fixture",
        geocode: { lat: 41.142, lng: -96.244 }, site_alignment_locked: true } },
    },
  };
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = { success: true };
    if (path === "/api/auth/status") body = { success: true, user_count: 1, registration_allowed: true };
    else if (path === "/api/auth/me") body = { user: { user_id: "map-test", email: "map@example.test", name: "Map fixture" } };
    else if (path === "/api/projects" && route.request().method() === "GET") body = { success: true, projects: [project] };
    else if (path === "/api/projects" && route.request().method() === "POST") {
      project = { ...project, ...route.request().postDataJSON() };
      body = { success: true, project };
    } else if (path === `/api/projects/${project.project_id}`) body = { success: true, project };
    else if (path.endsWith("/result")) body = { success: true, latest_result: {} };
    else if (path.startsWith("/api/jobs")) body = { success: true, jobs: [] };
    else if (path === "/api/customer-templates") body = { success: true, registry: { templates: [] } };
    else if (path === "/api/utility-catalogs") body = { success: true, catalog: { records: [] } };
    else {
      await route.fulfill({ status: 404, json: { detail: `Unsupported map fixture endpoint: ${path}` } });
      return;
    }
    await route.fulfill({ status: 200, json: body });
  });
  await page.addInitScript(() => {
    localStorage.setItem("civora-ai-token", "map-fixture-token");
    sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  });
  await page.goto("/?debugPreview=1&mapDebug=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await page.getByTestId("header-projects-button").click();
  await page.getByRole("button", { name: "Open project Map Interaction Fixture" }).click();
  await expect(page.locator("canvas.mapboxgl-canvas").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("canvas-scale-source")).toContainText("LIVE MAP SCALE");
  // Canvas mounting and an initial scale callback precede the project's
  // camera fit. Wait for the actual anchor, not an arbitrary sleep.
  await expect.poll(() => page.evaluate(() => {
    const viewport = (window as unknown as { __civoraMapViewport?: { lat: number; lng: number; zoom: number } }).__civoraMapViewport;
    return Boolean(viewport && Math.abs(viewport.lat - 41.142) < 1e-7
      && Math.abs(viewport.lng + 96.244) < 1e-7 && viewport.zoom > 16);
  }), { timeout: 30_000 }).toBe(true);
}
