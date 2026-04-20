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
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-[repeat(2,minmax(0,1fr))] xl:grid-cols-[repeat(4,minmax(0,1fr))]">
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
            className="h-10 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="hidden" />
    </div>
  );
}
