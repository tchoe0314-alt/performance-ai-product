import type { UploadExistingConditionsResponse } from "../types";

export function buildImportedSurveyProvenance(data: UploadExistingConditionsResponse) {
  const canonical = data.canonical_existing_conditions ?? {};
  const coordinateSystem = canonical.coordinate_system && typeof canonical.coordinate_system === "object"
    ? canonical.coordinate_system as Record<string, unknown>
    : {};
  const controlPackage = canonical.survey_control_package && typeof canonical.survey_control_package === "object"
    ? canonical.survey_control_package as Record<string, unknown>
    : {};
  const eligibility = canonical.grading_input_eligibility && typeof canonical.grading_input_eligibility === "object"
    ? canonical.grading_input_eligibility as Record<string, unknown>
    : {};
  return {
    survey_coordinate_system: coordinateSystem,
    survey_control_package: controlPackage,
    survey_grading_eligibility: {
      review_context_usable: eligibility.review_context_usable === true,
      accepted_grading_input: eligibility.accepted_grading_input === true,
      coordinate_units: typeof eligibility.coordinate_units === "string" ? eligibility.coordinate_units : null,
      horizontal_datum: typeof eligibility.horizontal_datum === "string" ? eligibility.horizontal_datum : null,
      vertical_datum: typeof eligibility.vertical_datum === "string" ? eligibility.vertical_datum : null,
      control_verified: eligibility.control_verified === true,
      blockers: Array.isArray(eligibility.blockers) ? eligibility.blockers as Array<Record<string, unknown>> : [],
      truth_label: typeof eligibility.truth_label === "string" ? eligibility.truth_label : "Imported survey/control acceptance is not established.",
    },
  };
}

export function mapSurveyPointsToSite(
  points: number[][],
  width: number | null | undefined,
  height: number | null | undefined,
) {
  if (!points.length || !width || !height) return [];
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 1e-6);
  const spanY = Math.max(maxY - minY, 1e-6);
  const withinLot = minX >= 0 && minY >= 0 && maxX <= width * 1.2 && maxY <= height * 1.2;
  const mapped = points.map((p) => {
    const x = withinLot ? p[0] : ((p[0] - minX) / spanX) * width;
    const y = withinLot ? p[1] : ((p[1] - minY) / spanY) * height;
    const z = typeof p[2] === "number" ? p[2] : undefined;
    return { x, y, z };
  });
  const step = Math.max(1, Math.ceil(mapped.length / 2000));
  return mapped.filter((_, idx) => idx % step === 0);
}

export function summarizeExistingConditionsUpload(data: UploadExistingConditionsResponse) {
  const matrix = data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix ?? [];
  const countByStatus = (status: string) => matrix.filter((item) => item.status === status).length;
  const canonical = countByStatus("canonical");
  const reviewRequired = countByStatus("review_required");
  const metadataOnly = countByStatus("metadata_only");
  const blocked = countByStatus("blocked");
  const confidence = String(
    data.import_validation?.terrain_source_confidence?.label ??
      ((data.existing_conditions_package?.terrain_source_confidence as Record<string, unknown> | undefined)?.label) ??
      "missing",
  );
  const blockerMessages = matrix
    .flatMap((item) => item.blocker_messages ?? [])
    .concat((data.blockers ?? []).map((item) => String(item.reason || item.message || item.field || "")))
    .filter((item, index, items) => item && items.indexOf(item) === index)
    .slice(0, 5);
  const targets = matrix
    .flatMap((item) => item.canonical_targets ?? [])
    .filter((item, index, items) => item && items.indexOf(item) === index);
  return [
    `Existing-condition import: ${data.filename ?? "file"} (${data.file_type ?? "unknown"}).`,
    `Matrix: canonical ${canonical}, review-required ${reviewRequired}, metadata-only ${metadataOnly}, blocked ${blocked}.`,
    `Terrain confidence: ${confidence}. Canonical targets: ${targets.length ? targets.join(", ") : "none"}.`,
    blockerMessages.length ? `Exact blockers:\n${blockerMessages.map((item) => `- ${item}`).join("\n")}` : "Exact blockers: none recorded.",
  ].join("\n");
}

function labelForTarget(target: string) {
  const normalized = target.replace(/_/g, " ").toLowerCase();
  if (target === "survey_points") return "Survey/control points";
  if (target === "terrain_surface" || target === "dem_surface") return "Terrain surface";
  if (target === "lidar_point_cloud" || target === "terrain_evidence") return "LiDAR / point-cloud terrain evidence";
  if (target === "terrain_surface_metadata") return "Surface metadata";
  if (target === "pipe_network_metadata") return "Pipe-network metadata";
  if (target === "gis_layers") return "GIS/context layers";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function labelForFileType(fileType: string) {
  const normalized = fileType.toLowerCase();
  if (normalized === "csv") return "CSV survey/topo";
  if (normalized === "tif" || normalized === "tiff" || normalized === "geotiff") return "GeoTIFF terrain";
  if (normalized === "las" || normalized === "laz") return "LAS/LiDAR point cloud";
  if (normalized === "landxml" || normalized === "xml") return "LandXML exchange";
  if (normalized === "geojson" || normalized === "json") return "GeoJSON/GIS context";
  if (normalized === "dxf") return "DXF source drawing";
  return `${fileType.toUpperCase()} source`;
}

export function buildExistingConditionsSourceEffects(data: UploadExistingConditionsResponse) {
  const matrix = data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix ?? [];
  const targets = matrix
    .flatMap((item) => item.canonical_targets ?? [])
    .filter((item, index, items) => item && items.indexOf(item) === index);
  const blockedMessages = matrix
    .flatMap((item) => item.blocker_messages ?? [])
    .concat((data.blockers ?? []).map((item) => String(item.reason || item.message || item.field || "")))
    .filter((item, index, items) => item && items.indexOf(item) === index)
    .slice(0, 2);
  const fileType = String(data.file_type || "source");
  const sourceLabel = labelForFileType(fileType);
  const rows = [
    `${sourceLabel}: ${data.success ? "imported as review source evidence" : "stored, but not usable as source evidence yet"}.`,
    targets.length
      ? `Affects: ${targets.map(labelForTarget).join(", ")}.`
      : "Affects: no canonical model targets yet.",
    "Does not replace survey control, professional review, or construction documents.",
  ];
  if (blockedMessages.length) {
    rows.push(`Needs review: ${blockedMessages.join(" ")}`);
  }
  return rows;
}
