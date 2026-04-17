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
      </div>

      <div className="hidden" />
    </div>
  );
}
