type PreviewHoverDetail = {
  label: string;
  value: string;
};

type PreviewObjectHoverCardProps = {
  details: PreviewHoverDetail[];
};

export function PreviewObjectHoverCard({ details }: PreviewObjectHoverCardProps) {
  if (!details.length) return null;

  return (
    <div className="absolute left-1/2 top-full z-10 mt-3 w-48 -translate-x-1/2 rounded-2xl border border-slate-200 bg-white p-3 text-[11px] text-slate-600 shadow">
      <div className="space-y-1">
        {details.map((detail) => (
          <div key={detail.label} className="flex items-center justify-between gap-2">
            <span className="text-slate-500">{detail.label}</span>
            <span className="font-semibold text-slate-900">{detail.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
