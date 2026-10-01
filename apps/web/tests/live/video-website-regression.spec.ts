import { expect, test } from "@playwright/test";
import { buildDashboardDemoWorkspaceSeed } from "../../app/utils/dashboardDemoWorkspaceSeed";
import { buildDashboardPreview3DView } from "../../app/utils/dashboardPreview3DItems";

test("fictional seed has no real map anchor and supplies complete synthetic terrain", () => {
  const seed = buildDashboardDemoWorkspaceSeed({ debugEmptyLayout: false, debugEmptyObjects: false });
  expect(seed.demoProject.project_input?.meta?.site_inputs?.geocode).toBeUndefined();
  // A stale result must not create a second building after editing the live object.
  seed.demoPlacements.find(item => item.id === "demo-building-a")!.w = 160;
  const view = buildDashboardPreview3DView({
    backendResult: seed.demoResult, buildingPlacements: seed.demoPlacements,
    cadEntityPreview: { sourceIds: new Set(), linkedIds: new Set(), items3D: [], objects: [] },
    lot: { w: 760, h: 520 }, planPreviewAnnotations: null,
    previewLayersEffective: { buildings: true, roads: true, drainage: true, utilities: true, structures: true, lots: true },
    sourceConfidenceByObjectId: new Map(),
  });
  const samples = view.preview3DEffectiveItems.filter(item => item.terrainSample);
  expect(samples).toHaveLength(64);
  expect(samples.every(item => /synthetic demo surface/i.test(String(item.source)))).toBe(true);
  expect(Math.max(...samples.map(item => item.x))).toBe(760);
  expect(Math.max(...samples.map(item => item.y))).toBe(520);
  expect(view.preview3DEffectiveItems.filter(item => item.label === "Multifamily Building A")).toHaveLength(1);
});

test("recorded website workflow selects objects and opens 3D without duplicate keys or false map placement", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo/workspace?seedDemo=1&debugPreview=1");
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible();
  await expect(page.getByTestId("preview-inner-map-toggle")).not.toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Draw", exact: true }).first().click();
  const list = page.getByTestId("object-manager-panel");
  if (!(await list.evaluate(el => (el as HTMLDetailsElement).open))) await list.locator(":scope > summary").click();
  await page.getByTestId("object-manager-row").filter({ hasText: "Multifamily Building A" }).first().getByTestId("object-manager-select").click();
  await expect(page.getByTestId("draw-selected-object-card")).toContainText("Multifamily Building A");
  await expect(page.getByTestId("object-detailed-geometry")).toHaveCount(1);
  await page.getByTestId("preview-mode-3d").click();
  await expect(page.getByTestId("civil-3d-canvas-mount").locator("canvas")).toBeVisible();
  await expect(page.getByTestId("civil-3d-terrain-state")).toContainText("Synthetic demo terrain");
  const canvas = page.getByTestId("civil-3d-canvas-mount").locator("canvas");
  await expect.poll(async () => JSON.parse(await canvas.getAttribute("data-rendered-geometry") || "[]")
    .find((item: { id: string }) => item.id === "demo-loop-road")?.geometryType).toBe("polyline");
  await expect.poll(async () => JSON.parse(await canvas.getAttribute("data-rendered-geometry") || "[]")
    .find((item: { id: string }) => item.id === "demo-loop-road")?.corridorFacesUp).toBe(true);
  await expect.poll(async () => JSON.parse(await canvas.getAttribute("data-rendered-geometry") || "[]")
    .find((item: { id: string }) => item.id === "demo-parking-north")?.geometryType).toBe("polygon");
  await expect(page.getByTestId("civil-3d-object-strip").getByRole("button", { name: /Multifamily Building A/ })).toHaveCount(1);
  await page.screenshot({ path: "/tmp/civora-video-website-fixed.png" });
  expect(errors.filter(error => /same key|hydration|uncaught/i.test(error))).toEqual([]);
});
