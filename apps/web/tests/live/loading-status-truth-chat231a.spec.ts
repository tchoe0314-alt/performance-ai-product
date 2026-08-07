import { expect, test, type Page } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

async function collectPageErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

async function openDemoWorkspace(page: Page, query = "debugPreview=1&aiRealismProvider=mock") {
  const params = new URLSearchParams(query);
  if (!params.has("seedDemo")) {
    params.set("seedDemo", "1");
  }
  await page.goto(`/demo/workspace?${params.toString()}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
}

async function openPanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible()) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 10_000 });
}

async function focusCommand(page: Page) {
  const chatInput = page.getByTestId("civora-chat-input");
  if (await chatInput.isVisible()) {
    await chatInput.click();
    await expect(chatInput).toBeFocused({ timeout: 5_000 });
    return chatInput;
  }
  await page.keyboard.press(process.platform === "darwin" ? "Meta+K" : "Control+K");
  if (await chatInput.isVisible()) {
    await expect(chatInput).toBeFocused({ timeout: 5_000 });
    return chatInput;
  }
  const commandInput = page.getByTestId("civora-command-input");
  await expect(commandInput).toBeFocused({ timeout: 5_000 });
  return commandInput;
}

async function runCommand(page: Page, command: string) {
  const input = await focusCommand(page);
  await input.fill(command);
  await input.press("Enter");
}

async function mockSignedInProjectShell(page: Page) {
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
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [] }) });
  });
  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          success: true,
          projects: [
            {
              project_id: "pw-project",
              name: "Playwright Project",
              description: "Saved by test",
              has_result: false,
              updated_at: 1_700_000_000,
            },
          ],
        }),
      });
      return;
    }
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    await new Promise((resolve) => setTimeout(resolve, 120));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: String(payload.name || "Playwright Project"),
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
          updated_at: Date.now() / 1000,
        },
      }),
    });
  });
  await page.route("**/api/projects/pw-project", async (route) => {
    if (route.request().method() === "DELETE") {
      await new Promise((resolve) => setTimeout(resolve, 120));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 120));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: "Playwright Project",
          project_input: { input_mode: "user", manual_fields: {}, meta: { site_inputs: {} } },
          has_result: false,
          updated_at: Date.now() / 1000,
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

test.describe("Chat 231A loading states and status truth", () => {
  test("uses one command surface, unified status, shortcuts, and no layout errors", async ({ page }) => {
    const errors = await collectPageErrors(page);
    await page.route("**/api/auth/**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true }) });
    });
    await page.route("**/api/jobs**", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, jobs: [] }) });
    });
    await page.route("**/api/projects", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ success: true, projects: [] }) });
    });
    await openDemoWorkspace(page);

    await expect(page.getByTestId("floating-command-bar")).toHaveCount(0);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(0);

    await openPanel(page, /^Setup$/, /Setup|Address \/ Location|Site Boundary/i);
    await expect(page.getByTestId("project-status-summary")).toContainText(/needs review|ready|blocked|working/i);

    await page.keyboard.press("/");
    await expect(page.getByTestId("floating-command-bar")).toHaveCount(1);
    await expect(page.getByTestId("civora-command-input")).toHaveCount(1);
    await expect(page.getByTestId("civora-command-input")).toBeFocused();

    await page.locator("body").click({ position: { x: 24, y: 24 } });
    await page.keyboard.press("?");
    await expect(page.getByTestId("shortcuts-help-overlay")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("shortcuts-help-overlay")).toHaveCount(0);
    await expect(page.getByTestId("civora-command-input")).not.toBeFocused();

    await page.keyboard.press("G");
    await expect(page.getByTestId("project-status-summary")).toContainText(/Ready/i);
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Generate Systems/i);

    await page.keyboard.press("D");
    await expect(page.getByTestId("workspace-right-panel")).toContainText(/Draw & Objects|Tools/i);

    await page.keyboard.press("P");
    await expect(page.getByTestId("project-status-summary")).toContainText(/Ready/i);
    await expect(page.getByTestId("projects-drawer")).toBeVisible();

    await page.evaluate(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "s", metaKey: true, ctrlKey: true, bubbles: true }));
    });
    await expect(page.getByTestId("project-status-summary")).toContainText(/Needs input/i);
    await expect(page.getByTestId("project-status-summary")).toContainText(/Save needs sign-in|demo workspace|sign in\/connect backend/i);

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    expect(errors).toEqual([]);
  });

  test("reports apply address and source discovery blockers with next action", async ({ page }) => {
    await openDemoWorkspace(page);
    await openPanel(page, /^Setup$/, /Setup|Address \/ Location|Site Boundary/i);

    const addressDetails = page.getByTestId("setup-address-truth");
    await expect(addressDetails).toBeVisible();
    if (!(await addressDetails.evaluate((element) => element.hasAttribute("open")))) {
      await addressDetails.locator("summary").click();
    }
    await addressDetails.getByLabel("Type project address").fill("1 Main St, Test City, TX");
    await page.getByRole("button", { name: "Apply address" }).click();

    await expect(page.getByTestId("project-status-summary")).toContainText(/needs review|needs input/i);
    await expect(page.getByTestId("project-status-summary")).toContainText(/Address applied locally|Sign in\/connect backend to apply address/i);
  });

  test("generate and deliver loading states resolve to review or blocker summaries", async ({ page }) => {
    await openDemoWorkspace(page);

    await openPanel(page, "Generate", /Generate systems/i);
    await page.getByTestId("generate-main-action").click();
    await expect(page.getByTestId("project-status-summary")).toContainText(/working|needs review/i, { timeout: 5_000 });
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:|Needs input/i, { timeout: 10_000 });

    await openPanel(page, /^Deliver$/, /Review package/i);
    await page.getByRole("button", { name: /Make Review Package/i }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText(/needs input|needs review/i);
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|Needs input/i);
  });

  test("chat status answers match visible status and unsafe commands refuse boundaries", async ({ page }) => {
    await openDemoWorkspace(page);

    await openPanel(page, /^Setup$/, /Setup|Address \/ Location|Site Boundary/i);
    const visibleStatus = (await page.getByTestId("project-status-summary").innerText()).toLowerCase();
    await runCommand(page, "what should I do next?");
    await expect(page.getByText(/Current status:/i).last()).toContainText(/needs input|needs review|ready|working|update recommended/i);
    await expect(page.getByText(/Current status:/i).last()).toContainText(visibleStatus.includes("needs input") ? "Needs input" : /needs review|ready|working|update recommended/i);

    await runCommand(page, "what is blocked?");
    await expect(page.getByText(/Needs input|No needs-input items|No current needs-input items/i).last()).toBeVisible();

    await runCommand(page, "whats blockd rn");
    await expect(page.getByText(/Needs input|Nothing is stopping the current review workflow/i).last()).toBeVisible();
    const chatPanel = page.getByTestId("workspace-right-panel");
    await expect(chatPanel.getByTestId("civora-chat-input")).toBeVisible();
    await expect(chatPanel).not.toContainText(/site type or land use|which systems to include/i);

    await runCommand(page, "wut changed since i drew stuff");
    await expect(page.getByText(/Last Generate|Recent changes|Changed\/stale systems|No edits, Generate runs, or review packages/i).last()).toBeVisible();
    await expect(chatPanel).not.toContainText(/site type or land use|which systems to include/i);

    await runCommand(page, "stamp this");
    await expect(page.getByText(/can't stamp, seal, sign, certify/i).last()).toBeVisible();
    await expect(chatPanel).toContainText(/can't stamp, seal, sign, certify/i);
  });

  test("AI visualization and project persistence show truthful loading, success, or blocker state", async ({ page }) => {
    await mockSignedInProjectShell(page);
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });

    await openPanel(page, "Projects", /Projects/i);
    await page.getByRole("button", { name: "Save Project" }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText(/working|ready/i, { timeout: 5_000 });
    await expect(page.getByTestId("project-status-summary")).toContainText(/Project saved|Saving project/i, { timeout: 10_000 });

    await page.getByRole("button", { name: /Open project Playwright Project/i }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText(/working|ready/i, { timeout: 5_000 });
    await expect(page.getByTestId("project-status-summary")).toContainText(/Project opened|Opening project/i, { timeout: 10_000 });

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByRole("button", { name: /Delete project Playwright Project/i }).click();
    await expect(page.getByTestId("project-status-summary")).toContainText(/working|ready/i, { timeout: 5_000 });
    await expect(page.getByTestId("project-status-summary")).toContainText(/Project deleted|Deleting project/i, { timeout: 10_000 });

    await openDemoWorkspace(page, "debugPreview=1&aiRealismProvider=mock");
    await runCommand(page, "create AI visualization");
    await expect(page.getByTestId("preview-quality-high").first()).toHaveAttribute("aria-pressed", "true", { timeout: 5_000 });
    await expect(page.getByTestId("project-status-summary")).toContainText(/Ready: Plan Sheet view on/i);
    await expect(page.getByTestId("ai-realism-off").first()).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Minimize" }).click();
    await page.getByTestId("ai-realism-on").first().click();
    await expect(page.getByTestId("ai-realism-image")).toBeVisible({ timeout: 10_000 });

    await runCommand(page, "turn AI visualization off");
    await expect(page.getByTestId("preview-quality-standard").first()).toHaveAttribute("aria-pressed", "true", { timeout: 5_000 });
  });
});
