export type ReportGateListItem = {
  label: string;
  value: string;
  status: string;
};

export function ReportGateListPanel({
  title,
  items,
  blockColor = "red",
}: {
  title: string;
  items: readonly ReportGateListItem[];
  blockColor?: "red" | "amber";
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</p>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            <span className="font-semibold text-slate-700">{item.label}</span>
            <span
              className={`text-right text-xs font-semibold uppercase tracking-[0.12em] ${
                item.status === "block"
                  ? blockColor === "amber"
                    ? "text-amber-600"
                    : "text-red-600"
                  : item.status === "review"
                    ? "text-amber-600"
                    : "text-slate-500"
              }`}
            >
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
