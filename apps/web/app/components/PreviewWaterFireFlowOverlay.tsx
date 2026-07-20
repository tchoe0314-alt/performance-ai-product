import type { buildWaterFireFlowViewModel } from "../utils/previewWaterFireFlow";

type WaterFireFlowViewModel = ReturnType<typeof buildWaterFireFlowViewModel>;

type PreviewWaterFireFlowOverlayProps = {
  waterFireFlow: WaterFireFlowViewModel;
  previewQuality: "standard" | "high";
  sitePointToPreviewPercent: (point: [number, number]) => [number, number];
};

function hydrantStatusColor(status: string) {
  if (status === "pass") return "#16a34a";
  if (status === "fail") return "#dc2626";
  return "#c2410c";
}

export function PreviewWaterFireFlowOverlay({
  waterFireFlow,
  previewQuality,
  sitePointToPreviewPercent,
}: PreviewWaterFireFlowOverlayProps) {
  if (!waterFireFlow.hasData) return null;

  return (
    <g>
      {waterFireFlow.pressureZones.map((zone) => {
        if (zone.geometry.length < 3) return null;
        const points = zone.geometry.map((pt) => sitePointToPreviewPercent(pt).join(",")).join(" ");
        return (
          <polygon
            key={`water-zone-${zone.id}`}
            points={points}
            fill={zone.color}
            opacity={previewQuality === "high" ? 0.035 : 0.08}
            stroke={zone.color}
            strokeWidth={previewQuality === "high" ? 0.12 : 0.28}
            strokeDasharray={previewQuality === "high" ? "0.7 0.55" : "1.4 0.8"}
          />
        );
      })}
      {waterFireFlow.networkSegments.map((segment) => {
        if (segment.geometry.length < 2) return null;
        const points = segment.geometry.map((pt) => sitePointToPreviewPercent(pt).join(",")).join(" ");
        return (
          <polyline
            key={`water-segment-${segment.id}`}
            points={points}
            fill="none"
            stroke={segment.networkType === "loop" ? "#2563eb" : "#c2410c"}
            strokeWidth={
              previewQuality === "high"
                ? segment.networkType === "loop"
                  ? 0.16
                  : 0.12
                : segment.networkType === "loop"
                  ? 0.46
                  : 0.36
            }
            strokeDasharray={
              segment.networkType === "loop"
                ? previewQuality === "high"
                  ? "1 0.45"
                  : undefined
                : previewQuality === "high"
                  ? "0.55 0.42"
                  : "1.2 0.8"
            }
            opacity={previewQuality === "high" ? 0.7 : 0.9}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        );
      })}
      {waterFireFlow.hydrants.map((hydrant) => {
        const [x, y] = sitePointToPreviewPercent([hydrant.x, hydrant.y]);
        const selected = waterFireFlow.selectedHydrant?.id === hydrant.id;
        const statusColor = hydrantStatusColor(hydrant.status);
        return (
          <g key={`hydrant-marker-${hydrant.id}`}>
            <circle
              cx={x}
              cy={y}
              r={selected ? 0.72 : 0.48}
              fill={previewQuality === "high" ? "#ffffff" : statusColor}
              stroke={statusColor}
              strokeWidth={selected ? 0.22 : 0.16}
              opacity={previewQuality === "high" ? 0.78 : 0.95}
            >
              <title>{hydrant.label}</title>
            </circle>
          </g>
        );
      })}
    </g>
  );
}
