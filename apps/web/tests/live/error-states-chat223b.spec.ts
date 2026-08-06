import { expect, test, type Page } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

async function openDemoWorkspace(page: Page, query = "debugPreview=1") {
  await page.goto(`/demo/workspace?${query}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
}

async function openWorkspacePanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible()) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).filter({ visible: true }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 10_000 });
}

async function mockSignedInShell(page: Page) {
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
      body: JSON.stringify({ user: { user_id: "pw-user", email: "pw@example.com", name: "Playwright" } }),
    });
  });
  await page.route("**/api/jobs**", async (route) => {
    if (
      route.request().method() === "POST" &&
      new URL(route.request().url()).pathname === "/api/jobs/source-context"
    ) {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Queue endpoint unavailable in this focused fixture." }),
      });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [] }) });
  });
  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [] }) });
      return;
    }
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: "Playwright Project",
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
        },
      }),
    });
  });
  await page.addInitScript(
    ([tokenKey, restoreKey, authToken]) => {
      window.localStorage.setItem(tokenKey, authToken);
      window.sessionStorage.setItem(restoreKey, "1");
    },
    [TOKEN_KEY, SESSION_RESTORE_KEY, "pw-token"] as const,
  );
}

async function mockGeocode(page: Page) {
  await page.route("**/api/geocode", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        status: "ready",
        lat: 32.8,
        lng: -96.8,
        display_name: "1 MAIN ST, TEST CITY, TX",
        provider: "test_geocoder",
      }),
    });
  });
}

test.describe("Chat 223B empty/error/loading/recovery states", () => {
  test("login reports invalid credentials instead of an expired session", async ({ page }) => {
    await page.route("**/api/auth/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, account_setup: "configured" }),
      });
    });
    await page.route("**/api/auth/login", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or password." }),
      });
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "Sign In Mode" }).click();
    await page.getByLabel("Email", { exact: true }).fill("engineer@example.com");
    await page.getByLabel("Password", { exact: true }).fill("incorrect-password");
    await page.getByRole("button", { name: "Sign In", exact: true }).click();

    await expect(page.getByText("Invalid email or password.")).toBeVisible();
    await expect(page.getByText("Session expired. Sign in again.")).toHaveCount(0);
  });

  test("auth distinguishes expired session from unavailable backend", async ({ page }) => {
    await page.route("**/api/auth/status", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, user_count: 1, registration_allowed: true }),
      });
    });
    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "expired" }) });
    });
    await page.addInitScript(
      ([tokenKey, restoreKey, authToken]) => {
        window.localStorage.setItem(tokenKey, authToken);
        window.sessionStorage.setItem(restoreKey, "1");
      },
      [TOKEN_KEY, SESSION_RESTORE_KEY, "expired-token"] as const,
    );

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Session expired. Sign in again.")).toBeVisible({ timeout: 30_000 });

    await page.route("**/api/auth/status", async (route) => route.abort("connectionrefused"));
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("text=/Backend unreachable|Account status will appear here once/i").first()).toBeVisible({ timeout: 30_000 });
  });

  test("Apply Address shows signed-out blocker inline", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&seedDemo=1");
    await openWorkspacePanel(page, /^Setup$/, /Setup|Address \/ Location|Site Boundary/i);
    const addressDetails = page.getByTestId("setup-address-truth");
    await expect(addressDetails).toBeVisible();
    if (!(await addressDetails.evaluate((element) => element.hasAttribute("open")))) {
      await addressDetails.locator("summary").click();
    }
    await addressDetails.getByLabel("Type project address").fill("1 Main St, Test City, TX");
    await page.getByRole("button", { name: "Apply address" }).click();

    await expect(page.getByTestId("apply-address-status")).toContainText(
      "Address saved locally. Live geocode and source lookup need sign-in/backend access",
    );
  });

  test("Auto Site Context separates provider failure from successful no-feature results", async ({ page }) => {
    await mockSignedInShell(page);
    await mockGeocode(page);
    await page.route("**/api/existing-conditions/fetch-online", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: false,
          status: "fetch_failed",
          online_existing_conditions_discovery_v1: {
            version: "online_existing_conditions_discovery_v1",
            status: "fetch_failed",
            candidate_count: 0,
            sources: [],
            blockers: ["Provider timed out."],
            review_required: true,
            acceptance_status: "missing",
          },
        }),
      });
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Setup" }).first().click();
    const addressDetails = page.getByTestId("setup-address-truth");
    await expect(addressDetails).toBeVisible();
    if (!(await addressDetails.evaluate((element) => element.hasAttribute("open")))) {
      await addressDetails.locator("summary").click();
    }
    await addressDetails.getByLabel("Type project address").fill("1 Main St, Test City, TX");
    await page.getByRole("button", { name: "Apply address" }).click();
    await expect(page.getByTestId("auto-site-context-candidates")).toContainText(/provider lookup could not complete|provider lookup failed/i, { timeout: 30_000 });

    await page.unroute("**/api/existing-conditions/fetch-online");
    await page.route("**/api/existing-conditions/fetch-online", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          status: "ready_no_features",
          online_existing_conditions_discovery_v1: {
            version: "online_existing_conditions_discovery_v1",
            status: "no_features",
            candidate_count: 0,
            sources: [
              { key: "roads", label: "roads", provider: "Test Roads", candidate_count: 0, blockers: ["No features inside the locked site."] },
            ],
            review_required: true,
            acceptance_status: "missing",
          },
        }),
      });
    });
    await page.getByRole("button", { name: "Apply address" }).click();
    await expect(page.getByTestId("auto-site-context-candidates")).toContainText(/No source candidates found yet/i, { timeout: 30_000 });
    await expect(page.getByTestId("auto-site-context-found")).toContainText(/No usable features/i);
  });

  test("Apply Address rejects an uncertain match before source discovery", async ({ page }) => {
    await mockSignedInShell(page);
    let sourceContextRequested = false;
    page.on("request", (request) => {
      if (/\/api\/(?:jobs\/source-context|existing-conditions\/fetch-online)/.test(request.url())) {
        sourceContextRequested = true;
      }
    });
    await page.route("**/api/geocode", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: false,
          status: "uncertain_match",
          blocked: true,
          message: "Address lookup returned an uncertain or unrelated match.",
          blockers: [
            {
              area: "geocode",
              code: "address_match_uncertain",
              message: "Address lookup returned an uncertain or unrelated match.",
            },
          ],
        }),
      });
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Setup" }).first().click();
    await page.getByLabel("Type project address").fill("asdfghjkl; not a real address");
    await page.getByRole("button", { name: "Apply address" }).click();

    await expect(page.getByTestId("apply-address-status")).toContainText("uncertain or unrelated match");
    await expect(page.getByTestId("project-status-summary")).toContainText("Apply address needs correction");
    await expect(page.getByTestId("site-status")).toContainText("Site Open");
    expect(sourceContextRequested).toBe(false);
  });

  test("upload, PDF, and survey/topo failures stay inline", async ({ page }, testInfo) => {
    await openDemoWorkspace(page);
    await openWorkspacePanel(page, /^Setup$/, /Setup|Address \/ Location|Site Boundary/i);
    const sources = page.getByTestId("setup-survey-terrain-card");
    if (!(await sources.evaluate((element) => element.hasAttribute("open")))) {
      await sources.locator(":scope > summary").click();
    }
    await expect(sources).toContainText(/Map snapshot|Survey/i, { timeout: 10_000 });
    await sources.getByRole("button", { name: /^Import$/ }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText("Import inputs", { timeout: 10_000 });
    const imagePath = testInfo.outputPath("site-image.png");
    await testInfo.attach("empty-image", { body: Buffer.from("not an image"), contentType: "text/plain" });
    await page.locator('input[accept="image/*"]').first().setInputFiles({ name: "site-image.png", mimeType: "image/png", buffer: Buffer.from("not an image") });
    await expect(page.getByTestId("image-upload-status")).toContainText("Image upload failed: Sign in/connect backend to upload images.");

    await page.locator('input[accept*=".csv"]').first().setInputFiles({ name: "survey.txt", mimeType: "text/plain", buffer: Buffer.from("bad") });
    await expect(page.getByTestId("survey-upload-status").first()).toContainText("Survey/topo upload failed: Unsupported file.");
    expect(imagePath).toContain("site-image.png");

    await page.getByRole("button", { name: "Plan PDF visual editor" }).click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText("PDF Plan Visual Editor", { timeout: 10_000 });
    await page.locator('input[accept="application/pdf,.pdf"]').setInputFiles({ name: "plan.txt", mimeType: "text/plain", buffer: Buffer.from("bad") });
    await expect(page.getByTestId("pdf-upload-status")).toContainText("PDF upload failed: Unsupported file.");
  });

  test("Generate partial runs say started with skipped systems", async ({ page }) => {
    await openDemoWorkspace(page, "debugPreview=1&seedDemo=1");
    page.on("dialog", async (dialog) => dialog.accept());
    await openWorkspacePanel(page, "Generate", /Generate systems/i);
    const systemDetails = page.getByTestId("generate-system-details");
    if (!(await systemDetails.evaluate((element) => element.hasAttribute("open")))) {
      await systemDetails.locator("summary").click();
    }
    await page.getByTestId("generate-drainage").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText("Started, with skipped systems", { timeout: 10_000 });
  });

  test("Jobs panel shows refresh failure, stale warning, and status-specific detail", async ({ page }) => {
    await mockSignedInShell(page);
    let jobsFail = false;
    const staleUpdatedAt = Math.floor(Date.now() / 1000) - 3600;
    await page.unroute("**/api/jobs**");
    await page.route("**/api/jobs**", async (route) => {
      if (jobsFail) {
        await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "jobs backend unavailable" }) });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          jobs: [
            {
              job_id: "job-stale",
              job_type: "orchestrate",
              status: "running",
              progress: 42,
              updated_at: staleUpdatedAt,
              created_at: staleUpdatedAt,
              can_cancel: true,
              can_retry: false,
              can_resume: false,
            },
            {
              job_id: "job-source-complete",
              job_type: "source_context",
              status: "completed",
              progress: 100,
              stage_detail: "Source lookup complete. 18 items are ready for review.",
              updated_at: staleUpdatedAt - 10,
              created_at: staleUpdatedAt - 20,
              can_cancel: false,
              can_retry: false,
              can_resume: false,
            },
          ],
        }),
      });
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("header-projects-button").click();
    await page.getByRole("button", { name: "Open Jobs" }).click();
    await page.getByTestId("async-jobs-panel").getByRole("button", { name: "Refresh" }).click();
    await expect(page.getByTestId("jobs-stale-warning")).toContainText("Backend status is stale", { timeout: 30_000 });
    await expect(page.getByTestId("job-detail-drawer")).toContainText("Running. Civora has not recorded the next stage detail yet.");
    await page.getByRole("button", {
      name: "job-source-complete source context completed Source lookup complete. 18 items are ready for review.",
    }).click();
    await expect(page.getByTestId("job-detail-drawer")).toContainText("job-source-complete");
    await expect(page.getByTestId("job-detail-drawer")).toContainText("Source lookup complete. 18 items are ready for review.");
    jobsFail = true;
    await page.getByTestId("async-jobs-panel").getByRole("button", { name: "Refresh" }).click();
    await expect(page.getByTestId("jobs-refresh-status")).toContainText("Job refresh failed", { timeout: 30_000 });
    jobsFail = false;
    await page.getByTestId("async-jobs-panel").getByRole("button", { name: "Refresh" }).click();
    await expect(page.getByTestId("jobs-refresh-status")).toContainText("Jobs refreshed.", { timeout: 30_000 });
    await expect(page.getByTestId("jobs-refresh-status")).not.toContainText("Job refresh failed");
  });

  test("export download failures set visible deliver/export status", async ({ page }) => {
    await openDemoWorkspace(page);
    await openWorkspacePanel(page, /^Deliver$/, /Review package/i);
    await page.getByTestId("workspace-right-panel").getByRole("button", { name: "Export DXF" }).click();
    await expect(page.getByTestId("deliver-export-status")).toContainText(/Export needs input|authenticate with a backend session/i);
  });

  test("chat backend failures append friendly retry guidance", async ({ page }) => {
    await mockSignedInShell(page);
    await page.route("**/api/chat/decide", async (route) => {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "chat backend unavailable" }) });
    });
    await page.route("**/api/jobs/orchestrate", async (route) => {
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "queue unavailable" }) });
    });

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
    await page.getByTestId("header-chat-button").click();
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Command Center|Conversation/i);
    const input = page
      .getByTestId("workspace-right-panel")
      .getByPlaceholder("Message Civora AI with what you want to create or change...");
    await input.fill("Tell me something unusual about this workspace qzx-backend-only");
    await input.press("Enter");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/retry your message|could not reach the backend|could not finish/i, { timeout: 30_000 });
  });
});
