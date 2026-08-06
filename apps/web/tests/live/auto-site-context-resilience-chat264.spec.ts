import { expect, test } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

test("source context reports progress, cancels safely, and force-refreshes on retry", async ({ page }) => {
  let projectInput: Record<string, unknown> = {};
  let sourceJobCount = 0;
  let cancelCount = 0;
  const forceRefreshValues: boolean[] = [];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path === "/api/auth/status") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, user_count: 1 }) });
      return;
    }
    if (path === "/api/auth/me") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ user: { user_id: "chat264-user", email: "chat264@example.com" } }) });
      return;
    }
    if (path === "/api/projects" && method === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [] }) });
      return;
    }
    if (path.startsWith("/api/projects") && method !== "GET") {
      const payload = (request.postDataJSON() ?? {}) as { project_input?: Record<string, unknown> };
      projectInput = payload.project_input ?? projectInput;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          project: {
            project_id: "chat264-project",
            name: "Source Context Test",
            project_input: projectInput,
            latest_result: null,
            has_result: false,
          },
        }),
      });
      return;
    }
    if (path === "/api/geocode") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          status: "ready",
          lat: 41.18524,
          lng: -96.23702,
          display_name: "20525 MARGO ST, GRETNA, NE 68028",
          provider: "test_geocoder",
          confidence: 0.96,
          location_context: { jurisdiction: { country_code: "US", state: "NE", city: "Gretna" } },
        }),
      });
      return;
    }
    if (path === "/api/jobs/source-context" && method === "POST") {
      sourceJobCount += 1;
      const payload = request.postDataJSON() as { request?: { force_refresh?: boolean } };
      forceRefreshValues.push(Boolean(payload.request?.force_refresh));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: { job_id: `source-job-${sourceJobCount}`, job_type: "source_context", status: "queued", progress: 12 },
        }),
      });
      return;
    }
    if ((path === "/api/jobs/source-job-1" || path === "/api/jobs/source-job-3") && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            job_id: path.endsWith("source-job-3") ? "source-job-3" : "source-job-1",
            job_type: "source_context",
            status: "running",
            stage: "Finding Site Sources",
            stage_detail: "Checked building footprints. 4 of 10 source checks complete.",
            progress: 41,
          },
        }),
      });
      return;
    }
    if ((path === "/api/jobs/source-job-1/cancel" || path === "/api/jobs/source-job-3/cancel") && method === "POST") {
      cancelCount += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, job: { job_id: "source-job-1", status: "cancelled" } }) });
      return;
    }
    if (path === "/api/jobs/source-job-2" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            job_id: "source-job-2",
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
                  { key: "building_footprints", label: "building footprints", provider: "Test Buildings", candidate_count: 1, review_required: true },
                ],
                missing_sources: [],
                review_required: true,
                acceptance_status: "candidate",
              },
              map_feature_detection_report_v1: {
                version: "map_feature_detection_report_v1",
                candidate_count: 1,
                feature_candidates: [
                  { candidate_id: "building-1", feature_type: "building_footprint", source_type: "official_gis", source_name: "Test Buildings", confidence: 0.9, review_required: true, acceptance_status: "pending" },
                ],
              },
              candidate_review_inbox_v1: {
                version: "candidate_review_inbox_v1",
                candidate_count: 1,
                counts: { accepted: 0, rejected: 0, pending: 1 },
                candidates: [],
                review_required: true,
              },
              source_context_fetch_metrics_v1: { version: "source_context_fetch_metrics_v1", mode: "concurrent_provider_fanout", elapsed_seconds: 2.1 },
              source_context_cache_v1: { version: "source_context_cache_v1", status: "bypassed", force_refresh: true },
            },
          },
        }),
      });
      return;
    }
    if (path === "/api/jobs" && method === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [] }) });
      return;
    }

    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
  });

  await page.addInitScript(
    ([tokenKey, restoreKey]) => {
      window.localStorage.setItem(tokenKey, "chat264-token");
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY] as const,
  );

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Setup" }).first().click();
  const addressSection = page.getByTestId("setup-address-truth");
  if (!(await addressSection.evaluate((node) => node.hasAttribute("open")))) {
    await addressSection.locator("summary").click();
  }
  await page.getByLabel("Type project address").fill("20525 Margo St, Gretna, NE");
  await page.getByRole("button", { name: "Apply address" }).click();

  const progress = page.getByTestId("auto-site-context-progress");
  await expect(progress).toBeVisible({ timeout: 10_000 });
  await expect(progress).toContainText("Finding Site Sources", { timeout: 10_000 });
  await expect(progress).toContainText("41%");
  await page.getByTestId("cancel-site-context").click();
  await expect(page.getByTestId("auto-site-context-summary")).toContainText("Source lookup cancelled");
  await expect.poll(() => cancelCount).toBe(1);

  await page.getByTestId("rerun-site-context").click();
  await expect(page.getByTestId("auto-site-context-candidates")).toContainText("1 source candidate", { timeout: 10_000 });
  await page.getByTestId("rerun-site-context").click();
  await expect(page.getByTestId("auto-site-context-progress")).toContainText("41%", { timeout: 10_000 });
  await page.getByTestId("cancel-site-context").click();
  await expect(page.getByTestId("auto-site-context-candidates")).toContainText("Source lookup cancelled");
  await expect(page.getByTestId("auto-site-context-found")).toContainText("building footprints");
  await expect(page.getByTestId("review-found-context")).toBeEnabled();
  await expect.poll(() => cancelCount).toBe(2);

  expect(forceRefreshValues).toEqual([false, true, true]);
  expect(sourceJobCount).toBe(3);
});
