import { expect, test, type Page } from "@playwright/test";
import { buildDashboardQuantityRows } from "../../app/utils/dashboardQuantityRows";
import { QuantitiesPanel } from "../../app/components/QuantitiesPanel";

test("previous quantity totals are labelled and cannot be downloaded as current", () => {
  const rows = buildDashboardQuantityRows({ quantityTotals: { building_area_sf: 1200 }, quantityExplain: {}, costEstimate: { explain: {} } });
  const props = { rows, staleSystemCount: 0, trustScoreLabel: "Ready", onExportReport: () => {},
    formatMetric: (value: number | null, unit: string) => `${value} ${unit}`,
    statusLabelForQuantityReview: (status: string) => status, calculationReference: "calculation-1" };
  // Playwright represents imported JSX as a component tree, not React DOM.
  const previous = JSON.stringify(QuantitiesPanel({ ...props, outdated: true }));
  expect(previous).toContain("Out of date");
  expect(previous).toContain("Previous calculation. Recalculate for current totals.");
  expect(previous).toContain('"disabled":true');
  expect(previous).toContain("1200");
  const current = JSON.stringify(QuantitiesPanel(props));
  expect(current).toContain("Calculation: calculation-1");
  expect(current).toContain('"disabled":false');
});

async function openQuantitiesPanel(page: Page) {
  await page.goto("/demo/workspace?debugPreview=1&debugPanel=quantities", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  await expect(panel).toContainText("Quantity takeoff", { timeout: 5_000 });
  await expect(panel.getByTestId("quantity-calculation-source")).toContainText("Calculation version unverified.");
  return panel;
}

test("Quantities panel remains reachable and keeps review export state", async ({ page }) => {
  const panel = await openQuantitiesPanel(page);

  await expect(panel).toContainText("Rows");
  await expect(panel).toContainText("Missing cost");
  await expect(panel).toContainText("Untraced");
  await expect(panel).toContainText("Deltas");
  await expect(panel.getByRole("button", { name: "Export report" })).toBeDisabled();
  await expect(panel).toContainText("No traceable quantity result was produced.");
  await expect(panel).toContainText("Review generation inputs and run the required systems again.");
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
