const civoraDoes = [
  "Supports site planning and review workflows.",
  "Organizes source-backed context from project inputs, GIS-style sources, PDFs, imagery, and uploaded survey/topo files.",
  "Helps with layout and drafting, including objects, boundaries, drawings, and system drafts.",
  "Builds review package materials such as sheets, reports, quantities, blockers, and source notes.",
  "Creates AI visualization for presentation and review from the current layout; it is not evidence.",
];

const civoraDoesNot = [
  "It does not replace licensed professionals.",
  "It does not stamp, seal, sign, certify, or approve construction.",
  "It does not submit construction documents.",
  "It does not act as engineer of record.",
  "It does not turn GIS, AI, PDF, satellite, or other source data into survey or control.",
];

function TrustList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
        {title}
      </p>
      <ul className="mt-3 space-y-2 text-sm leading-5 text-slate-700">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TrustPanel() {
  return (
    <div className="space-y-4" data-testid="civora-trust-panel">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Product boundary
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-700">
          Civora supports site planning and review workflows. It helps teams gather source-backed context, draft layouts, prepare review packages, and create AI visualization from the current review layout.
        </p>
        <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold leading-5 text-amber-800">
          Outputs are planning and review aids. Licensed professionals remain responsible for final decisions and field use.
        </p>
      </div>
      <div className="grid gap-3">
        <TrustList title="What Civora does" items={civoraDoes} />
        <TrustList title="What Civora does not do" items={civoraDoesNot} />
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Review package boundary
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-700">
          Deliver creates review-only packages with visible missing items, source notes, and blockers so a project team can hand off clearer material for professional review.
        </p>
      </div>
    </div>
  );
}
