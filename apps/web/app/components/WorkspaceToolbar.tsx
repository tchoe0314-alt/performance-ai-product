"use client";

import React from "react";

type WorkspaceToolbarProps = {
  onRefreshWorkspace: () => void;
};

export default function WorkspaceToolbar({
  onRefreshWorkspace,
}: WorkspaceToolbarProps) {
  return (
    <div className="flex items-center justify-between border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex items-center gap-2">
        <a
          href="/upgrades"
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Upgrades
        </a>
        <button
          type="button"
          onClick={onRefreshWorkspace}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
