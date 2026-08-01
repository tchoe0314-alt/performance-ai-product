import { expect, test, type Page } from "@playwright/test";
import { buildDashboardQuantityRows } from "../../app/utils/dashboardQuantityRows";

async function openQuantitiesPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=quantities", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Quantity takeoff", { timeout: 5_000 });
  await expect(panel).toContainText("Traceable canonical quantities");
  return panel;
}

test("Quantities panel remains reachable and keeps review export state", async ({ page }) => {
  const panel = await openQuantitiesPanel(page);

  await expect(panel).toContainText("Rows");
  await expect(panel).toContainText("Missing cost");
  await expect(panel).toContainText("Untraced");
  await expect(panel).toContainText("Deltas");
  await expect(panel.getByRole("button", { name: "Export report" })).toBeDisabled();
  await expect(panel).toContainText("Run systems to populate quantities.");
});

test("Informational quantity totals remain references instead of false cost or trace gaps", () => {
  const rows = buildDashboardQuantityRows({
    quantityTotals: {
      building_area_sf: 28_000,
      parking_area_sf: 42_000,
    },
    quantityExplain: {
      quantity_audit: {
        parking_area_sf: {
          canonical_object_ids: ["parking-1"],
          trace_complete: true,
        },
      },
    },
    costEstimate: {
      line_items: [
        {
          metric: "parking_area_sf",
          item: "Asphalt parking pavement",
          unit: "sf",
          unit_cost: 7.5,
          amount: 315_000,
          source_object_ids: ["parking-1"],
          trace_complete: true,
        },
      ],
      explain: {},
    },
  });

  const building = rows.find((row) => row.metric === "building_area_sf");
  const parking = rows.find((row) => row.metric === "parking_area_sf");

  expect(building).toMatchObject({
    status: "reference",
    costApplicable: false,
    traceRequired: false,
    traceComplete: true,
    missingCost: false,
    costItem: "Reference total",
  });
  expect(parking).toMatchObject({
    status: "review",
    costApplicable: true,
    traceRequired: true,
    traceComplete: true,
    missingCost: false,
  });
});
