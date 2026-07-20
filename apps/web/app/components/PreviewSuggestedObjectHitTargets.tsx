import type { MouseEvent as ReactMouseEvent } from "react";

import type { BuildingPlacement } from "../types";
import { PreviewObjectHoverCard } from "./PreviewObjectHoverCard";
import type { PreviewHoverDetail } from "../utils/previewHoverDetails";

type PreviewRectPercent = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type PreviewSuggestedObjectHitTargetsProps = {
  suggestedPlacements: BuildingPlacement[];
  passiveOverlayPointerEvents: string;
  drawingOwnsCanvasHits: boolean;
  hoveredObjectId: string | null;
  objectHoverDetails: PreviewHoverDetail[];
  mapAnchoredRectPercent: (item: BuildingPlacement) => PreviewRectPercent;
  rectIntersectsPreview: (rect: PreviewRectPercent) => boolean;
  resolveObjectHitZIndex: (item: BuildingPlacement, rect: PreviewRectPercent, selected: boolean) => number;
  selectedBuildingId: string | null;
  showMap: boolean;
  handleBuildingMouseDown: (
    event: ReactMouseEvent<HTMLDivElement>,
    item: BuildingPlacement,
    mode?: "move" | "resize" | "rotate",
  ) => void;
  setHoveredObjectId: (id: string | null) => void;
};

export function PreviewSuggestedObjectHitTargets({
  suggestedPlacements,
  passiveOverlayPointerEvents,
  drawingOwnsCanvasHits,
  hoveredObjectId,
  objectHoverDetails,
  mapAnchoredRectPercent,
  rectIntersectsPreview,
  resolveObjectHitZIndex,
  selectedBuildingId,
  showMap,
  handleBuildingMouseDown,
  setHoveredObjectId,
}: PreviewSuggestedObjectHitTargetsProps) {
  return (
    <>
      {suggestedPlacements
        .filter((item) => item.placed && Number.isFinite(item.x) && Number.isFinite(item.y))
        .map((item) => {
          const rectPct = mapAnchoredRectPercent(item);
          if (!rectIntersectsPreview(rectPct)) return null;
          const rotation = showMap ? 0 : (item.rotation ?? 0);
          const hitZIndex = resolveObjectHitZIndex(item, rectPct, selectedBuildingId === item.id);
          return (
            <div
              key={item.id}
              className={`${passiveOverlayPointerEvents} absolute`}
              style={{
                left: `${rectPct.left}%`,
                top: `${rectPct.top}%`,
                width: `${rectPct.width}%`,
                height: `${rectPct.height}%`,
                zIndex: hitZIndex,
                scrollMarginBottom: "10rem",
                transform: `rotate(${rotation}deg)`,
                transformOrigin: "center",
                cursor: "move",
              }}
              onMouseDown={(event) => {
                if (drawingOwnsCanvasHits) return;
                handleBuildingMouseDown(event, item, "move");
              }}
              onMouseEnter={() => {
                if (drawingOwnsCanvasHits) return;
                setHoveredObjectId(item.id);
              }}
              onMouseLeave={() => setHoveredObjectId(null)}
            >
              <div className="h-full w-full rounded-[8px] border border-dashed border-amber-400 bg-amber-200/10" />
              {hoveredObjectId === item.id ? <PreviewObjectHoverCard details={objectHoverDetails} /> : null}
            </div>
          );
        })}
    </>
  );
}
