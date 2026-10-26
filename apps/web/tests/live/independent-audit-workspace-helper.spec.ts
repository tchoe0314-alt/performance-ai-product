import { expect, test } from "@playwright/test";
import { openWorkspaceTool, workspaceCommandButton } from "./helpers/workspaceNavigation";
import { revealPreviewCanvas } from "./testUiHelpers";

test("mobile preview helper waits for the post-reload drawer before closing it", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.setContent("<div>Loading</div>");
  await page.evaluate(() => {
    setTimeout(() => {
      document.body.innerHTML = `<div data-testid="workspace-canvas-shell">Canvas</div>
        <button aria-label="Preview view options">View</button>
        <aside><button aria-label="Close panel" onclick="this.closest('aside').remove()">Close</button></aside>`;
    }, 100);
  });
  await revealPreviewCanvas(page);
  await expect(page.getByRole("button", { name: "Close panel", exact: true })).toHaveCount(0);
});

test("mobile preview helper closes a later drawer before declaring the toolbar actionable", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.setContent(`<div data-testid="workspace-canvas-shell">Canvas</div>
    <button aria-label="Preview view options" disabled>View</button>`);
  await page.evaluate(() => {
    // Controlled delayed lifecycle: the shell is already mounted, unlike the
    // earlier test. This delay simulates hydration; it is not a test-side sleep.
    setTimeout(() => {
      document.body.insertAdjacentHTML("beforeend", `<aside data-testid="workspace-right-panel"
        style="position:fixed;inset:0;z-index:10;background:white">
        <button aria-label="Close panel" onclick="this.closest('aside').remove()">Close</button></aside>`);
      (document.querySelector('[aria-label="Preview view options"]') as HTMLButtonElement).disabled = false;
    }, 100);
  });
  await revealPreviewCanvas(page);
  await page.getByLabel("Preview view options", { exact: true }).click({ trial: true, timeout: 1000 });
  await expect(page.getByTestId("workspace-right-panel")).toHaveCount(0);
});

test("navigation helper waits for the mounted stage interface after reload", async ({ page }) => {
  await page.setContent("<div>Loading</div>");
  await page.evaluate(() => {
    setTimeout(() => {
      document.body.innerHTML = `<div data-testid="workspace-canvas-shell">Canvas</div>
        <button data-testid="workspace-stage-explore">Explore</button>
        <select data-testid="workspace-stage-panel"><option value="generate">Generate</option><option value="objects">Draw</option></select>`;
    }, 100);
  });
  await openWorkspaceTool(page, "Draw");
  await expect(page.getByTestId("workspace-stage-panel")).toHaveValue("objects");
});

test("navigation helper still supports the mounted older deployed interface", async ({ page }) => {
  await page.setContent(`<div data-testid="workspace-canvas-shell">Canvas</div>
    <button onclick="this.dataset.clicked='true'">Draw</button>`);
  await openWorkspaceTool(page, "Draw");
  await expect(page.getByRole("button", { name: "Draw", exact: true })).toHaveAttribute("data-clicked", "true");
});

for (const label of ["Run Civora command", "Send"]) test(`command helper targets only ${label}`, async ({ page }) => {
  await page.setContent(`<button aria-label="${label}" onclick="this.dataset.clicked='true'">Run</button>
    <button aria-label="Send invitation">Invite</button><button aria-label="Send support request">Support</button>`);
  await workspaceCommandButton(page).click();
  await expect(page.getByRole("button", { name: label, exact: true })).toHaveAttribute("data-clicked", "true");
  await expect(page.getByRole("button", { name: "Send invitation", exact: true })).not.toHaveAttribute("data-clicked");
});
