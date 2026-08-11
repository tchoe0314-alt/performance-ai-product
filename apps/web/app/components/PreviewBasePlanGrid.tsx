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
            <text x={2.2} y={3.1} fontSize="0.62" fontWeight={760} fill={cadReferenceMode ? "rgba(248,250,252,0.68)" : "rgba(15,23,42,0.62)"}>
              {cadReferenceMode ? "CAD RECREATION" : hasSurveyOrTerrainEvidence ? "SOURCE EXHIBIT" : "CONCEPT PLAN"} · {Math.round(lotWidth)} FT x {Math.round(lotHeight)} FT
            </text>
          </g>
        ) : null}
        <rect
          data-testid="canonical-site-boundary"
          x={1.2}
          y={1.2}
          width={97.6}
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
                <text x={50} y={2.55} textAnchor="middle" fontSize="0.66" fill="#475569">SOURCE POINT EXTENT · {sourceSurveyTrace.length} PTS SHOWN</text>
                <text x={50} y={98.2} textAnchor="middle" fontSize="0.66" fill="#475569">UPLOADED POINTS FOR REVIEW · FIELD VERIFY</text>
                <text x={2.2} y={50} transform="rotate(-90 2.2 50)" textAnchor="middle" fontSize="0.66" fill="#475569">SOURCE REVIEW</text>
                <text x={97.8} y={50} transform="rotate(90 97.8 50)" textAnchor="middle" fontSize="0.66" fill="#475569">NOT SURVEY CONTROL</text>
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
      {showMap && siteLocked ? (
        <g data-testid="map-site-boundary" pointerEvents="none">
          <rect
            x={0.7}
            y={0.7}
            width={98.6}
            height={98.6}
            rx={0.18}
            fill="rgba(255,255,255,0.015)"
            stroke="rgba(15,23,42,0.88)"
            strokeWidth={0.2}
          />
          <rect
            x={1.05}
            y={1.05}
            width={97.9}
            height={97.9}
            rx={0.12}
            fill="none"
            stroke="rgba(255,255,255,0.9)"
            strokeWidth={0.07}
          />
          <title>Locked site boundary at the current map scale.</title>
        </g>
      ) : null}
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
