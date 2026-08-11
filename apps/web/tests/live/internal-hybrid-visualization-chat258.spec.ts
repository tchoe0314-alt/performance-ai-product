import { expect, test, type Page } from "@playwright/test";

import { setPreviewQuality } from "./testUiHelpers";

const PRIVATE_RENDER =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1344 896"><rect width="1344" height="896" fill="#8cab78"/><path d="M0 650h1344v150H0z" fill="#4b5563"/><path d="M300 210h420v260H300z" fill="#d8c5a4"/><ellipse cx="1000" cy="520" rx="160" ry="105" fill="#5eb8d4"/></svg>',
  );

async function installPrivateRendererMocks(page: Page) {
  let submittedLayoutHash = "";
  let submittedObjectCount = 0;
  await page.addInitScript(() => {
    window.localStorage.setItem("civora-ai-token", "private-renderer-user-token");
    window.sessionStorage.setItem("civora-ai-session-auth-restore", "1");
  });
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
          user: { user_id: "private-visual-user", name: "Private Visual User", email: "visual@example.com" },
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
      const body = request.postDataJSON() as { source_layout_hash: string; source_objects: unknown[] };
      submittedLayoutHash = body.source_layout_hash;
      submittedObjectCount = body.source_objects.length;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: { job_id: "private-visual-job", status: "queued" },
          provider: { name: "civora", self_hosted: true, external: false },
        }),
      });
      return;
    }
    if (path === "/api/jobs/private-visual-job") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          job: {
            job_id: "private-visual-job",
            status: "completed",
            stage: "Completed",
            stage_detail: "Private visualization ready.",
            progress: 100,
            result: {
              artifact: {
                type: "high_quality_ai_render_v3",
                project_id: "demo-pinecrest-mixed-use",
                source_layout_hash: submittedLayoutHash,
                site_frame: { width_ft: 760, height_ft: 520, map_context_available: true },
                source_objects_summary: {
                  total: submittedObjectCount,
                  objects_included: ["Multifamily Building A (multifamily_building)", "Detention Basin A (basin)"],
                  counts_by_type: { multifamily_building: 1, parking: 1, driveway: 1, basin: 1 },
                },
                missing_inputs: ["terrain/source confidence"],
                stale: false,
                generated_timestamp: "2026-08-04T12:00:00Z",
                review_only: true,
                not_site_evidence: true,
                construction_release_allowed: false,
                visualization_only: true,
                not_engineering_evidence: true,
                renderer: "civora_hybrid",
                provider: "civora",
                model: "stabilityai/stable-diffusion-xl-base-1.0",
                mime_type: "image/webp",
                map_context_used: false,
                self_hosted: true,
                reference_manifest: {
                  contract: "civora_visual_reference_v2",
                  object_count: submittedObjectCount,
                  control_kinds: ["edge", "height_depth"],
                },
                renderer_provenance: {
                  engine: "diffusers_sdxl_controlnet",
                  model_license: "openrail++",
                  no_image_retention: true,
                },
                image_data_url: PRIVATE_RENDER,
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
  return {
    submittedObjectCount: () => submittedObjectCount,
  };
}

test("private hybrid visualization is distinct, source-traced, and visual-only", async ({ page }) => {
  const api = await installPrivateRendererMocks(page);
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto("/?debugPreview=1&seedDemo=1&aiRealismProvider=external", {
    waitUntil: "domcontentloaded",
  });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
  await setPreviewQuality(page, "high");
  await page.getByTestId("ai-realism-on").click();

  await expect(page.getByTestId("ai-realism-image")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("ai-realism-preview-badge")).toContainText("Civora private visual");
  await page.getByTestId("ai-realism-details-toggle").click();
  await expect(page.getByTestId("ai-realism-renderer")).toContainText("Civora private hybrid renderer");
  await expect(page.getByTestId("ai-realism-control-provenance")).toContainText(
    "edge + height_depth · private worker · no map imagery",
  );
  await expect(page.getByTestId("ai-realism-watermark")).toContainText("visual concept only");
  await expect(page.getByTestId("ai-realism-source-summary")).toContainText("high_quality_ai_render_v3");
  expect(api.submittedObjectCount()).toBeGreaterThan(0);

  const artifact = await page.evaluate(
    () => (window as typeof window & { __civoraAiRealismArtifact?: unknown }).__civoraAiRealismArtifact,
  );
  expect(artifact).toMatchObject({
    type: "high_quality_ai_render_v3",
    renderer: "civora_hybrid",
    provider: "civora",
    self_hosted: true,
    map_context_used: false,
    visualization_only: true,
    not_engineering_evidence: true,
    construction_release_allowed: false,
  });
  expect(consoleErrors).toEqual([]);
});
