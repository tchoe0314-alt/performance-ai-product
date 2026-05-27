"use client";

import { TextInput } from "./ui";

type DisciplineToggle = {
  label: string;
  checked: boolean;
  onToggle: () => void;
};

type ProjectControlsProps = {
  siteName: string;
  fileName: string;
  onSiteNameChange: (value: string) => void;
  onFileNameChange: (value: string) => void;
  onSiteNameEdited: () => void;
  onFileNameEdited: () => void;
  onSaveProjectNames: () => void;
  onRefreshWorkspace: () => void;
  disciplineToggles: DisciplineToggle[];
};

export default function ProjectControls({
  siteName,
  fileName,
  onSiteNameChange,
  onFileNameChange,
  onSiteNameEdited,
  onFileNameEdited,
  onSaveProjectNames,
  onRefreshWorkspace,
  disciplineToggles,
}: ProjectControlsProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="w-full lg:hidden">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
          Current Project
        </p>
        <p className="mt-1 truncate text-sm font-semibold text-slate-950">
          {siteName || "Untitled Project"}
        </p>
      </div>
      <div className="grid min-w-0 flex-1 gap-3 md:grid-cols-[minmax(180px,280px)_minmax(180px,280px)]">
        <TextInput
          value={siteName}
          onChange={(e) => {
            onSiteNameChange(e.target.value);
            onSiteNameEdited();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              onSaveProjectNames();
            }
          }}
          placeholder="Project name"
        />

        <div className="flex items-center gap-2">
          <TextInput
            value={fileName}
            onChange={(e) => {
              onFileNameChange(e.target.value);
              onFileNameEdited();
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                onSaveProjectNames();
              }
            }}
            placeholder="File name"
          />
          <button
            type="button"
            onClick={onRefreshWorkspace}
            className="h-10 whitespace-nowrap rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {disciplineToggles.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={item.onToggle}
            className={`rounded-lg border px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
              item.checked
                ? "border-slate-900 bg-slate-950 text-white"
                : "border-slate-200 bg-white text-slate-500 hover:text-slate-900"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
