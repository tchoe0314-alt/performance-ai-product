import { expect, test } from "@playwright/test";

import {
  buildPreviewMarkerVisual,
  formatPreviewSnapStep,
  resolvePreviewManipulationSnapStep,
} from "../../app/utils/previewCanvasDetail";

test("drawing zoom exposes explicit precision without changing map placement increments", () => {
  expect(resolvePreviewManipulationSnapStep(0.55, false)).toBe(5);
  expect(resolvePreviewManipulationSnapStep(1.79, false)).toBe(5);
  expect(resolvePreviewManipulationSnapStep(1.8, false)).toBe(1);
  expect(resolvePreviewManipulationSnapStep(2.99, false)).toBe(1);
  expect(resolvePreviewManipulationSnapStep(3, false)).toBe(0.5);
  expect(resolvePreviewManipulationSnapStep(4, false)).toBe(0.5);
  for (const scale of [0.55, 1, 2, 4]) {
    expect(resolvePreviewManipulationSnapStep(scale, true)).toBe(5);
  }
  expect(formatPreviewSnapStep(5)).toBe("5 ft");
  expect(formatPreviewSnapStep(0.5)).toBe("0.5 ft");
});

test("dense overview markers shrink while selected symbols stay readable", () => {
  const overview = buildPreviewMarkerVisual(0.55, false);
  const standard = buildPreviewMarkerVisual(1, false);
  const detail = buildPreviewMarkerVisual(3, false);
  const selectedOverview = buildPreviewMarkerVisual(0.55, true);

  expect(overview.radius).toBeLessThan(standard.radius);
  expect(standard.radius).toBeLessThan(detail.radius);
  expect(overview.fontSize).toBeLessThan(standard.fontSize);
  expect(selectedOverview).toEqual({ radius: 1.05, fontSize: 1.55, strokeWidth: 0.22 });
});
