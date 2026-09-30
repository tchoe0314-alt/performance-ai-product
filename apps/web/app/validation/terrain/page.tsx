import Link from "next/link";
import { Check, Database, ExternalLink, ShieldCheck, TriangleAlert } from "lucide-react";
import TerrainBenchmarkMap from "./TerrainBenchmarkMap";

const passedChecks = [
  "Exact downloaded-source fingerprint",
  "Coordinate reference system",
  "Raster width and height",
  "Valid elevation-cell count",
  "Minimum elevation",
  "Maximum elevation",
  "Mean elevation",
  "Independent raster comparison",
];

const blockers = [
  "Accepted property boundary",
  "Survey control and benchmark",
  "Vertical-datum acceptance",
  "Independent licensed-engineer review",
];

export default function TerrainValidationPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-5 py-8 text-slate-950 sm:py-12">
      <div className="mx-auto max-w-6xl">
        <nav className="flex items-center justify-between gap-4">
          <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 transition hover:text-slate-950">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">C</span>
            Civora workspace
          </Link>
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800">
            Automated checks passed
          </span>
        </nav>

        <header className="mt-12 max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-blue-600">Validation evidence</p>
          <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">Civora processed real, rights-cleared terrain.</h1>
          <p className="mt-5 text-lg leading-8 text-slate-600">
            This benchmark uses public-domain USGS elevation data—not a mock surface. Civora imported it, preserved its coordinate reference, and matched an independent raster reading across every measured check.
          </p>
        </header>

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.35fr_.8fr]">
          <TerrainBenchmarkMap />

          <aside className="space-y-4">
            <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
              <div className="flex items-center gap-3">
                <ShieldCheck className="h-6 w-6 text-emerald-700" />
                <div>
                  <p className="text-sm font-semibold text-emerald-950">8 of 8 checks passed</p>
                  <p className="text-xs text-emerald-800">Exact source and numeric comparisons</p>
                </div>
              </div>
              <ul className="mt-4 space-y-2">
                {passedChecks.map((check) => (
                  <li key={check} className="flex gap-2 text-sm text-emerald-950">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                    {check}
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-3">
                <Database className="h-5 w-5 text-blue-600" />
                <h2 className="font-semibold">Verified source</h2>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <dt className="text-slate-500">Cells</dt><dd className="text-right font-semibold">4,096</dd>
                <dt className="text-slate-500">Resolution</dt><dd className="text-right font-semibold">64 × 64</dd>
                <dt className="text-slate-500">Coordinates</dt><dd className="text-right font-semibold">EPSG:4326</dd>
                <dt className="text-slate-500">Elevation</dt><dd className="text-right font-semibold">83.36–86.00 m</dd>
              </dl>
              <a
                href="https://www.usgs.gov/3d-elevation-program/about-3dep-products-services"
                target="_blank"
                rel="noreferrer"
                className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700 hover:text-blue-900"
              >
                View USGS data rights <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </section>
          </aside>
        </div>

        <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-6">
          <div className="flex gap-4">
            <TriangleAlert className="mt-0.5 h-6 w-6 shrink-0 text-amber-700" />
            <div>
              <h2 className="text-lg font-semibold text-amber-950">Passed does not mean construction-ready</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-amber-900">
                The benchmark proves reliable terrain ingestion. Civora correctly refuses to call this a professional survey or approved design until the required human and project evidence is attached.
              </p>
              <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                {blockers.map((blocker) => (
                  <li key={blocker} className="rounded-lg border border-amber-200 bg-white/70 px-3 py-2 text-sm font-medium text-amber-950">
                    {blocker}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
