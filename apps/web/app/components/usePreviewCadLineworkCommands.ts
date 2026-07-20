import { useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { BuildingPlacement } from "../types";
import {
  filletGeometry,
  offsetGeometry,
  trimOrExtendGeometry,
  type CadSegment2D,
} from "../utils/cadGeometryKernel";
import { boundsForSiteGeometry } from "../utils/geometryTransforms";
import {
  buildReviewRequiredCommandMeta,
  parseCadNumber,
} from "../utils/previewCadCommandParsing";
import type { CadCommandHistoryEntry } from "./previewPanelTypes";

type UsePreviewCadLineworkCommandsOptions = {
  buildingPlacements: BuildingPlacement[];
  cadFilletRadius: string;
  cadOffsetDistance: string;
  cadSegments: CadSegment2D[];
  cadTransformValue: string;
  lotHeight: number;
  lotWidth: number;
  selectedCadIds: string[];
  selectedCadObject: BuildingPlacement | null | undefined;
  selectedVertex: { id: string; index: number } | null;
  getCadLayer: (item: BuildingPlacement) => string;
  onCreateCustomGeometry: (input: {
    mode: "polyline" | "polygon" | "rect" | "point";
    points: Array<[number, number]>;
    label?: string;
    meta?: Record<string, unknown>;
  }) => void;
  onRemoveBuilding: (id: string) => void;
  onSelectBuilding: (id: string | null) => void;
  onSelectObjects?: (ids: string[]) => void;
  onUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  previewObjectEditableSource: (item: BuildingPlacement) => boolean;
  pushCadCommandFeedback: (
    command: string,
    status: CadCommandHistoryEntry["status"],
    message: string,
  ) => void;
  resolveVisualKind: (item: BuildingPlacement) => string;
  setCadCommandStatus: Dispatch<SetStateAction<string>>;
  setCadSelectionSet: Dispatch<SetStateAction<string[]>>;
  updateCadObject: (
    target: BuildingPlacement,
    updates: Partial<BuildingPlacement>,
    label: string,
  ) => void;
};

export function usePreviewCadLineworkCommands({
  buildingPlacements,
  cadFilletRadius,
  cadOffsetDistance,
  cadSegments,
  cadTransformValue,
  lotHeight,
  lotWidth,
  selectedCadIds,
  selectedCadObject,
  selectedVertex,
  getCadLayer,
  onCreateCustomGeometry,
  onRemoveBuilding,
  onSelectBuilding,
  onSelectObjects,
  onUpdateBuilding,
  previewObjectEditableSource,
  pushCadCommandFeedback,
  resolveVisualKind,
  setCadCommandStatus,
  setCadSelectionSet,
  updateCadObject,
}: UsePreviewCadLineworkCommandsOptions) {
  const joinSelectedCadObjects = useCallback(() => {
    const selectedTargets = selectedCadIds
      .map((id) => buildingPlacements.find((item) => item.id === id))
      .filter((item): item is BuildingPlacement => Boolean(
        item &&
          item.type !== "site" &&
          !item.locked &&
          !item.meta?.ui_hidden &&
          Array.isArray(item.geometry) &&
          item.geometry.length >= 2,
      ));
    if (selectedTargets.length < 2) {
      pushCadCommandFeedback("JOIN", "blocked", "JOIN blocked: select two or more editable draft line/area objects first.");
      return;
    }
    const remaining = selectedTargets.map((item) => ({
      item,
      geometry: (item.geometry as Array<[number, number]>).map(([x, y]) => [x, y] as [number, number]),
    }));
    const first = remaining.shift();
    if (!first) {
      pushCadCommandFeedback("JOIN", "blocked", "JOIN blocked: selected geometry could not be read.");
      return;
    }
    const joinedGeometry = [...first.geometry];
    const distance = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1]);
    while (remaining.length) {
      const tail = joinedGeometry[joinedGeometry.length - 1];
      let bestIndex = 0;
      let bestReverse = false;
      let bestDistance = Number.POSITIVE_INFINITY;
      remaining.forEach((candidate, index) => {
        const start = candidate.geometry[0];
        const end = candidate.geometry[candidate.geometry.length - 1];
        const startDistance = distance(tail, start);
        const endDistance = distance(tail, end);
        if (startDistance < bestDistance) {
          bestDistance = startDistance;
          bestIndex = index;
          bestReverse = false;
        }
        if (endDistance < bestDistance) {
          bestDistance = endDistance;
          bestIndex = index;
          bestReverse = true;
        }
      });
      const [next] = remaining.splice(bestIndex, 1);
      const nextGeometry = bestReverse ? [...next.geometry].reverse() : next.geometry;
      const nextStart = nextGeometry[0];
      joinedGeometry.push(
        ...(distance(tail, nextStart) < 0.001 ? nextGeometry.slice(1) : nextGeometry),
      );
    }
    if (joinedGeometry.length < 2) {
      pushCadCommandFeedback("JOIN", "blocked", "JOIN blocked: selected geometry did not produce a joined line.");
      return;
    }
    const joinedLabel =
      selectedTargets.length === 2
        ? `${selectedTargets[0].label || "Draft"} + ${selectedTargets[1].label || "Draft"} Join`
        : `Joined Draft Object ${selectedTargets.length}`;
    selectedTargets.forEach((item) => {
      onUpdateBuilding(item.id, {
        meta: {
          ...(item.meta ?? {}),
          ui_hidden: true,
          joined_source_trace: true,
          joined_into_label: joinedLabel,
          review_status: "engineer_review_required",
          engineering_status: "draft_review_required",
          construction_release_allowed: false,
        },
      });
    });
    onCreateCustomGeometry({
      mode: "polyline",
      points: joinedGeometry,
      label: joinedLabel,
      meta: buildReviewRequiredCommandMeta("JOIN", {
        joined_from_object_ids: selectedTargets.map((item) => item.id),
        joined_from_labels: selectedTargets.map((item) => item.label),
        joined_source_count: selectedTargets.length,
        cad_layer: getCadLayer(selectedTargets[0]),
        source_type: "manual_drawn_join",
      }),
    });
    setCadSelectionSet([]);
    onSelectObjects?.([]);
    pushCadCommandFeedback("JOIN", "applied", `JOIN created ${joinedLabel} from ${selectedTargets.length} draft source objects; sources are hidden as review trace pieces.`);
  }, [
    buildingPlacements,
    getCadLayer,
    onCreateCustomGeometry,
    onSelectObjects,
    onUpdateBuilding,
    pushCadCommandFeedback,
    selectedCadIds,
    setCadSelectionSet,
  ]);

  const splitSelectedJoinedObject = useCallback(() => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("SPLIT", "blocked", "SPLIT blocked: select one joined draft object first.");
      return;
    }
    const sourceIds = Array.isArray(selectedCadObject.meta?.joined_from_object_ids)
      ? selectedCadObject.meta.joined_from_object_ids.map((id) => String(id)).filter(Boolean)
      : [];
    if (!sourceIds.length) {
      pushCadCommandFeedback("SPLIT", "blocked", "SPLIT blocked: selected object has no joined source trace to restore.");
      return;
    }
    const sourceObjects = buildingPlacements.filter((item) => sourceIds.includes(item.id));
    if (!sourceObjects.length) {
      pushCadCommandFeedback("SPLIT", "blocked", "SPLIT blocked: joined source trace objects are missing.");
      return;
    }
    sourceObjects.forEach((item) => {
      onUpdateBuilding(item.id, {
        meta: {
          ...(item.meta ?? {}),
          ui_hidden: false,
          split_from_joined_object_id: selectedCadObject.id,
          split_from_joined_label: selectedCadObject.label,
          review_status: "engineer_review_required",
          engineering_status: "draft_review_required",
          construction_release_allowed: false,
        },
      });
    });
    onRemoveBuilding(selectedCadObject.id);
    setCadSelectionSet(sourceObjects.map((item) => item.id));
    onSelectObjects?.(sourceObjects.map((item) => item.id));
    onSelectBuilding(sourceObjects[0]?.id ?? null);
    pushCadCommandFeedback("SPLIT", "applied", `SPLIT restored ${sourceObjects.length} source trace object${sourceObjects.length === 1 ? "" : "s"} from ${selectedCadObject.label || "joined object"}.`);
  }, [
    buildingPlacements,
    onRemoveBuilding,
    onSelectBuilding,
    onSelectObjects,
    onUpdateBuilding,
    pushCadCommandFeedback,
    selectedCadObject,
    setCadSelectionSet,
  ]);

  const changeSelectedPolylineState = useCallback((mode: "close" | "open" | "reverse") => {
    const command = mode === "close" ? "CLOSE" : mode === "open" ? "OPEN" : "REVERSE";
    if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry) || selectedCadObject.geometry.length < 2) {
      pushCadCommandFeedback(command, "blocked", `${command} blocked: select one editable draft line or area object first.`);
      return;
    }
    if (selectedCadObject.type === "site" || selectedCadObject.locked || !previewObjectEditableSource(selectedCadObject)) {
      pushCadCommandFeedback(command, "blocked", `${command} blocked: selected object is locked, source-only, or required project evidence.`);
      return;
    }
    const geometry = (selectedCadObject.geometry as Array<[number, number]>).map(([x, y]) => [x, y] as [number, number]);
    if (geometry.length < 2) {
      pushCadCommandFeedback(command, "blocked", `${command} blocked: selected object has no editable vertices.`);
      return;
    }
    const first = geometry[0];
    const last = geometry[geometry.length - 1];
    const explicitlyClosed = Boolean(last && Math.hypot(first[0] - last[0], first[1] - last[1]) < 0.001);
    const stripDuplicateClosure = () => (explicitlyClosed ? geometry.slice(0, -1) : geometry);
    if (mode === "close") {
      const base = stripDuplicateClosure();
      if (base.length < 3) {
        pushCadCommandFeedback("CLOSE", "blocked", "CLOSE blocked: draft linework needs at least three vertices to become a closed area.");
        return;
      }
      if (selectedCadObject.geometryType !== "polyline" && !explicitlyClosed) {
        pushCadCommandFeedback("CLOSE", "info", "CLOSE skipped: selected object is already treated as closed area geometry.");
        return;
      }
      const nextGeometry = [...base, base[0]];
      const nextBounds = boundsForSiteGeometry(nextGeometry);
      updateCadObject(
        selectedCadObject,
        {
          geometry: nextGeometry,
          geometryType: "polygon",
          x: nextBounds.minX,
          y: nextBounds.minY,
          w: Math.max(5, nextBounds.width),
          d: Math.max(5, nextBounds.height),
          meta: {
            ...(selectedCadObject.meta ?? {}),
            cad_polyline_closed: true,
            cad_polyline_state_command: "CLOSE",
            engineering_status: "draft_review_required",
            review_status: "engineer_review_required",
            construction_release_allowed: false,
          },
        },
        "Close polyline",
      );
      pushCadCommandFeedback("CLOSE", "applied", "CLOSE converted selected draft linework into closed review area geometry.");
      return;
    }
    if (mode === "open") {
      if (selectedCadObject.geometryType === "polyline" && !explicitlyClosed) {
        pushCadCommandFeedback("OPEN", "info", "OPEN skipped: selected linework is already open.");
        return;
      }
      const nextGeometry = stripDuplicateClosure();
      if (nextGeometry.length < 2) {
        pushCadCommandFeedback("OPEN", "blocked", "OPEN blocked: opening this object would leave too few vertices.");
        return;
      }
      const nextBounds = boundsForSiteGeometry(nextGeometry);
      updateCadObject(
        selectedCadObject,
        {
          geometry: nextGeometry,
          geometryType: "polyline",
          x: nextBounds.minX,
          y: nextBounds.minY,
          w: Math.max(5, nextBounds.width),
          d: Math.max(5, nextBounds.height),
          meta: {
            ...(selectedCadObject.meta ?? {}),
            cad_polyline_closed: false,
            cad_polyline_state_command: "OPEN",
            engineering_status: "draft_review_required",
            review_status: "engineer_review_required",
            construction_release_allowed: false,
          },
        },
        "Open polyline",
      );
      pushCadCommandFeedback("OPEN", "applied", "OPEN converted selected draft area into open review linework.");
      return;
    }
    const nextGeometry = [...geometry].reverse();
    const nextBounds = boundsForSiteGeometry(nextGeometry);
    updateCadObject(
      selectedCadObject,
      {
        geometry: nextGeometry,
        x: nextBounds.minX,
        y: nextBounds.minY,
        w: Math.max(5, nextBounds.width),
        d: Math.max(5, nextBounds.height),
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_polyline_state_command: "REVERSE",
          engineering_status: "draft_review_required",
          review_status: "engineer_review_required",
          construction_release_allowed: false,
        },
      },
      "Reverse polyline",
    );
    pushCadCommandFeedback("REVERSE", "applied", "REVERSE flipped the selected draft linework vertex order.");
  }, [previewObjectEditableSource, pushCadCommandFeedback, selectedCadObject, updateCadObject]);

  const toggleSelectedCadHatch = useCallback(() => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("HATCH", "blocked", "HATCH blocked: select a closed draft area, box, building, basin, parking field, or closed polyline first.");
      return;
    }
    if (selectedCadObject.type === "site" || selectedCadObject.locked || !previewObjectEditableSource(selectedCadObject)) {
      pushCadCommandFeedback("HATCH", "blocked", "HATCH blocked: selected object is locked, source-only, or required project evidence.");
      return;
    }
    const geometry = Array.isArray(selectedCadObject.geometry)
      ? (selectedCadObject.geometry as Array<[number, number]>)
      : [];
    const first = geometry[0];
    const last = geometry[geometry.length - 1];
    const closedLinework = Boolean(
      geometry.length >= 4 &&
        first &&
        last &&
        Math.hypot(first[0] - last[0], first[1] - last[1]) < 0.001,
    );
    const closedArea =
      selectedCadObject.geometryType === "polygon" ||
      selectedCadObject.geometryType === "rect" ||
      (!selectedCadObject.geometryType && selectedCadObject.type !== "utility_corridor") ||
      Boolean(selectedCadObject.meta?.cad_polyline_closed) ||
      closedLinework;
    if (!closedArea) {
      pushCadCommandFeedback("HATCH", "blocked", "HATCH blocked: select a closed draft area, or use CLOSE first to turn linework into an area.");
      return;
    }
    const enabled = Boolean(selectedCadObject.meta?.cad_hatch_enabled);
    const visualKind = resolveVisualKind(selectedCadObject);
    const pattern =
      visualKind === "water"
        ? "water"
        : visualKind === "landscape"
          ? "landscape"
          : "diagonal";
    updateCadObject(
      selectedCadObject,
      {
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_hatch_enabled: !enabled,
          cad_hatch_pattern: pattern,
          cad_hatch_source: "manual_drawn_review",
          engineering_status: "draft_review_required",
          review_status: "engineer_review_required",
          construction_release_allowed: false,
        },
      },
      enabled ? "Remove hatch" : "Apply hatch",
    );
    pushCadCommandFeedback(
      "HATCH",
      "applied",
      enabled
        ? "HATCH removed from selected draft area."
        : "HATCH applied as draft review fill; it is visual drafting context only and not engineering evidence.",
    );
  }, [previewObjectEditableSource, pushCadCommandFeedback, resolveVisualKind, selectedCadObject, updateCadObject]);

  const offsetSelectedCadObject = useCallback(() => {
    if (!selectedCadObject) return;
    const distance = parseCadNumber(cadOffsetDistance, 0);
    if (!distance) return;
    if (!Array.isArray(selectedCadObject.geometry)) {
      setCadCommandStatus("OFFSET blocked: selected object has no editable line or polygon vertices.");
      return;
    }
    const result = offsetGeometry(
      selectedCadObject.geometry as Array<[number, number]>,
      distance,
      selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect",
    );
    if (!result.ok) {
      setCadCommandStatus(`OFFSET blocked: ${result.reason}`);
      return;
    }
    const nextBounds = boundsForSiteGeometry(result.value);
    const updates: Partial<BuildingPlacement> = {
      geometry: result.value,
      x: nextBounds.minX,
      y: nextBounds.minY,
      w: Math.max(5, nextBounds.width),
      d: Math.max(5, nextBounds.height),
      meta: {
        ...(selectedCadObject.meta ?? {}),
        cad_offset_distance_ft: distance,
        geometry_kernel_warnings: result.warnings ?? [],
      },
    };
    updateCadObject(selectedCadObject, updates, "Offset");
    setCadCommandStatus(`OFFSET applied ${distance} ft as draft review geometry.`);
  }, [cadOffsetDistance, selectedCadObject, setCadCommandStatus, updateCadObject]);

  const offsetSelectedCadObjectBy = useCallback((valueOverride?: string) => {
    if (!selectedCadObject) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET blocked: select one editable draft object first.");
      return;
    }
    const distance = parseCadNumber(valueOverride ?? cadOffsetDistance, 0);
    if (!distance) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET blocked: provide a non-zero distance like OFFSET 10.");
      return;
    }
    if (!Array.isArray(selectedCadObject.geometry)) {
      pushCadCommandFeedback("OFFSET", "blocked", "OFFSET blocked: selected object has no editable line or polygon vertices.");
      return;
    }
    const result = offsetGeometry(
      selectedCadObject.geometry as Array<[number, number]>,
      distance,
      selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect",
    );
    if (!result.ok) {
      pushCadCommandFeedback("OFFSET", "blocked", `OFFSET blocked: ${result.reason}`);
      return;
    }
    const nextBounds = boundsForSiteGeometry(result.value);
    const updates: Partial<BuildingPlacement> = {
      geometry: result.value,
      x: nextBounds.minX,
      y: nextBounds.minY,
      w: Math.max(5, nextBounds.width),
      d: Math.max(5, nextBounds.height),
      meta: {
        ...(selectedCadObject.meta ?? {}),
        cad_offset_distance_ft: distance,
        geometry_kernel_warnings: result.warnings ?? [],
      },
    };
    updateCadObject(selectedCadObject, updates, "Offset");
    pushCadCommandFeedback("OFFSET", "applied", `OFFSET applied ${distance} ft as draft review geometry.`);
  }, [cadOffsetDistance, pushCadCommandFeedback, selectedCadObject, updateCadObject]);

  const trimExtendSelectedCadObject = useCallback(
    (kind: "trim" | "extend", amountOverride?: string) => {
      if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry)) {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: select one editable line/polyline draft object first.`);
        return;
      }
      const geometry = selectedCadObject.geometry as Array<[number, number]>;
      const amount = Math.max(1, parseCadNumber(amountOverride ?? cadTransformValue, 10));
      if (selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect") {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: polygon trim/extend needs an explicit cutting edge and is not applied automatically.`);
        return;
      }
      const result = trimOrExtendGeometry(geometry, kind, cadSegments, {
        amountFt: amount,
        selectedObjectId: selectedCadObject.id,
        siteWidth: lotWidth,
        siteHeight: lotHeight,
      });
      if (!result.ok) {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: ${result.reason}`);
        return;
      }
      const nextBounds = boundsForSiteGeometry(result.value);
      updateCadObject(
        selectedCadObject,
        {
          geometry: result.value,
          x: nextBounds.minX,
          y: nextBounds.minY,
          w: Math.max(5, nextBounds.width),
          d: Math.max(5, nextBounds.height),
        },
        kind === "trim" ? "Trim" : "Extend",
      );
      pushCadCommandFeedback(kind, "applied", `${kind.toUpperCase()} applied to terminal segment as draft review geometry.`);
    },
    [cadSegments, cadTransformValue, lotHeight, lotWidth, pushCadCommandFeedback, selectedCadObject, updateCadObject],
  );

  const filletSelectedCadObject = useCallback(() => {
    if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry)) {
      pushCadCommandFeedback("FILLET", "blocked", "FILLET blocked: select one editable draft object with vertices first.");
      return;
    }
    const geometry = selectedCadObject.geometry as Array<[number, number]>;
    const radius = Math.max(1, parseCadNumber(cadFilletRadius, 5));
    const index = selectedVertex?.id === selectedCadObject.id ? selectedVertex.index : 1;
    const result = filletGeometry(
      geometry,
      radius,
      index,
      selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect",
    );
    if (!result.ok) {
      pushCadCommandFeedback("FILLET", "blocked", `FILLET blocked: ${result.reason}`);
      return;
    }
    const nextBounds = boundsForSiteGeometry(result.value);
    updateCadObject(
      selectedCadObject,
      {
        geometry: result.value,
        x: nextBounds.minX,
        y: nextBounds.minY,
        w: Math.max(5, nextBounds.width),
        d: Math.max(5, nextBounds.height),
        meta: {
          ...(selectedCadObject.meta ?? {}),
          cad_fillet_radius_ft: radius,
          cad_fillet_storage: "tangent_chord_vertices",
          geometry_kernel_warnings: result.warnings ?? [],
        },
      },
      "Fillet",
    );
    pushCadCommandFeedback("FILLET", "applied", "FILLET applied as tangent chord draft geometry.");
  }, [cadFilletRadius, pushCadCommandFeedback, selectedCadObject, selectedVertex, updateCadObject]);

  return {
    changeSelectedPolylineState,
    filletSelectedCadObject,
    joinSelectedCadObjects,
    offsetSelectedCadObject,
    offsetSelectedCadObjectBy,
    splitSelectedJoinedObject,
    toggleSelectedCadHatch,
    trimExtendSelectedCadObject,
  };
}
