"use client";

import React from "react";

import type { StrategyMode } from "../types";
import { TextInput } from "./ui";

type DisciplineToggle = {
  label: string;
  checked: boolean;
  onToggle: () => void;
};

type ProjectControlsProps = {
  strategyMode: StrategyMode;
  onStrategyModeChange: (mode: StrategyMode) => void;
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
  strategyMode,
  onStrategyModeChange,
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
      <div className="grid gap-3 md:grid-cols-[repeat(3,minmax(0,1fr))] xl:grid-cols-[repeat(6,minmax(0,1fr))]">
        {[
          {
            value: "manual",
            label: "Manual",
            desc: "Strict and explicit",
          },
          {
            value: "assisted",
            label: "Assisted",
            desc: "AI fills gaps",
          },
        ].map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onStrategyModeChange(option.value as StrategyMode)}
            className={`rounded-2xl border px-4 py-3 text-left transition ${
              strategyMode === option.value
                ? "border-slate-900 bg-slate-950 text-white"
                : "border-slate-200 bg-white text-slate-900 hover:bg-slate-50"
            }`}
          >
            <p className="text-sm font-medium">{option.label}</p>
            <p
              className={`mt-1 text-xs ${
                strategyMode === option.value ? "text-slate-300" : "text-slate-500"
              }`}
            >
              {option.desc}
            </p>
          </button>
        ))}

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

      <div className="flex flex-wrap gap-2">
        {disciplineToggles.map(({ label, checked, onToggle }) => (
          <button
            key={label}
            type="button"
            onClick={onToggle}
            className={`rounded-full border px-3 py-2 text-xs font-medium transition ${
              checked
                ? "border-slate-900 bg-slate-950 text-white"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
