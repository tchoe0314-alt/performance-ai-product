import type { BuildingPlacement } from "../types";
import type { CadSymbolKind } from "../utils/cadToolTypes";

type PreviewRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type PreviewCadMarkersProps = {
  objects: BuildingPlacement[];
  selectedBuildingId: string | null;
  currentSiteSize: {
    width: number;
    height: number;
  };
  sitePointToPreviewPercent: (point: [number, number]) => [number, number];
  mapAnchoredRectPercent: (item: BuildingPlacement) => PreviewRect;
  shouldRevealObjectLabel: (item: BuildingPlacement) => boolean;
  getObjectGeometryPoints: (item: BuildingPlacement) => Array<[number, number]>;
};

const symbolGlyphs: Record<CadSymbolKind, string> = {
  hydrant: "H",
  inlet: "I",
  manhole: "M",
  valve: "V",
  tree: "T",
  light: "L",
  sign: "S",
  utility_marker: "U",
  benchmark: "B",
  note_callout: "N",
};

function objectCenter(item: BuildingPlacement): [number, number] {
  return [(item.x ?? 0) + item.w / 2, (item.y ?? 0) + item.d / 2];
}

function firstGeometryPoint(item: BuildingPlacement): [number, number] {
  return Array.isArray(item.geometry) && item.geometry[0]
    ? item.geometry[0]
    : objectCenter(item);
}

export function PreviewCadMarkers({
  objects,
  selectedBuildingId,
  currentSiteSize,
  sitePointToPreviewPercent,
  mapAnchoredRectPercent,
  shouldRevealObjectLabel,
  getObjectGeometryPoints,
}: PreviewCadMarkersProps) {
  return (
    <>
      {objects
        .filter((item) => item.geometryType === "point" && item.meta?.cad_symbol)
        .map((item) => {
          const symbol = String(item.meta?.cad_symbol || "utility_marker") as CadSymbolKind;
          const [x, y] = sitePointToPreviewPercent(firstGeometryPoint(item));
          return (
            <g key={`cad-symbol-${item.id}`} data-testid="cad-symbol">
              <circle cx={x} cy={y} r={1.05} fill="#ffffff" stroke="#0f172a" strokeWidth={0.22} />
              <text x={x} y={y + 0.48} textAnchor="middle" fontSize="1.55" fill="#0f172a" fontWeight={800}>
                {symbolGlyphs[symbol] ?? "U"}
              </text>
            </g>
          );
        })}
      {objects
        .filter((item) => item.meta?.cad_entity_type === "circle" && Number.isFinite(Number(item.meta?.cad_radius)))
        .map((item) => {
          const [x, y] = sitePointToPreviewPercent(firstGeometryPoint(item));
          const radiusFt = Math.max(0, Number(item.meta?.cad_radius));
          const radiusPct = Math.max(0.35, (radiusFt / Math.max(currentSiteSize.width, currentSiteSize.height, 1)) * 100);
          const isSelected = selectedBuildingId === item.id;
          return (
            <g key={`cad-circle-${item.id}`} data-testid="cad-entity-circle">
              <circle
                cx={x}
                cy={y}
                r={radiusPct}
                fill="rgba(124, 58, 237, 0.08)"
                stroke={isSelected ? "#f59e0b" : "#7c3aed"}
                strokeWidth={isSelected ? 0.75 : 0.42}
              >
                <title>{String(item.meta?.cad_source_confidence || "review required")}</title>
              </circle>
            </g>
          );
        })}
      {objects
        .filter((item) => item.meta?.cad_entity_type === "text")
        .map((item) => {
          const [x, y] = sitePointToPreviewPercent(firstGeometryPoint(item));
          return (
            <g key={`cad-text-${item.id}`} data-testid="cad-entity-text">
              <circle cx={x} cy={y} r={0.5} fill="#64748b" opacity={0.72} />
            </g>
          );
        })}
      {objects
        .filter((item) => item.meta?.unsupported_entity_placeholder)
        .map((item) => {
          const rect = mapAnchoredRectPercent(item);
          const blockers = Array.isArray(item.meta?.cad_review_blockers) ? item.meta.cad_review_blockers.map(String) : [];
          return (
            <g key={`cad-unsupported-${item.id}`} data-testid="cad-entity-unsupported">
              <rect
                x={rect.left}
                y={rect.top}
                width={Math.max(1.2, rect.width)}
                height={Math.max(1.2, rect.height)}
                fill="rgba(251, 191, 36, 0.12)"
                stroke="#b45309"
                strokeWidth={0.42}
                strokeDasharray="1.4 1"
              >
                <title>{blockers[0] || "Unsupported draft entity requires review."}</title>
              </rect>
            </g>
          );
        })}
      {objects
        .filter((item) => item.meta?.cad_dimension_label && shouldRevealObjectLabel(item) && getObjectGeometryPoints(item).length >= 2)
        .map((item) => {
          const points = getObjectGeometryPoints(item);
          const [a, b] = points;
          const mode = String(item.meta?.cad_dimension_mode || "linear");
          const start: [number, number] = mode === "linear" ? [a[0], Math.max(a[1], b[1]) + 8] : a;
          const end: [number, number] = mode === "linear" ? [b[0], Math.max(a[1], b[1]) + 8] : b;
          const [x1, y1] = sitePointToPreviewPercent(start);
          const [x2, y2] = sitePointToPreviewPercent(end);
          const labelX = (x1 + x2) / 2;
          const labelY = (y1 + y2) / 2 - 1.1;
          return (
            <g key={`cad-dim-${item.id}`} data-testid="cad-dimension-label">
              <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#0f766e" strokeWidth={0.35} strokeDasharray="1 0.7" />
              <circle cx={x1} cy={y1} r={0.42} fill="#0f766e" />
              <circle cx={x2} cy={y2} r={0.42} fill="#0f766e" />
              <text x={labelX} y={Math.max(labelY, 3)} textAnchor="middle" fontSize="2.2" fill="#0f766e" fontWeight={800}>
                {String(item.meta?.cad_dimension_label).slice(0, 24)}
              </text>
            </g>
          );
        })}
    </>
  );
}
