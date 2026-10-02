import type { BuildingPlacement } from "../types";
import type { CanonicalUpdateCommand } from "./canonicalEditCommands";

export type CanonicalDependencyPolicy = "follow" | "ask" | "fixed";

type RelationshipRecord = {
  policy?: CanonicalDependencyPolicy;
  object_ids?: string[];
};

export type ParkingDependencyResult = {
  policy: CanonicalDependencyPolicy;
  before: BuildingPlacement[];
  after: BuildingPlacement[];
  proposalObjectIds: string[];
  reflowReports: ParkingReflowReport[];
};

export type ParkingReflowReport = {
  objectId: string;
  strategy: "translated" | "south" | "north" | "east" | "west" | "best_available";
  status: "clear" | "review";
  insideSite: boolean;
  collisionObjectIds: string[];
  stallCountPreserved: boolean;
};

export type CanonicalDependencyProposal = {
  id: string;
  transactionId: string;
  buildingId: string;
  buildingLabel: string;
  before: BuildingPlacement[];
  after: BuildingPlacement[];
  reflowReports: ParkingReflowReport[];
  createdAt: string;
  projectId: string | null;
  sourceSnapshot: string;
};

/** Approval is atomic and fails closed if any project/object changed during review. */
export function resolveDependencyProposal(proposal: CanonicalDependencyProposal, placements: BuildingPlacement[], projectId: string | null) {
  if (proposal.projectId !== projectId || proposal.sourceSnapshot !== JSON.stringify(placements)) {
    return { accepted: false as const, placements, reason: "The project changed during review. Request a fresh proposal; your current plan was not changed." };
  }
  const afterById = new Map(proposal.after.map(item => [item.id, item]));
  return { accepted: true as const, placements: placements.map(item => afterById.get(item.id) ?? item) };
}

type Rect = { x: number; y: number; w: number; d: number };

const rectFor = (item: BuildingPlacement): Rect => ({
  x: item.x ?? 0,
  y: item.y ?? 0,
  w: Math.max(1, item.w),
  d: Math.max(1, item.d),
});

const overlapArea = (a: Rect, b: Rect, padding = 0) => {
  const width = Math.max(0, Math.min(a.x + a.w + padding, b.x + b.w + padding) - Math.max(a.x - padding, b.x - padding));
  const depth = Math.max(0, Math.min(a.y + a.d + padding, b.y + b.d + padding) - Math.max(a.y - padding, b.y - padding));
  return width * depth;
};

function planParkingReflow(
  placements: BuildingPlacement[],
  linked: BuildingPlacement[],
  beforeBuilding: BuildingPlacement,
  afterBuilding: BuildingPlacement,
  centerShiftX: number,
  centerShiftY: number,
) {
  const linkedIds = new Set(linked.map((item) => item.id));
  const site = placements.find((item) => item.type === "site" && item.placed);
  const siteRect = site ? rectFor(site) : null;
  const ignoredSurfaceTypes = new Set(["site", "road", "sidewalk", "drive_aisle", "access_drive"]);
  const obstacles = placements.filter((item) =>
    item.placed &&
    item.id !== beforeBuilding.id &&
    !linkedIds.has(item.id) &&
    !ignoredSurfaceTypes.has(item.type ?? ""),
  );
  const accepted: BuildingPlacement[] = [];
  const reports: ParkingReflowReport[] = [];
  const gap = 24;
  const buildingRect = rectFor(afterBuilding);
  const clampToSite = (candidate: Rect): Rect => {
    if (!siteRect) return candidate;
    const inset = 12;
    return {
      ...candidate,
      x: Math.min(Math.max(candidate.x, siteRect.x + inset), Math.max(siteRect.x + inset, siteRect.x + siteRect.w - candidate.w - inset)),
      y: Math.min(Math.max(candidate.y, siteRect.y + inset), Math.max(siteRect.y + inset, siteRect.y + siteRect.d - candidate.d - inset)),
    };
  };
  linked.forEach((parking) => {
    const base = rectFor(parking);
    const translated = { ...base, x: base.x + centerShiftX, y: base.y + centerShiftY };
    const rawCandidates: Array<{ strategy: ParkingReflowReport["strategy"]; rect: Rect }> = [
      { strategy: "translated", rect: translated },
      { strategy: "south", rect: { ...base, x: buildingRect.x + (buildingRect.w - base.w) / 2, y: buildingRect.y + buildingRect.d + gap } },
      { strategy: "north", rect: { ...base, x: buildingRect.x + (buildingRect.w - base.w) / 2, y: buildingRect.y - base.d - gap } },
      { strategy: "east", rect: { ...base, x: buildingRect.x + buildingRect.w + gap, y: buildingRect.y + (buildingRect.d - base.d) / 2 } },
      { strategy: "west", rect: { ...base, x: buildingRect.x - base.w - gap, y: buildingRect.y + (buildingRect.d - base.d) / 2 } },
    ];
    const candidates = rawCandidates.map(({ strategy, rect }) => {
      const candidate = clampToSite(rect);
      const outside = siteRect
        ? candidate.x < siteRect.x || candidate.y < siteRect.y || candidate.x + candidate.w > siteRect.x + siteRect.w || candidate.y + candidate.d > siteRect.y + siteRect.d
        : false;
      const collisionIds = [...obstacles, ...accepted].filter((item) => overlapArea(candidate, rectFor(item), 6) > 0).map((item) => item.id);
      const displacement = Math.hypot(candidate.x - translated.x, candidate.y - translated.y);
      const score = (outside ? 1_000_000 : 0) + collisionIds.length * 100_000 + displacement;
      return { strategy, rect: candidate, outside, collisionIds, score };
    }).sort((a, b) => a.score - b.score);
    const best = candidates[0];
    const deltaX = best.rect.x - base.x;
    const deltaY = best.rect.y - base.y;
    const existingCols = Math.max(1, Number(parking.meta?.parkingModuleCols ?? 1));
    const existingRows = Math.max(1, Number(parking.meta?.parkingModuleRows ?? 1));
    const moduleCount = existingCols * existingRows;
    const aspect = Math.max(0.25, best.rect.w / Math.max(best.rect.d, 1));
    const moduleCols = Math.max(1, Math.min(moduleCount, Math.round(Math.sqrt(moduleCount * aspect))));
    const moduleRows = Math.max(1, Math.ceil(moduleCount / moduleCols));
    const report: ParkingReflowReport = {
      objectId: parking.id,
      strategy: best.collisionIds.length || best.outside ? "best_available" : best.strategy,
      status: best.collisionIds.length || best.outside ? "review" : "clear",
      insideSite: !best.outside,
      collisionObjectIds: best.collisionIds,
      stallCountPreserved: true,
    };
    reports.push(report);
    accepted.push({
      ...parking,
      x: best.rect.x,
      y: best.rect.y,
      geometry: parking.geometry?.map(([x, y]) => [x + deltaX, y + deltaY] as [number, number]),
      meta: {
        ...(parking.meta ?? {}),
        parkingModuleCols: moduleCols,
        parkingModuleRows: moduleRows,
        parking_reflow_v1: {
          version: 1,
          status: report.status,
          strategy: report.strategy,
          inside_site: report.insideSite,
          collision_object_ids: report.collisionObjectIds,
          stall_count_preserved: report.stallCountPreserved,
          review_only: true,
        },
      },
    });
  });
  return { placements: accepted, reports };
}

export function parkingDependencyRelationship(building: BuildingPlacement): Required<RelationshipRecord> {
  const relationships = building.meta?.canonical_relationships as Record<string, RelationshipRecord> | undefined;
  const parking = relationships?.parking;
  const policy = parking?.policy;
  return {
    policy: policy === "follow" || policy === "fixed" ? policy : "ask",
    object_ids: Array.isArray(parking?.object_ids) ? parking.object_ids.map(String).filter(Boolean) : [],
  };
}

export function setParkingDependencyPolicy(
  building: BuildingPlacement,
  policy: CanonicalDependencyPolicy,
): Partial<BuildingPlacement> {
  const relationships = (building.meta?.canonical_relationships as Record<string, RelationshipRecord> | undefined) ?? {};
  const parking = parkingDependencyRelationship(building);
  return {
    meta: {
      ...(building.meta ?? {}),
      canonical_relationships: {
        ...relationships,
        parking: { ...parking, policy },
      },
    },
  };
}

export function setParkingDependencyObjectLinked(
  building: BuildingPlacement,
  objectId: string,
  linked: boolean,
): Partial<BuildingPlacement> {
  const relationships = (building.meta?.canonical_relationships as Record<string, RelationshipRecord> | undefined) ?? {};
  const parking = parkingDependencyRelationship(building);
  const objectIds = new Set(parking.object_ids);
  if (linked) objectIds.add(objectId);
  else objectIds.delete(objectId);
  return {
    meta: {
      ...(building.meta ?? {}),
      canonical_relationships: {
        ...relationships,
        parking: { ...parking, object_ids: [...objectIds] },
      },
    },
  };
}

export function applyBuildingParkingDependency(
  placements: BuildingPlacement[],
  beforeBuilding: BuildingPlacement,
  afterBuilding: BuildingPlacement,
  command: CanonicalUpdateCommand,
): ParkingDependencyResult {
  const relationship = parkingDependencyRelationship(beforeBuilding);
  const rawRelationships = beforeBuilding.meta?.canonical_relationships as Record<string, RelationshipRecord> | undefined;
  const hasExplicitParkingRelationship = Boolean(rawRelationships && Object.prototype.hasOwnProperty.call(rawRelationships, "parking"));
  const linked = placements.filter((item) =>
    item.type === "parking" && (
      relationship.object_ids.includes(item.id) || (!hasExplicitParkingRelationship && item.meta?.canonical_parent_id === beforeBuilding.id)
    ),
  );
  if (!linked.length) return { policy: relationship.policy, before: [], after: [], proposalObjectIds: [], reflowReports: [] };

  const deltaX = (afterBuilding.x ?? 0) - (beforeBuilding.x ?? 0);
  const deltaY = (afterBuilding.y ?? 0) - (beforeBuilding.y ?? 0);
  const centerShiftX = deltaX + (afterBuilding.w - beforeBuilding.w) / 2;
  const centerShiftY = deltaY + (afterBuilding.d - beforeBuilding.d) / 2;
  const geometryChanged = centerShiftX !== 0 || centerShiftY !== 0;
  if (!geometryChanged || relationship.policy === "fixed") {
    return { policy: relationship.policy, before: linked, after: linked, proposalObjectIds: [], reflowReports: [] };
  }
  const reflow = planParkingReflow(placements, linked, beforeBuilding, afterBuilding, centerShiftX, centerShiftY);
  const after = reflow.placements.map((parking) => ({
    ...parking,
    meta: {
      ...(parking.meta ?? {}),
      canonical_parent_id: beforeBuilding.id,
      canonical_dependency_policy: relationship.policy,
      canonical_revision: Number(parking.meta?.canonical_revision ?? 0) + 1,
      canonical_last_edit: {
        transaction_id: command.transactionId,
        source: relationship.policy === "ask" ? "dependency_proposal" : "dependency",
        command: relationship.policy === "ask" ? "propose_follow_building" : "follow_building",
        changed_fields: ["x", "y"],
        created_at: command.createdAt,
      },
    },
  }));
  if (relationship.policy === "ask") {
    return { policy: "ask", before: linked, after, proposalObjectIds: linked.map((item) => item.id), reflowReports: reflow.reports };
  }
  return { policy: "follow", before: linked, after, proposalObjectIds: [], reflowReports: reflow.reports };
}
