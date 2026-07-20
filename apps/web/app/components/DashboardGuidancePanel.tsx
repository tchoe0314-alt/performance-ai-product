type DashboardGuidancePanelProps = {
  stats: Array<[string, number]>;
};

export function DashboardGuidancePanel({ stats }: DashboardGuidancePanelProps) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {stats.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
          <p className="mt-1 text-xl font-semibold text-slate-900">{value}</p>
        </div>
      ))}
    </div>
  );
}
