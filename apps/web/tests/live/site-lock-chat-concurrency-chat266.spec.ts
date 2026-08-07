import { expect, test, type Page } from "@playwright/test";

const TOKEN_KEY = "civora-ai-token";
const SESSION_RESTORE_KEY = "civora-ai-session-auth-restore";

async function mockSignedInSlowProjectSave(page: Page) {
  await page.route("**/api/auth/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, user_count: 1, registration_allowed: false }),
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
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true, jobs: [] }),
    });
  });
  for (const endpoint of ["customer-templates", "utility-catalogs", "projects-deleted"]) {
    await page.route(`**/api/${endpoint}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, templates: [], catalogs: [], projects: [] }),
      });
    });
  }
  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true, projects: [] }),
      });
      return;
    }
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    await new Promise((resolve) => setTimeout(resolve, 1_200));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: String(payload.name || "Untitled Project"),
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
          updated_at: Date.now() / 1000,
        },
      }),
    });
  });
  await page.route("**/api/projects/pw-project", async (route) => {
    const payload = route.request().postDataJSON() as Record<string, unknown>;
    await new Promise((resolve) => setTimeout(resolve, 1_200));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        project: {
          project_id: "pw-project",
          name: String(payload.name || "Untitled Project"),
          project_input: payload.project_input ?? {},
          latest_result: payload.latest_result ?? null,
          has_result: Boolean(payload.latest_result),
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

test("opening Chat during the first site save keeps the newer panel open", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await mockSignedInSlowProjectSave(page);

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: /^Setup$/ }).filter({ visible: true }).first().click();
  const siteSection = page.getByTestId("setup-site-box-controls");
  await siteSection.getByRole("button", { name: "Use 1000 ft x 1000 ft" }).click();
  await siteSection.getByRole("button", { name: "Lock Boundary" }).click();

  await page.getByTestId("header-chat-button").click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Chat");
  await expect(page.getByTestId("civora-chat-input")).toHaveCount(1);
  await expect(page.getByTestId("civora-command-input")).toHaveCount(0);

  await page.waitForTimeout(1_600);
  await expect(page.getByTestId("workspace-right-panel")).toContainText("Chat");
  await expect(page.getByTestId("civora-chat-input")).toHaveCount(1);
  await expect(page.getByTestId("civora-command-input")).toHaveCount(0);
  expect(errors).toEqual([]);
});
