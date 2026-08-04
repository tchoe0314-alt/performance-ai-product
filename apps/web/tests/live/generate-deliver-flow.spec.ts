import { expect, test, type Page } from "@playwright/test";

async function openDemoWorkspace(page: Page) {
  await page.route("**/api/plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        final_plan: {
          actions: [],
          meta: {
            grading: { export_validation: { ready: false, reasons: ["review_only_assumption"] } },
            convergence_summary: { blocked_exports: [], blocked_reasons: [] },
          },
        },
        explanation: { summary: "Generated review draft." },
      }),
    });
  });
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("left-sidebar")).toBeVisible({ timeout: 30_000 });
}

async function openWorkspacePanel(page: Page, name: RegExp | string, expected: RegExp | string) {
  const workspaceButton = page.getByRole("button", { name: "Open workspace controls" });
  if (await workspaceButton.isVisible()) {
    await workspaceButton.click();
  }
  await page.getByRole("button", { name }).first().click();
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 5_000 });
}

async function askChat(page: Page, question: string, expected: RegExp) {
  await page.getByTestId("header-chat-button").click();
  const input = page.getByPlaceholder("Message Civora AI with what you want to create or change...");
  await input.fill(question);
  await input.press("Enter");
  await expect(page.getByTestId("workspace-right-panel")).toContainText(expected, { timeout: 5_000 });
}

test.describe("Generate and Deliver product flow", () => {
  test("Generate uses Auto Site Context notes and Deliver makes a review-only package", async ({ page }) => {
    await openDemoWorkspace(page);

    await openWorkspacePanel(page, "Generate", /Generate systems/i);
    await expect(page.getByTestId("generate-auto-site-context")).toContainText(/review-required source candidate/i);
    await expect(page.getByTestId("generate-auto-site-context")).toContainText(/Sources still needed/i);
    await page.getByTestId("generate-main-action").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Ran:/i, { timeout: 5_000 });
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/Needs review:/i);
    const systemDetails = page.getByTestId("generate-system-details");
    if (!(await systemDetails.evaluate((node) => node.hasAttribute("open")))) {
      await systemDetails.locator("summary").click();
    }
    await page.getByTestId("generate-drainage").click();
    await expect(page.getByTestId("generate-flow-summary")).toContainText(/drainage/i);

    await openWorkspacePanel(page, /^Deliver$/, /Review package/i);
    await page.getByRole("button", { name: /Make Review Package/i }).click();
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Package made|Needs input/i);
    await expect(page.getByTestId("deliver-review-package-summary")).toContainText(/Auto Site Context source missing|generated system result|model preview|none recorded/i);
    await expect(page.getByTestId("deliver-review-package-summary")).not.toContainText(
      /construction readiness blocked|construction release blocked/i,
    );
    await expect(page.getByTestId("deliver-package-context")).toContainText(/Package includes/i);
    await expect(page.getByTestId("deliver-package-context")).toContainText(/draft object|source candidate|review package only/i);
    await expect(page.getByTestId("plan-sheet-editor")).toContainText(/Review-required/i);
    await expect(page.getByTestId("plan-sheet-editor")).not.toContainText(/construction-ready|Civora approved|stamped by Civora|sealed by Civora|signed by Civora/i);

    await page.getByTestId("workspace-right-panel").getByRole("button", { name: "Export DXF" }).click();
    await expect(page.getByTestId("deliver-export-status")).toContainText(/authenticate with a backend session before exporting review packages|Export needs input/i);

    await askChat(page, "what ran?", /Last Generate ran|Current fresh systems/i);
    await askChat(page, "what did you skip?", /Skipped:/i);
    await askChat(page, "what is blocked?", /Needs input|Outputs remain review-required/i);
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(
      /construction readiness blocked|construction release blocked/i,
    );
    await askChat(page, "what changed?", /Last Generate|Auto Site Context/i);
    await askChat(page, "what do I need next?", /next visible UI action|Review missing package inputs|review-required/i);
    await askChat(page, "can I export?", /Export needs input|engineer-review packages/i);
    await expect(page.getByTestId("workspace-right-panel")).not.toContainText(/construction-ready|Civora approved|stamped by Civora|sealed by Civora|signed by Civora/i);
  });
});
