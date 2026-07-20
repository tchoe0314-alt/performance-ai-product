import { useCallback } from "react";

import type { BuildingPlacement } from "../types";
import { transformGeometry } from "../utils/cadGeometryKernel";
import {
  boundsForSiteGeometry,
  translateSiteGeometry,
} from "../utils/geometryTransforms";
import {
  buildDraftGeometryCreatedMessage,
  buildReviewRequiredCommandMeta,
  parseCadNumber,
} from "../utils/previewCadCommandParsing";
import type { CadCommandHistoryEntry, PreviewPanelProps } from "./previewPanelTypes";

type CreateCustomGeometry = PreviewPanelProps["onCreateCustomGeometry"];

type UsePreviewCadTransformCommandsOptions = {
  buildingPlacements: BuildingPlacement[];
  canDrawObjects: boolean;
  cadTransformValue: string;
  selectedCadIds: string[];
  selectedCadObject: BuildingPlacement | null | undefined;
  getCadLayer: (item: BuildingPlacement) => string;
  getObjectGeometryPoints: (item: BuildingPlacement) => Array<[number, number]>;
  onCreateCustomGeometry: CreateCustomGeometry;
  pushCadCommandFeedback: (
    command: string,
    status: CadCommandHistoryEntry["status"],
    message: string,
  ) => void;
  updateCadObject: (
    target: BuildingPlacement,
    updates: Partial<BuildingPlacement>,
    label: string,
  ) => void;
};

export function usePreviewCadTransformCommands({
  buildingPlacements,
  canDrawObjects,
  cadTransformValue,
  selectedCadIds,
  selectedCadObject,
  getCadLayer,
  getObjectGeometryPoints,
  onCreateCustomGeometry,
  pushCadCommandFeedback,
  updateCadObject,
}: UsePreviewCadTransformCommandsOptions) {
  const createCadCommandGeometry = useCallback(
    (
      command: string,
      mode: "polyline" | "polygon" | "rect" | "point",
      points: Array<[number, number]>,
      options: { label?: string; meta?: Record<string, unknown>; minPoints?: number } = {},
    ) => {
      const minPoints = options.minPoints ?? (mode === "point" ? 1 : mode === "rect" ? 2 : mode === "polygon" ? 3 : 2);
      if (!canDrawObjects) {
        pushCadCommandFeedback(command, "blocked", `${command.toUpperCase()} blocked: create or size the drawing canvas before creating draft geometry.`);
        return false;
      }
      if (points.length < minPoints) {
        pushCadCommandFeedback(command, "blocked", `${command.toUpperCase()} blocked: expected at least ${minPoints} coordinate point${minPoints === 1 ? "" : "s"}.`);
        return false;
      }
      onCreateCustomGeometry({
        mode,
        points,
        label: options.label,
        meta: buildReviewRequiredCommandMeta(command, options.meta),
      });
      pushCadCommandFeedback(command, "applied", buildDraftGeometryCreatedMessage(command));
      return true;
    },
    [canDrawObjects, onCreateCustomGeometry, pushCadCommandFeedback],
  );

  const transformSelectedCadObjects = useCallback(
    (kind: "move" | "rotate" | "scale" | "flip_horizontal" | "flip_vertical", valueOverride?: string) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback(kind, "blocked", `${kind.toUpperCase()} blocked: select one or more editable draft objects first.`);
        return;
      }
      const amount = parseCadNumber(valueOverride ?? cadTransformValue, kind === "scale" ? 1 : 0);
      let applied = 0;
      let blocked = 0;
      selectedCadIds.forEach((id) => {
        const target = buildingPlacements.find((item) => item.id === id);
        if (!target || target.locked || target.type === "site") {
          blocked += 1;
          return;
        }
        if (kind === "move") {
          const updates: Partial<BuildingPlacement> = {
            x: (target.x ?? 0) + amount,
            y: (target.y ?? 0) + amount,
          };
          if (Array.isArray(target.geometry)) {
            const moved = transformGeometry(target.geometry as Array<[number, number]>, "move", amount);
            if (!moved.ok) {
              blocked += 1;
              pushCadCommandFeedback("MOVE", "blocked", `MOVE blocked: ${moved.reason}`);
              return;
            }
            updates.geometry = moved.value;
          }
          updateCadObject(target, updates, "Move");
          applied += 1;
          return;
        }
        if (kind === "rotate") {
          const updates: Partial<BuildingPlacement> = { rotation: ((target.rotation ?? 0) + amount + 360) % 360 };
          if (Array.isArray(target.geometry)) {
            const rotated = transformGeometry(target.geometry as Array<[number, number]>, "rotate", amount);
            if (!rotated.ok) {
              blocked += 1;
              pushCadCommandFeedback("ROTATE", "blocked", `ROTATE blocked: ${rotated.reason}`);
              return;
            }
            updates.geometry = rotated.value;
            const nextBounds = boundsForSiteGeometry(rotated.value);
            updates.x = nextBounds.minX;
            updates.y = nextBounds.minY;
            updates.w = Math.max(5, nextBounds.width);
            updates.d = Math.max(5, nextBounds.height);
          }
          updateCadObject(target, updates, "Rotate");
          applied += 1;
          return;
        }
        if (kind === "flip_horizontal" || kind === "flip_vertical") {
          const updates: Partial<BuildingPlacement> = {
            meta: {
              ...(target.meta ?? {}),
              [kind === "flip_horizontal" ? "flipped_horizontal" : "flipped_vertical"]: true,
            },
          };
          if (Array.isArray(target.geometry)) {
            const flipped = transformGeometry(target.geometry as Array<[number, number]>, kind, 0);
            if (!flipped.ok) {
              blocked += 1;
              pushCadCommandFeedback("MIRROR", "blocked", `MIRROR blocked: ${flipped.reason}`);
              return;
            }
            updates.geometry = flipped.value;
          }
          updateCadObject(target, updates, kind === "flip_horizontal" ? "Flip horizontal" : "Flip vertical");
          applied += 1;
          return;
        }
        const factor = amount;
        if (factor <= 0) {
          blocked += 1;
          pushCadCommandFeedback("SCALE", "blocked", "SCALE blocked: scale requires a positive factor.");
          return;
        }
        const nextW = Math.max(1, target.w * factor);
        const nextD = Math.max(1, target.d * factor);
        const updates: Partial<BuildingPlacement> = { w: nextW, d: nextD };
        if (Array.isArray(target.geometry)) {
          const scaled = transformGeometry(target.geometry as Array<[number, number]>, "scale", factor);
          if (!scaled.ok) {
            blocked += 1;
            pushCadCommandFeedback("SCALE", "blocked", `SCALE blocked: ${scaled.reason}`);
            return;
          }
          updates.geometry = scaled.value;
          const nextBounds = boundsForSiteGeometry(scaled.value);
          updates.x = nextBounds.minX;
          updates.y = nextBounds.minY;
          updates.w = Math.max(5, nextBounds.width);
          updates.d = Math.max(5, nextBounds.height);
        }
        updateCadObject(target, updates, "Scale");
        applied += 1;
      });
      if (applied || blocked) {
        pushCadCommandFeedback(
          kind,
          applied ? "applied" : "blocked",
          `${kind === "flip_horizontal" ? "MIRROR H" : kind === "flip_vertical" ? "MIRROR V" : kind.toUpperCase()} ${applied ? `applied to ${applied}` : "blocked for all"} selected object${applied === 1 ? "" : "s"}${blocked ? `; ${blocked} blocked` : ""}.`,
        );
      }
    },
    [buildingPlacements, cadTransformValue, pushCadCommandFeedback, selectedCadIds, updateCadObject],
  );

  const moveSelectedCadObjectsByVector = useCallback(
    (dx: number, dy: number) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback("MOVE", "blocked", "MOVE blocked: select one or more editable draft objects first.");
        return;
      }
      if (!Number.isFinite(dx) || !Number.isFinite(dy) || (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001)) {
        pushCadCommandFeedback("MOVE", "blocked", "MOVE blocked: provide a non-zero displacement like MOVE selected 20,0.");
        return;
      }
      let applied = 0;
      let blocked = 0;
      selectedCadIds.forEach((id) => {
        const target = buildingPlacements.find((item) => item.id === id);
        if (!target || target.locked || target.type === "site") {
          blocked += 1;
          return;
        }
        const updates: Partial<BuildingPlacement> = {
          x: (target.x ?? 0) + dx,
          y: (target.y ?? 0) + dy,
        };
        if (Array.isArray(target.geometry)) {
          updates.geometry = translateSiteGeometry(target.geometry as Array<[number, number]>, { x: dx, y: dy });
        }
        updateCadObject(target, updates, "Move");
        applied += 1;
      });
      pushCadCommandFeedback(
        "MOVE",
        applied ? "applied" : "blocked",
        `MOVE ${applied ? `applied ${dx.toFixed(3).replace(/\.?0+$/, "")},${dy.toFixed(3).replace(/\.?0+$/, "")} to ${applied}` : "blocked for all"} selected draft object${applied === 1 ? "" : "s"}${blocked ? `; ${blocked} blocked` : ""}.`,
      );
    },
    [buildingPlacements, pushCadCommandFeedback, selectedCadIds, updateCadObject],
  );

  const copySelectedCadObjectsByVector = useCallback(
    (vectorOverride?: [number, number]) => {
      if (!selectedCadIds.length) {
        pushCadCommandFeedback("COPY", "blocked", "COPY blocked: select one or more editable draft objects first.");
        return;
      }
      const vector = vectorOverride ?? [10, 10];
      if (!Number.isFinite(vector[0]) || !Number.isFinite(vector[1]) || (Math.abs(vector[0]) < 0.001 && Math.abs(vector[1]) < 0.001)) {
        pushCadCommandFeedback("COPY", "blocked", "COPY blocked: provide a non-zero vector like COPY 20,0.");
        return;
      }
      let created = 0;
      let blocked = 0;
      selectedCadIds.forEach((id) => {
        const target = buildingPlacements.find((item) => item.id === id);
        if (!target || target.locked || target.type === "site") {
          blocked += 1;
          return;
        }
        const selectedGeometry = getObjectGeometryPoints(target);
        if (!selectedGeometry.length) {
          blocked += 1;
          return;
        }
        const copiedGeometry = translateSiteGeometry(selectedGeometry, { x: vector[0], y: vector[1] }) ?? selectedGeometry;
        const mode =
          target.geometryType === "point"
            ? "point"
            : target.geometryType === "polyline"
              ? "polyline"
              : "polygon";
        onCreateCustomGeometry({
          mode,
          points: copiedGeometry,
          label: `${target.label || "Draft object"} Copy`,
          meta: buildReviewRequiredCommandMeta("COPY", {
            copied_from_object_id: target.id,
            copied_object_type: target.type,
            copy_vector: vector,
            source_type: "manual_drawn_copy",
            source_confidence: "draft_review_required",
            cad_layer: getCadLayer(target),
          }),
        });
        created += 1;
      });
      pushCadCommandFeedback(
        "COPY",
        created ? "applied" : "blocked",
        created
          ? `COPY created ${created} draft review cop${created === 1 ? "y" : "ies"} from selected object${selectedCadIds.length === 1 ? "" : "s"}${blocked ? `; ${blocked} blocked` : ""}.`
          : "COPY blocked: selected objects are locked or have no editable draft geometry.",
      );
    },
    [buildingPlacements, getCadLayer, getObjectGeometryPoints, onCreateCustomGeometry, pushCadCommandFeedback, selectedCadIds],
  );

  const alignOrDistributeSelectedCadObjects = useCallback(
    (
      command: "ALIGN" | "DISTRIBUTE",
      mode: "LEFT" | "RIGHT" | "CENTER" | "TOP" | "BOTTOM" | "MIDDLE" | "X" | "Y",
    ) => {
      const selectedTargets = selectedCadIds
        .map((id) => buildingPlacements.find((item) => item.id === id))
        .filter((item): item is BuildingPlacement => Boolean(item && !item.locked && item.type !== "site"));
      const minimum = command === "DISTRIBUTE" ? 3 : 2;
      if (selectedTargets.length < minimum) {
        pushCadCommandFeedback(
          command,
          "blocked",
          `${command} blocked: select at least ${minimum} editable draft objects first.`,
        );
        return;
      }
      const frameForObject = (item: BuildingPlacement) => {
        const points = getObjectGeometryPoints(item);
        const bounds = points.length ? boundsForSiteGeometry(points) : null;
        const left = bounds ? bounds.minX : item.x ?? 0;
        const top = bounds ? bounds.minY : item.y ?? 0;
        const width = Math.max(1, bounds ? bounds.width : item.w ?? 1);
        const height = Math.max(1, bounds ? bounds.height : item.d ?? 1);
        return {
          left,
          top,
          right: left + width,
          bottom: top + height,
          centerX: left + width / 2,
          centerY: top + height / 2,
          width,
          height,
        };
      };
      const moveTargetBy = (target: BuildingPlacement, dx: number, dy: number, label: string) => {
        if (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001) return false;
        const updates: Partial<BuildingPlacement> = {
          x: (target.x ?? 0) + dx,
          y: (target.y ?? 0) + dy,
        };
        if (Array.isArray(target.geometry)) {
          updates.geometry = translateSiteGeometry(target.geometry as Array<[number, number]>, { x: dx, y: dy });
        }
        updateCadObject(target, updates, label);
        return true;
      };

      let moved = 0;
      if (command === "ALIGN") {
        const anchor = selectedTargets[0];
        const anchorFrame = frameForObject(anchor);
        selectedTargets.forEach((target) => {
          const frame = frameForObject(target);
          let dx = 0;
          let dy = 0;
          if (mode === "LEFT") dx = anchorFrame.left - frame.left;
          if (mode === "RIGHT") dx = anchorFrame.right - frame.right;
          if (mode === "CENTER" || mode === "X") dx = anchorFrame.centerX - frame.centerX;
          if (mode === "TOP") dy = anchorFrame.top - frame.top;
          if (mode === "BOTTOM") dy = anchorFrame.bottom - frame.bottom;
          if (mode === "MIDDLE" || mode === "Y") dy = anchorFrame.centerY - frame.centerY;
          if (moveTargetBy(target, dx, dy, `Align ${mode.toLowerCase()}`)) moved += 1;
        });
        pushCadCommandFeedback(
          "ALIGN",
          "applied",
          `ALIGN ${mode} aligned ${selectedTargets.length} selected draft object${selectedTargets.length === 1 ? "" : "s"} to ${anchor.label || "the first selected object"}${moved ? "" : " (already aligned)"}.`,
        );
        return;
      }

      const axis = mode === "Y" || mode === "MIDDLE" ? "Y" : "X";
      const sorted = [...selectedTargets].sort((a, b) => {
        const frameA = frameForObject(a);
        const frameB = frameForObject(b);
        return axis === "X" ? frameA.centerX - frameB.centerX : frameA.centerY - frameB.centerY;
      });
      const firstFrame = frameForObject(sorted[0]);
      const lastFrame = frameForObject(sorted[sorted.length - 1]);
      const start = axis === "X" ? firstFrame.centerX : firstFrame.centerY;
      const end = axis === "X" ? lastFrame.centerX : lastFrame.centerY;
      if (Math.abs(end - start) < 0.001) {
        pushCadCommandFeedback("DISTRIBUTE", "blocked", `DISTRIBUTE ${axis} blocked: selected objects need different ${axis.toLowerCase()} positions.`);
        return;
      }
      const step = (end - start) / (sorted.length - 1);
      sorted.slice(1, -1).forEach((target, index) => {
        const frame = frameForObject(target);
        const desired = start + step * (index + 1);
        const dx = axis === "X" ? desired - frame.centerX : 0;
        const dy = axis === "Y" ? desired - frame.centerY : 0;
        if (moveTargetBy(target, dx, dy, `Distribute ${axis}`)) moved += 1;
      });
      pushCadCommandFeedback(
        "DISTRIBUTE",
        "applied",
        `DISTRIBUTE ${axis} spaced ${selectedTargets.length} selected draft objects evenly${moved ? "" : " (already spaced)"}.`,
      );
    },
    [buildingPlacements, getObjectGeometryPoints, pushCadCommandFeedback, selectedCadIds, updateCadObject],
  );

  const arraySelectedCadObject = useCallback(
    (rowCount: number, columnCount: number, spacing: [number, number]) => {
      if (!selectedCadObject || !Array.isArray(selectedCadObject.geometry)) {
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: select one editable draft object with geometry first.");
        return;
      }
      const rows = Math.max(1, Math.min(20, Math.floor(rowCount || 1)));
      const columns = Math.max(1, Math.min(20, Math.floor(columnCount || 1)));
      if (rows * columns <= 1) {
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: use at least 2 total copies, like ARRAY 2 3 20,15.");
        return;
      }
      const [dx, dy] = spacing;
      if (!Number.isFinite(dx) || !Number.isFinite(dy) || (Math.abs(dx) < 0.001 && Math.abs(dy) < 0.001)) {
        pushCadCommandFeedback("ARRAY", "blocked", "ARRAY blocked: provide a non-zero spacing vector like ARRAY 2 3 20,15.");
        return;
      }
      const sourceGeometry = selectedCadObject.geometry as Array<[number, number]>;
      let created = 0;
      for (let row = 0; row < rows; row += 1) {
        for (let column = 0; column < columns; column += 1) {
          if (row === 0 && column === 0) continue;
          const copiedGeometry = translateSiteGeometry(sourceGeometry, { x: dx * column, y: dy * row }) ?? sourceGeometry;
          const ok = createCadCommandGeometry("ARRAY", selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect" ? "polygon" : "polyline", copiedGeometry, {
            label: `${selectedCadObject.label || "Draft object"} Array ${row + 1}-${column + 1}`,
            meta: {
              array_source_object_id: selectedCadObject.id,
              array_rows: rows,
              array_columns: columns,
              array_spacing: [dx, dy],
            },
            minPoints: selectedCadObject.geometryType === "polygon" || selectedCadObject.geometryType === "rect" ? 3 : 2,
          });
          if (ok) created += 1;
        }
      }
      pushCadCommandFeedback("ARRAY", created ? "applied" : "blocked", created ? `ARRAY created ${created} draft review cop${created === 1 ? "y" : "ies"} from ${selectedCadObject.label || "selected object"}.` : "ARRAY blocked: no copies could be created.");
    },
    [createCadCommandGeometry, pushCadCommandFeedback, selectedCadObject],
  );

  return {
    alignOrDistributeSelectedCadObjects,
    arraySelectedCadObject,
    copySelectedCadObjectsByVector,
    createCadCommandGeometry,
    moveSelectedCadObjectsByVector,
    transformSelectedCadObjects,
  };
}
