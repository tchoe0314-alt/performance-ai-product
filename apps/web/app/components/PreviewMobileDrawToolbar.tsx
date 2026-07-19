import type { ComponentType } from "react";
import type { DrawMode } from "../utils/cadToolTypes";

type DrawModeButton = {
  mode: DrawMode;
  label: string;
  icon: ComponentType<{ className?: string }>;
  disabled?: boolean;
  disabledLabel?: string;
};

function mobileDrawLabel(mode: DrawMode, label: string) {
  if (mode === "site") return "Site";
  if (mode === "polyline") return "Line";
  if (mode === "polygon") return "Area";
  if (mode === "rect") return "Box";
  if (mode === "point") return "Point";
  return label;
}

export function PreviewMobileDrawToolbar({
  drawModeButtons,
  drawMode,
  compactViewport,
  canFinishDraftGeometry,
  finishDraftBlockedReason,
  selectedDeletable,
  siteLocked,
  onActivateTool,
  onFinish,
  onCancel,
  onChangeSite,
  onResetView,
  onDeleteSelected,
}: {
  drawModeButtons: DrawModeButton[];
  drawMode: DrawMode;
  compactViewport: boolean;
  canFinishDraftGeometry: boolean;
  finishDraftBlockedReason: string | null;
  selectedDeletable: boolean;
  siteLocked: boolean;
  onActivateTool: (mode: DrawMode, blockedMessage?: string) => void;
  onFinish: () => void;
  onCancel: () => void;
  onChangeSite?: () => void;
  onResetView: () => void;
  onDeleteSelected: () => void;
}) {
  return (
    <div className="absolute inset-x-1 bottom-1 z-[70] max-h-[52%] overflow-y-auto rounded-xl border border-slate-200 bg-white/95 p-2 shadow-[0_20px_50px_-28px_rgba(15,23,42,0.55)] backdrop-blur sm:inset-x-2 sm:bottom-2 md:hidden">
      <div className="grid grid-cols-4 gap-1.5 pb-1 min-[420px]:grid-cols-7">
        {drawModeButtons.map((item) => {
          const Icon = item.icon;
          const active = drawMode === item.mode;
          const disabled = Boolean(item.disabled);
          const label = mobileDrawLabel(item.mode, item.label);
          return (
            <button
              key={`mobile-${item.mode}`}
              type="button"
              data-testid={compactViewport && item.mode === "site" ? "draw-site-boundary-toolbar-mobile" : undefined}
              title={disabled ? item.disabledLabel ?? item.label : item.label}
              aria-label={item.mode === "site" ? "Site boundary drawing tool" : item.label}
              data-blocked={disabled ? "true" : undefined}
              onClick={() => onActivateTool(item.mode, disabled ? item.disabledLabel ?? `${item.label} blocked.` : undefined)}
              className={`relative z-[90] inline-flex min-h-10 min-w-0 items-center justify-center gap-1 rounded-lg border px-1.5 py-2 text-[11px] font-semibold transition ${
                active
                  ? "border-slate-900 bg-slate-950 text-white"
                  : disabled
                    ? "border-amber-200 bg-amber-50 text-amber-700"
                    : "border-slate-200 bg-white text-slate-700"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span className="truncate">{label}</span>
            </button>
          );
        })}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {drawMode !== "select" && drawMode !== "point" ? (
          <button
            type="button"
            onClick={onFinish}
            disabled={!canFinishDraftGeometry}
            title={finishDraftBlockedReason ?? "Finish drawn geometry"}
            className={`relative z-[90] min-h-10 flex-1 rounded-lg border px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] ${
              !canFinishDraftGeometry
                ? "cursor-not-allowed border-amber-200 bg-amber-50 text-amber-800"
                : "border-slate-900 bg-slate-950 text-white"
            }`}
          >
            Finish
          </button>
        ) : null}
        <button
          type="button"
          onClick={onCancel}
          className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700"
        >
          Cancel
        </button>
        {siteLocked && onChangeSite ? (
          <button
            type="button"
            title="Unlock the site boundary for editing"
            aria-label="Change Site Boundary"
            onClick={onChangeSite}
            className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700"
          >
            Change Site
          </button>
        ) : null}
        <button
          type="button"
          onClick={onResetView}
          className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700"
        >
          Reset
        </button>
        <button
          type="button"
          disabled={!selectedDeletable}
          onClick={onDeleteSelected}
          className="min-h-10 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-300"
        >
          Delete
        </button>
      </div>
      {finishDraftBlockedReason ? (
        <p className="mt-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700">
          {finishDraftBlockedReason}
        </p>
      ) : null}
    </div>
  );
}
