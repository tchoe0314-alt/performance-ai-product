import { expect, test, type Page } from "@playwright/test";
import { buildDashboardQuantityRows } from "../../app/utils/dashboardQuantityRows";
import { QuantitiesPanel } from "../../app/components/QuantitiesPanel";
import { quantityConstructionTakeoffForReport } from "../../app/utils/dashboardExportActions";

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
  await page.goto("/demo/workspace?debugPreview=1&seedDemo=1&debugPanel=quantities", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("workspace-canvas-shell")).toBeVisible({ timeout: 30_000 });
  const panel = page.getByTestId("workspace-right-panel");
  if (!(await panel.getByText("Quantity takeoff", { exact: true }).count())) {
    await page.getByTestId("workspace-stage-analyze").click();
    await page.getByTestId("workspace-stage-panel").selectOption("quantities");
  }
  await expect(panel).toContainText("Quantity takeoff", { timeout: 5_000 });
  await expect(panel.getByTestId("quantity-calculation-source")).toContainText("Previous calculation. Recalculate for current totals.");
  return panel;
}

test("Quantities panel remains reachable and keeps review export state", async ({ page }) => {
  const panel = await openQuantitiesPanel(page);

  await expect(panel).toContainText("Rows");
  await expect(panel).toContainText("Missing cost");
  await expect(panel).toContainText("Untraced");
  await expect(panel).toContainText("Deltas");
  await expect(panel.getByTestId("construction-takeoff-breakdown")).toContainText("Earthwork cut");
  await expect(panel.getByTestId("construction-takeoff-breakdown")).toContainText("100.0 cy");
  await expect(panel.getByTestId("construction-takeoff-breakdown")).toContainText("Earthwork fill");
  await expect(panel.getByTestId("construction-takeoff-breakdown")).toContainText("50.0 cy");
  await expect(panel.getByTestId("construction-takeoff-breakdown")).toContainText("centerline_horizontal");
  await expect(panel.getByTestId("construction-takeoff-breakdown")).toContainText("structure_face_to_face_horizontal");
  await expect(panel.getByTestId("construction-takeoff-breakdown")).toContainText("storm · inlet: 2");
  await expect(panel.getByRole("button", { name: "Export report" })).toBeDisabled();
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

test("construction breakdown renders explicit bases and is preserved in the review report", () => {
  const constructionTakeoff = {
    earthwork: { cut_cy: 100, fill_cy: 50, haul_quantity_inferred: false },
    pipes_by_system_and_diameter: [
      { system: "storm", diameter_in: 18, measurement_basis: "centerline_horizontal", horizontal_length_ft: 50, three_dimensional_length_ft: 50.16, source_object_ids: ["STM-1"] },
      { system: "storm", diameter_in: 18, measurement_basis: "structure_face_to_face_horizontal", horizontal_length_ft: 40, three_dimensional_length_ft: null, source_object_ids: ["STM-2"] },
      { system: "sanitary", diameter_in: 18, measurement_basis: "centerline_horizontal", horizontal_length_ft: 70, three_dimensional_length_ft: null, source_object_ids: ["SAN-1"] },
    ],
    structures_by_system_and_type: [
      { system: "storm", structure_type: "manhole", count: 1, source_object_ids: ["MH-1"] },
    ],
  };
  const rendered = JSON.stringify(QuantitiesPanel({
    rows: [],
    staleSystemCount: 0,
    trustScoreLabel: "Ready",
    onExportReport: () => {},
    formatMetric: (value, unit) => `${value ?? "Pending"} ${unit}`,
    statusLabelForQuantityReview: (status) => status,
    constructionTakeoff,
  }));
  expect(rendered).toContain("Construction breakdown");
  expect(rendered).toContain("Earthwork cut");
  expect(rendered).toContain("100 cy");
  expect(rendered).toContain("Earthwork fill");
  expect(rendered).toContain("50 cy");
  expect(rendered).toContain("centerline_horizontal");
  expect(rendered).toContain("structure_face_to_face_horizontal");
  expect(rendered).toContain("Haul quantity: not inferred");
  expect(rendered).toContain("Missing — no group rate applied");
  expect(rendered).toContain("Distinct structures");
  expect(rendered).toContain("manhole");

  expect(quantityConstructionTakeoffForReport({ quantities: { tables: { construction_takeoff: constructionTakeoff } } })).toEqual(constructionTakeoff);
  expect(quantityConstructionTakeoffForReport({})).toBeNull();
});

test("missing construction evidence renders pending instead of zero", () => {
  const rendered = JSON.stringify(QuantitiesPanel({
    rows: [], staleSystemCount: 0, trustScoreLabel: "Ready", onExportReport: () => {},
    formatMetric: (value, unit) => value == null ? "Pending" : `${value} ${unit}`,
    statusLabelForQuantityReview: (status) => status,
    constructionTakeoff: { earthwork: { cut_cy: null, fill_cy: null, unit: "cy", status: "missing", haul_quantity_inferred: false } },
  }));
  expect(rendered).toContain("Earthwork cut");
  expect(rendered).toContain("Earthwork fill");
  expect(rendered).toContain("Pending");
  expect(rendered).not.toContain("0 cy");
});
