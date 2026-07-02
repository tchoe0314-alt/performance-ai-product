import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page, query = "debugPreview=1") {
  await page.goto(`/demo/workspace?${query}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
}

async function enableHighQuality(page: Page) {
  const canvas = page.getByTestId("workspace-canvas-shell");
  await canvas.getByTestId("preview-quality-high").click();
  await expect(canvas).toContainText("High Quality");
  await expect(page.getByTestId("ai-realism-toggle")).toBeVisible();
}

async function getAiArtifact(page: Page) {
  return page.evaluate(() => (window as typeof window & { __civoraAiRealismArtifact?: unknown }).__civoraAiRealismArtifact);
}

test.describe("Chat 226 AI realism preview", () => {
  test("keeps Standard technical preview and High Quality geometry mode working", async ({ page }) => {
    await openDemoWorkspace(page);
    const canvas = page.getByTestId("workspace-canvas-shell");

    await canvas.getByTestId("preview-quality-standard").click();
    await expect(page.getByTestId("preview-map-fallback-surface")).toBeVisible();
    await expect(page.getByTestId("preview-source-confidence-summary")).toBeVisible();

    await enableHighQuality(page);
    await expect(page.getByTestId("high-quality-preview-only-label")).toContainText("Presentation/realism mode");
    await expect(page.getByTestId("ai-realism-off")).toHaveClass(/bg-slate-950/);
    await expect(page.getByTestId("plan-polyline-object").first()).toBeVisible();
    await expect(page.getByTestId("plan-parking-stall-cues").first()).toBeVisible();
  });

  test("shows truthful blockers for empty layout and unavailable provider", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&chat226EmptyLayout=1&aiRealismProvider=mock");
    await enableHighQuality(page);
    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-blocker")).toContainText(
      "Add or generate site objects before creating AI realism.",
    );

    await openDemoWorkspace(page);
    await enableHighQuality(page);
    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-blocker")).toContainText("AI realism provider is not configured.");
  });

  test("creates a review-only mock artifact with visible watermark and source summary", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock");
    const initialLayoutHash = await page.evaluate(() => (window as typeof window & { __civoraAiRealismLayoutHash?: string }).__civoraAiRealismLayoutHash);
    await enableHighQuality(page);

    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-image")).toBeVisible();
    await expect(page.getByTestId("ai-realism-watermark")).toContainText(
      "AI visualization from current review layout",
    );
    await expect(page.getByTestId("ai-realism-source-summary")).toContainText("high_quality_ai_render_v1");
    await expect(page.getByTestId("ai-realism-objects-included")).toContainText("Detention Basin A");
    await expect(page.getByTestId("ai-realism-generated-timestamp")).toContainText(/T.*Z/);

    const artifact = await getAiArtifact(page);
    expect(artifact).toMatchObject({
      type: "high_quality_ai_render_v1",
      project_id: "demo-pinecrest-mixed-use",
      source_layout_hash: initialLayoutHash,
      review_only: true,
      not_site_evidence: true,
      construction_release_allowed: false,
      stale: false,
    });

    const geometryBeforeToggle = await page.evaluate(() => ({
      hash: (window as typeof window & { __civoraAiRealismLayoutHash?: string }).__civoraAiRealismLayoutHash,
      objectCount: document.querySelectorAll("[data-object-overlay]").length,
    }));
    await page.getByTestId("ai-realism-off").click();
    await page.getByTestId("ai-realism-on").click();
    const geometryAfterToggle = await page.evaluate(() => ({
      hash: (window as typeof window & { __civoraAiRealismLayoutHash?: string }).__civoraAiRealismLayoutHash,
      objectCount: document.querySelectorAll("[data-object-overlay]").length,
    }));
    expect(geometryAfterToggle).toEqual(geometryBeforeToggle);
  });

  test("marks the visualization stale after the review layout changes", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock");
    await enableHighQuality(page);
    await page.getByTestId("ai-realism-on").click();
    await expect(page.getByTestId("ai-realism-image")).toBeVisible();

    await page.getByRole("button", { name: "Object Manager" }).click();
    await expect(page.getByTestId("draw-cad-tools-section")).toBeVisible();
    await page.getByLabel("CAD command input").fill("LINE 20,20 90,20");
    await page.getByLabel("CAD command input").press("Enter");
    await expect(page.getByTestId("cad-command-feedback-panel")).toContainText("LINE created");

    await expect(page.getByTestId("ai-realism-stale-warning")).toContainText(
      "AI visualization is stale. Regenerate from current layout.",
    );
    const staleArtifact = await getAiArtifact(page);
    expect(staleArtifact).toMatchObject({
      type: "high_quality_ai_render_v1",
      stale: true,
      review_only: true,
      not_site_evidence: true,
      construction_release_allowed: false,
    });
    await page.getByTestId("ai-realism-regenerate").click();
    await expect(page.getByTestId("ai-realism-stale-warning")).toHaveCount(0);
  });

  test("does not expose unsafe construction-ready wording", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock");
    await enableHighQuality(page);
    await page.getByTestId("ai-realism-on").click();
    const text = await page.getByTestId("workspace-canvas-shell").innerText();
    expect(text).not.toMatch(/construction-ready|\bstamp\b|\bseal\b|certify|certified|approved for construction|engineer of record/i);
  });
});
