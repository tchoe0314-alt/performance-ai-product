import { expect, test } from "@playwright/test";

import { siteBoundaryAreaAcres } from "../../app/hooks/useDashboardSiteBoundaryDrawAction";

test("concave boundary acreage follows the outline instead of its envelope", () => {
  const concaveFeet: Array<[number, number]> = [
    [0, 0],
    [100, 0],
    [100, 100],
    [50, 50],
    [0, 100],
  ];

  // Shoelace area is 7,500 sf; the bounding box is 10,000 sf.
  expect(siteBoundaryAreaAcres(concaveFeet, "ft")).toBeCloseTo(7_500 / 43_560, 10);
  expect(siteBoundaryAreaAcres(concaveFeet, "ft")).not.toBeCloseTo(10_000 / 43_560, 5);
});

test("metric boundary acreage uses the same outline calculation", () => {
  const rectangleMetres: Array<[number, number]> = [
    [0, 0],
    [100, 0],
    [100, 40],
    [0, 40],
  ];

  expect(siteBoundaryAreaAcres(rectangleMetres, "m")).toBeCloseTo(4_000 / 4046.8564224, 10);
});
