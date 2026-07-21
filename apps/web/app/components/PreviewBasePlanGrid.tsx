import { SURVEY_SHEET_SPOT_ELEVATIONS } from "../utils/previewLayoutHelpers";

type PreviewBasePlanGridProps = {
  showMap: boolean;
  isHighQuality: boolean;
  siteLocked: boolean;
  lotWidth: number;
  lotHeight: number;
  planScaleBar: {
    widthPct: number;
    lengthFt: number;
  };
};

const titleBlockLines = [15, 30, 47, 64, 82];
const cornerLabels: Array<[number, number, string]> = [
  [1.2, 1.2, "NW CORNER"],
  [83.8, 1.2, "NE CORNER"],
  [1.2, 98.8, "SW CORNER"],
  [83.8, 98.8, "SE CORNER"],
];

export function PreviewBasePlanGrid({
  showMap,
  isHighQuality,
  siteLocked,
  lotWidth,
  lotHeight,
  planScaleBar,
}: PreviewBasePlanGridProps) {
  return (
    <>
      <g data-testid="cad-plan-grid" opacity={showMap ? 0 : 1}>
        <rect
          x={0}
          y={0}
          width={100}
          height={100}
          fill={showMap ? "transparent" : isHighQuality ? "rgba(255,255,255,0.94)" : "transparent"}
          stroke="transparent"
          strokeWidth={0}
        />
        {isHighQuality ? (
          <g data-testid="survey-base-plan-frame" pointerEvents="none">
            <rect x={0.8} y={0.8} width={98.4} height={98.4} fill="none" stroke="#111827" strokeWidth={0.22} />
            <rect x={84.6} y={0.8} width={14.6} height={98.4} fill="rgba(255,255,255,0.86)" stroke="#111827" strokeWidth={0.14} />
            {titleBlockLines.map((y) => (
              <line key={`sheet-title-line-${y}`} x1={84.6} y1={y} x2={99.2} y2={y} stroke="#111827" strokeWidth={0.08} />
            ))}
            <text x={91.9} y={6.2} textAnchor="middle" fontSize="1.05" fontWeight={850} fill="#111827">SITE REVIEW</text>
            <text x={91.9} y={8.0} textAnchor="middle" fontSize="0.86" fontWeight={700} fill="#334155">CONCEPT EXHIBIT</text>
            <text x={91.9} y={11.9} textAnchor="middle" fontSize="0.72" fill="#475569">{Math.round(lotWidth)} FT x {Math.round(lotHeight)} FT</text>
            <text x={91.9} y={13.4} textAnchor="middle" fontSize="0.72" fill="#475569">SOURCE REVIEW</text>
            <text x={86.0} y={33.0} fontSize="0.8" fontWeight={850} fill="#111827">LEGEND</text>
            <line x1={86.0} y1={34.0} x2={89.8} y2={34.0} stroke="#111827" strokeWidth={0.16} strokeDasharray="1 0.7" />
            <text x={90.4} y={34.4} fontSize="0.72" fill="#334155">PROPERTY LINE</text>
            <line x1={86.0} y1={37.0} x2={89.8} y2={37.0} stroke="#f97316" strokeWidth={0.18} strokeDasharray="1.2 0.8" />
            <text x={90.4} y={37.4} fontSize="0.72" fill="#334155">STORM</text>
            <line x1={86.0} y1={40.0} x2={89.8} y2={40.0} stroke="#16a34a" strokeWidth={0.18} strokeDasharray="1.2 0.8" />
            <text x={90.4} y={40.4} fontSize="0.72" fill="#334155">SANITARY</text>
            <line x1={86.0} y1={43.0} x2={89.8} y2={43.0} stroke="#0284c7" strokeWidth={0.18} strokeDasharray="1.2 0.8" />
            <text x={90.4} y={43.4} fontSize="0.72" fill="#334155">WATER</text>
            <rect x={86.0} y={45.6} width={3.6} height={1.4} fill="rgba(255,255,255,0.7)" stroke="#111827" strokeWidth={0.1} />
            <text x={90.4} y={46.7} fontSize="0.72" fill="#334155">BUILDING</text>
            <text x={86.0} y={68.5} fontSize="0.72" fontWeight={850} fill="#111827">NOTES</text>
            <text x={86.0} y={70.4} fontSize="0.55" fill="#64748b">SOURCE REVIEW ONLY</text>
            <text x={86.0} y={72.0} fontSize="0.55" fill="#64748b">FIELD VERIFY</text>
            <text x={86.0} y={87.2} fontSize="0.78" fill="#334155">SHEET</text>
            <text x={91.8} y={95.5} textAnchor="middle" fontSize="3.1" fontWeight={900} fill="#111827">C1.0</text>
            <path d="M 92 20 L 92 14 L 90.6 17.2 L 92 16.5 L 93.4 17.2 Z" fill="#111827" />
            <text x={92} y={22.5} textAnchor="middle" fontSize="1.5" fontWeight={800} fill="#111827">N</text>
          </g>
        ) : null}
        <rect
          x={1.2}
          y={1.2}
          width={isHighQuality ? 82.6 : 97.6}
          height={97.6}
          fill={siteLocked && !isHighQuality ? "rgba(16,185,129,0.024)" : "none"}
          stroke={siteLocked ? (isHighQuality ? "#111827" : "rgba(5,150,105,0.62)") : isHighQuality ? "rgba(15,23,42,0.44)" : "rgba(51,65,85,0.36)"}
          strokeWidth={siteLocked ? (isHighQuality ? 0.11 : 0.34) : 0.22}
          strokeDasharray={isHighQuality ? "2 0.9 0.35 0.9" : siteLocked ? undefined : "2 1.2"}
        />
        {siteLocked ? (
          <>
            {!isHighQuality ? (
              <text x={2.4} y={4.2} fontSize={1.12} fill="rgba(4,120,87,0.58)" fontWeight={800} letterSpacing={0.16}>
                SITE LOCKED · {Math.round(lotWidth)} FT x {Math.round(lotHeight)} FT
              </text>
            ) : null}
            {isHighQuality ? (
              <g data-testid="survey-boundary-annotation" pointerEvents="none">
                <text x={42.6} y={2.55} textAnchor="middle" fontSize="0.66" fill="#475569">N 89°58&apos;30&quot; E · {Math.round(lotWidth)}.00&apos;</text>
                <text x={42.6} y={98.2} textAnchor="middle" fontSize="0.66" fill="#475569">S 89°58&apos;30&quot; W · {Math.round(lotWidth)}.00&apos;</text>
                <text x={2.2} y={50} transform="rotate(-90 2.2 50)" textAnchor="middle" fontSize="0.66" fill="#475569">N 00°01&apos;30&quot; W · {Math.round(lotHeight)}.00&apos;</text>
                <text x={83.8} y={50} transform="rotate(90 83.8 50)" textAnchor="middle" fontSize="0.66" fill="#475569">S 00°01&apos;30&quot; E · {Math.round(lotHeight)}.00&apos;</text>
                {cornerLabels.map(([x, y, label]) => (
                  <g key={`corner-${label}`}>
                    <line x1={x - 0.75} y1={y} x2={x + 0.75} y2={y} stroke="#334155" strokeWidth={0.08} />
                    <line x1={x} y1={y - 0.75} x2={x} y2={y + 0.75} stroke="#334155" strokeWidth={0.08} />
                    <text x={x + 0.9} y={y + (y < 50 ? 1.65 : -0.9)} fontSize="0.52" fill="#64748b">{label}</text>
                  </g>
                ))}
              </g>
            ) : null}
          </>
        ) : null}
        <title>Local review canvas site extent.</title>
        <line x1={4} y1={95} x2={4 + planScaleBar.widthPct} y2={95} stroke="#0f172a" strokeWidth={0.34} />
        <line x1={4} y1={94.1} x2={4} y2={95.9} stroke="#0f172a" strokeWidth={0.22} />
        <line x1={4 + planScaleBar.widthPct} y1={94.1} x2={4 + planScaleBar.widthPct} y2={95.9} stroke="#0f172a" strokeWidth={0.22} />
        <text x={4} y={93.1} fontSize="1.25" fill="#0f172a" fontWeight={700}>0</text>
        <text x={4 + planScaleBar.widthPct} y={93.1} fontSize="1.25" fill="#0f172a" fontWeight={700} textAnchor="end">
          {planScaleBar.lengthFt} FT
        </text>
      </g>
      {isHighQuality && !showMap && siteLocked ? (
        <g data-testid="plan-grading-context-lines" opacity={0.2} pointerEvents="none">
          {[0, 1, 2, 3, 4].map((index) => {
            const y = 18 + index * 12.5;
            const offset = index * 1.8;
            return (
              <path
                key={`review-contour-${index}`}
                d={`M ${9 + offset} ${y} C ${25 + offset} ${y - 4.2} ${37 - offset} ${y + 5.8} ${54 + offset} ${y + 1.2} S ${79 - offset} ${y - 3.6} ${93 - offset * 0.2} ${y + 1.8}`}
                fill="none"
                stroke="#64748b"
                strokeWidth={0.07}
              >
                <title>Subtle review contour cue. Not survey control.</title>
              </path>
            );
          })}
          {SURVEY_SHEET_SPOT_ELEVATIONS.map((spot) => (
            <g key={`spot-${spot.label}-${spot.x}-${spot.y}`} data-testid="survey-spot-elevation">
              <text x={spot.x} y={spot.y} fontSize="0.86" fill="#64748b">{spot.label}</text>
              <line x1={spot.x - 0.32} y1={spot.y - 0.32} x2={spot.x + 0.32} y2={spot.y + 0.32} stroke="#64748b" strokeWidth={0.08} />
              <line x1={spot.x - 0.32} y1={spot.y + 0.32} x2={spot.x + 0.32} y2={spot.y - 0.32} stroke="#64748b" strokeWidth={0.08} />
            </g>
          ))}
        </g>
      ) : null}
    </>
  );
}
