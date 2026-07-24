"use client";

import { AlertTriangle, Route, ShieldCheck, Table2 } from "lucide-react";

import { formatClearance } from "../utils/previewGeometryTruth";

type CoordinationSeverity = "clear" | "watch" | "conflict";

type UtilityCoordinationRow = {
  id: string;
  systemA: string;
  systemB: string;
  crossingType: "vertical" | "horizontal" | "unknown";
  clearanceFt: number | null;
  status: CoordinationSeverity;
  rerouteOptions: string[];
  constructabilityScore: number;
};

type UtilityCoordinationSummary = {
  crossingCount: number;
  conflictCount: number;
  watchCount: number;
  avgScore: number;
  status: CoordinationSeverity;
};

type UtilityCoordinationDockProps = {
  rows: UtilityCoordinationRow[];
  summary: UtilityCoordinationSummary;
};

export function UtilityCoordinationDock({ rows, summary }: UtilityCoordinationDockProps) {
  const verticalCount = rows.filter((row) => row.crossingType === "vertical").length;
  const horizontalCount = rows.filter((row) => row.crossingType === "horizontal").length;
  const highlightedReroute = (rows.find((row) => row.status === "conflict") ?? rows[0])?.rerouteOptions.join(" · ");

  return (
    <details className="civora-coordination-dock mb-3 rounded-2xl border border-slate-200 bg-white/82 shadow-sm backdrop-blur-xl">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 text-sm font-semibold text-slate-900 marker:hidden">
        <span className="flex min-w-0 items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-slate-400" />
          <span className="truncate">
            Coordination {summary.conflictCount ? `${summary.conflictCount} conflicts` : summary.watchCount ? `${summary.watchCount} watch items` : "clear"}
          </span>
        </span>
        <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
          summary.status === "conflict"
            ? "bg-red-50 text-red-700"
            : summary.status === "watch"
              ? "bg-amber-50 text-amber-700"
              : "bg-emerald-50 text-emerald-700"
        }`}>
          {summary.status}
        </span>
      </summary>
      <div className="grid gap-3 border-t border-slate-200/70 p-3 xl:grid-cols-[1.1fr_1.4fr_1fr]">
      <section className="rounded-xl border border-slate-200 bg-white/90 p-3 shadow-sm" data-testid="utility-conflict-viewer">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Conflict Viewer</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">
              {summary.conflictCount
                ? `${summary.conflictCount} conflicts need review`
                : summary.watchCount
                  ? `${summary.watchCount} clearance items need review`
                  : "No utility conflicts flagged"}
            </p>
          </div>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
              summary.status === "conflict"
                ? "bg-red-50 text-red-700"
                : summary.status === "watch"
                  ? "bg-amber-50 text-amber-700"
                  : "bg-emerald-50 text-emerald-700"
            }`}
          >
            <AlertTriangle className="h-3 w-3" />
            {summary.status}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {[
            ["Crossings", summary.crossingCount],
            ["Conflicts", summary.conflictCount],
            ["Watch", summary.watchCount],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-500">
          Coordination evidence is review-only. Clearance and reroute guidance do not approve construction or replace the responsible engineer.
        </p>
      </section>

      <section className="min-w-0 rounded-xl border border-slate-200 bg-white/90 p-3 shadow-sm" data-testid="utility-crossing-table">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Crossing Table</p>
          <Table2 className="h-4 w-4 text-slate-400" />
        </div>
        <div className="mt-3 overflow-hidden rounded-lg border border-slate-200">
          <div className="grid grid-cols-[1.2fr_0.7fr_0.7fr_0.7fr] bg-slate-50 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">
            <span>Pair</span>
            <span>Type</span>
            <span>Clearance</span>
            <span>Score</span>
          </div>
          <div className="max-h-36 overflow-auto">
            {rows.length ? (
              rows.map((row) => (
                <div key={row.id} className="grid grid-cols-[1.2fr_0.7fr_0.7fr_0.7fr] border-t border-slate-100 px-3 py-2 text-xs">
                  <span className="min-w-0 truncate font-semibold text-slate-800">{row.systemA} / {row.systemB}</span>
                  <span className="capitalize text-slate-500">{row.crossingType}</span>
                  <span className={row.status === "conflict" ? "font-semibold text-red-700" : row.status === "watch" ? "font-semibold text-amber-700" : "font-semibold text-emerald-700"}>
                    {formatClearance(row.clearanceFt)}
                  </span>
                  <span className="font-semibold text-slate-800">{row.constructabilityScore}</span>
                </div>
              ))
            ) : (
              <div className="px-3 py-4 text-sm text-slate-500">No crossing evidence has been generated yet.</div>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white/90 p-3 shadow-sm" data-testid="utility-constructability-scoring">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Constructability</p>
          <ShieldCheck className="h-4 w-4 text-slate-400" />
        </div>
        <div className="mt-3">
          <div className="flex items-end justify-between gap-3">
            <span className="text-3xl font-semibold text-slate-900">{summary.avgScore}</span>
            <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">review score</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full rounded-full ${
                summary.avgScore < 55 ? "bg-red-500" : summary.avgScore < 75 ? "bg-amber-500" : "bg-emerald-500"
              }`}
              style={{ width: `${Math.min(Math.max(summary.avgScore, 4), 100)}%` }}
            />
          </div>
        </div>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" data-testid="utility-clearance-view">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Vertical / Horizontal Clearance</p>
          <p className="mt-1 text-xs font-semibold text-slate-700">
            {verticalCount} vertical · {horizontalCount} horizontal
          </p>
        </div>
        <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2" data-testid="utility-reroute-options">
          <div className="flex items-center gap-2">
            <Route className="h-3.5 w-3.5 text-slate-400" />
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Reroute Options</p>
          </div>
          <p className="mt-1 line-clamp-2 text-xs font-medium text-slate-700">
            {highlightedReroute || "Generate utilities to see reroute options."}
          </p>
        </div>
      </section>
      </div>
    </details>
  );
}
