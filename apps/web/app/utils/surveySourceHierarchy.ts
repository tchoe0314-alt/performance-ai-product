export type SurveySourceTier = {
  id: string;
  rank: number;
  title: string;
  examples: string;
  use: string;
  confidence: string;
};

export const SURVEY_SOURCE_HIERARCHY: SurveySourceTier[] = [
  {
    id: "professional-survey-control",
    rank: 1,
    title: "Professional survey / control",
    examples: "Boundary, topo, ALTA/NSPS, benchmark, datum, CRS, control points",
    use: "Best source for boundary and terrain reliance.",
    confidence: "Highest, when metadata and control are present.",
  },
  {
    id: "civil-cad-landxml-points",
    rank: 2,
    title: "Civil CAD / LandXML / point files",
    examples: "DXF, LandXML surface, CSV/TXT/NEZ/PNEZD points, breaklines",
    use: "Best machine-readable geometry when it came from survey/design files.",
    confidence: "High review value; still needs source/control verification.",
  },
  {
    id: "lidar-dem-geotiff",
    rank: 3,
    title: "LiDAR / DEM / GeoTIFF terrain",
    examples: "LAS/LAZ point cloud, GeoTIFF, raster DEM, public elevation grids",
    use: "Good terrain context when survey topo is missing.",
    confidence: "Terrain review context unless tied to accepted control.",
  },
  {
    id: "utility-records-asbuilts",
    rank: 4,
    title: "Utility records / as-builts",
    examples: "City utility maps, record drawings, private locate notes",
    use: "Better utility context than generic GIS layers.",
    confidence: "Review context until field-located or owner-verified.",
  },
  {
    id: "gis-public-context",
    rank: 5,
    title: "GIS / parcel / public context",
    examples: "Parcels, ROW, roads, buildings, floodplain, wetlands, public contours",
    use: "Fast starter layer for early planning.",
    confidence: "Candidate context only, not survey/control.",
  },
];

export function bestSurveySourceLabel(options: {
  surveyFileName?: string | null;
  surveyPreviewPointCount?: number;
  hasTerrainSource?: boolean;
  uploadedImagePreviewUrl?: string | null;
  uploadedImageApiUrl?: string | null;
}) {
  const surveyFileName = String(options.surveyFileName || "").toLowerCase();
  const surveyPointCount = Number(options.surveyPreviewPointCount || 0);
  if (surveyPointCount > 0) return "Best source: uploaded survey/control points";
  if (/\.(dxf|xml|landxml|csv|txt|nez|pnezd)$/i.test(surveyFileName)) {
    return "Best source: uploaded CAD/surface/point file for review";
  }
  if (/\.(las|laz|tif|tiff)$/i.test(surveyFileName) || options.hasTerrainSource) {
    return "Best source: terrain/LiDAR/DEM context for review";
  }
  if (options.uploadedImagePreviewUrl || options.uploadedImageApiUrl) {
    return "Best source: uploaded image/map snapshot for visual review";
  }
  return "Best source: none yet; start with survey/topo/CAD if available";
}
