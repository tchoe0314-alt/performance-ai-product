import type { BuildingPlacement } from "../types";

type LotBounds = { w: number; h: number };
export type GradingDrainageReviewContextMode = "grading" | "drainage" | "both";

export function buildGradingDrainageReviewContextPlacements({
  lot,
  mode = "both",
}: {
  lot: LotBounds;
  mode?: GradingDrainageReviewContextMode;
}) {
  const stamp = Date.now();
  const wantsGrading = mode === "grading" || mode === "both";
  const wantsDrainage = mode === "drainage" || mode === "both";
  const additions: BuildingPlacement[] = [];
  const makeLine = (
    suffix: string,
    label: string,
    geometry: Array<[number, number]>,
    meta: Record<string, unknown>,
  ): BuildingPlacement => {
    const bounds = geometry.reduce(
      (acc, [x, y]) => ({
        minX: Math.min(acc.minX, x),
        minY: Math.min(acc.minY, y),
        maxX: Math.max(acc.maxX, x),
        maxY: Math.max(acc.maxY, y),
      }),
      { minX: lot.w, minY: lot.h, maxX: 0, maxY: 0 },
    );
    return {
      id: `review-${suffix}-${stamp}-${Math.random().toString(36).slice(2, 8)}`,
      label,
      type: "custom",
      w: Math.max(10, bounds.maxX - bounds.minX),
      d: Math.max(10, bounds.maxY - bounds.minY),
      x: bounds.minX,
      y: bounds.minY,
      rotation: 0,
      locked: false,
      placed: true,
      source: "user",
      generated: false,
      geometryType: "polyline",
      geometry,
      capabilities: {
        movable: true,
        resizable: false,
        rotatable: false,
        deletable: true,
      },
      systemDependencies: ["grading", "drainage"],
      meta: {
        command_created: true,
        source_confidence: "user_drawn_review_required",
        draft_review_required: true,
        construction_release_allowed: false,
        ...meta,
      },
    };
  };
  if (wantsGrading) {
    additions.push(
      makeLine(
        "grading-fall-line",
        "Review Grading Fall Line",
        [
          [lot.w * 0.18, lot.h * 0.22],
          [lot.w * 0.42, lot.h * 0.34],
          [lot.w * 0.70, lot.h * 0.58],
          [lot.w * 0.84, lot.h * 0.74],
        ],
        {
          cad_layer: "C-GRADE",
          ui_color: "#64748b",
          role: "grading_fall_direction_review_line",
          slope_context: "draft_review_required",
        },
      ),
    );
  }
  if (wantsDrainage) {
    additions.push(
      makeLine(
        "drainage-area-cue",
        "Review Drainage Area Cue",
        [
          [lot.w * 0.22, lot.h * 0.28],
          [lot.w * 0.58, lot.h * 0.30],
          [lot.w * 0.78, lot.h * 0.56],
          [lot.w * 0.70, lot.h * 0.78],
          [lot.w * 0.28, lot.h * 0.72],
          [lot.w * 0.22, lot.h * 0.28],
        ],
        {
          cad_layer: "C-DRAIN",
          ui_color: "#0ea5e9",
          role: "drainage_area_review_boundary",
          hydrology_context: "draft_review_required",
        },
      ),
    );
  }
  return additions;
}
