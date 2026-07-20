import type { BuildingPlacement } from "../types";
import {
  getGeometryBounds,
  getObjectEditBlocker,
  normalizeGeometryPoints,
} from "./objectGeometry";

export type ObjectManagerVertexActions = {
  handleUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  reportObjectActionBlocker: (message: string) => void;
  setObjectManagerStatusMessage: (message: string) => void;
  setStatusMessage: (message: string) => void;
};

export function runObjectVertexCoordinateUpdate({
  item,
  vertexIndex,
  axis,
  rawValue,
  buildingPlacements,
  actions,
}: {
  item: BuildingPlacement;
  vertexIndex: number;
  axis: "x" | "y";
  rawValue: string;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerVertexActions;
}) {
  const latestItem = buildingPlacements.find((candidate) => candidate.id === item.id) ?? item;
  const blocker = getObjectEditBlocker(latestItem, "resize");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  const value = Number(rawValue);
  if (!Number.isFinite(value)) {
    actions.reportObjectActionBlocker("Vertex edit blocked: enter a finite coordinate.");
    return;
  }
  const geometry = normalizeGeometryPoints(latestItem.geometry);
  if (!geometry?.length || vertexIndex < 0 || vertexIndex >= geometry.length) {
    actions.reportObjectActionBlocker("Vertex edit blocked: select a draft object with editable vertices.");
    return;
  }
  const nextGeometry = geometry.map(([x, y], index) =>
    index === vertexIndex
      ? ([axis === "x" ? value : x, axis === "y" ? value : y] as [number, number])
      : ([x, y] as [number, number]),
  );
  const bounds = getGeometryBounds(nextGeometry);
  actions.handleUpdateBuilding(latestItem.id, {
    x: bounds.minX,
    y: bounds.minY,
    w: Math.max(1, bounds.width),
    d: Math.max(1, bounds.depth),
    geometry: nextGeometry,
  });
  const message = `Updated ${latestItem.label} vertex ${vertexIndex + 1} ${axis.toUpperCase()} to ${value}.`;
  actions.setObjectManagerStatusMessage(`${message} Vertex coordinates remain draft review geometry.`);
  actions.setStatusMessage(message);
}

export function runObjectVertexInsert({
  item,
  vertexIndex,
  actions,
}: {
  item: BuildingPlacement;
  vertexIndex: number;
  actions: ObjectManagerVertexActions;
}) {
  const blocker = getObjectEditBlocker(item, "resize");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  const geometry = normalizeGeometryPoints(item.geometry);
  if (!geometry?.length || vertexIndex < 0 || vertexIndex >= geometry.length) {
    actions.reportObjectActionBlocker("Insert vertex blocked: select a draft object with editable vertices.");
    return;
  }
  if (item.geometryType === "point") {
    actions.reportObjectActionBlocker("Insert vertex blocked: point objects can only have one editable coordinate.");
    return;
  }
  const current = geometry[vertexIndex];
  const next = geometry[vertexIndex + 1] ?? (item.geometryType === "polygon" || item.geometryType === "rect" ? geometry[0] : null);
  const inserted: [number, number] = next
    ? [(current[0] + next[0]) / 2, (current[1] + next[1]) / 2]
    : [current[0] + 20, current[1]];
  const nextGeometry = [
    ...geometry.slice(0, vertexIndex + 1),
    inserted,
    ...geometry.slice(vertexIndex + 1),
  ];
  const bounds = getGeometryBounds(nextGeometry);
  actions.handleUpdateBuilding(item.id, {
    x: bounds.minX,
    y: bounds.minY,
    w: Math.max(1, bounds.width),
    d: Math.max(1, bounds.depth),
    geometry: nextGeometry,
  });
  const message = `Inserted vertex ${vertexIndex + 2} on ${item.label}.`;
  actions.setObjectManagerStatusMessage(`${message} Vertex coordinates remain draft review geometry.`);
  actions.setStatusMessage(message);
}

export function runObjectVertexDelete({
  item,
  vertexIndex,
  actions,
}: {
  item: BuildingPlacement;
  vertexIndex: number;
  actions: ObjectManagerVertexActions;
}) {
  const blocker = getObjectEditBlocker(item, "resize");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  const geometry = normalizeGeometryPoints(item.geometry);
  if (!geometry?.length || vertexIndex < 0 || vertexIndex >= geometry.length) {
    actions.reportObjectActionBlocker("Delete vertex blocked: select a draft object with editable vertices.");
    return;
  }
  const minimumVertices = item.geometryType === "polygon" || item.geometryType === "rect"
    ? 3
    : item.geometryType === "polyline"
      ? 2
      : 1;
  if (geometry.length <= minimumVertices) {
    actions.reportObjectActionBlocker(`Delete vertex blocked: ${item.geometryType ?? "draft object"} geometry needs at least ${minimumVertices} point${minimumVertices === 1 ? "" : "s"}.`);
    return;
  }
  const nextGeometry = geometry.filter((_, index) => index !== vertexIndex);
  const bounds = getGeometryBounds(nextGeometry);
  actions.handleUpdateBuilding(item.id, {
    x: bounds.minX,
    y: bounds.minY,
    w: Math.max(1, bounds.width),
    d: Math.max(1, bounds.depth),
    geometry: nextGeometry,
  });
  const message = `Deleted vertex ${vertexIndex + 1} from ${item.label}.`;
  actions.setObjectManagerStatusMessage(`${message} Vertex coordinates remain draft review geometry.`);
  actions.setStatusMessage(message);
}

export function runObjectVertexSnapToNearestEndpoint({
  item,
  vertexIndex,
  buildingPlacements,
  actions,
}: {
  item: BuildingPlacement;
  vertexIndex: number;
  buildingPlacements: BuildingPlacement[];
  actions: ObjectManagerVertexActions;
}) {
  const blocker = getObjectEditBlocker(item, "resize");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  const geometry = normalizeGeometryPoints(item.geometry);
  if (!geometry?.length || vertexIndex < 0 || vertexIndex >= geometry.length) {
    actions.reportObjectActionBlocker("Snap vertex blocked: select a draft object with editable vertices.");
    return;
  }
  const sourcePoint = geometry[vertexIndex];
  const candidates = buildingPlacements.flatMap((candidate) => {
    if (candidate.id === item.id || candidate.meta?.ui_hidden || candidate.type === "site") return [];
    const candidateGeometry = normalizeGeometryPoints(candidate.geometry);
    if (candidateGeometry?.length) {
      return candidateGeometry.map((point, index) => ({
        point,
        label: `${candidate.label} V${index + 1}`,
      }));
    }
    if (candidate.source === "manual_drawn" || candidate.type === "custom") {
      return [
        { point: [candidate.x ?? 0, candidate.y ?? 0] as [number, number], label: `${candidate.label} corner` },
        { point: [(candidate.x ?? 0) + candidate.w, (candidate.y ?? 0) + candidate.d] as [number, number], label: `${candidate.label} opposite corner` },
      ];
    }
    return [];
  });
  if (!candidates.length) {
    actions.reportObjectActionBlocker("Snap vertex blocked: no other visible draft endpoints are available.");
    return;
  }
  const nearest = candidates
    .map((candidate) => ({
      ...candidate,
      distance: Math.hypot(candidate.point[0] - sourcePoint[0], candidate.point[1] - sourcePoint[1]),
    }))
    .sort((a, b) => a.distance - b.distance)[0];
  if (!nearest || !Number.isFinite(nearest.distance)) {
    actions.reportObjectActionBlocker("Snap vertex blocked: no finite draft endpoint was found.");
    return;
  }
  const nextGeometry = geometry.map(([x, y], index) =>
    index === vertexIndex ? ([nearest.point[0], nearest.point[1]] as [number, number]) : ([x, y] as [number, number]),
  );
  const bounds = getGeometryBounds(nextGeometry);
  actions.handleUpdateBuilding(item.id, {
    x: bounds.minX,
    y: bounds.minY,
    w: Math.max(1, bounds.width),
    d: Math.max(1, bounds.depth),
    geometry: nextGeometry,
  });
  const message = `Snapped ${item.label} vertex ${vertexIndex + 1} to ${nearest.label}.`;
  actions.setObjectManagerStatusMessage(`${message} Snap is draft geometry cleanup only.`);
  actions.setStatusMessage(message);
}

export function runObjectVertexAlignToPrevious({
  item,
  vertexIndex,
  axis,
  actions,
}: {
  item: BuildingPlacement;
  vertexIndex: number;
  axis: "x" | "y";
  actions: ObjectManagerVertexActions;
}) {
  const blocker = getObjectEditBlocker(item, "resize");
  if (blocker) {
    actions.reportObjectActionBlocker(blocker);
    return;
  }
  const geometry = normalizeGeometryPoints(item.geometry);
  if (!geometry?.length || vertexIndex < 0 || vertexIndex >= geometry.length) {
    actions.reportObjectActionBlocker("Align vertex blocked: select a draft object with editable vertices.");
    return;
  }
  if (geometry.length < 2) {
    actions.reportObjectActionBlocker("Align vertex blocked: at least two draft points are required.");
    return;
  }
  const canWrap = item.geometryType === "polygon" || item.geometryType === "rect";
  const previousIndex = vertexIndex > 0 ? vertexIndex - 1 : canWrap ? geometry.length - 1 : -1;
  if (previousIndex < 0 || previousIndex >= geometry.length) {
    actions.reportObjectActionBlocker("Align vertex blocked: this open line vertex has no previous point.");
    return;
  }
  const targetValue = geometry[previousIndex][axis === "x" ? 0 : 1];
  const currentValue = geometry[vertexIndex][axis === "x" ? 0 : 1];
  if (Math.abs(currentValue - targetValue) < 0.001) {
    actions.reportObjectActionBlocker(`Align vertex blocked: vertex ${vertexIndex + 1} already shares ${axis.toUpperCase()} with the previous vertex.`);
    return;
  }
  const nextGeometry = geometry.map(([x, y], index) =>
    index === vertexIndex
      ? ([axis === "x" ? targetValue : x, axis === "y" ? targetValue : y] as [number, number])
      : ([x, y] as [number, number]),
  );
  const bounds = getGeometryBounds(nextGeometry);
  actions.handleUpdateBuilding(item.id, {
    x: bounds.minX,
    y: bounds.minY,
    w: Math.max(1, bounds.width),
    d: Math.max(1, bounds.depth),
    geometry: nextGeometry,
  });
  const message = `Aligned ${item.label} vertex ${vertexIndex + 1} ${axis.toUpperCase()} to previous vertex.`;
  actions.setObjectManagerStatusMessage(`${message} Vertex alignment remains draft review geometry.`);
  actions.setStatusMessage(message);
}
