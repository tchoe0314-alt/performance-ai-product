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
    ([tokenKey, authToken]) => window.localStorage.setItem(tokenKey, authToken),
    [TOKEN_KEY, "pw-token"] as const,
  );
}

async function openApp(page: Page) {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
}

async function openProjects(page: Page) {
  await page.getByRole("button", { name: "Open projects from header" }).click();
  await expect(page.getByTestId("projects-drawer")).toBeVisible();
}

async function openSetup(page: Page) {
  await page.getByRole("button", { name: "Open workspace controls" }).click();
  await page.getByRole("button", { name: /^Setup$/ }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Project Setup");
}

test.describe("project drawer reliability", () => {
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
    await page.getByTestId("setup-address-truth").locator("summary").click();
    await page.getByLabel("Type project address").fill("123 Main St, Test City, TX");
    await page.getByRole("button", { name: "Apply address" }).click();
    await expect(page.getByTestId("auto-site-context-summary")).toContainText(/parcel\/site boundary|candidates/i, { timeout: 30_000 });
    await page.getByRole("button", { name: "Open chat from header" }).click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toBeVisible();
    await page.getByPlaceholder("Message Civora AI with what you want to create or change...").fill("Generate a parking layout note.");

    await openProjects(page);
    await page.getByRole("button", { name: "Save Project" }).click();
    await expect(page.getByTestId("project-drawer-state")).toContainText("Saved");
    expect(store.size).toBe(1);
    const firstProjectId = Array.from(store.keys())[0];
    expect(JSON.stringify(store.get(firstProjectId)?.project_input)).toContain("123 MAIN ST");
    expect(JSON.stringify(store.get(firstProjectId)?.project_input)).toContain("Generate a parking layout note.");

    await page.getByRole("button", { name: "New Project" }).first().click();
    await openProjects(page);
    await expect(page.getByTestId("project-drawer-state")).toContainText("Unsaved draft");
    await openSetup(page);
    await expect(page.getByLabel("Type project address")).toHaveValue("");
    await expect(page.getByText("parcel/site boundary")).not.toBeVisible();
    await page.getByRole("button", { name: "Open chat from header" }).click();
    await expect(page.getByPlaceholder("Message Civora AI with what you want to create or change...")).toHaveValue("");

    await openProjects(page);
    await page.getByRole("button", { name: "Open project Untitled Project" }).first().click();
    await expect(page.getByTestId("project-drawer-state")).toContainText("Saved");
    await openSetup(page);
    await expect(page.getByTestId("workspace-right-panel")).toContainText("123 MAIN ST, TEST CITY, TX");
    await page.getByRole("button", { name: "Open chat from header" }).click();
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
    const deleteRequest = page.waitForRequest((request) =>
      request.method() === "DELETE" && request.url().includes(`/api/projects/${firstProjectId}`),
    );
    await expect(page.getByRole("button", { name: "Delete project Untitled Project" }).first()).toBeVisible();
    await page.getByRole("button", { name: "Delete project Untitled Project" }).first().click({ force: true });
    await deleteRequest;
    await openProjects(page);
    await expect(page.getByTestId("project-drawer-detail")).toContainText("Project deleted.");
    expect(store.has(firstProjectId)).toBe(false);

    await page.route("**/api/projects", async (route) => {
      if (route.request().method() === "POST") {
        await route.abort("connectionrefused");
        return;
      }
      await route.fallback();
    });
    await page.getByRole("button", { name: "Save Project" }).click();
    await expect(page.getByTestId("project-drawer-detail")).toContainText(
      /Save blocked: Backend unreachable or CORS\/API blocked/i,
    );

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(pageErrors).toEqual([]);
    expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
  });
});
