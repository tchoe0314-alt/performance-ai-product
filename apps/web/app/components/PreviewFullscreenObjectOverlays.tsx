import type { MouseEvent as ReactMouseEvent } from "react";

import type { BuildingPlacement } from "../types";

type PreviewRectPercent = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type PreviewFullscreenEditableObjectOverlayProps = {
  rectPct: PreviewRectPercent;
  rotation: number;
  hitZIndex: number;
  allowMapInteraction: boolean;
  allowItemInteraction: boolean;
  placementMode: boolean;
  borderColor: string;
  outlineColor?: string;
  onMoveMouseDown: (event: ReactMouseEvent<HTMLDivElement>) => void;
  onRotateMouseDown: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onRotateClick: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onResizeMouseDown: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onSelect: (event: ReactMouseEvent<HTMLDivElement>) => void;
};

type PreviewFullscreenSuggestedObjectOverlayProps = {
  item: BuildingPlacement;
  rectPct: PreviewRectPercent;
  rotation: number;
  hitZIndex: number;
  borderColor: string;
  onHover: (id: string | null) => void;
  onSelect: (event: ReactMouseEvent<HTMLDivElement>) => void;
};

export function PreviewFullscreenEditableObjectOverlay({
  rectPct,
  rotation,
  hitZIndex,
  allowMapInteraction,
  allowItemInteraction,
  placementMode,
  borderColor,
  outlineColor,
  onMoveMouseDown,
  onRotateMouseDown,
  onRotateClick,
  onResizeMouseDown,
  onSelect,
}: PreviewFullscreenEditableObjectOverlayProps) {
  return (
    <div
      data-object-overlay
      className={`${allowMapInteraction || !allowItemInteraction ? "pointer-events-none" : "pointer-events-auto"} absolute`}
      style={{
        left: `${rectPct.left}%`,
        top: `${rectPct.top}%`,
        width: `${rectPct.width}%`,
        height: `${rectPct.height}%`,
        zIndex: hitZIndex,
        scrollMarginBottom: "10rem",
        transform: `rotate(${rotation}deg)`,
        transformOrigin: "center",
        cursor: placementMode ? "move" : "default",
      }}
      onMouseDown={onMoveMouseDown}
      onClick={onSelect}
    >
      <div
        className={`pointer-events-none h-full w-full rounded-[8px] border bg-slate-900/10 transition ${borderColor}`}
        style={outlineColor ? { borderColor: outlineColor } : undefined}
      />
      <button
        type="button"
        className="absolute -right-3 -top-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
        onMouseDown={onRotateMouseDown}
        onClick={onRotateClick}
      >
        R
      </button>
      <button
        type="button"
        className="absolute -right-3 -bottom-3 h-6 w-6 rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600 shadow"
        onMouseDown={onResizeMouseDown}
      >
        Z
      </button>
      <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
        Snap 5ft
      </div>
    </div>
  );
}

export function PreviewFullscreenSuggestedObjectOverlay({
  item,
  rectPct,
  rotation,
  hitZIndex,
  borderColor,
  onHover,
  onSelect,
}: PreviewFullscreenSuggestedObjectOverlayProps) {
  return (
    <div
      className="pointer-events-auto absolute"
      style={{
        left: `${rectPct.left}%`,
        top: `${rectPct.top}%`,
        width: `${rectPct.width}%`,
        height: `${rectPct.height}%`,
        zIndex: hitZIndex,
        scrollMarginBottom: "10rem",
        transform: `rotate(${rotation}deg)`,
        transformOrigin: "center",
        cursor: "pointer",
      }}
      onMouseEnter={() => onHover(item.id)}
      onMouseLeave={() => onHover(null)}
      onClick={onSelect}
    >
      <div className={`h-full w-full rounded-[8px] border border-dashed bg-slate-50/70 transition ${borderColor}`} />
      <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
        Suggested
      </div>
    </div>
  );
}
