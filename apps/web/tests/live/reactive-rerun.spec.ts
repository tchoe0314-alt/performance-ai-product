import { expect, test } from "@playwright/test";

test("focused generate sends reactive checkpoint metadata", async ({ page }) => {
  let observedPayload: unknown = null;

  await page.route("**/api/orchestrate", async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    observedPayload = body;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        message: "Reactive partial rerun complete.",
        final_plan: {
          actions: [],
          meta: {
            reactive_partial_rerun: {
              enabled: true,
              checkpoint_restored: true,
              impacted_stages: ["grading", "drainage", "storm_pipes"],
              rerun_stages: ["grading", "drainage", "storm_pipes"],
              skipped_stages: ["layout"],
              telemetry: {
                elapsed_ms: 42,
                quick_threshold_ms: 5000,
                within_quick_threshold: true,
              },
            },
            reactive_update_report: {
              execution_mode: "isolated_downstream_partial_rerun",
              partial_rerun_executed: true,
              impacted_stages: ["grading", "drainage", "storm_pipes"],
            },
          },
        },
        assumptions: [],
        issues: [],
        warnings: [],
        errors: [],
        metadata: {},
      }),
    });
  });

  await page.route("**/api/preview", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        preview_image_data_url:
          "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
      }),
    });
  });

  await page.goto("/?demo=workspace", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /^Generate$/ }).first().click();
  await expect(page.getByTestId("reactive-rerun-status")).toBeVisible();
  page.once("dialog", async (dialog) => {
    expect(dialog.message()).toContain("saved checkpoint");
    await dialog.accept();
  });
  await page.getByTestId("generate-grading").click();
  await expect.poll(() => observedPayload).not.toBeNull();
  if (!observedPayload) {
    throw new Error("Expected reactive rerun payload to be captured.");
  }

  const payload = observedPayload as Record<string, unknown>;
  const meta = (payload.meta ?? {}) as Record<string, unknown>;
  const orchestratorMeta = (meta.orchestrator_meta ?? {}) as Record<string, unknown>;
  const runtimeResume = (orchestratorMeta.runtime_resume ?? {}) as Record<string, unknown>;
  expect(meta.requested_system).toBe("grading");
  expect(meta.reactive_partial_rerun_request).toMatchObject({
    enabled: true,
    requested_system: "grading",
    checkpoint_attached: true,
  });
  expect(Array.isArray(meta.changed_targets)).toBe(true);
  expect((meta.changed_targets as string[])).toContain("grading");
  expect(runtimeResume.final_plan).toBeTruthy();
  await expect(page.getByText("Last partial rerun")).toBeVisible();
});
