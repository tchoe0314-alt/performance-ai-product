import { expect, test } from "@playwright/test";
import { openWorkspaceTool } from "./helpers/workspaceNavigation";

test("empty workspace controls expose exact effects and blocked actions make no network mutation", async ({ page }) => {
  const writes: string[] = [];
  page.on("request", request => {
    if (request.method() === "POST" && /\/api\/(?:jobs\/)?(?:orchestrate|jobs\/export|export\/landxml)/.test(request.url())) writes.push(request.url());
  });
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=0&aiRealismProvider=mock", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();

  await openWorkspaceTool(page, "Setup");
  const site = page.getByTestId("setup-site-box-controls");
  if (!(await site.evaluate(node => node.hasAttribute("open")))) await site.locator("summary").click();
  await expect(page.getByTestId("setup-draw-site-boundary")).toHaveCount(1);
  await expect(page.getByTestId("create-centered-site-button")).toHaveCount(1);
  await expect(page.getByTestId("use-1000-site-size")).toHaveCount(1);
  await expect(page.getByTestId("create-centered-site-button")).toBeDisabled();
  await expect(page.getByTestId("create-centered-site-button")).toHaveAttribute("title", "Enter width and depth, or draw a boundary first");

  await openWorkspaceTool(page, "Draw");
  const drawControls = ["cad-tool-point", "cad-tool-line", "cad-tool-polyline", "cad-tool-arc", "cad-tool-box", "cad-tool-circle", "cad-tool-text"];
  for (const id of drawControls) await expect(page.getByTestId(id)).toHaveCount(1);

  await openWorkspaceTool(page, "Generate");
  await expect(page.getByTestId("generate-main-action")).toHaveCount(1);
  await expect(page.getByTestId("generate-layout-options")).toHaveCount(1);
  await expect(page.getByTestId("generate-layout-options")).toBeDisabled();
  await expect(page.getByTestId("generate-layout-options")).toHaveAttribute("title", "Lock a site boundary in Setup before comparing layouts.");
  await page.getByTestId("generate-main-action").click();
  await expect(page.getByTestId("generate-flow-summary")).toContainText("Lock a site boundary");

  await openWorkspaceTool(page, "Review");
  await expect(page.getByTestId("review-result-truth")).toHaveAttribute("data-result-state", "missing");
  await expect(page.getByRole("button", { name: "Run review scan", exact: true })).toHaveCount(1);
  await page.getByRole("button", { name: "Run review scan", exact: true }).click();
  await expect(page.getByText("Address provides site context only. Add or confirm buildings and access objects to run analysis.", { exact: true }).first()).toBeVisible();

  await openWorkspaceTool(page, "Deliver");
  const exports = page.getByTestId("deliver-export-actions");
  for (const name of ["Review PDF", "Export DXF", "Report", "Quantities"]) {
    await expect(exports.getByRole("button", { name, exact: true })).toHaveCount(1);
  }
  await expect(page.getByTestId("deliver-package-contents")).toContainText("Generated resultMissing");
  await exports.getByRole("button", { name: "Review PDF", exact: true }).click();
  await expect(page.getByTestId("deliver-export-status")).toContainText("input");
  await exports.getByRole("button", { name: "Export DXF", exact: true }).click();
  await expect(page.getByTestId("deliver-export-status")).toContainText("input");
  await exports.getByRole("button", { name: "Report", exact: true }).click();
  await expect(page.getByTestId("deliver-export-status")).toContainText("input");
  expect(writes).toEqual([]);
});
