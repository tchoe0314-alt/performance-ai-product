import type { Dispatch, SetStateAction } from "react";
import { useCallback } from "react";

import type { BuildingPlacement, SiteObjectType } from "../types";
import type { ParkingParams } from "../utils/previewGeometryTruth";

export type DashboardAccessAnalysisPath = {
  id: string;
  buildingId: string;
  accessId: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
  label: string;
  points?: Array<{ x: number; y: number }>;
};

export type DashboardAccessAnalysisIssue = {
  id: string;
  buildingId: string;
  accessId: string;
  distanceFt: number;
  thresholdFt: number;
  message: string;
  pathId: string;
  issueType: "distance" | "no_access" | "no_buildings" | "no_access_objects";
};

type AskClarification = (question: string, action: string, payload?: Record<string, unknown>) => void;

type UseDashboardSiteAccessAnalysisOptions = {
  askClarification: AskClarification;
  buildingPlacements: BuildingPlacement[];
  setAnalysisEmptyReason: Dispatch<SetStateAction<string | null>>;
  setAnalysisFocusLocked: Dispatch<SetStateAction<boolean>>;
  setAnalysisIssues: Dispatch<SetStateAction<DashboardAccessAnalysisIssue[]>>;
  setAnalysisPaths: Dispatch<SetStateAction<DashboardAccessAnalysisPath[]>>;
  setAnalysisSelectedIssueId: Dispatch<SetStateAction<string | null>>;
  setStatusMessage: (message: string) => void;
};

export function useDashboardSiteAccessAnalysis({
  askClarification,
  buildingPlacements,
  setAnalysisEmptyReason,
  setAnalysisFocusLocked,
  setAnalysisIssues,
  setAnalysisPaths,
  setAnalysisSelectedIssueId,
  setStatusMessage,
}: UseDashboardSiteAccessAnalysisOptions) {
  return useCallback(() => {
    const confirmed = buildingPlacements.filter(
      (item) => item.placed && (item.source === "user" || item.source === "user_confirmed"),
    );
    const accessTypes = new Set<SiteObjectType>(["road", "entrance", "parking", "sidewalk", "driveway"]);
    const buildingTypes = new Set<SiteObjectType>([
      "building",
      "retail_building",
      "multifamily_building",
      "industrial_building",
      "office_building",
      "pad",
    ]);
    const buildings = confirmed.filter((item) => buildingTypes.has(item.type as SiteObjectType));
    const access = confirmed.filter((item) => accessTypes.has(item.type as SiteObjectType));
    if (!buildings.length || !access.length) {
      setAnalysisIssues([]);
      setAnalysisPaths([]);
      setAnalysisSelectedIssueId(null);
      setAnalysisFocusLocked(false);
      let reason = "Address provides site context only. Add or confirm buildings and access objects to run analysis.";
      if (!buildings.length && access.length) {
        reason = "Add or confirm buildings to run access analysis.";
      }
      if (!access.length && buildings.length) {
        reason = "Add or confirm roads, driveways, or access objects to run access analysis.";
      }
      setAnalysisEmptyReason(reason);
      askClarification(reason, "access_analysis_missing");
      return;
    }
    setAnalysisEmptyReason(null);
    const issues: DashboardAccessAnalysisIssue[] = [];
    const paths: DashboardAccessAnalysisPath[] = [];
    const threshold = 150;
    const adjacencyGap = 25;
    const buildingAccessGap = 60;

    type GraphEdge = { to: string; weight: number; points: Array<{ x: number; y: number }> };
    const graph: Record<string, GraphEdge[]> = {};

    const addEdge = (from: string, to: string, weight: number, points: Array<{ x: number; y: number }>) => {
      if (!graph[from]) graph[from] = [];
      graph[from].push({ to, weight, points });
    };

    const clampToRect = (pt: { x: number; y: number }, rect: { x: number; y: number; w: number; d: number }) => ({
      x: Math.min(Math.max(pt.x, rect.x), rect.x + rect.w),
      y: Math.min(Math.max(pt.y, rect.y), rect.y + rect.d),
    });

    const distancePointToRect = (pt: { x: number; y: number }, rect: { x: number; y: number; w: number; d: number }) => {
      const closest = clampToRect(pt, rect);
      const dx = pt.x - closest.x;
      const dy = pt.y - closest.y;
      return { distance: Math.hypot(dx, dy), closest };
    };

    const closestPointOnSegment = (
      a: { x: number; y: number },
      b: { x: number; y: number },
      p: { x: number; y: number },
    ) => {
      const abx = b.x - a.x;
      const aby = b.y - a.y;
      const ab2 = abx * abx + aby * aby;
      if (!ab2) return { x: a.x, y: a.y };
      const t = ((p.x - a.x) * abx + (p.y - a.y) * aby) / ab2;
      const clamped = Math.max(0, Math.min(1, t));
      return { x: a.x + abx * clamped, y: a.y + aby * clamped };
    };

    const getAccessPolyline = (item: BuildingPlacement): Array<{ x: number; y: number }> => {
      if (item.geometryType === "polyline" && Array.isArray(item.geometry) && item.geometry.length > 1) {
        return item.geometry.map(([x, y]) => ({ x, y }));
      }
      const x = item.x ?? 0;
      const y = item.y ?? 0;
      const isHorizontal = item.w >= item.d;
      if (item.type === "parking") {
        const params = (item.meta as { parkingParams?: ParkingParams })?.parkingParams ?? {};
        const stallDepth = Number.isFinite(params.stallDepth) ? Number(params.stallDepth) : 18;
        const aisleWidth = Number.isFinite(params.aisleWidth) ? Number(params.aisleWidth) : 24;
        const angleDeg = Number.isFinite(params.angleDeg) ? Number(params.angleDeg) : 90;
        const loading = params.loading === "single" ? "single" : "double";
        const angleRad = (Math.max(Math.min(angleDeg, 89), 0) * Math.PI) / 180;
        const depthAdj = stallDepth / Math.cos(angleRad || 0.0001);
        const moduleDepth = depthAdj * (loading === "double" ? 2 : 1) + aisleWidth;
        const scale = item.d < moduleDepth ? item.d / moduleDepth : 1;
        const scaledStall = depthAdj * scale;
        const scaledAisle = aisleWidth * scale;
        const centerY =
          loading === "double"
            ? y + (item.d - scaledAisle) / 2 + scaledAisle / 2
            : y + scaledStall + scaledAisle / 2;
        const start = { x: x + 4, y: centerY };
        const end = { x: x + item.w - 4, y: centerY };
        return [start, end];
      }
      if (isHorizontal) {
        return [
          { x, y: y + item.d / 2 },
          { x: x + item.w, y: y + item.d / 2 },
        ];
      }
      return [
        { x: x + item.w / 2, y },
        { x: x + item.w / 2, y: y + item.d },
      ];
    };

    const accessPaths = access.map((item) => ({
      id: item.id,
      type: item.type,
      points: getAccessPolyline(item),
    }));

    accessPaths.forEach((path) => {
      const points = path.points;
      if (points.length < 2) return;
      for (let i = 0; i < points.length - 1; i += 1) {
        const a = points[i];
        const b = points[i + 1];
        const weight = Math.hypot(b.x - a.x, b.y - a.y);
        const nodeA = `${path.id}-p${i}`;
        const nodeB = `${path.id}-p${i + 1}`;
        addEdge(nodeA, nodeB, weight, [a, b]);
        addEdge(nodeB, nodeA, weight, [b, a]);
      }
    });

    const pathEndpoints = accessPaths
      .map((path) => {
        const points = path.points;
        if (points.length < 2) return null;
        return [
          { id: `${path.id}-p0`, point: points[0] },
          { id: `${path.id}-p${points.length - 1}`, point: points[points.length - 1] },
        ];
      })
      .flat()
      .filter(Boolean) as Array<{ id: string; point: { x: number; y: number } }>;

    for (let i = 0; i < pathEndpoints.length; i += 1) {
      for (let j = i + 1; j < pathEndpoints.length; j += 1) {
        const a = pathEndpoints[i];
        const b = pathEndpoints[j];
        const distance = Math.hypot(a.point.x - b.point.x, a.point.y - b.point.y);
        if (distance <= adjacencyGap) {
          addEdge(a.id, b.id, Math.max(distance, 1), [a.point, b.point]);
          addEdge(b.id, a.id, Math.max(distance, 1), [b.point, a.point]);
        }
      }
    }

    const buildPathPoints = (edgePoints: Array<Array<{ x: number; y: number }>>) => {
      const points: Array<{ x: number; y: number }> = [];
      edgePoints.forEach((segment) => {
        segment.forEach((pt, idx) => {
          if (!points.length) {
            points.push(pt);
            return;
          }
          const last = points[points.length - 1];
          if (Math.hypot(last.x - pt.x, last.y - pt.y) < 0.01) return;
          if (idx === 0) {
            points.push(pt);
            return;
          }
          points.push(pt);
        });
      });
      return points;
    };

    buildings.forEach((building) => {
      const buildingNodeId = `building-${building.id}`;
      const buildingRect = { x: building.x ?? 0, y: building.y ?? 0, w: building.w, d: building.d };
      graph[buildingNodeId] = [];
      accessPaths.forEach((path) => {
        const points = path.points;
        if (points.length < 2) return;
        let closestDistance = Number.POSITIVE_INFINITY;
        let closestPoint: { x: number; y: number } | null = null;
        let closestNodeId: string | null = null;
        for (let i = 0; i < points.length - 1; i += 1) {
          const a = points[i];
          const b = points[i + 1];
          const segmentPoint = closestPointOnSegment(a, b, {
            x: buildingRect.x + buildingRect.w / 2,
            y: buildingRect.y + buildingRect.d / 2,
          });
          const { distance } = distancePointToRect(segmentPoint, buildingRect);
          if (distance < closestDistance) {
            closestDistance = distance;
            closestPoint = segmentPoint;
            closestNodeId = `${path.id}-p${i}`;
          }
        }
        if (closestPoint && closestNodeId && closestDistance <= buildingAccessGap) {
          addEdge(buildingNodeId, closestNodeId, Math.max(closestDistance, 1), [
            clampToRect(closestPoint, buildingRect),
            closestPoint,
          ]);
        }
      });

      const distances = new Map<string, number>();
      const prev = new Map<string, { node: string; points: Array<{ x: number; y: number }> }>();
      const unvisited = new Set<string>(Object.keys(graph));
      distances.set(buildingNodeId, 0);

      while (unvisited.size) {
        let current: string | null = null;
        let bestDistance = Number.POSITIVE_INFINITY;
        unvisited.forEach((nodeId) => {
          const dist = distances.get(nodeId);
          if (dist !== undefined && dist < bestDistance) {
            bestDistance = dist;
            current = nodeId;
          }
        });
        if (!current) break;
        unvisited.delete(current);
        const edges = graph[current] ?? [];
        edges.forEach((edge) => {
          if (!unvisited.has(edge.to)) return;
          const nextDist = bestDistance + edge.weight;
          const existing = distances.get(edge.to);
          if (existing === undefined || nextDist < existing) {
            distances.set(edge.to, nextDist);
            prev.set(edge.to, { node: current as string, points: edge.points });
          }
        });
      }

      let closestAccessId: string | null = null;
      let closestDistance = Number.POSITIVE_INFINITY;
      let closestNodeId: string | null = null;
      accessPaths.forEach((path) => {
        path.points.forEach((_, idx) => {
          const nodeId = `${path.id}-p${idx}`;
          const dist = distances.get(nodeId);
          if (dist !== undefined && dist < closestDistance) {
            closestDistance = dist;
            closestNodeId = nodeId;
            closestAccessId = path.id;
          }
        });
      });

      if (!closestAccessId || !Number.isFinite(closestDistance)) {
        issues.push({
          id: `${building.id}-no-access`,
          buildingId: building.id,
          accessId: "",
          distanceFt: 0,
          thresholdFt: threshold,
          message: `Building ${building.label} has no access path.`,
          pathId: "",
          issueType: "no_access",
        });
        return;
      }

      const edgePoints: Array<Array<{ x: number; y: number }>> = [];
      let cursor: string | null = closestNodeId;
      while (cursor && cursor !== buildingNodeId) {
        const step = prev.get(cursor);
        if (!step) break;
        edgePoints.unshift(step.points);
        cursor = step.node;
      }

      const points = buildPathPoints(edgePoints);
      const from = points[0] ?? { x: buildingRect.x, y: buildingRect.y };
      const to = points[points.length - 1] ?? from;
      const pathId = `${building.id}-${closestAccessId}`;
      paths.push({
        id: pathId,
        buildingId: building.id,
        accessId: closestAccessId,
        from,
        to,
        label: `Access ${Math.round(closestDistance)} ft`,
        points,
      });
      if (closestDistance > threshold) {
        issues.push({
          id: `${building.id}-distance`,
          buildingId: building.id,
          accessId: closestAccessId,
          distanceFt: closestDistance,
          thresholdFt: threshold,
          message: `Building ${building.label} is ${Math.round(closestDistance)} ft from nearest access (>${threshold} ft).`,
          pathId,
          issueType: "distance",
        });
      }
    });

    setAnalysisIssues(issues);
    setAnalysisPaths(paths);
    setAnalysisSelectedIssueId(issues[0]?.id ?? null);
    setAnalysisFocusLocked(Boolean(issues[0]?.id));
    setStatusMessage("Site access analysis complete (conceptual).");
  }, [
    askClarification,
    buildingPlacements,
    setAnalysisEmptyReason,
    setAnalysisFocusLocked,
    setAnalysisIssues,
    setAnalysisPaths,
    setAnalysisSelectedIssueId,
    setStatusMessage,
  ]);
}
