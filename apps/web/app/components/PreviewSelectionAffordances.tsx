import type { MouseEvent as ReactMouseEvent, Ref } from "react";

import type { BuildingPlacement } from "../types";

type SelectionIndex = { id: string; index: number } | null;
type PreviewEditCapabilities = {
  movable: boolean;
  resizable: boolean;
  rotatable: boolean;
  deletable: boolean;
};

type PreviewSelectionAffordancesProps = {
  item: BuildingPlacement;
  caps: PreviewEditCapabilities;
  show: boolean;
  isEditableVertexGeometry: boolean;
  isPolyline: boolean;
  isPolygon: boolean;
  showObjectLabel: boolean;
  draggingMode: string | null;
  draggingVertex: SelectionIndex;
  hoveredVertex: SelectionIndex;
  selectedVertex: SelectionIndex;
  hoveredSegment: SelectionIndex;
  polylineInsertHintDismissed: boolean;
  segmentRef?: Ref<SVGSVGElement>;
  onVertexHover: (vertex: Exclude<SelectionIndex, null> | null) => void;
  onSegmentHover: (segment: Exclude<SelectionIndex, null> | null) => void;
  onVertexMouseDown: (event: ReactMouseEvent<HTMLButtonElement>, item: BuildingPlacement, index: number) => void;
  onSegmentMouseDown: (event: ReactMouseEvent<SVGLineElement>) => void;
  onSegmentClick: (event: ReactMouseEvent<SVGLineElement>, item: BuildingPlacement, index: number) => void;
  onDeleteVertex: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onRotateMouseDown: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onRotateClick: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onResizeMouseDown: (event: ReactMouseEvent<HTMLButtonElement>) => void;
  onDeleteClick: (event: ReactMouseEvent<HTMLButtonElement>) => void;
};

function isSegmentEditableType(item: BuildingPlacement, isPolygon: boolean) {
  return isPolygon || item.type === "custom" || item.type === "road" || item.type === "driveway" || item.type === "sidewalk";
}

export function PreviewSelectionAffordances({
  item,
  caps,
  show,
  isEditableVertexGeometry,
  isPolyline,
  isPolygon,
  showObjectLabel,
  draggingMode,
  draggingVertex,
  hoveredVertex,
  selectedVertex,
  hoveredSegment,
  polylineInsertHintDismissed,
  segmentRef,
  onVertexHover,
  onSegmentHover,
  onVertexMouseDown,
  onSegmentMouseDown,
  onSegmentClick,
  onDeleteVertex,
  onRotateMouseDown,
  onRotateClick,
  onResizeMouseDown,
  onDeleteClick,
}: PreviewSelectionAffordancesProps) {
  if (!show) return null;

  const geometry = Array.isArray(item.geometry) ? item.geometry : [];
  const canEditSegments = isEditableVertexGeometry && geometry.length > 1 && isSegmentEditableType(item, isPolygon);

  return (
    <>
      {isEditableVertexGeometry
        ? geometry.map((pt, idx) => {
            const handleLeft = ((pt[0] - (item.x ?? 0)) / Math.max(item.w, 1)) * 100;
            const handleTop = ((pt[1] - (item.y ?? 0)) / Math.max(item.d, 1)) * 100;
            const isDragging =
              draggingMode === "vertex" &&
              draggingVertex?.id === item.id &&
              draggingVertex?.index === idx;
            const isHovered = hoveredVertex?.id === item.id && hoveredVertex?.index === idx;
            const isSelectedVertex = selectedVertex?.id === item.id && selectedVertex?.index === idx;
            return (
              <button
                key={`vertex-${item.id}-${idx}`}
                type="button"
                className={`absolute -translate-x-1/2 -translate-y-1/2 rounded-full border shadow transition ${
                  isDragging
                    ? "h-4 w-4 border-amber-600 bg-amber-500 ring-4 ring-amber-200 cursor-grabbing"
                    : isHovered
                      ? "h-4 w-4 border-amber-500 bg-amber-400 ring-2 ring-amber-200 cursor-grab"
                      : isSelectedVertex
                        ? "h-4 w-4 border-amber-600 bg-amber-500 ring-2 ring-amber-200"
                        : "h-3.5 w-3.5 border-white bg-amber-300 cursor-grab"
                }`}
                style={{ left: `${handleLeft}%`, top: `${handleTop}%` }}
                onMouseEnter={() => onVertexHover({ id: item.id, index: idx })}
                onMouseLeave={() => onVertexHover(null)}
                onMouseDown={(event) => onVertexMouseDown(event, item, idx)}
              />
            );
          })
        : null}
      {canEditSegments ? (
        <svg ref={segmentRef} className="absolute inset-0" viewBox="0 0 100 100" preserveAspectRatio="none">
          {geometry.map((pt, idx, arr) => {
            if (idx === arr.length - 1 && !isPolygon) return null;
            const next = idx === arr.length - 1 ? arr[0] : arr[idx + 1];
            const x1 = ((pt[0] - (item.x ?? 0)) / Math.max(item.w, 1)) * 100;
            const y1 = ((pt[1] - (item.y ?? 0)) / Math.max(item.d, 1)) * 100;
            const x2 = ((next[0] - (item.x ?? 0)) / Math.max(item.w, 1)) * 100;
            const y2 = ((next[1] - (item.y ?? 0)) / Math.max(item.d, 1)) * 100;
            const isHoveredSeg = hoveredSegment?.id === item.id && hoveredSegment?.index === idx;
            return (
              <g key={`seg-${item.id}-${idx}`}>
                {isHoveredSeg ? (
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="rgba(245,158,11,0.6)"
                    strokeWidth={1.3}
                    strokeLinecap="round"
                  />
                ) : null}
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke="transparent"
                  strokeWidth={8}
                  strokeLinecap="round"
                  pointerEvents="stroke"
                  onMouseEnter={() => onSegmentHover({ id: item.id, index: idx })}
                  onMouseLeave={() => onSegmentHover(null)}
                  onMouseDown={onSegmentMouseDown}
                  onClick={(event) => onSegmentClick(event, item, idx)}
                />
              </g>
            );
          })}
        </svg>
      ) : null}
      {isEditableVertexGeometry ? (
        <div className="pointer-events-none absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-amber-700 shadow">
          Vertex edit
        </div>
      ) : null}
      {isEditableVertexGeometry && selectedVertex?.id === item.id ? (
        <button
          type="button"
          className="absolute -bottom-16 left-1/2 -translate-x-1/2 rounded-full border border-rose-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-rose-600 shadow"
          onClick={onDeleteVertex}
        >
          Delete vertex
        </button>
      ) : null}
      {isEditableVertexGeometry && !polylineInsertHintDismissed && isSegmentEditableType(item, isPolygon) ? (
        <div className="pointer-events-none absolute -bottom-12 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow">
          Click a segment to add a vertex
        </div>
      ) : null}
      {caps.rotatable ? (
        <button
          type="button"
          title="Rotate selected object"
          aria-label="Rotate selected object"
          data-testid="selected-object-rotate-handle"
          className="absolute -right-3 -top-3 h-7 w-7 rounded-full border border-slate-300 bg-white text-[10px] font-semibold text-slate-700 shadow-lg hover:bg-slate-50"
          onMouseDown={onRotateMouseDown}
          onClick={onRotateClick}
        >
          R
        </button>
      ) : null}
      {caps.resizable ? (
        <button
          type="button"
          title="Resize selected object"
          aria-label="Resize selected object"
          data-testid="selected-object-resize-handle"
          className="absolute -right-3 -bottom-3 h-7 w-7 rounded-full border border-slate-300 bg-white text-[10px] font-semibold text-slate-700 shadow-lg hover:bg-slate-50"
          onMouseDown={onResizeMouseDown}
        >
          Z
        </button>
      ) : null}
      {caps.deletable ? (
        <button
          type="button"
          title="Delete selected object"
          aria-label="Delete selected object"
          data-testid="selected-object-delete-handle"
          className="absolute -left-3 -top-3 h-7 w-7 rounded-full border border-rose-200 bg-white text-[10px] font-semibold text-rose-600 shadow-lg hover:bg-rose-50"
          onClick={onDeleteClick}
        >
          &times;
        </button>
      ) : null}
      {showObjectLabel && caps.movable && !isPolyline ? (
        <div className="pointer-events-none absolute -bottom-6 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 shadow">
          Snap 5ft
        </div>
      ) : null}
      {showObjectLabel && typeof item.x === "number" && typeof item.y === "number" ? (
        <div className="pointer-events-none absolute -bottom-12 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[9px] font-semibold text-slate-600 shadow">
          X {item.x.toFixed(1)} ft • Y {item.y.toFixed(1)} ft
        </div>
      ) : null}
    </>
  );
}
