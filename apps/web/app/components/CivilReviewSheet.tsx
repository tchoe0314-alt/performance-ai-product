"use client";

import { useState } from "react";

import type { BuildingPlacement } from "../types";

type CivilReviewSheetProps = {
  projectName: string;
  addressLabel: string;
  lotWidth: number;
  lotHeight: number;
  placements: BuildingPlacement[];
  sourceCandidateCount: number;
  missingSources: string[];
  generatedAt?: string;
};

const SHEET_WIDTH = 1200;
const SHEET_HEIGHT = 760;
const VIEW_X = 318;
const VIEW_Y = 86;
const VIEW_W = 812;
const VIEW_H = 424;

const objectTone: Record<string, { fill: string; stroke: string; dash?: string }> = {
  site: { fill: "rgba(255,255,255,0)", stroke: "#111827" },
  building: { fill: "#e5e7eb", stroke: "#475569" },
  office_building: { fill: "#e5e7eb", stroke: "#475569" },
  parking: { fill: "#f8fafc", stroke: "#64748b" },
  basin: { fill: "#dbeafe", stroke: "#2563eb" },
  driveway: { fill: "#e2e8f0", stroke: "#475569" },
  road: { fill: "#e2e8f0", stroke: "#475569" },
  sidewalk: { fill: "#fef3c7", stroke: "#d97706" },
  utility_corridor: { fill: "rgba(255,255,255,0)", stroke: "#9333ea", dash: "8 6" },
  hydrant: { fill: "#fee2e2", stroke: "#dc2626" },
  inlet: { fill: "#dbeafe", stroke: "#2563eb" },
  outfall: { fill: "#dcfce7", stroke: "#16a34a" },
  manhole: { fill: "#f1f5f9", stroke: "#334155" },
  custom: { fill: "rgba(226,232,240,.5)", stroke: "#64748b" },
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function formatFt(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "not set";
  return `${Math.round(value).toLocaleString()} ft`;
}

function displayType(type?: string): string {
  return String(type || "object").replaceAll("_", " ");
}

function toTitleCase(value: string): string {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isUtility(type?: string): boolean {
  return ["utility_corridor", "hydrant", "inlet", "outfall", "manhole"].includes(type || "");
}

function toSheetRect(item: BuildingPlacement, scaleX: number, scaleY: number) {
  const x = VIEW_X + clamp((item.x ?? 0) * scaleX, 0, VIEW_W);
  const y = VIEW_Y + clamp((item.y ?? 0) * scaleY, 0, VIEW_H);
  const w = clamp(Math.max(4, item.w * scaleX), 4, VIEW_W);
  const h = clamp(Math.max(4, item.d * scaleY), 4, VIEW_H);
  return {
    x: clamp(x, VIEW_X, VIEW_X + VIEW_W - w),
    y: clamp(y, VIEW_Y, VIEW_Y + VIEW_H - h),
    w,
    h,
  };
}

function uniqueTypes(placements: BuildingPlacement[]): string[] {
  const values = new Set(
    placements
      .filter((item) => item.type && item.type !== "site" && !Boolean(item.meta?.ui_hidden))
      .map((item) => displayType(item.type)),
  );
  return Array.from(values).slice(0, 8);
}

export default function CivilReviewSheet({
  projectName,
  addressLabel,
  lotWidth,
  lotHeight,
  placements,
  sourceCandidateCount,
  missingSources,
  generatedAt,
}: CivilReviewSheetProps) {
  const [expanded, setExpanded] = useState(false);
  const width = lotWidth > 0 ? lotWidth : placements.find((item) => item.type === "site")?.w || 1000;
  const height = lotHeight > 0 ? lotHeight : placements.find((item) => item.type === "site")?.d || 1000;
  const scaleX = VIEW_W / Math.max(width, 1);
  const scaleY = VIEW_H / Math.max(height, 1);
  const visiblePlacements = placements.filter((item) => !Boolean(item.meta?.ui_hidden));
  const sheetObjects = visiblePlacements.filter((item) => item.type !== "site" && item.placed !== false);
  const utilityObjects = sheetObjects.filter((item) => isUtility(item.type));
  const planObjects = sheetObjects.filter((item) => !isUtility(item.type));
  const legendTypes = uniqueTypes(visiblePlacements);
  const dateLabel = new Intl.DateTimeFormat("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "2-digit",
    }).format(generatedAt ? new Date(generatedAt) : new Date());

  return (
    <section
      className={`overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm ${
        expanded ? "fixed inset-4 z-[90] flex flex-col" : ""
      }`}
      data-testid="civil-review-sheet-preview"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            Civil Review Sheet
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-950">
            Plan-sheet style review package preview
          </p>
          <p className="mt-1 max-w-xl text-xs leading-5 text-slate-500">
            Formatted like a professional review sheet with a plan viewport, legend, notes, profile strip, and title block. It is still review-only.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-amber-700">
            Not for construction
          </span>
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50"
            data-testid="civil-review-sheet-expand"
          >
            {expanded ? "Close full sheet" : "View full sheet"}
          </button>
        </div>
      </div>

      <div className={`${expanded ? "min-h-0 flex-1 overflow-auto bg-slate-100 p-4" : "bg-slate-100 p-3"}`}>
        <div className="mx-auto max-w-full overflow-auto rounded-xl border border-slate-300 bg-slate-200 p-2">
          <svg
            role="img"
            aria-label="Civil review sheet preview"
            viewBox={`0 0 ${SHEET_WIDTH} ${SHEET_HEIGHT}`}
            className={`${expanded ? "w-full min-w-[1100px]" : "min-w-[900px]"} bg-white`}
            data-testid="civil-review-sheet-svg"
          >
            <defs>
              <pattern id="civil-sheet-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2e8f0" strokeWidth="1" />
              </pattern>
              <pattern id="civil-sheet-profile-grid" width="36" height="20" patternUnits="userSpaceOnUse">
                <path d="M 36 0 L 0 0 0 20" fill="none" stroke="#e5e7eb" strokeWidth="1" />
              </pattern>
            </defs>

            <rect x="18" y="18" width="1164" height="724" fill="#fff" stroke="#111827" strokeWidth="3" />
            <rect x="34" y="34" width="1132" height="692" fill="#fff" stroke="#475569" strokeWidth="1.5" />

            <g data-testid="civil-review-sheet-notes">
              <rect x="54" y="64" width="228" height="190" fill="#f8fafc" stroke="#cbd5e1" />
              <text x="70" y="92" fontSize="18" fontWeight="700" fill="#0f172a">GENERAL NOTES</text>
              {[
                "1. Review-only planning exhibit.",
                "2. Source labels remain required.",
                "3. Survey/control required before reliance.",
                "4. Utility locations require owner/field proof.",
                "5. Geometry is draft until reviewed.",
              ].map((note, index) => (
                <text key={note} x="70" y={124 + index * 24} fontSize="14" fill="#334155">
                  {note}
                </text>
              ))}
            </g>

            <g data-testid="civil-review-sheet-legend">
              <rect x="54" y="276" width="228" height="194" fill="#fff" stroke="#cbd5e1" />
              <text x="70" y="304" fontSize="18" fontWeight="700" fill="#0f172a">LEGEND</text>
              {(legendTypes.length ? legendTypes : ["site boundary", "draft object", "utility review"]).map((label, index) => {
                const typeKey = label.replaceAll(" ", "_");
                const tone = objectTone[typeKey] || objectTone.custom;
                return (
                  <g key={`${label}-${index}`}>
                    <rect
                      x="72"
                      y={328 + index * 20}
                      width="28"
                      height="10"
                      rx="2"
                      fill={tone.fill}
                      stroke={tone.stroke}
                      strokeDasharray={tone.dash}
                    />
                    <text x="112" y={338 + index * 20} fontSize="13" fill="#334155">
                      {toTitleCase(label)}
                    </text>
                  </g>
                );
              })}
            </g>

            <g data-testid="civil-review-sheet-vicinity">
              <rect x="54" y="492" width="228" height="120" fill="#f8fafc" stroke="#cbd5e1" />
              <text x="70" y="520" fontSize="18" fontWeight="700" fill="#0f172a">VICINITY</text>
              <path d="M88 576 C126 540 162 604 214 552" fill="none" stroke="#94a3b8" strokeWidth="8" strokeLinecap="round" />
              <path d="M80 590 L236 540" fill="none" stroke="#cbd5e1" strokeWidth="5" strokeLinecap="round" />
              <circle cx="168" cy="570" r="12" fill="#111827" />
              <text x="70" y="600" fontSize="12" fill="#64748b">Context map placeholder from project sources.</text>
            </g>

            <g data-testid="civil-review-sheet-plan">
              <rect x={VIEW_X} y={VIEW_Y} width={VIEW_W} height={VIEW_H} fill="url(#civil-sheet-grid)" stroke="#111827" strokeWidth="2" />
              <rect x={VIEW_X + 20} y={VIEW_Y + 20} width={VIEW_W - 40} height={VIEW_H - 40} fill="none" stroke="#111827" strokeWidth="2.5" strokeDasharray="12 8" />
              <text x={VIEW_X} y={VIEW_Y - 22} fontSize="20" fontWeight="700" fill="#0f172a">SITE / UTILITY REVIEW PLAN</text>
              <text x={VIEW_X} y={VIEW_Y - 4} fontSize="12" fontWeight="600" fill="#64748b">
                Source-backed where available · draft geometry stays review-required
              </text>

              {planObjects.map((item) => {
                const rect = toSheetRect(item, scaleX, scaleY);
                const tone = objectTone[item.type || "custom"] || objectTone.custom;
                const radius = item.type === "basin" ? 22 : item.type === "road" || item.type === "driveway" ? 18 : 6;
                return (
                  <g key={item.id}>
                    <rect
                      x={rect.x}
                      y={rect.y}
                      width={rect.w}
                      height={rect.h}
                      rx={radius}
                      fill={tone.fill}
                      stroke={tone.stroke}
                      strokeWidth={item.type === "road" || item.type === "driveway" ? 5 : 2.5}
                      strokeDasharray={tone.dash}
                      opacity={item.source === "generated" ? 0.9 : 1}
                    />
                    {item.type === "parking" && rect.w > 70 && rect.h > 36
                      ? Array.from({ length: Math.min(10, Math.max(3, Math.floor(rect.w / 34))) }).map((_, index) => (
                          <line
                            key={`${item.id}-stall-${index}`}
                            x1={rect.x + 12 + index * 32}
                            x2={rect.x + 12 + index * 32}
                            y1={rect.y + 8}
                            y2={rect.y + rect.h - 8}
                            stroke="#94a3b8"
                            strokeWidth="1.5"
                          />
                        ))
                      : null}
                    {item.type === "basin" ? (
                      <>
                        <ellipse cx={rect.x + rect.w / 2} cy={rect.y + rect.h / 2} rx={Math.max(12, rect.w * 0.32)} ry={Math.max(10, rect.h * 0.24)} fill="none" stroke="#60a5fa" strokeWidth="2" />
                        <ellipse cx={rect.x + rect.w / 2} cy={rect.y + rect.h / 2} rx={Math.max(8, rect.w * 0.18)} ry={Math.max(6, rect.h * 0.12)} fill="#bfdbfe" stroke="#3b82f6" strokeWidth="1.5" />
                      </>
                    ) : null}
                  </g>
                );
              })}

              {utilityObjects.map((item, index) => {
                const rect = toSheetRect(item, scaleX, scaleY);
                const tone = objectTone[item.type || "utility_corridor"] || objectTone.utility_corridor;
                const y = rect.y + rect.h / 2 + (index % 3) * 8;
                return (
                  <g key={item.id}>
                    <path
                      d={`M ${VIEW_X + 36} ${y} C ${rect.x} ${y - 32}, ${rect.x + rect.w} ${y + 20}, ${VIEW_X + VIEW_W - 42} ${y}`}
                      fill="none"
                      stroke={tone.stroke}
                      strokeWidth="3"
                      strokeDasharray={tone.dash || "10 7"}
                      strokeLinecap="round"
                    />
                    <circle cx={rect.x + rect.w / 2} cy={rect.y + rect.h / 2} r="7" fill={tone.fill === "rgba(255,255,255,0)" ? "#fff" : tone.fill} stroke={tone.stroke} strokeWidth="2" />
                  </g>
                );
              })}

              <g>
                <path d={`M ${VIEW_X + VIEW_W - 70} ${VIEW_Y + 72} L ${VIEW_X + VIEW_W - 48} ${VIEW_Y + 28} L ${VIEW_X + VIEW_W - 26} ${VIEW_Y + 72} Z`} fill="#111827" />
                <text x={VIEW_X + VIEW_W - 52} y={VIEW_Y + 90} textAnchor="middle" fontSize="13" fontWeight="700" fill="#111827">N</text>
              </g>
              <g>
                <line x1={VIEW_X + 34} x2={VIEW_X + 174} y1={VIEW_Y + VIEW_H - 28} y2={VIEW_Y + VIEW_H - 28} stroke="#111827" strokeWidth="5" />
                <line x1={VIEW_X + 34} x2={VIEW_X + 34} y1={VIEW_Y + VIEW_H - 38} y2={VIEW_Y + VIEW_H - 18} stroke="#111827" strokeWidth="2" />
                <line x1={VIEW_X + 174} x2={VIEW_X + 174} y1={VIEW_Y + VIEW_H - 38} y2={VIEW_Y + VIEW_H - 18} stroke="#111827" strokeWidth="2" />
                <text x={VIEW_X + 104} y={VIEW_Y + VIEW_H - 44} textAnchor="middle" fontSize="12" fontWeight="700" fill="#334155">
                  {formatFt(Math.min(width, height) / 5)}
                </text>
              </g>
            </g>

            <g data-testid="civil-review-sheet-profile">
              <rect x="318" y="544" width="812" height="112" fill="url(#civil-sheet-profile-grid)" stroke="#111827" strokeWidth="2" />
              <text x="318" y="530" fontSize="18" fontWeight="700" fill="#0f172a">SCHEMATIC PROFILE / REVIEW STRIP</text>
              <path d="M344 626 C462 590 570 620 690 584 C810 550 918 596 1104 558" fill="none" stroke="#64748b" strokeWidth="3" />
              <path d="M344 616 C520 614 706 606 1104 594" fill="none" stroke="#9333ea" strokeWidth="3" strokeDasharray="12 8" />
              <path d="M344 638 C508 638 672 630 1104 628" fill="none" stroke="#2563eb" strokeWidth="3" strokeDasharray="4 8" />
              <text x="344" y="574" fontSize="12" fontWeight="700" fill="#64748b">EG/FG review profile</text>
              <text x="344" y="608" fontSize="12" fontWeight="700" fill="#9333ea">Utility review alignment</text>
              <text x="344" y="652" fontSize="12" fontWeight="700" fill="#2563eb">Storm/water schematic</text>
            </g>

            <g data-testid="civil-review-sheet-title-block">
              <rect x="54" y="638" width="1076" height="70" fill="#fff" stroke="#111827" strokeWidth="2" />
              <line x1="430" y1="638" x2="430" y2="708" stroke="#111827" />
              <line x1="760" y1="638" x2="760" y2="708" stroke="#111827" />
              <line x1="964" y1="638" x2="964" y2="708" stroke="#111827" />
              <text x="72" y="662" fontSize="18" fontWeight="800" fill="#0f172a">CIVORA REVIEW PLAN</text>
              <text x="72" y="686" fontSize="13" fill="#334155">{projectName || "Untitled Project"}</text>
              <text x="448" y="662" fontSize="12" fontWeight="700" fill="#64748b">ADDRESS / CONTEXT</text>
              <text x="448" y="686" fontSize="13" fill="#0f172a">{addressLabel || "No address applied"}</text>
              <text x="778" y="662" fontSize="12" fontWeight="700" fill="#64748b">SITE SIZE</text>
              <text x="778" y="686" fontSize="13" fill="#0f172a">{formatFt(width)} x {formatFt(height)}</text>
              <text x="982" y="658" fontSize="12" fontWeight="700" fill="#64748b">SHEET</text>
              <text x="982" y="684" fontSize="24" fontWeight="800" fill="#0f172a">C-0.1</text>
              <text x="1050" y="684" fontSize="12" fill="#334155">{dateLabel}</text>
            </g>

            <g>
              <rect x="318" y="668" width="476" height="40" fill="#fff7ed" stroke="#fed7aa" />
              <text x="334" y="692" fontSize="14" fontWeight="800" fill="#c2410c">
                REVIEW ONLY - NOT FOR CONSTRUCTION
              </text>
            </g>

            <g data-testid="civil-review-sheet-source-summary">
              <text x="54" y="724" fontSize="12" fontWeight="700" fill="#475569">
                Source candidates: {sourceCandidateCount} · Missing: {missingSources.slice(0, 3).join(", ") || "none reported"} · Output requires qualified review.
              </text>
            </g>
          </svg>
        </div>
      </div>
    </section>
  );
}
