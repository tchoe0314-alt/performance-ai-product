import { expect, test } from "@playwright/test";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";
import { revealPreviewCanvas } from "./testUiHelpers";

test("mobile preview helper waits for the post-reload drawer before closing it", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await page.setContent("<div>Loading</div>");
  await page.evaluate(() => {
    setTimeout(() => {
      document.body.innerHTML = `<div data-testid="workspace-canvas-shell">Canvas</div>
        <aside><button aria-label="Close panel" onclick="this.closest('aside').remove()">Close</button></aside>`;
    }, 100);
  });
  await revealPreviewCanvas(page);
  await expect(page.getByRole("button", { name: "Close panel", exact: true })).toHaveCount(0);
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
