type AnalysisPath = {
  id: string;
  buildingId: string;
  accessId: string;
  from: { x: number; y: number };
  to: { x: number; y: number };
  label: string;
  points?: Array<{ x: number; y: number }>;
};

type PreviewAnalysisPathsOverlayProps = {
  analysisPaths?: AnalysisPath[];
  analysisHighlight?: { buildingId: string; accessId: string; pathId: string } | null;
  sitePointToPreviewPercent: (point: [number, number]) => [number, number];
};

export function PreviewAnalysisPathsOverlay({
  analysisPaths,
  analysisHighlight,
  sitePointToPreviewPercent,
}: PreviewAnalysisPathsOverlayProps) {
  if (!analysisPaths?.length) return null;

  return (
    <svg className="absolute inset-0" viewBox="0 0 100 100" preserveAspectRatio="none">
      {analysisPaths.map((path) => {
        const isSelected = analysisHighlight?.pathId === path.id;
        const points = path.points?.length ? path.points : [path.from, path.to];
        const coords = points
          .map((pt) => {
            const [x, y] = sitePointToPreviewPercent([pt.x, pt.y]);
            return `${x},${y}`;
          })
          .join(" ");
        const labelPoint = points[Math.floor(points.length / 2)] ?? path.from;
        const [labelX, labelY] = sitePointToPreviewPercent([labelPoint.x, labelPoint.y]);
        return (
          <g key={path.id}>
            <polyline
              points={coords}
              fill="none"
              stroke={isSelected ? "#ef4444" : "#f97316"}
              strokeWidth={isSelected ? "0.75" : "0.4"}
              strokeDasharray="2 2"
            />
            <text
              x={labelX}
              y={labelY}
              fontSize="3"
              fill={isSelected ? "#dc2626" : "#ea580c"}
              textAnchor="middle"
            >
              {path.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
