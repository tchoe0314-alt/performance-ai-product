import type { BuildingPlacement } from "../types";
import type { AutoSiteContextRow } from "./dashboardAutoSiteContext";
import type { AutoSiteContextFlowSummary, GenerateFlowSummary, ReviewPackageFlowSummary } from "./dashboardDataTypes";
import type { ProjectStatusSummary } from "./workspaceShell";
import type { SystemStatus } from "./workflowConstants";

export type DashboardChatPlacementFormatter = (item: BuildingPlacement) => string;

export function formatDashboardChatPlacement(item: BuildingPlacement): string {
  const dims = `${item.w} ft x ${item.d} ft`;
  const position =
    item.placed && typeof item.x === "number" && typeof item.y === "number"
      ? `@ ${Math.round(item.x)} ft, ${Math.round(item.y)} ft`
      : "unplaced";
  const lockTag = item.locked ? "locked" : "unlocked";
  return `${item.label} (${item.type ?? "building"}, ${dims}, ${position}, ${lockTag})`;
}

export function buildDashboardPreviewExplanationMessage({
  placed,
  buildingPlacements,
  selected,
  formatPlacement = formatDashboardChatPlacement,
}: {
  placed: BuildingPlacement[];
  buildingPlacements: BuildingPlacement[];
  selected: BuildingPlacement | null;
  formatPlacement?: DashboardChatPlacementFormatter;
}): string {
  const visibleObjects = placed.filter((item) => !item.meta?.ui_hidden);
  const byKind = (matcher: (item: BuildingPlacement) => boolean) => visibleObjects.filter(matcher).length;
  const lineCount = byKind((item) =>
    ["road", "driveway", "sidewalk", "utility_corridor"].includes(String(item.type)) ||
    ["line", "polyline"].includes(String(item.geometryType)),
  );
  const pointCount = byKind((item) =>
    ["hydrant", "inlet", "outfall", "manhole", "point"].includes(String(item.type)) ||
    String(item.geometryType) === "point",
  );
  const areaCount = byKind((item) =>
    ["site", "building", "office_building", "parking", "basin"].includes(String(item.type)) ||
    ["box", "rectangle", "polygon"].includes(String(item.geometryType)),
  );
  const sourcePreviewCount = visibleObjects.filter((item) =>
    ["detected_from_gis", "detected_from_image", "inferred"].includes(String(item.source)),
  ).length;
  const draftCount = visibleObjects.filter((item) =>
    ["user", "user_confirmed", "manual_drawn"].includes(String(item.source)) || item.meta?.command_created,
  ).length;
  const semanticCount = visibleObjects.filter((item) =>
    Boolean(item.meta?.semantic_object_model || item.meta?.semantic_geometry_state),
  ).length;
  const fallbackCount = visibleObjects.filter((item) =>
    Boolean(item.meta?.fallback_bounds_only || item.meta?.bounds_only || item.meta?.generated_review_concept),
  ).length;
  const hiddenTraceCount = buildingPlacements.filter((item) => item.meta?.combined_into_object_id || item.meta?.ui_hidden).length;
  const combinedCount = visibleObjects.filter((item) =>
    Array.isArray(item.meta?.combined_from_object_ids) && item.meta.combined_from_object_ids.length > 0,
  ).length;
  const selectedLine = selected
    ? `Selected now: ${formatPlacement(selected)}.`
    : "Nothing is selected; click a shape or open Object Manager to inspect one.";

  return [
    "The preview is a review canvas, so every mark should have a job:",
    `- Lines are usually roads, driveways, sidewalks, utilities, or draft linework (${lineCount} visible).`,
    `- Circles/points are usually hydrants, inlets, outfalls, manholes, or point markers (${pointCount} visible).`,
    `- Filled/outlined areas are the site, buildings, parking, basins, or drawn areas (${areaCount} visible).`,
    sourcePreviewCount ? `- ${sourcePreviewCount} item(s) came from source/context detection and are shown as review candidates.` : "",
    draftCount ? `- ${draftCount} item(s) are user/draft objects you can select, rename, hide, recolor, or delete in Object Manager.` : "",
    semanticCount ? `- ${semanticCount} item(s) are semantic objects, so Generate can understand them as buildings, parking, basins, roads, or utilities instead of anonymous lines.` : "",
    combinedCount ? `- ${combinedCount} combined object(s) are shown as one clean item; their original source pieces stay hidden until you choose Explode combined.` : "",
    fallbackCount ? `- ${fallbackCount} item(s) are fallback/bounds previews, so they are planning placeholders until better source or drawn geometry exists.` : "",
    hiddenTraceCount ? `- ${hiddenTraceCount} hidden/trace piece(s) are intentionally tucked away to keep the plan clean; Object Manager can show or explode them when needed.` : "",
    selectedLine,
    "If something looks wrong, select it and use Object Manager to rename, change type/color, combine/explode, hide it, or delete it. Civora should not leave unexplained marks on the canvas.",
  ].filter(Boolean).join("\n");
}

export function buildDashboardUsedLayoutMessage({
  userLayoutObjects,
  generateFlowSummary,
  systemsImpactedByPlacement,
  formatPlacement = formatDashboardChatPlacement,
}: {
  userLayoutObjects: BuildingPlacement[];
  generateFlowSummary: GenerateFlowSummary | null;
  systemsImpactedByPlacement: (item: BuildingPlacement) => string[];
  formatPlacement?: DashboardChatPlacementFormatter;
}): string {
  if (!userLayoutObjects.length) {
    return "I do not have placed user layout objects to use yet. Draw or add objects, place them inside the site, then run Generate. I will keep those objects as review context instead of treating them as final professional evidence.";
  }
  const semanticCount = userLayoutObjects.filter((item) =>
    Boolean(item.meta?.semantic_object_model || item.meta?.semantic_geometry_state),
  ).length;
  const geometryCount = userLayoutObjects.filter((item) => Boolean(item.geometry || item.geometryType)).length;
  const generateNotes = generateFlowSummary?.notes ?? [];
  const generateUsedLayout = generateNotes.some((note) => /User layout context used by Generate/i.test(note));
  const listedObjects = userLayoutObjects.slice(0, 12).map((item) => {
    const systemText = systemsImpactedByPlacement(item);
    return `- ${formatPlacement(item)}${systemText.length ? `; affects ${systemText.join(", ")}` : ""}`;
  });

  return [
    generateUsedLayout
      ? "Generate used these placed/drawn objects as review context:"
      : "These placed/drawn objects are ready to be used as Generate review context:",
    listedObjects.join("\n"),
    userLayoutObjects.length > listedObjects.length
      ? `- plus ${userLayoutObjects.length - listedObjects.length} more placed object(s).`
      : "",
    `${semanticCount} semantic object(s), ${geometryCount} geometry-backed object(s).`,
    "They remain editable draft/review context; they do not become survey/control or final professional evidence.",
  ].filter(Boolean).join("\n");
}

export function buildDashboardAutoSiteContextMessage(autoSiteContextRows: AutoSiteContextRow[]): string {
  const foundRows = autoSiteContextRows.filter((row) => row.status === "found");
  const missingRows = autoSiteContextRows.filter((row) => row.status === "missing");
  const assumedRows = autoSiteContextRows.filter((row) => row.status === "assumed");
  const outsideRows = autoSiteContextRows.filter((row) => row.status === "outside");
  return [
    foundRows.length
      ? `Found inside the site: ${foundRows.map((row) => `${row.title} (${row.detail})`).join("; ")}.`
      : "Found inside the site: no usable source candidates yet.",
    missingRows.length
      ? `Missing or unavailable: ${missingRows.map((row) => `${row.title} (${row.detail})`).join("; ")}.`
      : "Missing or unavailable: source evidence not available yet.",
    assumedRows.length
      ? `Assumed/inferred: ${assumedRows.map((row) => `${row.title} (${row.detail})`).join("; ")}.`
      : "",
    outsideRows.length
      ? `Outside active site: ${outsideRows.map((row) => `${row.title} (${row.detail})`).join("; ")}.`
      : "",
    "These are source-context candidates for review, not survey/control or final professional evidence.",
  ].filter(Boolean).join("\n");
}

export function buildDashboardWhatChangedMessage({
  systemStatuses,
  projectStatusSummary,
  restoreTruthLabel,
  currentProjectUpdatedAt,
  hasAppliedAddress,
  appliedAddressLabel,
  onlineSourceLookupUnavailable,
  onlineSourceLookupLabel,
  siteAddress,
  placedCount,
  pendingPlacementCount,
  hasAssumedTerrainSlope,
  hasVerifiedSurveyControl,
  generateFlowSummary,
  reviewPackageFlowSummary,
  autoSiteContextFlowSummary,
  planSheetRevisionCount,
}: {
  systemStatuses: Record<string, SystemStatus>;
  projectStatusSummary: ProjectStatusSummary;
  restoreTruthLabel: string;
  currentProjectUpdatedAt?: number | null;
  hasAppliedAddress: boolean;
  appliedAddressLabel: string;
  onlineSourceLookupUnavailable: boolean;
  onlineSourceLookupLabel: string;
  siteAddress: string;
  placedCount: number;
  pendingPlacementCount: number;
  hasAssumedTerrainSlope: boolean;
  hasVerifiedSurveyControl: boolean;
  generateFlowSummary: GenerateFlowSummary | null;
  reviewPackageFlowSummary: ReviewPackageFlowSummary | null;
  autoSiteContextFlowSummary: AutoSiteContextFlowSummary;
  planSheetRevisionCount: number;
}): string {
  const staleSystems = Object.entries(systemStatuses)
    .filter(([, status]) => status === "stale")
    .map(([system]) => system);
  const freshSystems = Object.entries(systemStatuses)
    .filter(([, status]) => status === "fresh")
    .map(([system]) => system);
  return [
    `Project status: ${projectStatusSummary.state}. ${projectStatusSummary.detail} Next: ${projectStatusSummary.nextAction}`,
    `Workspace persistence: ${restoreTruthLabel}${currentProjectUpdatedAt ? `, last saved ${new Date(currentProjectUpdatedAt * 1000).toLocaleString()}` : ""}.`,
    hasAppliedAddress
      ? `Address state: applied (${appliedAddressLabel || "coordinate context"}). ${onlineSourceLookupUnavailable ? "Address applied; online source lookup not configured/available." : onlineSourceLookupLabel}`
      : siteAddress.trim()
        ? "Address state: entered but not applied."
        : "Address state: missing.",
    `${placedCount} placed object${placedCount === 1 ? "" : "s"} and ${pendingPlacementCount} pending placement object${pendingPlacementCount === 1 ? "" : "s"}.`,
    hasAssumedTerrainSlope
      ? "Terrain slope is assumed; survey/control still needed."
      : hasVerifiedSurveyControl
        ? "Survey/control is uploaded for review."
        : "Survey/control still needed.",
    staleSystems.length ? `Changed systems needing rerun: ${staleSystems.join(", ")}.` : "No stale systems are marked from object/control edits.",
    freshSystems.length ? `Current generated systems: ${freshSystems.join(", ")}.` : "No generated systems are marked current yet.",
    generateFlowSummary
      ? `Last Generate: ran ${generateFlowSummary.ran.join(", ") || "none"}; skipped ${generateFlowSummary.skipped.join(", ") || "none"}; needs review ${generateFlowSummary.needs_review.slice(0, 3).join("; ") || "standard engineer review"}.`
      : "Generate has not recorded a run summary yet.",
    reviewPackageFlowSummary
      ? `Last Review Package: created ${reviewPackageFlowSummary.outputs_created.join(", ")}; missing ${reviewPackageFlowSummary.missing.slice(0, 3).join("; ") || "none recorded"}.`
      : "No review package summary has been made yet.",
    autoSiteContextFlowSummary.candidateCount > 0 || autoSiteContextFlowSummary.missingLabels.length
      ? `Auto Site Context: ${autoSiteContextFlowSummary.candidateCount} review candidate(s); missing ${autoSiteContextFlowSummary.missingLabels.join(", ") || "source evidence not available yet"}.`
      : "Auto Site Context has no recorded candidates yet.",
    planSheetRevisionCount ? `Sheet revisions: ${planSheetRevisionCount}.` : "No sheet revision entries recorded yet.",
  ].join("\n");
}
