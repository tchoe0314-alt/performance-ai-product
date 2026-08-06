import { expect, test, type Page, type Route } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";

type SavedProject = {
  project_id: string;
  name: string;
  description?: string;
  updated_at: number;
  project_input: Record<string, unknown>;
  latest_result?: Record<string, unknown> | null;
  has_result?: boolean;
};

function projectSummary(project: SavedProject) {
  return {
    project_id: project.project_id,
    name: project.name,
    description: project.description ?? "",
    updated_at: project.updated_at,
    has_result: Boolean(project.latest_result && Object.keys(project.latest_result).length),
  };
}

function readProjectInputName(projectInput: Record<string, unknown> | undefined) {
  const manualFields =
    projectInput?.manual_fields && typeof projectInput.manual_fields === "object"
      ? (projectInput.manual_fields as Record<string, unknown>)
      : {};
  return typeof manualFields.project_name === "string" ? manualFields.project_name : "";
}

async function mockShell(page: Page, store: Map<string, SavedProject>) {
  let nextProjectNumber = 1;

  await page.route("**/api/auth/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, registration_allowed: true }),
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

  await page.route("**/api/customer-templates", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        registry: {
          version: "customer_template_registry_v1",
          templates: [],
          review_required: true,
          construction_release_allowed: false,
        },
      }),
    });
  });

  await page.route("**/api/utility-catalogs", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        catalog: {
          version: "utility_catalog_v1",
          records: [],
          review_required: true,
          construction_release_allowed: false,
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
        display_name: "123 MAIN ST, TEST CITY, TX",
        provider: "test_geocoder",
        confidence: 0.95,
        crs: { epsg: "EPSG:4326", units: "degrees" },
        location_context: {
          address: "123 MAIN ST, TEST CITY, TX",
          coordinates: { lat: 32.8, lng: -96.8 },
          truth_label: "Address/geocode is location context only.",
        },
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
            { key: "parcel_site_boundary", label: "parcel/site boundary", provider: "Test Parcels", candidate_count: 1, review_required: true },
            { key: "public_utilities", label: "public utility layers", provider: "", candidate_count: 0, review_required: true },
          ],
          missing_sources: [{ key: "public_utilities", label: "public utility layers" }],
          review_required: true,
          acceptance_status: "candidate",
          construction_release_allowed: false,
        },
        map_feature_detection_report_v1: {
          version: "map_feature_detection_report_v1",
          candidate_count: 1,
          feature_candidates: [
            { candidate_id: "parcel-1", feature_type: "parcel_or_site_boundary", source_type: "official_gis", source_name: "Test Parcels", evidence_source: "Test Parcels", confidence: 0.88, review_required: true, acceptance_status: "pending" },
          ],
        },
        existing_conditions_package: { status: "review_required", production_ready: false },
        existing_conditions_summary: { production_ready: false },
      }),
    });
  });

  await page.route("**/api/projects**", async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/projects" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          projects: Array.from(store.values()).map(projectSummary),
        }),
      });
      return;
    }

    if (path === "/api/projects" && method === "POST") {
      const payload = request.postDataJSON() as {
        project_id?: string | null;
        name?: string;
        project_input?: Record<string, unknown>;
        latest_result?: Record<string, unknown> | null;
      };
      const projectId = payload.project_id || `pw-project-${nextProjectNumber++}`;
      const existing = store.get(projectId);
      const project: SavedProject = {
        project_id: projectId,
        name: payload.name || readProjectInputName(payload.project_input) || existing?.name || "Untitled Project",
        description: existing?.description ?? "",
        updated_at: Math.floor(Date.now() / 1000),
        project_input: payload.project_input ?? existing?.project_input ?? {},
        latest_result: payload.latest_result !== undefined ? payload.latest_result : existing?.latest_result ?? null,
        has_result: Boolean(payload.latest_result ?? existing?.latest_result),
      };
      store.set(projectId, project);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, project }),
      });
      return;
    }

    const detailMatch = path.match(/^\/api\/projects\/([^/]+)$/);
    if (detailMatch && method === "GET") {
      const project = store.get(detailMatch[1]);
      await route.fulfill({
        status: project ? 200 : 404,
        contentType: "application/json",
        body: JSON.stringify(project ? { success: true, project } : { detail: "Project not found." }),
      });
      return;
    }

    const resultMatch = path.match(/^\/api\/projects\/([^/]+)\/result$/);
    if (resultMatch && method === "GET") {
      const project = store.get(resultMatch[1]);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, project_id: resultMatch[1], latest_result: project?.latest_result ?? {} }),
      });
      return;
    }

    const duplicateMatch = path.match(/^\/api\/projects\/([^/]+)\/duplicate$/);
    if (duplicateMatch && method === "POST") {
      const source = store.get(duplicateMatch[1]);
      if (!source) {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Project not found." }),
        });
        return;
      }
      const project: SavedProject = {
        ...structuredClone(source),
        project_id: `pw-project-${nextProjectNumber++}`,
        name: `${source.name} Copy`,
        updated_at: Math.floor(Date.now() / 1000),
      };
      store.set(project.project_id, project);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, project }),
      });
      return;
    }

    if (detailMatch && method === "DELETE") {
      const deleted = store.delete(detailMatch[1]);
      await route.fulfill({
        status: deleted ? 200 : 404,
        contentType: "application/json",
        body: JSON.stringify(deleted ? { success: true, project_id: detailMatch[1] } : { detail: "Project not found." }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true }),
    });
  });

  await page.addInitScript(
    ([tokenKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
      window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
    },
    [TOKEN_KEY, "pw-token"] as const,
  );
}

async function openApp(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
}

async function openProjects(page: Page) {
  await page.getByTestId("header-projects-button").click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible();
}

async function openSetup(page: Page) {
  await page.getByRole("button", { name: "Open workspace controls" }).click();
  await page.getByRole("button", { name: /^Setup$/ }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(/Setup|Address \/ Location|Site Boundary/);
}

test.describe("project drawer reliability", () => {
  test("keeps a large saved-project list searchable and initially compact", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    for (let index = 1; index <= 20; index += 1) {
      store.set(`project-${index}`, {
        project_id: `project-${index}`,
        name: index === 19 ? "Omaha Retail Review" : `Project ${index}`,
        description: index === 19 ? "North 10th Street" : `Saved project ${index}`,
        updated_at: 1_700_000_000 + index,
        project_input: { input_mode: "user", manual_fields: {}, meta: { site_inputs: {} } },
        latest_result: null,
      });
    }
    await mockShell(page, store);
    await openApp(page);
    await openProjects(page);

    const drawer = page.getByTestId("projects-drawer");
    await expect(drawer.getByRole("button", { name: /^Open project / })).toHaveCount(12);
    await drawer.getByRole("button", { name: "Show 8 more" }).click();
    await expect(drawer.getByRole("button", { name: /^Open project / })).toHaveCount(20);

    await drawer.getByPlaceholder("Search projects").fill("north 10th");
    await expect(drawer.getByRole("button", { name: "Open project Omaha Retail Review" })).toBeVisible();
    await expect(drawer.getByRole("button", { name: /^Open project / })).toHaveCount(1);
    await drawer.getByPlaceholder("Search projects").fill("not a saved project");
    await expect(drawer).toContainText("No projects match that search.");
    await drawer.getByRole("button", { name: "Clear search" }).click();
    await expect(drawer.getByRole("button", { name: /^Open project / })).toHaveCount(12);
  });

  test("clears a stale saved-project reference and exposes one new-project action", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    await mockShell(page, store);
    await page.addInitScript(() => {
      window.localStorage.setItem("civora.activeProjectId", "deleted-project");
    });

    await openApp(page);
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("civora.activeProjectId")))
      .toBeNull();

    await openProjects(page);
    await expect(page.getByTestId("project-drawer-state")).toContainText("Unsaved draft");
    await expect(page.getByTestId("project-drawer-detail")).toContainText(
      "Started a clean unsaved workspace",
    );
    await expect(page.getByRole("button", { name: "New Project" })).toHaveCount(1);
    await expect(page.getByText(/Could not restore saved workspace/i)).toHaveCount(0);
  });

  test("restores a saved locked site with its dimensions and placed objects", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    store.set("locked-site-project", {
      project_id: "locked-site-project",
      name: "Locked Denver Site",
      updated_at: Math.floor(Date.now() / 1000),
      project_input: {
        meta: {
          site_inputs: {
            address: "201 W Colfax Ave, Denver, CO",
            site_alignment_locked: true,
          },
        },
        manual_fields: {
          lot: { x: 0, y: 0, w: 920, h: 730 },
          site_objects: [
            {
              id: "denver-office",
              label: "Denver Office",
              type: "office",
              x: 100,
              y: 120,
              width_ft: 250,
              depth_ft: 160,
              placed: true,
              source: "manual_drawn",
            },
          ],
        },
      },
      latest_result: null,
    });
    await mockShell(page, store);
    await openApp(page);
    await page.getByRole("button", { name: /^Generate$/ }).first().click();
    await page.getByTestId("generate-main-action").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/site boundary/i);
    await openProjects(page);
    await page.getByRole("button", { name: "Open project Locked Denver Site" }).click();

    await expect(page.getByTestId("site-status")).toContainText("Site Locked");
    const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
    if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
    await page
      .getByTestId("primary-workflow-sidebar")
      .getByRole("button", { name: /^Draw\b/i })
      .filter({ visible: true })
      .first()
      .click();
    await page.getByLabel("Select Denver Office").filter({ visible: true }).first().click();
    await expect(page.getByTestId("preview-object-manager-list")).toContainText("Denver Office");
    await openSetup(page);
    await expect(page.getByLabel("Width (ft)")).toHaveValue("920");
    await expect(page.getByLabel("Depth (ft)")).toHaveValue("730");
    await expect(page.getByTestId("setup-site-box-controls")).toContainText(/920 ft x 730 ft/i);
    await expect(page.getByTestId("setup-site-box-controls")).toContainText(/locked/i);
    await page.getByRole("button", { name: /^Generate$/ }).first().click();
    await expect(page.getByTestId("generate-flow-summary")).toHaveCount(0);
  });

  test("keeps the backend-assigned name when a project copy opens", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    store.set("source-project", {
      project_id: "source-project",
      name: "Original Site",
      updated_at: Math.floor(Date.now() / 1000),
      project_input: {
        meta: { site_inputs: { site_alignment_locked: true } },
        manual_fields: {
          project_name: "Original Site",
          lot: { x: 0, y: 0, w: 800, h: 600 },
        },
      },
      latest_result: null,
    });
    await mockShell(page, store);
    await openApp(page);
    await openProjects(page);

    await page.getByRole("button", { name: "Duplicate project Original Site" }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText("Ready: Project duplicated");
    await page.waitForTimeout(1_200);

    await expect(page.getByTestId("projects-drawer")).toContainText("Original Site Copy");
    await expect(page.getByTestId("projects-drawer").getByText("Original Site", { exact: true })).toHaveCount(1);
    expect(Array.from(store.values()).find((item) => item.project_id !== "source-project")?.name).toBe("Original Site Copy");
  });

  test("keeps a new workspace clean when an older save finishes late", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    await mockShell(page, store);
    const saveGateControl: { release?: () => void } = {};
    const saveGate = new Promise<void>((resolve) => {
      saveGateControl.release = resolve;
    });
    let markSaveStarted: (() => void) | null = null;
    const saveStarted = new Promise<void>((resolve) => {
      markSaveStarted = resolve;
    });
    await page.route("**/api/projects", async (route) => {
      if (route.request().method() !== "POST") {
        await route.fallback();
        return;
      }
      markSaveStarted?.();
      await saveGate;
      const payload = route.request().postDataJSON() as {
        name?: string;
        project_input?: Record<string, unknown>;
      };
      const project: SavedProject = {
        project_id: "late-save-project",
        name: payload.name || "Untitled Project",
        updated_at: Math.floor(Date.now() / 1000),
        project_input: payload.project_input ?? {},
        latest_result: null,
      };
      store.set(project.project_id, project);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, project }),
      });
    });

    await openApp(page);
    await openProjects(page);
    await page.getByRole("button", { name: "Save Project" }).click();
    await saveStarted;
    await page.getByRole("button", { name: "New Project" }).click();
    saveGateControl.release?.();
    await page.waitForTimeout(250);

    await expect(page.getByTestId("project-status-summary")).toContainText(
      "Ready: Clean workspace ready",
    );
    await openProjects(page);
    await expect(page.getByTestId("project-drawer-state")).toContainText("Unsaved draft");
    await expect(page.getByTestId("project-drawer-detail")).toContainText(
      "Save Project will persist this clean workspace",
    );
    await expect
      .poll(() => page.evaluate(() => window.localStorage.getItem("civora.activeProjectId")))
      .toBeNull();
  });

  test("keeps rapid drawn objects selected and persisted when autosaves finish out of order", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    store.set("rapid-draw-project", {
      project_id: "rapid-draw-project",
      name: "Rapid Draw Project",
      updated_at: Math.floor(Date.now() / 1000),
      project_input: {
        input_mode: "user",
        meta: { site_inputs: { site_alignment_locked: true } },
        manual_fields: { lot: { x: 0, y: 0, w: 1000, h: 1000 } },
      },
      latest_result: null,
    });
    await mockShell(page, store);

    let saveSequence = 0;
    await page.route("**/api/projects", async (route) => {
      if (route.request().method() !== "POST") {
        await route.fallback();
        return;
      }
      saveSequence += 1;
      const payload = route.request().postDataJSON() as {
        project_id?: string | null;
        name?: string;
        project_input?: Record<string, unknown>;
      };
      await new Promise((resolve) => setTimeout(resolve, saveSequence === 1 ? 700 : 40));
      const project: SavedProject = {
        project_id: payload.project_id || "rapid-draw-project",
        name: payload.name || "Rapid Draw Project",
        updated_at: Math.floor(Date.now() / 1000),
        project_input: payload.project_input ?? {},
        latest_result: null,
      };
      store.set(project.project_id, project);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, project }),
      });
    });

    await openApp(page);
    await openProjects(page);
    await page.getByRole("button", { name: "Open project Rapid Draw Project" }).click();
    await expect(page.getByTestId("site-status")).toContainText("Site Locked");

    const drawBox = async (first: [number, number], second: [number, number]) => {
      const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
      if (await workspaceButton.isVisible().catch(() => false)) await workspaceButton.click();
      await page
        .getByTestId("primary-workflow-sidebar")
        .getByRole("button", { name: /^Draw\b/i })
        .filter({ visible: true })
        .first()
        .click();
      await page.getByTestId("cad-tool-box").filter({ visible: true }).first().click();
      const panel = page.getByTestId("workspace-right-panel");
      await panel.getByRole("button", { name: "Minimize" }).click();
      const surface = page.getByTestId("preview-drawing-surface");
      const box = await surface.boundingBox();
      expect(box).not.toBeNull();
      await page.mouse.click(box!.x + box!.width * first[0], box!.y + box!.height * first[1]);
      await page.mouse.click(box!.x + box!.width * second[0], box!.y + box!.height * second[1]);
    };

    await drawBox([0.54, 0.34], [0.67, 0.46]);
    const objectManager = page.getByTestId("preview-object-manager");
    const firstSelected = objectManager.getByRole("textbox", { name: "Rename selected object" });
    await expect(firstSelected).toHaveValue(/Custom Rectangle/);
    await firstSelected.fill("Office Building A");
    await firstSelected.press("Enter");
    await objectManager.getByTestId("preview-object-manager-type").selectOption("building");

    await drawBox([0.72, 0.34], [0.85, 0.46]);
    const secondSelected = objectManager.getByRole("textbox", { name: "Rename selected object" });
    await expect(secondSelected).toHaveValue(/Custom Rectangle/);
    await secondSelected.fill("Parking Field A");
    await secondSelected.press("Enter");
    await objectManager.getByTestId("preview-object-manager-type").selectOption("parking");

    await page.waitForTimeout(1_800);
    const objectList = page.getByTestId("preview-object-manager-list");
    await expect(objectList).toContainText("Office Building A");
    await expect(objectList).toContainText("Parking Field A");
    await expect
      .poll(() => JSON.stringify(store.get("rapid-draw-project")?.project_input ?? {}))
      .toContain("Office Building A");
    expect(JSON.stringify(store.get("rapid-draw-project")?.project_input ?? {})).toContain("Parking Field A");
  });

  test("ignores a saved result that finishes loading after New Project", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    store.set("older-project", {
      project_id: "older-project",
      name: "Older Project",
      updated_at: Math.floor(Date.now() / 1000),
      project_input: {
        meta: {
          site_inputs: {
            address: "20525 Margo St, Gretna, NE",
            geocode: { lat: 41.142, lng: -96.244 },
            map_feature_detection_report_v1: { candidate_count: 14 },
          },
        },
        manual_fields: { lot: { x: 0, y: 0, w: 1000, h: 1000 } },
      },
      latest_result: {
        success: true,
        final_plan: { meta: { location_context: { address: "20525 Margo St, Gretna, NE" } } },
      },
      has_result: true,
    });
    await mockShell(page, store);
    const resultGateControl: { release?: () => void } = {};
    const resultGate = new Promise<void>((resolve) => {
      resultGateControl.release = resolve;
    });
    let markResultStarted: (() => void) | null = null;
    const resultStarted = new Promise<void>((resolve) => {
      markResultStarted = resolve;
    });
    await page.route("**/api/projects/older-project/result", async (route) => {
      markResultStarted?.();
      await resultGate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          project_id: "older-project",
          latest_result: store.get("older-project")?.latest_result ?? {},
        }),
      });
    });
    await openApp(page);
    await openProjects(page);
    await page.getByRole("button", { name: "Open project Older Project" }).click();
    await resultStarted;
    await page.getByRole("button", { name: "New Project" }).click();
    resultGateControl.release?.();
    await page.waitForTimeout(300);

    await expect(page.getByTestId("project-status-summary")).toContainText(
      "Ready: Clean workspace ready",
    );
    await openSetup(page);
    await expect(page.getByLabel("Type project address")).toHaveValue("");
    await expect(page.getByTestId("auto-site-context-summary")).toContainText("Found 0");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(
      "Local site coordinates",
    );
  });

  test("keeps a new workspace clean when an opened map schedules a delayed scale save", async ({ page }) => {
    test.skip(
      !process.env.NEXT_PUBLIC_MAPBOX_TOKEN,
      "Mapbox token is required to exercise the live map scale-save callback.",
    );
    const store = new Map<string, SavedProject>();
    store.set("mapped-project", {
      project_id: "mapped-project",
      name: "Mapped Project",
      updated_at: Math.floor(Date.now() / 1000),
      project_input: {
        meta: {
          site_inputs: {
            address: "20525 Margo St, Gretna, NE",
            geocode: { lat: 41.142, lng: -96.244 },
            site_alignment_locked: true,
          },
        },
        manual_fields: { lot: { x: 0, y: 0, w: 1000, h: 1000 } },
      },
      latest_result: null,
    });
    await mockShell(page, store);
    await openApp(page);
    await openProjects(page);
    await page.getByRole("button", { name: "Open project Mapped Project" }).click();
    await expect
      .poll(
        () =>
          page.evaluate(() =>
            Boolean((window as unknown as Record<string, unknown>).__civoraMapOverlayEnabled),
          ),
        { timeout: 30_000 },
      )
      .toBe(true);
    await expect(page.locator(".mapboxgl-canvas")).toBeVisible({ timeout: 30_000 });

    await openProjects(page);
    await page.getByRole("button", { name: "New Project" }).click();
    await page.evaluate(() => {
      window.localStorage.setItem("civora.activeProjectId", "mapped-project");
    });
    await page.waitForTimeout(1_500);

    await expect(page.getByTestId("project-status-summary")).toContainText(
      "Ready: Clean workspace ready",
    );
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(
      "Local site coordinates",
    );
    await openProjects(page);
    await expect(page.getByTestId("project-drawer-state")).toContainText("Unsaved draft");
    await expect(page.getByTestId("project-drawer-state")).not.toContainText("Restored saved workspace");
    expect(store.size).toBe(1);
  });

  test("map-backed drawing converts physical mouse positions to accurate site feet", async ({ page }) => {
    test.skip(
      !process.env.NEXT_PUBLIC_MAPBOX_TOKEN,
      "Mapbox token is required to verify physical map pointer coordinates.",
    );
    const store = new Map<string, SavedProject>();
    store.set("mapped-draw-project", {
      project_id: "mapped-draw-project",
      name: "Mapped Draw Project",
      updated_at: Math.floor(Date.now() / 1000),
      project_input: {
        meta: {
          site_inputs: {
            address: "20525 Margo St, Gretna, NE",
            geocode: { lat: 41.142, lng: -96.244 },
            site_alignment_locked: true,
          },
        },
        manual_fields: { lot: { x: 0, y: 0, w: 1000, h: 1000 } },
      },
      latest_result: null,
    });
    await mockShell(page, store);
    await openApp(page);
    await openProjects(page);
    await page.getByRole("button", { name: "Open project Mapped Draw Project" }).click();
    await expect(page.locator(".mapboxgl-canvas")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("canvas-scale-source")).toContainText("LIVE MAP SCALE", { timeout: 30_000 });
    await expect
      .poll(() => page.evaluate(() => (window as unknown as { __civoraShowMap?: boolean }).__civoraShowMap))
      .toBe(true);
    const mapOverlayTransforms = await page.evaluate(() => ({
      plan: getComputedStyle(document.querySelector('[data-testid="preview-plan-canvas-svg"]')!).transform,
      hits: getComputedStyle(document.querySelector('[data-testid="preview-drawing-overlays"]')!).transform,
    }));
    expect(mapOverlayTransforms.plan).toMatch(/^(none|matrix\(1, 0, 0, 1, 0, 0\))$/);
    expect(mapOverlayTransforms.hits).toMatch(/^(none|matrix\(1, 0, 0, 1, 0, 0\))$/);

    const drawButton = page
      .getByTestId("primary-workflow-sidebar")
      .getByRole("button", { name: /^Draw\b/i })
      .filter({ visible: true })
      .first();
    if (!(await drawButton.isVisible().catch(() => false))) {
      await page.getByRole("button", { name: "Open workspace controls" }).click();
    }
    await page
      .getByTestId("primary-workflow-sidebar")
      .getByRole("button", { name: /^Draw\b/i })
      .filter({ visible: true })
      .first()
      .click();

    const addBox = page.getByTestId("cad-tool-box").filter({ visible: true }).first();
    await expect(addBox).toBeEnabled();
    await addBox.click();

    const mapCanvas = page.locator(".mapboxgl-canvas").filter({ visible: true }).first();
    const mapCanvasBox = await mapCanvas.boundingBox();
    expect(mapCanvasBox).not.toBeNull();
    const viewport = page.viewportSize();
    expect(viewport).not.toBeNull();
    const visibleMapBounds = {
      left: Math.max(mapCanvasBox!.x, 0),
      top: Math.max(mapCanvasBox!.y, 0),
      right: Math.min(mapCanvasBox!.x + mapCanvasBox!.width, viewport!.width),
      bottom: Math.min(mapCanvasBox!.y + mapCanvasBox!.height, viewport!.height),
    };
    const visibleMapWidth = visibleMapBounds.right - visibleMapBounds.left;
    const visibleMapHeight = visibleMapBounds.bottom - visibleMapBounds.top;
    expect(visibleMapWidth).toBeGreaterThan(180);
    expect(visibleMapHeight).toBeGreaterThan(180);
    const first = {
      x: visibleMapBounds.left + visibleMapWidth * 0.35,
      y: visibleMapBounds.top + visibleMapHeight * 0.3,
    };
    const second = {
      x: visibleMapBounds.left + visibleMapWidth * 0.62,
      y: visibleMapBounds.top + visibleMapHeight * 0.68,
    };
    const readCursor = async (point: { x: number; y: number }) => {
      await page.mouse.move(point.x, point.y);
      await page.evaluate(
        () =>
          new Promise<void>((resolve) => {
            window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve()));
          }),
      );
      await expect(page.getByTestId("canvas-coordinate-readout")).toContainText(/X\s+-?[\d.]+\s+ft\s+\/\s+Y\s+-?[\d.]+\s+ft/i);
      const text = (await page.getByTestId("canvas-coordinate-readout").textContent()) ?? "";
      const match = text.match(/X\s+(-?[\d.]+)\s+ft\s+\/\s+Y\s+(-?[\d.]+)\s+ft/i);
      expect(match).not.toBeNull();
      return { x: Number(match![1]), y: Number(match![2]) };
    };
    const firstSitePoint = await readCursor(first);
    await page.mouse.click(first.x, first.y);
    const secondSitePoint = await readCursor(second);
    await page.mouse.click(second.x, second.y);
    await expect(page.getByText("Custom Rectangle 1").filter({ visible: true }).first()).toBeVisible();

    const scaleText = (await page.getByTestId("canvas-scale-source").textContent()) ?? "";
    const feetPerPixel = Number(scaleText.match(/([\d.]+)\s+FT\/PX/i)?.[1]);
    expect(feetPerPixel).toBeGreaterThan(0);
    const mapViewport = await page.evaluate(() =>
      (window as unknown as {
        __civoraMapViewport?: { lat?: number; zoom?: number };
      }).__civoraMapViewport,
    );
    expect(mapViewport?.lat).toEqual(expect.any(Number));
    expect(mapViewport?.zoom).toEqual(expect.any(Number));
    const handoff = page
      .locator('[data-canonical-geometry-handoff="canonical_geometry_handoff_v1"]')
      .filter({ visible: true })
      .first();
    await expect(handoff).toHaveAttribute("data-handoff-valid", "true");
    const dimensionsText =
      (await handoff.locator("p").filter({ hasText: /ft\s*x\s*.*ft/i }).first().textContent()) ?? "";
    const dimensions = dimensionsText.match(/([\d.]+)\s*ft\s*x\s*([\d.]+)\s*ft/i);
    expect(dimensions).not.toBeNull();
    const actualWidth = Number(dimensions![1]);
    const actualDepth = Number(dimensions![2]);
    const expectedWidth = Math.abs(second.x - first.x) * feetPerPixel;
    const pointerWidth = Math.abs(secondSitePoint.x - firstSitePoint.x);
    const pointerDepth = Math.abs(secondSitePoint.y - firstSitePoint.y);
    console.info("[map-geometry-proof]", {
      mapCanvasBox,
      feetPerPixel,
      first,
      second,
      firstSitePoint,
      secondSitePoint,
      actualWidth,
      actualDepth,
      expectedWidth,
    });
    expect(Math.abs(actualWidth - pointerWidth)).toBeLessThanOrEqual(6);
    expect(Math.abs(actualDepth - pointerDepth)).toBeLessThanOrEqual(6);
    expect(Math.abs(actualWidth - expectedWidth)).toBeLessThanOrEqual(Math.max(8, expectedWidth * 0.03));
  });

  test("ignores address discovery that finishes after New Project", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    await mockShell(page, store);
    const geocodeGateControl: { release?: () => void } = {};
    const geocodeGate = new Promise<void>((resolve) => {
      geocodeGateControl.release = resolve;
    });
    let markGeocodeStarted: (() => void) | null = null;
    const geocodeStarted = new Promise<void>((resolve) => {
      markGeocodeStarted = resolve;
    });
    await page.route("**/api/geocode", async (route) => {
      markGeocodeStarted?.();
      await geocodeGate;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          status: "ready",
          lat: 41.142,
          lng: -96.244,
          display_name: "20525 Margo St, Gretna, NE",
          provider: "test_geocoder",
          confidence: 0.95,
        }),
      });
    });

    await openApp(page);
    await openSetup(page);
    await page.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");
    await page.getByRole("button", { name: "Apply address" }).click();
    await geocodeStarted;
    await openProjects(page);
    await page.getByRole("button", { name: "New Project" }).click();
    geocodeGateControl.release?.();
    await page.waitForTimeout(300);

    await expect(page.getByTestId("project-status-summary")).toContainText(
      "Ready: Clean workspace ready",
    );
    await openSetup(page);
    await expect(page.getByLabel("Type project address")).toHaveValue("");
    await expect(page.getByTestId("auto-site-context-summary")).toContainText("Found 0");
    await expect(page.getByTestId("workspace-canvas-shell")).toContainText(
      "Local site coordinates",
    );
  });

  test("restores requested chat program as actionable placement tray objects", async ({ page }) => {
    const store = new Map<string, SavedProject>();
    store.set("requested-program-project", {
      project_id: "requested-program-project",
      name: "Requested Program Project",
      updated_at: Math.floor(Date.now() / 1000),
      project_input: {
        full_design_mode: true,
        input_mode: "user",
        prompt_text: "Saved project with requested program.",
        meta: {
          requested_site_program_v1: {
            schema_version: "requested_site_program_v1",
            source: "chat_natural_language",
            summary: "28,000 sf office building, 140 parking spaces; systems: water, sanitary, storm",
            review_required: true,
            engineer_review_required: true,
            construction_release_allowed: false,
            requested_objects: [
              { type: "office_building", label: "office building", area_sf: 28000, status: "requested_not_placed" },
              { type: "parking", label: "parking", stall_count: 140, status: "requested_not_placed" },
              { type: "detention_basin", label: "detention basin", status: "requested_not_placed" },
              { type: "driveway", label: "driveway connection", status: "requested_not_placed" },
              { type: "sidewalk", label: "sidewalks", status: "requested_not_placed" },
              { type: "ada_route", label: "ADA routes", status: "requested_not_placed" },
            ],
            requested_systems: ["water", "sanitary", "storm", "drainage", "roadway"],
          },
          site_inputs: {
            address: "20525 Margo St, Gretna, NE",
            site_alignment_locked: true,
          },
        },
        manual_fields: {
          project_name: "Requested Program Project",
          units: "ft",
          lot: { x: 0, y: 0, w: 1000, h: 1000 },
          site_plan: { parking_count: 140, building_program_sf: 28000, building_type: "office" },
        },
      },
      latest_result: {
        success: true,
        final_plan: {
          meta: {
            location_context: { address: "20525 Margo St, Gretna, NE" },
            requested_site_program_v1: {
              schema_version: "requested_site_program_v1",
              summary: "28,000 sf office building, 140 parking spaces; systems: water, sanitary, storm",
              construction_release_allowed: false,
            },
          },
        },
      },
      has_result: true,
    });
    await mockShell(page, store);
    await page.addInitScript(() => {
      window.localStorage.setItem("civora.activeProjectId", "requested-program-project");
    });

    await openApp(page);
    await openProjects(page);
    await expect(page.getByTestId("project-drawer-state")).toContainText(/Saved|Restored/i);
    await page.getByRole("button", { name: "Open project Requested Program Project" }).click();

    await page.getByRole("button", { name: "Open workspace controls" }).click();
    await page.getByRole("button", { name: /^Draw$/ }).first().click();
    await expect(page.getByTestId("needs-placement-tray")).toContainText("Office Building - 28,000 sf");
    await expect(page.getByTestId("needs-placement-tray")).toContainText("Parking Field - 140 stalls");
    await expect(page.getByTestId("needs-placement-tray")).toContainText("Detention Basin");
    await expect(page.getByTestId("needs-placement-tray")).toContainText("Public Water Line");
    await expect(page.getByTestId("needs-placement-tray")).toContainText("Public Sanitary Line");
    await expect(page.getByTestId("needs-placement-tray")).toContainText("Storm Sewer");

    await page.getByRole("button", { name: "Place Office Building - 28,000 sf" }).click();
    await page.getByTestId("workspace-canvas-shell").click({ position: { x: 360, y: 260 } });
    await expect(page.getByTestId("object-manager-panel")).toContainText("Office Building - 28,000 sf");
    await expect(page.getByTestId("object-manager-panel")).toContainText("7 pending");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Parking Field - 140 stalls");
    await expect(page.getByTestId("object-manager-panel")).toContainText("Unplaced");
    await page.getByTestId("header-chat-button").click();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("what should I do next?");
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").press("Enter");
    await expect(page.getByTestId("workspace-right-panel").getByText("Open Objects and place Parking Field - 140 stalls", { exact: false }).last()).toBeVisible();

    await page.getByRole("button", { name: /^Generate$/ }).first().click();
    const visibleGeneratePanel = page.getByTestId("workspace-right-panel");
    await expect(visibleGeneratePanel.getByTestId("generate-placement-context")).toContainText(
      "7 requested objects still need placement",
    );
    await expect(visibleGeneratePanel.getByTestId("generate-placement-context")).toContainText(
      "Parking Field - 140 stalls",
    );
  });

  test("opens, clears drafts, saves, restores, deletes, reloads, and reports backend blockers", async ({ page }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") consoleErrors.push(message.text());
    });

    const store = new Map<string, SavedProject>();
    await mockShell(page, store);
    await openApp(page);

    await openProjects(page);
    await expect(page.getByTestId("project-drawer-state")).toContainText("Unsaved draft");

    await openSetup(page);
    const addressDetails = page.getByTestId("setup-address-truth");
    await expect(addressDetails).toBeVisible();
    if (!(await addressDetails.evaluate((element) => element.hasAttribute("open")))) {
      await addressDetails.locator("summary").click();
    }
    await addressDetails.getByLabel("Type project address").fill("123 Main St, Test City, TX");
    await page.getByRole("button", { name: "Apply address" }).click();
    await expect(page.getByTestId("auto-site-context-summary")).toContainText(/parcel\/site boundary|candidates/i, { timeout: 30_000 });
    await page.getByTestId("header-chat-button").click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toBeVisible();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("Generate a parking layout note.");
    await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
    await page.getByTestId("civora-command-input").fill("add 140 parking spaces");
    await page.getByTestId("civora-command-input").press("Enter");
    await page.getByRole("button", { name: /^Draw$/ }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Parking Field - 140 stalls");
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Parking Field - 140 stalls was added as draft geometry.");
    await page.getByTestId("header-chat-button").click();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("Generate a parking layout note.");

    await openProjects(page);
    await page.getByRole("button", { name: "Save Project" }).click();
    await expect(page.getByTestId("project-drawer-state")).toContainText("Saved");
    expect(store.size).toBe(1);
    const firstProjectId = Array.from(store.keys())[0];
    expect(JSON.stringify(store.get(firstProjectId)?.project_input)).toContain("123 MAIN ST");
    expect(JSON.stringify(store.get(firstProjectId)?.project_input)).toContain("Generate a parking layout note.");

    await page.getByRole("button", { name: /^Draw$/ }).filter({ visible: true }).first().click();
    await page.getByTestId("cad-tool-line").filter({ visible: true }).first().click();
    await expect(page.getByTestId("cad-precision-tools")).toBeVisible();
    await openProjects(page);
    await page.getByRole("button", { name: "New Project" }).first().click();
    await expect(page.getByTestId("workspace-canvas-shell")).not.toContainText("Precision & commands");
    await openProjects(page);
    await expect(page.getByTestId("project-drawer-state")).toContainText("Unsaved draft");
    await openSetup(page);
    await expect(page.getByLabel("Type project address")).toHaveValue("");
    await expect(page.getByText("parcel/site boundary")).not.toBeVisible();
    await page.getByRole("button", { name: /^Draw$/ }).first().click();
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText("Parking Field - 140 stalls");
    await expect(page.getByRole("button", { name: "Undo", exact: true })).toBeDisabled();
    await page.getByTestId("header-chat-button").click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toHaveValue("");

    await openProjects(page);
    await page.getByRole("button", { name: "Open project Untitled Project" }).first().click();
    await expect(page.getByTestId("project-drawer-state")).toContainText("Saved");
    await openSetup(page);
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/123 Main St, Test City, TX/i);
    await page.getByTestId("header-chat-button").click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toHaveValue("Generate a parking layout note.");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await openSetup(page);
    await expect(page.getByTestId("workspace-right-panel")).toContainText("123 MAIN ST, TEST CITY, TX");

    page.once("dialog", async (dialog) => {
      expect(dialog.message()).toContain("Delete");
      await dialog.accept();
    });
    await openProjects(page);
    const deleteRequest = page.waitForRequest((request) => request.method() === "DELETE");
    await expect(page.getByRole("button", { name: "Delete project Untitled Project" }).first()).toBeVisible();
    await page.getByRole("button", { name: "Delete project Untitled Project" }).first().click({ force: true });
    const deletedProjectId = decodeURIComponent(new URL((await deleteRequest).url()).pathname.split("/").pop() ?? "");
    await openProjects(page);
    await expect(page.getByTestId("project-drawer-detail")).toContainText("Project deleted.");
    expect(store.has(deletedProjectId)).toBe(false);

    await page.route("**/api/projects", async (route) => {
      if (route.request().method() === "POST") {
        await route.abort("connectionrefused");
        return;
      }
      await route.fallback();
    });
    await page.getByRole("button", { name: "Save Project" }).click();
    await expect(page.getByTestId("project-drawer-detail")).toContainText(
      /Save needs attention: Backend connection needs attention/i,
    );

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(pageErrors).toEqual([]);
    expect(
      consoleErrors.filter(
        (message) =>
          !message.includes("ERR_CONNECTION_REFUSED") &&
          !message.includes("401 (Unauthorized)"),
      ),
    ).toEqual([]);
  });
});
