import { expect, test, type Route } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

test("focused generate sends reactive checkpoint metadata", async ({ page }) => {
  let observedPayload: unknown = null;

  await page.addInitScript(
    ([tokenKey, restoreKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, "reactive-rerun-token"] as const,
  );

  await page.route("**/api/auth/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, user: { user_id: "reactive-user", email: "reactive@example.com" } }),
    });
  });

  await page.route("**/api/jobs**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [] }) });
  });

  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [] }) });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, project: { project_id: "reactive-project", name: "Reactive Project", project_input: {} } }),
    });
  });

  const fulfillObservedGenerate = async (route: Route) => {
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
  };

  await page.route("**/api/orchestrate", fulfillObservedGenerate);
  await page.route("**/api/jobs/orchestrate", fulfillObservedGenerate);

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

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Setup$/ }).first().click();
  const siteDetails = page.getByTestId("setup-site-box-controls");
  if (!(await siteDetails.evaluate((element) => element.hasAttribute("open")))) {
    await siteDetails.locator("summary").click();
  }
  await page.getByRole("button", { name: "Use 1000 x 1000 ft" }).click();
  await page.getByRole("button", { name: "Use this site" }).click();
  await expect(page.getByText("SITE LOCKED").first()).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: /^Generate$/ }).first().click();
  await expect(page.getByTestId("generate-reactive-details")).toBeVisible();
  const systemDetails = page.getByTestId("generate-system-details");
  if (!(await systemDetails.evaluate((element) => element.hasAttribute("open")))) {
    await systemDetails.locator("summary").click();
  }
  await page.getByTestId("generate-grading").click();
  await expect.poll(() => observedPayload, { timeout: 8_000 }).not.toBeNull();
  await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran: grading/i, { timeout: 8_000 });
  await expect(page.getByTestId("generate-grading")).toBeEnabled({ timeout: 8_000 });
  await page.waitForTimeout(250);
  observedPayload = null;

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
  const nestedPayload =
    ((payload.requestPayload ?? payload.request ?? payload.payload) as Record<string, unknown> | undefined) ?? payload;
  const meta = (nestedPayload.meta ?? {}) as Record<string, unknown>;
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
  await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran: grading|Started/i);
});
