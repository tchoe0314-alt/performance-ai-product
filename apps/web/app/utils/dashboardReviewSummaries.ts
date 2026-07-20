import type {
  DetentionRoutingPoint,
  InletSpreadCheck,
  OverflowPathCheck,
  PipeSegment,
  PreviewResponse,
  SmartFixRecommendation,
  StormBlockerFix,
  StormProfilePoint,
  StormSummary,
  WaterFireFlowAnnotations,
} from "../types";

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : {};

const asArray = <T,>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : []);

const numberOrNull = (value: unknown) => {
  const next = typeof value === "number" ? value : Number(value);
  return Number.isFinite(next) ? next : null;
};

const firstNumber = (...values: unknown[]) => {
  for (const value of values) {
    const next = numberOrNull(value);
    if (next !== null) return next;
  }
  return null;
};

const text = (value: unknown, fallback = "") => {
  const next = String(value ?? "").trim();
  return next || fallback;
};

const normalizePath = (value: unknown) =>
  asArray<unknown>(value)
    .map((pt) => {
      if (Array.isArray(pt) && pt.length >= 2) {
        const x = numberOrNull(pt[0]);
        const y = numberOrNull(pt[1]);
        return x !== null && y !== null ? { x, y } : null;
      }
      const rec = asRecord(pt);
      const x = numberOrNull(rec.x);
      const y = numberOrNull(rec.y);
      return x !== null && y !== null ? { x, y } : null;
    })
    .filter((pt): pt is { x: number; y: number } => Boolean(pt));

export const buildStormPipeSegments = (stormSummary: StormSummary): PipeSegment[] => {
  const segments =
    stormSummary?.segments ||
    stormSummary?.pipe_segments ||
    stormSummary?.storm_pipe_segments ||
    [];
  return Array.isArray(segments) ? segments : [];
};

export const buildDrainageLowPoints = ({
  drainageSummary,
  gradingSummary,
}: {
  drainageSummary: Record<string, unknown>;
  gradingSummary: Record<string, unknown>;
}) => {
  const fromDrainage = Array.isArray(drainageSummary?.low_points)
    ? (drainageSummary.low_points as Array<Record<string, unknown>>)
    : [];
  const fromGrading = Array.isArray(gradingSummary?.low_points)
    ? (gradingSummary.low_points as Array<Record<string, unknown>>)
    : [];
  const candidates = fromDrainage.length ? fromDrainage : fromGrading;
  return candidates
    .map((item) => ({
      x: typeof item.x === "number" ? item.x : Number(item.x),
      y: typeof item.y === "number" ? item.y : Number(item.y),
      z: typeof item.z === "number" ? item.z : Number(item.z),
    }))
    .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
};

export const buildStormHydrologyReview = ({
  stormSummary,
  drainageSummary,
  pipeSegments,
  smartFixItems,
}: {
  stormSummary: StormSummary;
  drainageSummary: Record<string, unknown>;
  pipeSegments: PipeSegment[];
  smartFixItems: SmartFixRecommendation[];
}) => {
  const segments = pipeSegments.map((segment, index) => {
    const rec = asRecord(segment);
    return {
      id: text(rec.id || rec.pipe || rec.name, `Pipe ${index + 1}`),
      from: text(rec.from || rec.start_name, "Upstream"),
      to: text(rec.to || rec.end_name, "Downstream"),
      lengthFt: firstNumber(rec.length_ft) ?? 0,
      diameterIn: firstNumber(rec.diameter_in),
      slopePct: firstNumber(rec.slope_pct, (firstNumber(rec.slope_ft_ft) ?? 0) * 100),
      flowCfs: firstNumber(rec.flow_cfs, rec.governing_flow_cfs),
      capacityCfs: firstNumber(rec.capacity_cfs, rec.full_capacity_cfs),
      velocityFps: firstNumber(rec.velocity_fps),
      startInvertFt: firstNumber(rec.start_invert_ft, rec.start_invert),
      endInvertFt: firstNumber(rec.end_invert_ft, rec.end_invert),
      hglUpFt: firstNumber(rec.hgl_upstream_ft),
      hglDownFt: firstNumber(rec.hgl_downstream_ft),
      eglUpFt: firstNumber(rec.egl_upstream_ft),
      eglDownFt: firstNumber(rec.egl_downstream_ft),
      path: normalizePath(rec.path || rec.route_points),
    };
  });

  const rawHgl = [
    ...asArray<StormProfilePoint>(stormSummary.hgl_profile),
    ...asArray<StormProfilePoint>(stormSummary.hydraulic_profile),
  ];
  const rawEgl = asArray<StormProfilePoint>(stormSummary.egl_profile);
  const mergedProfile = rawHgl.length
    ? rawHgl
    : segments.flatMap((segment, index) => {
        const startStation = segments.slice(0, index).reduce((sum, item) => sum + item.lengthFt, 0);
        return [
          {
            segment_id: segment.id,
            station_ft: startStation,
            invert_ft: segment.startInvertFt ?? undefined,
            hgl_ft: segment.hglUpFt ?? undefined,
            egl_ft: segment.eglUpFt ?? undefined,
          },
          {
            segment_id: segment.id,
            station_ft: startStation + segment.lengthFt,
            invert_ft: segment.endInvertFt ?? undefined,
            hgl_ft: segment.hglDownFt ?? undefined,
            egl_ft: segment.eglDownFt ?? undefined,
          },
        ];
      });
  const profile = mergedProfile
    .map((point, index) => {
      const pointRecord = asRecord(point);
      const eglMatch = asRecord(rawEgl[index]);
      return {
        segmentId: text(pointRecord.segment_id || pointRecord.pipe || eglMatch.segment_id || eglMatch.pipe, "Profile"),
        stationFt: firstNumber(pointRecord.station_ft, eglMatch.station_ft, index * 100) ?? index * 100,
        invertFt: firstNumber(pointRecord.invert_ft),
        groundFt: firstNumber(pointRecord.ground_ft, pointRecord.rim_ft),
        hglFt: firstNumber(pointRecord.hgl_ft),
        eglFt: firstNumber(pointRecord.egl_ft, eglMatch.egl_ft),
        coverFt: firstNumber(pointRecord.cover_ft),
      };
    })
    .filter((point) => Number.isFinite(point.stationFt));

  const inletChecks = [
    ...asArray<InletSpreadCheck>(stormSummary.inlet_spread_checks),
    ...asArray<InletSpreadCheck>(stormSummary.inlet_capacity_checks),
  ].map((item, index) => ({
    id: text(item.inlet_id || item.name, `Inlet ${index + 1}`),
    x: firstNumber(item.x),
    y: firstNumber(item.y),
    spreadFt: firstNumber(item.spread_ft),
    allowableSpreadFt: firstNumber(item.allowable_spread_ft),
    depthFt: firstNumber(item.depth_ft),
    captureEfficiency: firstNumber(item.capture_efficiency),
    bypassCfs: firstNumber(item.bypass_cfs),
    interceptedCfs: firstNumber(item.intercepted_cfs),
    status: text(item.status, "review"),
    warnings: asArray<string>(item.warnings).map(String),
  }));

  const drainageRouting = asRecord(drainageSummary.detention_routing);
  const stormRouting = asRecord(stormSummary.detention_routing);
  const routingSource = Array.isArray(drainageSummary.detention_routing)
    ? drainageSummary.detention_routing
    : Array.isArray(stormSummary.detention_routing)
      ? stormSummary.detention_routing
      : drainageRouting.routing_points || stormRouting.routing_points;
  const detentionRouting = asArray<DetentionRoutingPoint>(routingSource).map((item, index) => ({
    timeMin: firstNumber(item.time_min, index * 15) ?? index * 15,
    stageFt: firstNumber(item.stage_ft, item.elevation_ft),
    inflowCfs: firstNumber(item.inflow_cfs),
    outflowCfs: firstNumber(item.outflow_cfs),
    storageCf: firstNumber(item.storage_cf),
    waterSurfaceAreaSf: firstNumber(item.water_surface_area_sf),
  }));

  const stormOverflow = asRecord(stormSummary.overflow_analysis);
  const overflowPaths = [
    ...asArray<OverflowPathCheck>(drainageSummary.overflow_paths),
    ...asArray<OverflowPathCheck>(stormOverflow.paths),
    ...asArray<OverflowPathCheck>(stormOverflow.overflow_paths),
  ].map((item, index) => ({
    id: text(item.id || item.name, `OF-${index + 1}`),
    name: text(item.name || item.id, `Overflow ${index + 1}`),
    capacityValid: Boolean(item.capacity_valid),
    capacityCfs: firstNumber(item.capacity_cfs),
    requiredCapacityCfs: firstNumber(item.required_capacity_cfs),
    freeboardFt: firstNumber(item.freeboard_ft),
    source: text(item.source, "not recorded"),
    path: normalizePath(item.path || item.route_points),
    warnings: asArray<string>(item.warnings).map(String),
  }));

  const blockerDetails = [
    ...asArray<StormBlockerFix>(stormSummary.storm_depth_blocker_details),
    ...asArray<StormBlockerFix>((drainageSummary as { blocker_details?: StormBlockerFix[] }).blocker_details),
    ...smartFixItems.filter((item) =>
      /storm|drain|hydro|inlet|overflow|detention|hgl|egl/i.test(
        `${item.blocker_code || ""} ${item.category || ""} ${item.what_is_wrong || ""}`,
      ),
    ),
  ].map((item, index) => {
    const record = asRecord(item);
    return {
      code: text(record.code || record.blocker_code, `storm_blocker_${index + 1}`),
      message: text(record.message || record.what_is_wrong, "Storm/hydrology blocker needs review."),
      fix: text(record.exact_fix || record.one_action_needed_next, "Resolve the source evidence or rerun drainage after updating inputs."),
      missingInputs: asArray<string>(record.missing_inputs).map(String),
      canFix: Boolean(record.can_civora_fix),
    };
  });
  const blockerStrings = [
    ...asArray<string>(stormSummary.blockers),
    ...asArray<string>(stormSummary.storm_depth_blockers),
    ...asArray<string>(stormSummary.missing_inputs),
    ...asArray<string>(stormOverflow.blockers),
    ...asArray<string>(stormOverflow.missing_inputs),
    ...asArray<string>((drainageSummary as { blockers?: string[] }).blockers),
    ...asArray<string>((drainageSummary as { missing_inputs?: string[] }).missing_inputs),
  ].map(String);
  blockerStrings.forEach((item, index) => {
    if (!blockerDetails.some((detail) => detail.code === item || detail.message === item)) {
      blockerDetails.push({
        code: item.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "") || `storm_blocker_${index + 1}`,
        message: item,
        fix: "Provide the missing source, adjust the affected storm element, then regenerate drainage/storm.",
        missingInputs: [],
        canFix: false,
      });
    }
  });

  return {
    segments,
    profile,
    inletChecks,
    detentionRouting,
    overflowPaths,
    blockerDetails,
    hasAny:
      segments.length > 0 ||
      profile.length > 0 ||
      inletChecks.length > 0 ||
      detentionRouting.length > 0 ||
      overflowPaths.length > 0 ||
      blockerDetails.length > 0,
  };
};

export const buildWaterFireFlowReview = (
  planPreviewAnnotations: PreviewResponse["preview_annotations"] | null,
) => {
  const annotations: WaterFireFlowAnnotations = planPreviewAnnotations?.water_fire_flow ?? {};
  const readiness = annotations.readiness ?? {};
  const statusFor = (value: unknown) => {
    if (value === true) return "Pass";
    if (value === false) return "Needs evidence";
    return "Review";
  };
  const checkRows = [
    ["Pressure", statusFor(readiness.pressure_valid)],
    ["Fire flow", statusFor(readiness.fire_flow_valid)],
    ["Hydrant spacing", statusFor(readiness.hydrant_spacing_valid)],
    ["Looping", statusFor(readiness.looping_valid)],
    ["Dead ends", statusFor(readiness.dead_end_valid)],
  ];
  const blockerCards = (annotations.blocker_cards ?? []).map((card, index) => ({
    id: String(card.id || `water-blocker-${index + 1}`),
    source: String(card.source || "water"),
    title: String(card.title || "Water/fire-flow evidence needs review."),
    nextAction: String(card.next_action || "Provide accepted source evidence and rerun water review."),
    severity: String(card.severity || "review"),
  }));
  const hasAny =
    Boolean(planPreviewAnnotations?.water_fire_flow) ||
    (annotations.hydrants ?? []).length > 0 ||
    (annotations.pressure_zones ?? []).length > 0 ||
    (annotations.network_segments ?? []).length > 0 ||
    (annotations.scenario_runs ?? []).length > 0 ||
    (annotations.spacing_checks ?? []).length > 0 ||
    (annotations.velocity_checks ?? []).length > 0 ||
    blockerCards.length > 0;
  return {
    hydrants: annotations.hydrants ?? [],
    pressureZones: annotations.pressure_zones ?? [],
    networkSegments: annotations.network_segments ?? [],
    scenarios: annotations.scenario_runs ?? [],
    spacingChecks: annotations.spacing_checks ?? [],
    velocityChecks: annotations.velocity_checks ?? [],
    blockerCards,
    readiness,
    checkRows,
    hasAny,
  };
};

export const buildGradingResultSummary = (gradingSummary: Record<string, unknown>) => {
  const record = gradingSummary && typeof gradingSummary === "object" ? gradingSummary : {};
  const existingSurface =
    record.existing_surface && typeof record.existing_surface === "object"
      ? (record.existing_surface as Record<string, unknown>)
      : {};
  const terrainProfile =
    existingSurface.terrain_profile && typeof existingSurface.terrain_profile === "object"
      ? (existingSurface.terrain_profile as Record<string, unknown>)
      : {};
  const terrainStats =
    terrainProfile.terrain_stats && typeof terrainProfile.terrain_stats === "object"
      ? (terrainProfile.terrain_stats as Record<string, unknown>)
      : {};
  const surfaceControls =
    record.surface_controls && typeof record.surface_controls === "object"
      ? (record.surface_controls as Record<string, unknown>)
      : {};
  const downhillVector =
    surfaceControls.downhill_vector && typeof surfaceControls.downhill_vector === "object"
      ? (surfaceControls.downhill_vector as Record<string, unknown>)
      : {};
  const highPoints = Array.isArray(existingSurface.high_points)
    ? (existingSurface.high_points as unknown[])
    : [];
  const lowPoints = Array.isArray(record.low_points)
    ? (record.low_points as unknown[])
    : Array.isArray(existingSurface.low_points)
      ? (existingSurface.low_points as unknown[])
      : [];
  const rangeValue =
    typeof existingSurface.range_z === "number"
      ? existingSurface.range_z
      : Number(existingSurface.range_z ?? 0);
  const sampleCount = Number(terrainStats.sample_count ?? 0);
  const missingCount = Number(terrainStats.missing_count ?? 0);
  const dx = Number(downhillVector.dx ?? terrainProfile.downhill_dx ?? 0);
  const dy = Number(downhillVector.dy ?? terrainProfile.downhill_dy ?? 0);
  const eastWest = Math.abs(dx) > 0.05 ? (dx > 0 ? "east" : "west") : "";
  const northSouth = Math.abs(dy) > 0.05 ? (dy > 0 ? "north" : "south") : "";
  const slopeDirection = [northSouth, eastWest].filter(Boolean).join("-") || "not established";
  const sourceQuality = String(record.grading_source_quality || terrainProfile.source_quality || "");
  const sourceDetail = String(record.grading_source_detail || terrainProfile.source_detail || "");
  return {
    hasResult: Boolean(sourceQuality || sourceDetail || highPoints.length || lowPoints.length || rangeValue),
    sourceQuality,
    sourceDetail,
    sampleCount: Number.isFinite(sampleCount) ? sampleCount : 0,
    missingCount: Number.isFinite(missingCount) ? missingCount : 0,
    elevationRange: Number.isFinite(rangeValue) ? rangeValue : 0,
    highPointCount: highPoints.length,
    lowPointCount: lowPoints.length,
    slopeSummary: slopeDirection === "not established" ? "Slope direction not established." : `Slope direction trends ${slopeDirection}.`,
  };
};
