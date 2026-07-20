import type { BuildingPlacement } from "../types";
import type { DraftUndoAction, RecentChange } from "./dashboardTypes";
import { getObjectDisplayType } from "./objectGeometry";
import { SITE_OBJECT_CATALOG } from "./siteObjectCatalog";

type ObjectChange = Omit<RecentChange, "id" | "createdAt">;

export function buildDashboardObjectUpdateRecentChange({
  target,
  updates,
  undo,
}: {
  target: BuildingPlacement;
  updates: Partial<BuildingPlacement>;
  undo: DraftUndoAction;
}): ObjectChange | null {
  if (typeof updates.label === "string" && updates.label !== target.label) {
    return {
      type: "object_renamed",
      label: "Object renamed",
      detail: `${target.label} renamed to ${updates.label || "Unnamed object"}.`,
      undo,
    };
  }
  if (updates.type && updates.type !== target.type) {
    return {
      type: "object_type_changed",
      label: "Object type changed",
      detail: `${target.label} changed from ${getObjectDisplayType(target)} to ${SITE_OBJECT_CATALOG[updates.type]?.label ?? updates.type}.`,
      undo,
    };
  }
  if (
    updates.meta &&
    "ui_hidden" in updates.meta &&
    Boolean(updates.meta.ui_hidden) !== Boolean(target.meta?.ui_hidden)
  ) {
    return {
      type: "object_visibility_changed",
      label: Boolean(updates.meta.ui_hidden) ? "Object hidden" : "Object shown",
      detail: `${target.label} is now ${Boolean(updates.meta.ui_hidden) ? "hidden from" : "visible in"} the preview.`,
      undo,
    };
  }
  if (
    updates.meta &&
    ("ui_color" in updates.meta || "color" in updates.meta || "style" in updates.meta)
  ) {
    return {
      type: "object_style_changed",
      label: "Object style changed",
      detail: `${target.label} style changed.`,
      undo,
    };
  }
  if (typeof updates.locked === "boolean" && updates.locked !== Boolean(target.locked)) {
    return {
      type: "object_style_changed",
      label: updates.locked ? "Object locked" : "Object unlocked",
      detail: `${target.label} was ${updates.locked ? "locked" : "unlocked"}.`,
      undo,
    };
  }
  if (
    typeof updates.x === "number" ||
    typeof updates.y === "number" ||
    typeof updates.w === "number" ||
    typeof updates.d === "number" ||
    typeof updates.h === "number" ||
    typeof updates.rotation === "number" ||
    Array.isArray(updates.geometry)
  ) {
    return {
      type: "object_style_changed",
      label: "Object geometry changed",
      detail: `${target.label} geometry changed.`,
      undo,
    };
  }
  return null;
}
