import { expect, test, type Page } from "@playwright/test";

import { setPreviewQuality } from "./testUiHelpers";

const EXTERNAL_IMAGE =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1536 1024"><rect width="1536" height="1024" fill="#86a66d"/><path d="M0 760h1536v180H0z" fill="#4b5563"/><rect x="370" y="260" width="460" height="280" fill="#d2c09f"/><ellipse cx="1120" cy="550" rx="180" ry="120" fill="#55b8d9"/></svg>',
  );

async function expectTechnicalPlanRestored(page: Page) {
  const mapCanvas = page.locator(".mapboxgl-canvas").filter({ visible: true });
  if ((await mapCanvas.count()) > 0) {
    await expect(mapCanvas.first()).toBeVisible();
    await expect(page.locator("[data-object-overlay]").first()).toBeVisible();
    return;
  }
  await expect(page.getByTestId("plan-polyline-object").first()).toBeVisible();
}

async function installAuthenticatedApiMocks(
  page: Page,
  options: { unavailable?: boolean; transientPollFailures?: number } = {},
) {
  let jobPolls = 0;
  let queueCalls = 0;
  let authorizationHeader = "";
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/api/auth/status") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, auth_enabled: true, user_count: 1 }),
      });
      return;
    }
    if (path === "/api/auth/me") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          user: { user_id: "visual-user", name: "Visual Reviewer", email: "visual@example.com" },
        }),
      });
      return;
    }
    if (path === "/api/projects") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, projects: [], deleted_projects: [] }),
      });
      return;
    }
    if (path === "/api/jobs" && request.method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, jobs: [], pagination: { total: 0, limit: 100, offset: 0 } }),
      });
      return;
    }
    if (path === "/api/jobs/ai-visualization") {
      queueCalls += 1;
      authorizationHeader = request.headers().authorization || "";
      if (options.unavailable) {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "External photorealistic visualization is not configured for this deployment." }),
        });
        return;
      }
      const body = request.postDataJSON();
      expect(body.source_objects.length).toBeGreaterThan(0);
      expect(body.site_frame.width_ft).toBeGreaterThan(0);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, job: { job_id: "visual-job-1", status: "queued" } }),
      });
      return;
    }
    if (path === "/api/jobs/visual-job-1") {
      jobPolls += 1;
      if (jobPolls <= (options.transientPollFailures || 0)) {
        await route.abort("failed");
        return;
      }
      if (jobPolls === (options.transientPollFailures || 0) + 1) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            success: true,
            job: {
              job_id: "visual-job-1",
              status: "running",
              stage: "Generating Photorealistic Visualization",
              stage_detail: "The external image provider is rendering a visual concept.",
              progress: 58,
            },
          }),
        });
        return;
      }
      const sourceLayoutHash = await page.evaluate(
        () => (window as typeof window & { __civoraAiRealismLayoutHash?: string }).__civoraAiRealismLayoutHash,
      );
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            job_id: "visual-job-1",
            status: "completed",
            stage: "Completed",
            stage_detail: "Visualization ready.",
            progress: 100,
            result: {
              artifact: {
                type: "high_quality_ai_render_v2",
                project_id: "demo-pinecrest-mixed-use",
                source_layout_hash: sourceLayoutHash,
                site_frame: { width_ft: 760, height_ft: 520, map_context_available: true },
                source_objects_summary: {
                  total: 4,
                  objects_included: ["Multifamily Building A (multifamily_building)"],
                  counts_by_type: { multifamily_building: 1, parking: 1, driveway: 1, basin: 1 },
                },
                missing_inputs: [],
                stale: false,
                generated_timestamp: "2026-08-04T12:00:00Z",
                review_only: true,
                not_site_evidence: true,
                construction_release_allowed: false,
                visualization_only: true,
                not_engineering_evidence: true,
                renderer: "external",
                provider: "openai",
                model: "gpt-image-2",
                mime_type: "image/webp",
                map_context_used: false,
                image_data_url: EXTERNAL_IMAGE,
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
      body: JSON.stringify({ success: true }),
    });
  });
  await page.addInitScript(() => {
    window.localStorage.setItem("civora-ai-token", "visual-token");
    window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  });
  return {
    queueCalls: () => queueCalls,
    jobPolls: () => jobPolls,
    authorizationHeader: () => authorizationHeader,
  };
}

async function openSeededWorkspace(page: Page) {
  await page.goto("/?debugPreview=1&seedDemo=1&aiRealismProvider=external", {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await setPreviewQuality(page, "high");
  await expect(page.getByTestId("ai-realism-on")).toBeVisible();
}

test.describe("external photorealistic visualization", () => {
  test("queues, reports progress, and displays an external visual-only artifact", async ({ page }) => {
    const api = await installAuthenticatedApiMocks(page);
    await openSeededWorkspace(page);

    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-generation-status")).toContainText(
      "Generating Photorealistic Visualization",
    );
    await expect(page.getByTestId("ai-realism-image")).toBeVisible({ timeout: 20_000 });
    await page.getByTestId("ai-realism-details-toggle").click();
    await expect(page.getByTestId("ai-realism-renderer")).toContainText(
      "External photorealistic concept · gpt-image-2",
    );
    await expect(page.getByTestId("ai-realism-watermark")).toContainText("visual concept only");

    expect(api.queueCalls()).toBe(1);
    expect(api.authorizationHeader()).toBe("Bearer visual-token");
    const artifact = await page.evaluate(
      () => (window as typeof window & { __civoraAiRealismArtifact?: unknown }).__civoraAiRealismArtifact,
    );
    expect(artifact).toMatchObject({
      type: "high_quality_ai_render_v2",
      renderer: "external",
      provider: "openai",
      model: "gpt-image-2",
      visualization_only: true,
      not_engineering_evidence: true,
      construction_release_allowed: false,
    });
  });

  test("shows an actionable provider-unavailable state without replacing the plan", async ({ page }) => {
    await installAuthenticatedApiMocks(page, { unavailable: true });
    await openSeededWorkspace(page);

    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-blocker")).toContainText(
      "External photorealistic visualization is not configured",
    );
    await page.getByTestId("ai-realism-off").click();
    await expectTechnicalPlanRestored(page);
  });

  test("keeps polling through brief hosted status interruptions", async ({ page }) => {
    const api = await installAuthenticatedApiMocks(page, { transientPollFailures: 2 });
    await openSeededWorkspace(page);

    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-generation-status")).toContainText(
      "Reconnecting to visualization job",
    );
    await expect(page.getByTestId("ai-realism-image")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("ai-realism-blocker")).toHaveCount(0);
    expect(api.jobPolls()).toBeGreaterThanOrEqual(4);
  });

  test("turning Visual off cancels browser polling and immediately restores the plan", async ({ page }) => {
    const api = await installAuthenticatedApiMocks(page);
    await openSeededWorkspace(page);

    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-generation-status")).toContainText(
      "Generating Photorealistic Visualization",
    );
    await page.getByTestId("ai-realism-off").click();
    await expectTechnicalPlanRestored(page);
    await page.waitForTimeout(1_200);

    await expect(page.getByTestId("ai-realism-image")).toHaveCount(0);
    expect(api.queueCalls()).toBe(1);
    expect(api.jobPolls()).toBe(1);
  });
});
