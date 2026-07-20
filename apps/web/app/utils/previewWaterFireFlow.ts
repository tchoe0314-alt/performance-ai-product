import type { BuildingPlacement, PreviewResponse } from "../types";
import {
  normalizeFlowStatus,
  readMetaNumber,
  toFiniteNumber,
} from "./previewGeometryTruth";
import type {
  FireScenarioView,
  WaterHydrantView,
  WaterNetworkSegmentView,
  WaterPressureZoneView,
} from "../components/previewPanelTypes";

type WaterFireFlowAnnotations = NonNullable<PreviewResponse["preview_annotations"]>["water_fire_flow"];

export function buildWaterFireFlowViewModel({
  annotations,
  buildingPlacements,
  suggestedPlacements,
  selectedFireScenarioId,
}: {
  annotations: WaterFireFlowAnnotations | undefined;
  buildingPlacements: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  selectedFireScenarioId: string | null;
}) {
  const placedObjects = [...buildingPlacements, ...suggestedPlacements].filter(
    (item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y),
  );
  const annotationZones: WaterPressureZoneView[] = (annotations?.pressure_zones ?? [])
    .map((zone, idx) => {
      const geometry = Array.isArray(zone.geometry) ? zone.geometry : [];
      return {
        id: zone.id || `pressure-zone-${idx + 1}`,
        label: zone.label || `Pressure Zone ${idx + 1}`,
        minPressurePsi: toFiniteNumber(zone.min_pressure_psi),
        maxPressurePsi: toFiniteNumber(zone.max_pressure_psi),
        residualTargetPsi: toFiniteNumber(zone.residual_target_psi) ?? 20,
        color: zone.color || (idx % 2 === 0 ? "#0ea5e9" : "#14b8a6"),
        geometry,
      };
    });
  const pressureZones = annotationZones;
  const defaultZone = pressureZones[0];
  const annotatedHydrants: WaterHydrantView[] = (annotations?.hydrants ?? [])
    .map((hydrant, idx) => {
      const staticPressurePsi = toFiniteNumber(hydrant.static_pressure_psi);
      const availableFlowGpm = toFiniteNumber(hydrant.available_flow_gpm);
      const residualPressurePsi = toFiniteNumber(hydrant.residual_pressure_psi);
      const row: WaterHydrantView = {
        id: hydrant.id || `hydrant-ann-${idx + 1}`,
        label: hydrant.label || `H-${idx + 1}`,
        x: toFiniteNumber(hydrant.x) ?? 0,
        y: toFiniteNumber(hydrant.y) ?? 0,
        zoneId: hydrant.zone_id || defaultZone?.id || "zone-a",
        staticPressurePsi,
        residualPressurePsi,
        availableFlowGpm,
        status: normalizeFlowStatus(hydrant.status),
        source: "annotation" as const,
      };
      return row;
    })
    .filter((hydrant) => Number.isFinite(hydrant.x) && Number.isFinite(hydrant.y));
  const canonicalHydrants: WaterHydrantView[] = placedObjects
    .filter((item) => item.type === "hydrant" || String(item.label || "").toLowerCase().includes("hydrant"))
    .map((item, idx) => {
      const meta = item.meta as Record<string, unknown> | undefined;
      const staticPressurePsi = readMetaNumber(meta, ["static_pressure_psi", "pressure_psi", "staticPressurePsi"]);
      const residualPressurePsi = readMetaNumber(meta, ["residual_pressure_psi", "residualPressurePsi"]);
      const availableFlowGpm = readMetaNumber(meta, ["available_flow_gpm", "flow_gpm", "availableFlowGpm"]);
      return {
        id: item.id || `hydrant-${idx + 1}`,
        label: item.label || `H-${idx + 1}`,
        x: (item.x ?? 0) + item.w / 2,
        y: (item.y ?? 0) + item.d / 2,
        zoneId: String(meta?.zone_id || meta?.pressure_zone_id || defaultZone?.id || "zone-a"),
        staticPressurePsi,
        residualPressurePsi,
        availableFlowGpm,
        status: normalizeFlowStatus(meta?.status),
        source: "canonical" as const,
      };
    });
  const hydrantsById = new Map<string, WaterHydrantView>();
  [...annotatedHydrants, ...canonicalHydrants].forEach((hydrant) => {
    if (!hydrantsById.has(hydrant.id)) hydrantsById.set(hydrant.id, hydrant);
  });
  const hydrants = Array.from(hydrantsById.values());
  const waterLineObjects = placedObjects.filter((item) => {
    const label = String(item.label || "").toLowerCase();
    const meta = item.meta as Record<string, unknown> | undefined;
    const system = String(meta?.system || meta?.discipline || "").toLowerCase();
    return (
      item.type === "utility_corridor" ||
      label.includes("water") ||
      label.includes("main") ||
      label.includes("fire") ||
      system.includes("water")
    );
  });
  const annotatedSegments: WaterNetworkSegmentView[] = (annotations?.network_segments ?? [])
    .map((segment, idx) => ({
      id: segment.id || `water-segment-ann-${idx + 1}`,
      label: segment.label || `W-${idx + 1}`,
      fromHydrantId: segment.from_hydrant_id,
      toHydrantId: segment.to_hydrant_id,
      fromNode: segment.from_node,
      toNode: segment.to_node,
      networkType: String(segment.network_type || "").toLowerCase().includes("dead") ? "dead_end" : "loop",
      diameterIn: toFiniteNumber(segment.diameter_in),
      lengthFt: toFiniteNumber(segment.length_ft),
      flowGpm: toFiniteNumber(segment.flow_gpm),
      velocityFps: toFiniteNumber(segment.velocity_fps),
      startPressurePsi: toFiniteNumber(segment.start_pressure_psi),
      endPressurePsi: toFiniteNumber(segment.end_pressure_psi),
      status: normalizeFlowStatus(segment.status),
      geometry: Array.isArray(segment.geometry) ? segment.geometry : [],
    }));
  const objectSegments: WaterNetworkSegmentView[] = waterLineObjects
    .filter((item) => item.geometryType === "polyline" && Array.isArray(item.geometry) && item.geometry.length > 1)
    .map((item, idx) => {
      const meta = item.meta as Record<string, unknown> | undefined;
      const geometry = item.geometry ?? [];
      const first = geometry[0];
      const last = geometry[geometry.length - 1];
      const closed = Boolean(first && last && Math.hypot(first[0] - last[0], first[1] - last[1]) < 5);
      return {
        id: item.id || `water-segment-${idx + 1}`,
        label: item.label || `Water Main ${idx + 1}`,
        networkType: closed ? "loop" : "dead_end",
        diameterIn: readMetaNumber(meta, ["diameter_in", "diameterIn"]),
        lengthFt: readMetaNumber(meta, ["length_ft", "lengthFt"]),
        flowGpm: readMetaNumber(meta, ["flow_gpm", "flowGpm"]),
        velocityFps: readMetaNumber(meta, ["velocity_fps", "velocityFps"]),
        startPressurePsi: readMetaNumber(meta, ["start_pressure_psi", "startPressurePsi"]),
        endPressurePsi: readMetaNumber(meta, ["end_pressure_psi", "endPressurePsi"]),
        status: normalizeFlowStatus(meta?.status),
        geometry,
      };
    });
  const networkSegments = [...annotatedSegments, ...objectSegments];
  const zoneById = new Map(pressureZones.map((zone) => [zone.id, zone]));
  const networkByHydrant = new Map<string, "loop" | "dead_end">();
  networkSegments.forEach((segment) => {
    if (segment.fromHydrantId) networkByHydrant.set(segment.fromHydrantId, segment.networkType);
    if (segment.toHydrantId) networkByHydrant.set(segment.toHydrantId, segment.networkType);
  });
  const annotatedScenarios: FireScenarioView[] = (annotations?.scenario_runs ?? [])
    .map((scenario, idx) => {
      const hydrant = hydrants.find((item) => item.id === scenario.hydrant_id) ?? hydrants[idx] ?? hydrants[0];
      const zone = hydrant ? zoneById.get(hydrant.zoneId) : defaultZone;
      const requiredFlowGpm = toFiniteNumber(scenario.required_flow_gpm);
      const availableFlowGpm = toFiniteNumber(scenario.available_flow_gpm) ?? hydrant?.availableFlowGpm ?? null;
      const staticPressurePsi = toFiniteNumber(scenario.static_pressure_psi) ?? hydrant?.staticPressurePsi ?? null;
      const residualTargetPsi = toFiniteNumber(scenario.residual_target_psi) ?? zone?.residualTargetPsi ?? null;
      const residualPressurePsi = toFiniteNumber(scenario.residual_pressure_psi) ?? hydrant?.residualPressurePsi ?? null;
      return {
        id: scenario.id || `fire-flow-${idx + 1}`,
        label: scenario.label || `${hydrant?.label || "Hydrant"} fire-flow`,
        hydrantId: hydrant?.id || scenario.hydrant_id || "",
        requiredFlowGpm,
        availableFlowGpm,
        staticPressurePsi,
        residualPressurePsi,
        residualTargetPsi,
        status: normalizeFlowStatus(scenario.status),
        networkType: hydrant ? networkByHydrant.get(hydrant.id) ?? "dead_end" : "dead_end",
        missingInputs: Array.isArray(scenario.missing_inputs) ? scenario.missing_inputs : [],
      };
    });
  const scenarios = annotatedScenarios;
  const selectedScenario =
    scenarios.find((scenario) => scenario.id === selectedFireScenarioId) ?? scenarios[0] ?? null;
  const selectedHydrant = selectedScenario
    ? hydrants.find((hydrant) => hydrant.id === selectedScenario.hydrantId) ?? null
    : null;
  const readiness = annotations?.readiness ?? null;
  const spacingChecks = annotations?.spacing_checks ?? [];
  const velocityChecks = annotations?.velocity_checks ?? [];
  const blockerCards = annotations?.blocker_cards ?? [];
  const hasData =
    hydrants.length > 0 ||
    networkSegments.length > 0 ||
    pressureZones.length > 0 ||
    scenarios.length > 0 ||
    spacingChecks.length > 0 ||
    velocityChecks.length > 0 ||
    blockerCards.length > 0 ||
    Boolean(readiness);
  return { hydrants, pressureZones, networkSegments, scenarios, selectedScenario, selectedHydrant, spacingChecks, velocityChecks, blockerCards, readiness, hasData };
}
