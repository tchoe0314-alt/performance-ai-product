import type { BuildingPlacement } from "../types";

export type PreviewObjectManagerCounts = {
  total: number;
  visible: number;
  draft: number;
  generated: number;
};

export const buildPreviewObjectManagerRows = (items: BuildingPlacement[]) => {
  const rows = new Map<string, BuildingPlacement>();
  items.forEach((item) => {
    if (!rows.has(item.id)) rows.set(item.id, item);
  });
  return Array.from(rows.values()).sort((a, b) => {
    const aHidden = a.meta?.ui_hidden ? 1 : 0;
    const bHidden = b.meta?.ui_hidden ? 1 : 0;
    if (aHidden !== bHidden) return aHidden - bHidden;
    if (a.type === "site" && b.type !== "site") return -1;
    if (b.type === "site" && a.type !== "site") return 1;
    return (a.label || a.id).localeCompare(b.label || b.id);
  });
};

export const buildPreviewObjectManagerCounts = ({
  rows,
  hiddenCadLayers,
  getCadLayer,
}: {
  rows: BuildingPlacement[];
  hiddenCadLayers: string[];
  getCadLayer: (item: BuildingPlacement) => string;
}): PreviewObjectManagerCounts => ({
  total: rows.length,
  visible: rows.filter((item) => !item.meta?.ui_hidden && !hiddenCadLayers.includes(getCadLayer(item))).length,
  draft: rows.filter(
    (item) =>
      item.source === "manual_drawn" ||
      item.type === "custom" ||
      item.meta?.engineering_status === "draft_review_required",
  ).length,
  generated: rows.filter((item) => item.generated || item.source === "generated").length,
});
