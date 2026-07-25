import {
  buildSourceBackedSurveySpots,
  buildSourceBackedSurveyTrace,
  type PreviewSurveyPoint,
} from "../utils/previewLayoutHelpers";

type PreviewBasePlanGridProps = {
  showMap: boolean;
  isHighQuality: boolean;
  cadReferenceMode?: boolean;
  siteLocked: boolean;
  hasSurveyOrTerrainEvidence: boolean;
  lotWidth: number;
  lotHeight: number;
  planScaleBar: {
    widthPct: number;
    lengthFt: number;
  };
  surveyPoints?: PreviewSurveyPoint[];
};

const titleBlockLines = [15, 30, 47, 64, 82];

export function PreviewBasePlanGrid({
  showMap,
  isHighQuality,
  cadReferenceMode = false,
  siteLocked,
  hasSurveyOrTerrainEvidence,
  lotWidth,
  lotHeight,
  planScaleBar,
  surveyPoints,
}: PreviewBasePlanGridProps) {
  const sourceSurveyTrace = buildSourceBackedSurveyTrace({ points: surveyPoints, lotWidth, lotHeight });
  const sourceSurveySpots = buildSourceBackedSurveySpots({ points: surveyPoints, lotWidth, lotHeight });
  const hasSourceSurveyPoints = sourceSurveyTrace.length > 0;
  const hasSourceElevations = sourceSurveySpots.length > 0;

  return (
    <>
      <g data-testid="cad-plan-grid" opacity={showMap ? 0 : 1}>
        <rect
          x={0}
          y={0}
          width={100}
          height={100}
          fill={showMap ? "transparent" : cadReferenceMode && isHighQuality ? "#020617" : isHighQuality ? "rgba(255,255,255,0.94)" : "transparent"}
          stroke="transparent"
          strokeWidth={0}
        />
        {isHighQuality ? (
          <g data-testid="survey-base-plan-frame" pointerEvents="none">
            <rect x={0.8} y={0.8} width={98.4} height={98.4} fill="none" stroke={cadReferenceMode ? "#f8fafc" : "#111827"} strokeWidth={0.1} />
            <rect x={84.6} y={0.8} width={14.6} height={98.4} fill={cadReferenceMode ? "rgba(2,6,23,0.88)" : "rgba(255,255,255,0.66)"} stroke={cadReferenceMode ? "#f8fafc" : "#111827"} strokeWidth={0.065} />
            {titleBlockLines.map((y) => (
              <line key={`sheet-title-line-${y}`} x1={84.6} y1={y} x2={99.2} y2={y} stroke={cadReferenceMode ? "#e5e7eb" : "#111827"} strokeWidth={0.05} />
            ))}
            <text x={91.9} y={6.2} textAnchor="middle" fontSize="0.98" fontWeight={850} fill={cadReferenceMode ? "#f8fafc" : "#111827"}>SITE REVIEW</text>
            <text x={91.9} y={8.0} textAnchor="middle" fontSize="0.76" fontWeight={700} fill={cadReferenceMode ? "#cbd5e1" : "#334155"}>
              {cadReferenceMode ? "CAD RECREATION" : hasSurveyOrTerrainEvidence ? "SOURCE EXHIBIT" : "CONCEPT PLAN"}
            </text>
            <text x={91.9} y={11.9} textAnchor="middle" fontSize="0.66" fill={cadReferenceMode ? "#cbd5e1" : "#475569"}>{Math.round(lotWidth)} FT x {Math.round(lotHeight)} FT</text>
            <text x={91.9} y={13.4} textAnchor="middle" fontSize="0.62" fill={cadReferenceMode ? "#94a3b8" : "#475569"}>
              {cadReferenceMode ? "DRAFT REVIEW GEOMETRY" : hasSurveyOrTerrainEvidence ? "SOURCE REVIEW" : "NO SURVEY / TOPO SOURCE"}
            </text>
            <text x={86.0} y={33.0} fontSize="0.72" fontWeight={850} fill={cadReferenceMode ? "#f8fafc" : "#111827"}>LEGEND</text>
            <line x1={86.0} y1={34.0} x2={89.8} y2={34.0} stroke={cadReferenceMode ? "#f8fafc" : "#111827"} strokeWidth={0.16} strokeDasharray="1 0.7" />
            <text x={90.4} y={34.4} fontSize="0.62" fill={cadReferenceMode ? "#cbd5e1" : "#334155"}>PROPERTY LINE</text>
            <line x1={86.0} y1={37.0} x2={89.8} y2={37.0} stroke="#f97316" strokeWidth={0.18} strokeDasharray="1.2 0.8" />
            <text x={90.4} y={37.4} fontSize="0.62" fill={cadReferenceMode ? "#cbd5e1" : "#334155"}>STORM</text>
            <line x1={86.0} y1={40.0} x2={89.8} y2={40.0} stroke="#16a34a" strokeWidth={0.18} strokeDasharray="1.2 0.8" />
            <text x={90.4} y={40.4} fontSize="0.62" fill={cadReferenceMode ? "#cbd5e1" : "#334155"}>SANITARY</text>
            <line x1={86.0} y1={43.0} x2={89.8} y2={43.0} stroke="#0284c7" strokeWidth={0.18} strokeDasharray="1.2 0.8" />
            <text x={90.4} y={43.4} fontSize="0.62" fill={cadReferenceMode ? "#cbd5e1" : "#334155"}>WATER</text>
            <rect x={86.0} y={45.6} width={3.6} height={1.4} fill={cadReferenceMode ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.7)"} stroke={cadReferenceMode ? "#f8fafc" : "#111827"} strokeWidth={0.1} />
            <text x={90.4} y={46.7} fontSize="0.62" fill={cadReferenceMode ? "#cbd5e1" : "#334155"}>BUILDING</text>
            <text x={86.0} y={68.5} fontSize="0.66" fontWeight={850} fill={cadReferenceMode ? "#f8fafc" : "#111827"}>NOTES</text>
            <text x={86.0} y={70.4} fontSize="0.5" fill={cadReferenceMode ? "#94a3b8" : "#64748b"}>
              {cadReferenceMode ? "EDITABLE DRAFT PLAN" : hasSurveyOrTerrainEvidence ? "SOURCE REVIEW ONLY" : "DRAWN / GENERATED CONTEXT"}
            </text>
            <text x={86.0} y={72.0} fontSize="0.5" fill={cadReferenceMode ? "#94a3b8" : "#64748b"}>
              {cadReferenceMode ? "NOT SURVEY CONTROL" : hasSurveyOrTerrainEvidence ? "FIELD VERIFY" : "ADD SURVEY OR TERRAIN"}
            </text>
            <text x={86.0} y={87.2} fontSize="0.68" fill={cadReferenceMode ? "#cbd5e1" : "#334155"}>SHEET</text>
            <text x={91.8} y={95.5} textAnchor="middle" fontSize="2.72" fontWeight={900} fill={cadReferenceMode ? "#f8fafc" : "#111827"}>C1.0</text>
            <path d="M 92 20 L 92 14 L 90.6 17.2 L 92 16.5 L 93.4 17.2 Z" fill={cadReferenceMode ? "#f8fafc" : "#111827"} />
            <text x={92} y={22.5} textAnchor="middle" fontSize="1.5" fontWeight={800} fill={cadReferenceMode ? "#f8fafc" : "#111827"}>N</text>
          </g>
        ) : null}
        <rect
          x={1.2}
          y={1.2}
          width={isHighQuality ? 82.6 : 97.6}
          height={97.6}
          fill="none"
          stroke={siteLocked ? (cadReferenceMode && isHighQuality ? "rgba(248,250,252,0.52)" : isHighQuality ? "rgba(15,23,42,0.42)" : "rgba(51,65,85,0.42)") : cadReferenceMode && isHighQuality ? "rgba(248,250,252,0.34)" : isHighQuality ? "rgba(15,23,42,0.28)" : "rgba(51,65,85,0.28)"}
          strokeWidth={siteLocked ? (isHighQuality ? 0.04 : 0.18) : 0.12}
          strokeDasharray={isHighQuality ? "1.9 1.35" : siteLocked ? undefined : "2 1.2"}
        />
        {siteLocked ? (
          <>
            {!isHighQuality ? (
              <text x={2.4} y={4.2} fontSize={1.12} fill="rgba(4,120,87,0.58)" fontWeight={800} letterSpacing={0.16}>
                SITE LOCKED · {Math.round(lotWidth)} FT x {Math.round(lotHeight)} FT
              </text>
            ) : null}
            {isHighQuality && hasSourceSurveyPoints ? (
              <g data-testid="survey-boundary-annotation" pointerEvents="none">
                <text x={42.6} y={2.55} textAnchor="middle" fontSize="0.66" fill="#475569">SOURCE POINT EXTENT · {sourceSurveyTrace.length} PTS SHOWN</text>
                <text x={42.6} y={98.2} textAnchor="middle" fontSize="0.66" fill="#475569">UPLOADED POINTS FOR REVIEW · FIELD VERIFY</text>
                <text x={2.2} y={50} transform="rotate(-90 2.2 50)" textAnchor="middle" fontSize="0.66" fill="#475569">SOURCE REVIEW</text>
                <text x={83.8} y={50} transform="rotate(90 83.8 50)" textAnchor="middle" fontSize="0.66" fill="#475569">NOT SURVEY CONTROL</text>
                {sourceSurveyTrace.slice(0, 24).map((point) => (
                  <g key={point.id} data-testid="source-survey-point">
                    <circle cx={point.x} cy={point.y} r={0.22} fill={point.hasElevation ? "#334155" : "#94a3b8"} opacity={0.78} />
                    <title>Uploaded/source point shown in site coordinates for review.</title>
                  </g>
                ))}
              </g>
            ) : null}
          </>
        ) : null}
        <title>Local review canvas site extent.</title>
        <line x1={4} y1={95} x2={4 + planScaleBar.widthPct} y2={95} stroke={cadReferenceMode && isHighQuality ? "#f8fafc" : "#0f172a"} strokeWidth={isHighQuality ? 0.22 : 0.3} />
        <line x1={4} y1={94.1} x2={4} y2={95.9} stroke={cadReferenceMode && isHighQuality ? "#f8fafc" : "#0f172a"} strokeWidth={isHighQuality ? 0.15 : 0.2} />
        <line x1={4 + planScaleBar.widthPct} y1={94.1} x2={4 + planScaleBar.widthPct} y2={95.9} stroke={cadReferenceMode && isHighQuality ? "#f8fafc" : "#0f172a"} strokeWidth={isHighQuality ? 0.15 : 0.2} />
        <text x={4} y={93.1} fontSize="1.25" fill={cadReferenceMode && isHighQuality ? "#f8fafc" : "#0f172a"} fontWeight={700}>0</text>
        <text x={4 + planScaleBar.widthPct} y={93.1} fontSize="1.25" fill={cadReferenceMode && isHighQuality ? "#f8fafc" : "#0f172a"} fontWeight={700} textAnchor="end">
          {planScaleBar.lengthFt} FT
        </text>
      </g>
      {isHighQuality && !showMap && siteLocked && hasSourceElevations ? (
        <g data-testid="plan-grading-context-lines" opacity={0.2} pointerEvents="none">
          {sourceSurveySpots.map((spot) => (
            <g key={spot.id} data-testid="survey-spot-elevation">
              <text x={spot.x} y={spot.y} fontSize="0.86" fill="#64748b">{spot.label}</text>
              <line x1={spot.x - 0.32} y1={spot.y - 0.32} x2={spot.x + 0.32} y2={spot.y + 0.32} stroke="#64748b" strokeWidth={0.08} />
              <line x1={spot.x - 0.32} y1={spot.y + 0.32} x2={spot.x + 0.32} y2={spot.y - 0.32} stroke="#64748b" strokeWidth={0.08} />
              <title>Uploaded/source elevation point. Review only.</title>
            </g>
          ))}
        </g>
      ) : null}
    </>
  );
}
