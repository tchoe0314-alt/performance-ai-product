export type PreviewMarkerVisual = {
  radius: number;
  fontSize: number;
  strokeWidth: number;
};

export function resolvePreviewManipulationSnapStep(canvasScale: number, showMap: boolean) {
  if (showMap) return 5;
  if (canvasScale >= 3) return 0.5;
  if (canvasScale >= 1.8) return 1;
  return 5;
}

export function buildPreviewMarkerVisual(canvasScale: number, selected: boolean): PreviewMarkerVisual {
  if (selected) return { radius: 1.05, fontSize: 1.55, strokeWidth: 0.22 };
  if (canvasScale < 0.85) return { radius: 0.66, fontSize: 0.92, strokeWidth: 0.16 };
  if (canvasScale < 1.5) return { radius: 0.82, fontSize: 1.16, strokeWidth: 0.18 };
  return { radius: 0.94, fontSize: 1.34, strokeWidth: 0.2 };
}

export function formatPreviewSnapStep(step: number) {
  return Number.isInteger(step) ? `${step} ft` : `${step.toFixed(1)} ft`;
}
