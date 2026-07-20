import type {
  ChatMessage,
  ManualFields,
  ProjectInput,
  SiteInputs,
} from "../types";
import { createWelcomeMessage } from "./chat";
import { buildAssumedSlopeEstimate, DEFAULT_SYSTEM_STATUS, isEngineeringSystemStatus, type SystemStatus } from "./workflowConstants";
import { toArray } from "./formatting";
import { buildProjectInputPlacements } from "./projectInputRestore";

export function buildDashboardProjectInputView(projectInput: ProjectInput, siteInputs: SiteInputs | null | undefined) {
  const manualFields = projectInput.manual_fields ?? {};
  const lot = (manualFields.lot ?? {}) as { w?: number; h?: number };
  const sitePlan = (manualFields.site_plan ?? {}) as {
    parking_count?: number;
    building_program_sf?: number;
    building_type?: string;
  };
  const gradingFields = (manualFields.grading ?? {}) as {
    min_slope_pct?: number;
    max_parking_slope_pct?: number;
    max_road_grade_pct?: number;
    max_ada_cross_slope_pct?: number;
    assumed_terrain_source?: boolean;
    assumed_terrain_slope_pct?: number;
  };
  const drainageFields = (manualFields.drainage ?? {}) as NonNullable<ManualFields["drainage"]>;
  const drainageForced = Array.isArray(drainageFields?.forced_inlets)
    ? (drainageFields?.forced_inlets as Array<Record<string, unknown>>)
    : [];
  const disciplines = toArray(manualFields.disciplines);
  const buildingsList = Array.isArray(manualFields.buildings) ? manualFields.buildings : [];
  const restoredThread: ChatMessage[] = Array.isArray(projectInput.meta?.chat_thread)
    ? projectInput.meta.chat_thread
        .filter((message) => message && typeof message.content === "string")
        .map((message): ChatMessage => ({
          id:
            typeof message.id === "string"
              ? message.id
              : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          role:
            message.role === "user" ||
            message.role === "assistant" ||
            message.role === "system"
              ? message.role
              : "assistant",
          content: message.content,
          createdAt:
            typeof message.createdAt === "number"
              ? message.createdAt
              : Date.now(),
          kind:
            message.kind === "status" ||
            message.kind === "explanation" ||
            message.kind === "action"
              ? message.kind
              : "message",
          feedback:
            message.feedback === "up" || message.feedback === "down"
              ? message.feedback
              : undefined,
          phaseTag: typeof message.phaseTag === "string" ? message.phaseTag : undefined,
        }))
    : [];
  const autoNamed = Boolean(projectInput.meta?.auto_named);
  const autoFileNamed = Boolean(projectInput.meta?.auto_file_named);
  const mergedPlacements = buildProjectInputPlacements({ projectInput, siteInputs: siteInputs ?? ({} as SiteInputs) });
  const officeProgramDims =
    sitePlan.building_type === "office" &&
    typeof sitePlan.building_program_sf === "number" &&
    !manualFields.building_width &&
    !manualFields.building_depth
      ? (() => {
          const depth = Math.round(Math.sqrt(sitePlan.building_program_sf / 1.8));
          const width = Math.round(sitePlan.building_program_sf / Math.max(depth, 1));
          return { width: String(width), depth: String(depth) };
        })()
      : null;
  const assumedTerrainSlopePct =
    typeof (gradingFields as Record<string, unknown>).assumed_terrain_slope_pct === "number"
      ? Number((gradingFields as Record<string, unknown>).assumed_terrain_slope_pct)
      : null;
  const drainageForcedInlets = drainageForced
    .map((item) => {
      const rec = item as { x?: number; y?: number; name?: string };
      if (typeof rec?.x !== "number" || typeof rec?.y !== "number") return null;
      return { x: rec.x, y: rec.y, name: typeof rec.name === "string" ? rec.name : undefined };
    })
    .filter(Boolean) as Array<{ x: number; y: number; name?: string }>;
  const rawMaxSlopeAdjust = (manualFields.drainage ?? {}).max_slope_adjust;
  const restoredSystemState = projectInput.meta?.system_dirty_state;
  const systemStatuses =
    restoredSystemState && typeof restoredSystemState === "object"
      ? {
          roads: isEngineeringSystemStatus((restoredSystemState as Record<string, unknown>).roads) ? (restoredSystemState as Record<string, SystemStatus>).roads : DEFAULT_SYSTEM_STATUS.roads,
          parking: isEngineeringSystemStatus((restoredSystemState as Record<string, unknown>).parking) ? (restoredSystemState as Record<string, SystemStatus>).parking : DEFAULT_SYSTEM_STATUS.parking,
          grading: isEngineeringSystemStatus((restoredSystemState as Record<string, unknown>).grading) ? (restoredSystemState as Record<string, SystemStatus>).grading : DEFAULT_SYSTEM_STATUS.grading,
          drainage: isEngineeringSystemStatus((restoredSystemState as Record<string, unknown>).drainage) ? (restoredSystemState as Record<string, SystemStatus>).drainage : DEFAULT_SYSTEM_STATUS.drainage,
          utilities: isEngineeringSystemStatus((restoredSystemState as Record<string, unknown>).utilities) ? (restoredSystemState as Record<string, SystemStatus>).utilities : DEFAULT_SYSTEM_STATUS.utilities,
        }
      : null;

  return {
    manualFields,
    promptText: projectInput.prompt_text ?? "",
    imagePath: projectInput.image_path ?? "",
    siteName: manualFields.project_name ?? "",
    fileName: manualFields.file_name ?? "",
    siteNameAuto: autoNamed || !manualFields.project_name,
    fileNameAuto: autoFileNamed || !(manualFields.file_name ?? manualFields.project_name),
    units: manualFields.units ?? "ft",
    projectType: manualFields.project_type ?? "",
    lotWidth: String(lot.w ?? ""),
    lotHeight: String(lot.h ?? ""),
    setback: String(manualFields.setback ?? ""),
    buildingWidth: String(manualFields.building_width ?? ""),
    buildingDepth: String(manualFields.building_depth ?? ""),
    buildingCount: buildingsList.length ? String(buildingsList.length) : "",
    mergedPlacements,
    parkingCount: String(sitePlan.parking_count ?? ""),
    officeProgramDims,
    minSlopePct: String(gradingFields.min_slope_pct ?? ""),
    assumedTerrainSlopePct,
    assumedSlopeEstimate:
      typeof assumedTerrainSlopePct === "number" ? buildAssumedSlopeEstimate(assumedTerrainSlopePct) : null,
    pipeMinSlopePct: String(drainageFields.min_pipe_slope_pct ?? ""),
    drainageForcedInlets,
    drainageConnectOrphans: Boolean((manualFields.drainage ?? {}).connect_orphans),
    drainageAllowSlopeAdjust: Boolean((manualFields.drainage ?? {}).allow_slope_adjustment),
    drainageMaxSlopeAdjust:
      typeof rawMaxSlopeAdjust === "number" && Number.isFinite(rawMaxSlopeAdjust)
        ? rawMaxSlopeAdjust
        : 0.001,
    maxParkingSlopePct: String(gradingFields.max_parking_slope_pct ?? ""),
    maxRoadGradePct: String(gradingFields.max_road_grade_pct ?? ""),
    maxAdaCrossSlopePct: String(gradingFields.max_ada_cross_slope_pct ?? ""),
    roads: disciplines.includes("corridor"),
    grading: disciplines.includes("grading"),
    drainage: disciplines.includes("drainage"),
    utilities: disciplines.includes("utility"),
    systemStatuses,
    chatThread: restoredThread.length ? restoredThread : [createWelcomeMessage()],
  };
}
