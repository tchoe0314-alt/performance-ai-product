import type { BuildingPlacement } from "../types";

export type DashboardExistingConditionRow = {
  label: string;
  value: string;
  status: "review" | "block";
  action: string;
};

export type DashboardConfirmedObjectCounts = {
  buildings: number;
  access: number;
};

const BUILDING_TYPES = new Set(["building", "retail_building", "multifamily_building", "industrial_building", "office_building", "pad"]);
const ACCESS_TYPES = new Set(["road", "entrance", "parking", "sidewalk", "driveway"]);

export function buildDashboardConfirmedObjectCounts(buildingPlacements: BuildingPlacement[]): DashboardConfirmedObjectCounts {
  const confirmed = buildingPlacements.filter(
    (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
  );
  return {
    buildings: confirmed.filter((item) => BUILDING_TYPES.has(String(item.type))).length,
    access: confirmed.filter((item) => ACCESS_TYPES.has(String(item.type))).length,
  };
}

export function buildDashboardExistingConditionRows({
  hasAppliedAddress,
  appliedAddressLabel,
  hasLocationEvidence,
  hasVerifiedSurveyControl,
  coordinateSystem,
  hasTerrainSource,
  mapAnalysisSuccess,
  uploadedImageApiUrl,
  uploadedImagePreviewUrl,
  onlineSourceLookupLabel,
}: {
  hasAppliedAddress: boolean;
  appliedAddressLabel: string;
  hasLocationEvidence: boolean;
  hasVerifiedSurveyControl: boolean;
  coordinateSystem: string;
  hasTerrainSource: boolean;
  mapAnalysisSuccess: boolean;
  uploadedImageApiUrl: string;
  uploadedImagePreviewUrl: string;
  onlineSourceLookupLabel: string;
}): DashboardExistingConditionRow[] {
  return [
    {
      label: "Address / location evidence",
      value: hasAppliedAddress
        ? `Applied: ${appliedAddressLabel || "coordinate context"}`
        : hasLocationEvidence
          ? "Map/image location context"
          : "Missing",
      status: hasLocationEvidence ? "review" : "block",
      action: "Setup panel -> enter an address, pick a geocode suggestion, then Apply address.",
    },
    {
      label: "Survey / control",
      value: hasVerifiedSurveyControl ? "Uploaded / verify control" : "Missing verified control",
      status: hasVerifiedSurveyControl ? "review" : "block",
      action: "Import & Survey panel -> upload survey/topo/control evidence.",
    },
    {
      label: "Datum / CRS",
      value: coordinateSystem || "Missing",
      status: coordinateSystem ? "review" : "block",
      action: "Data panel -> add coordinate system/datum evidence when available.",
    },
    {
      label: "Terrain",
      value: hasTerrainSource ? "Available for review" : "Missing survey, DEM, or assumed slope",
      status: hasTerrainSource ? "review" : "block",
      action: "Import & Survey panel -> upload terrain, apply geocoded map terrain, or choose assumed slope when prompted.",
    },
    {
      label: "GIS / map context",
      value: mapAnalysisSuccess ? "Analyzed" : uploadedImageApiUrl || uploadedImagePreviewUrl ? "Image uploaded" : onlineSourceLookupLabel,
      status: mapAnalysisSuccess || uploadedImageApiUrl || uploadedImagePreviewUrl || hasAppliedAddress ? "review" : "block",
      action: "Setup panel -> upload a map snapshot and run Analyze map snapshot.",
    },
  ];
}

export function buildDashboardSourceHubMetrics({
  coordinateSystem,
  hasTerrainSource,
  mapAnalysisSuccess,
  lowConfidenceCount,
  needsSurveyControlCount,
  staleOrMissingCount,
}: {
  coordinateSystem: string;
  hasTerrainSource: boolean;
  mapAnalysisSuccess: boolean;
  lowConfidenceCount: number;
  needsSurveyControlCount: number;
  staleOrMissingCount: number;
}): Array<[string, string | number]> {
  return [
    ["CRS / datum", coordinateSystem || "Not set"],
    ["Terrain", hasTerrainSource ? "Provided" : "Missing"],
    ["GIS", mapAnalysisSuccess ? "Analyzed" : "Not analyzed"],
    ["Low confidence", lowConfidenceCount],
    ["Need control", needsSurveyControlCount],
    ["Stale/missing", staleOrMissingCount],
  ];
}
