type PreviewMetricOverlayStat = {
  label: string;
  value: number | null;
  unit: string;
};

type PreviewMetricOverlayCardProps = {
  title: string;
  position: "top-left" | "bottom-left";
  stats: PreviewMetricOverlayStat[];
  formatMetric: (value: number, unit: string) => string;
  formatCount?: (value: number, unit: string) => string;
};

export function PreviewMetricOverlayCard({
  title,
  position,
  stats,
  formatMetric,
  formatCount,
}: PreviewMetricOverlayCardProps) {
  const visibleStats = stats.filter((item) => Number(item.value || 0) > 0);
  if (!visibleStats.length) return null;

  return (
    <div
      className={`pointer-events-none absolute left-6 w-[240px] rounded-2xl border border-slate-200/70 bg-white/90 p-3 text-xs text-slate-700 shadow-sm backdrop-blur ${
        position === "top-left" ? "top-6" : "bottom-6"
      }`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
        {title}
      </p>
      <div className="mt-2 space-y-1">
        {visibleStats.map((item) => (
          <div key={item.label} className="flex items-center justify-between gap-2">
            <span>{item.label}</span>
            <span className="font-semibold">
              {item.unit === "stalls" && formatCount
                ? formatCount(Number(item.value || 0), item.unit)
                : formatMetric(Number(item.value || 0), item.unit)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
