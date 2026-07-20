import type { ReactNode } from "react";

import type { BuildingPlacement } from "../types";

type DetailProfileRow = {
  label: string;
  value: string;
};

type DashboardDetailsPanelProps = {
  profileRows: DetailProfileRow[];
  selectedInspector: ReactNode;
  objects: BuildingPlacement[];
  activePlacementId: string | null;
  onSelectObject: (id: string) => void;
};

const isDraftReviewGeometry = (item: BuildingPlacement) => {
  const meta = item.meta && typeof item.meta === "object" ? item.meta as Record<string, unknown> : {};
  return (
    item.type === "custom" ||
    item.source === "manual_drawn" ||
    meta.classification_status === "draft_review_required" ||
    meta.engineering_status === "draft_review_required"
  );
};

export function DashboardDetailsPanel({
  profileRows,
  selectedInspector,
  objects,
  activePlacementId,
  onSelectObject,
}: DashboardDetailsPanelProps) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Profiles and cross sections</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          {profileRows.map(({ label, value }) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <p className="font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
              <p className="mt-1 font-semibold text-slate-800">{value}</p>
            </div>
          ))}
        </div>
      </div>
      {selectedInspector}
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Object list</p>
        <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
          {objects.length ? (
            objects.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectObject(item.id)}
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm font-semibold transition ${
                  activePlacementId === item.id
                    ? "border-slate-950 bg-slate-950 text-white"
                    : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-white"
                }`}
              >
                {item.label}
                <span className="mt-1 block text-[10px] uppercase tracking-[0.12em] opacity-70">
                  {isDraftReviewGeometry(item)
                    ? "Canonical geometry · Draft review required"
                    : `${item.placed ? "Placed" : "Not placed"} · ${item.locked ? "Locked" : "Editable"}`}
                </span>
              </button>
            ))
          ) : (
            <p className="text-sm text-slate-500">No objects yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
