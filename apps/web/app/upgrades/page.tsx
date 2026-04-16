export default function UpgradesPage() {
  const upgrades = [
    "Interactive 3D preview with full configuration",
    "Issue navigator highlights in preview",
    "Engineering metrics tied to live model outputs",
    "Materials and quantity takeoffs",
    "Survey + slope inference from imagery",
    "Map snapshot ingestion (Google Maps, GIS exports)",
    "Clickable issue detection and fix routing",
    "Concept coverage for bridges, pools, subdivisions",
    "Environmental / regulatory depth",
    "Construction and inspection workflows",
    "Operations support dashboards",
  ];

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#e2e8f0_100%)] p-6">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
            Upgrades
          </p>
          <h1 className="mt-3 text-3xl font-semibold text-slate-950">
            What still needs upgrades
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            This page tracks all features you asked for so we can build them end-to-end before
            the deep polish pass.
          </p>
        </div>

        <div className="grid gap-3">
          {upgrades.map((item) => (
            <div
              key={item}
              className="flex items-center justify-between rounded-[22px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700"
            >
              <span className="font-medium">{item}</span>
              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                Pending
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
