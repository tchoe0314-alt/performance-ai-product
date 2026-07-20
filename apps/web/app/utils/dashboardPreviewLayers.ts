export type PreviewLayerToggles = {
  buildings: boolean;
  roads: boolean;
  grading: boolean;
  drainage: boolean;
  utilities: boolean;
  structures: boolean;
  lots: boolean;
};

export function applyPreviewLayerGating(
  previewLayers: PreviewLayerToggles,
  gatingPhaseKey?: string | null,
): PreviewLayerToggles {
  if (!gatingPhaseKey) return previewLayers;
  switch (gatingPhaseKey) {
    case "layout":
      return { ...previewLayers, grading: false, drainage: false, utilities: false };
    case "grading":
      return { ...previewLayers, drainage: false, utilities: false };
    case "drainage_storm":
      return { ...previewLayers, grading: false, utilities: false };
    case "utilities":
      return { ...previewLayers, grading: false, drainage: false };
    default:
      return previewLayers;
  }
}

export function buildPreviewLayerList(previewLayersEffective: PreviewLayerToggles) {
  const layers = new Set<string>();
  if (previewLayersEffective.buildings) {
    [
      "BUILDING",
      "STRUCTURE",
      "PAD",
      "C-BUILDING",
      "C-BOUNDARY",
      "C-SETBACK",
    ].forEach((layer) => layers.add(layer));
  }
  if (previewLayersEffective.roads) {
    [
      "ROAD",
      "PAVEMENT",
      "PARKING",
      "WALK",
      "C-ROAD",
      "C-PAVEMENT",
      "C-PARKING",
      "C-DRIVEWAY",
      "C-SIDEWALK",
      "C-CENTERLINE",
    ].forEach((layer) => layers.add(layer));
  }
  if (previewLayersEffective.grading) {
    [
      "SURFACE",
      "FG_CONTOUR",
      "EG_CONTOUR",
      "SPOT_FG",
      "DRAIN_FLOW",
      "FLOW_ARROW",
      "C-CONTOUR",
      "C-SPOT-ELEV",
      "C-GRADING",
      "C-CUT",
      "C-FILL",
    ].forEach((layer) => layers.add(layer));
  }
  if (previewLayersEffective.drainage) {
    [
      "DRAIN",
      "PIPE",
      "STORM",
      "BASIN_BOUNDARY",
      "C-STRM-PIPE",
      "C-STRM-INLET",
      "C-STRM-MH",
      "C-DRAIN-FLOW",
      "C-LOW-POINT",
      "C-POND",
    ].forEach((layer) => layers.add(layer));
  }
  if (previewLayersEffective.utilities) {
    ["UTILITY", "WATER", "SAN", "C-WATR", "C-SAN", "C-UTIL", "C-HYDRANT"].forEach((layer) =>
      layers.add(layer),
    );
  }
  if (previewLayersEffective.structures) {
    ["BRIDGE", "POOL", "STRUCTURE"].forEach((layer) => layers.add(layer));
  }
  if (previewLayersEffective.lots) {
    ["LOT", "OPEN_SPACE", "EASEMENT"].forEach((layer) => layers.add(layer));
  }
  return Array.from(layers);
}
