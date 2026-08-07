import { expect, test, type Page } from "@playwright/test";

import type { BuildingPlacement, Preview3DItem } from "../../app/types";
import {
  canonicalPlacementFootprintSignature,
  canonicalPreview3DFootprintSignature,
} from "../../app/utils/canonicalGeometrySignature";
import {
  buildPlacementPreview3DItems,
  mergePlacementLedPreview3DItems,
} from "../../app/utils/dashboardPreview3DItems";
import { normalizePreview3DLayer } from "../../app/utils/preview3DLayer";

const placement = (
  id: string,
  type: NonNullable<BuildingPlacement["type"]>,
  x: number,
  y: number,
  w: number,
  d: number,
  geometryType: BuildingPlacement["geometryType"] = "rect",
  geometry?: Array<[number, number]>,
): BuildingPlacement => ({
  id,
  label: id,
  type,
  x,
  y,
  w,
  d,
  h: type.includes("building") ? 42 : undefined,
  rotation: id === "office" ? 17 : 0,
  geometryType,
  geometry,
  source: "user",
  placed: true,
});

test.describe("canonical geometry parity", () => {
  test("maps every supported site-program footprint into 3D without changing geometry", () => {
    const placements: BuildingPlacement[] = [
      placement("office", "office_building", 30, 35, 120, 80, "polygon", [
        [30, 35],
        [150, 35],
        [150, 90],
        [115, 115],
        [30, 115],
      ]),
      placement("parking", "parking", 170, 35, 160, 105),
      placement("basin", "basin", 350, 55, 90, 75),
      placement("driveway", "driveway", 55, 150, 250, 28),
      placement("sidewalk", "sidewalk", 55, 188, 250, 8),
      placement("water", "utility_corridor", 60, 220, 310, 8, "polyline", [
        [60, 220],
        [210, 205],
        [370, 220],
      ]),
      placement("sanitary", "utility_corridor", 60, 245, 310, 8, "polyline", [
        [60, 245],
        [205, 255],
        [370, 245],
      ]),
      placement("storm", "utility_corridor", 60, 270, 310, 8, "polyline", [
        [60, 270],
        [220, 280],
        [370, 270],
      ]),
    ];

    const items = buildPlacementPreview3DItems({
      lot: { w: 500, h: 350 },
      buildingPlacements: placements,
      cadEntityPreviewItems3D: [],
      sourceConfidenceByObjectId: new Map(),
    });
    const objectItems = items.filter((item) => item.layer !== "TERRAIN");

    expect(objectItems).toHaveLength(placements.length);
    placements.forEach((source) => {
      const item = objectItems.find((candidate) => candidate.id === source.id);
      expect(item, `${source.id} should exist in 3D`).toBeTruthy();
      expect(canonicalPreview3DFootprintSignature(item!)).toBe(
        canonicalPlacementFootprintSignature(source),
      );
      expect(item?.linkedObjectId).toBe(source.id);
    });
  });

  test("deduplicates an exact rendering copy but preserves nearby distinct objects", () => {
    const placementItem: Preview3DItem = {
      id: "building-a",
      x: 0,
      y: 0,
      w: 100,
      h: 60,
      height: 30,
      color: "#ddd",
      label: "Building A",
      layer: "BUILDING",
    };
    const exactBackendCopy: Preview3DItem = {
      ...placementItem,
      id: "backend-building-a",
      label: "Generated Building A",
    };
    const nearbyDistinctBuilding: Preview3DItem = {
      ...placementItem,
      id: "building-b",
      x: 10,
      label: "Building B",
    };

    expect(mergePlacementLedPreview3DItems([exactBackendCopy], [placementItem])).toHaveLength(1);
    expect(mergePlacementLedPreview3DItems([nearbyDistinctBuilding], [placementItem])).toHaveLength(2);
  });

  test("keeps storm utilities distinct from drainage features", () => {
    expect(normalizePreview3DLayer("UTILITY", ["Storm Sewer", "storm"])).toBe("UTILITY");
    expect(normalizePreview3DLayer("", ["Storm trunk pipe"])).toBe("UTILITY");
    expect(normalizePreview3DLayer("DRAINAGE", ["Detention Basin A"])).toBe("DRAINAGE");
    expect(normalizePreview3DLayer("", ["Storm inlet S-15"])).toBe("DRAINAGE");
  });
});

async function openDemoWorkspace(page: Page) {
  await page.route("**/api/**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true }),
    });
  });
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("site-status")).toContainText("Site Locked", { timeout: 30_000 });
}

test("2D and 3D expose identical canonical footprints through repeated mode changes", async ({ page }) => {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await openDemoWorkspace(page);
  const twoDObjects = page.locator("[data-object-overlay][data-cad-object-id][data-canonical-geometry-signature]");
  await expect(twoDObjects.first()).toBeVisible();
  const twoDSignatures = await twoDObjects.evaluateAll((nodes) =>
    Object.fromEntries(
      nodes.map((node) => [
        node.getAttribute("data-cad-object-id"),
        node.getAttribute("data-canonical-geometry-signature"),
      ]),
    ),
  );

  await page.getByTestId("preview-quality-high").click();
  await page.getByTestId("preview-mode-3d").click();
  await expect(page.getByTestId("civil-3d-viewer")).toBeVisible({ timeout: 20_000 });
  const threeDObjects = page.locator(
    "[data-testid='civil-3d-object-strip'] [data-canonical-object-id][data-canonical-geometry-signature]",
  );
  expect(await threeDObjects.count()).toBeGreaterThan(6);
  const threeDSignatures = await threeDObjects.evaluateAll((nodes) =>
    Object.fromEntries(
      nodes.map((node) => [
        node.getAttribute("data-canonical-object-id"),
        node.getAttribute("data-canonical-geometry-signature"),
      ]),
    ),
  );
  const sharedIds = Object.keys(threeDSignatures).filter((id) => twoDSignatures[id]);
  expect(sharedIds.length).toBeGreaterThan(6);
  sharedIds.forEach((id) => expect(threeDSignatures[id]).toBe(twoDSignatures[id]));

  for (let index = 0; index < 5; index += 1) {
    await page.getByTestId("preview-mode-2d").click();
    await page.getByTestId(index % 2 ? "preview-quality-high" : "preview-quality-standard").click();
    await page.getByTestId("preview-mode-3d").click();
    await expect(page.getByTestId("civil-3d-viewer")).toBeVisible();
  }

  const signaturesAfterToggles = await page
    .locator("[data-testid='civil-3d-object-strip'] [data-canonical-object-id][data-canonical-geometry-signature]")
    .evaluateAll((nodes) =>
      Object.fromEntries(
        nodes.map((node) => [
          node.getAttribute("data-canonical-object-id"),
          node.getAttribute("data-canonical-geometry-signature"),
        ]),
      ),
    );
  sharedIds.forEach((id) => expect(signaturesAfterToggles[id]).toBe(twoDSignatures[id]));
  expect(new Set(Object.keys(signaturesAfterToggles)).size).toBe(Object.keys(signaturesAfterToggles).length);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  expect(pageErrors).toEqual([]);
  expect(consoleErrors.filter((message) => !message.includes("ERR_CONNECTION_REFUSED"))).toEqual([]);
});
