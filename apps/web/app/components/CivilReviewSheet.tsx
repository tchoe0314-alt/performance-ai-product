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
const PLAN_X = 70;
const PLAN_Y = 74;
const PLAN_W = 850;
const PLAN_H = 610;
const TITLE_X = 938;
const TITLE_W = 194;

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

function isUtility(type?: string): boolean {
  return ["utility_corridor", "hydrant", "inlet", "outfall", "manhole"].includes(type || "");
}

function toTitleCase(value: string): string {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function uniqueTypes(placements: BuildingPlacement[]): string[] {
  const values = new Set(
    placements
      .filter((item) => item.type && item.type !== "site" && !Boolean(item.meta?.ui_hidden))
      .map((item) => displayType(item.type)),
  );
  return Array.from(values).slice(0, 8);
}

function toPlanRect(item: BuildingPlacement, scaleX: number, scaleY: number) {
  const w = clamp(Math.max(8, item.w * scaleX), 8, PLAN_W);
  const h = clamp(Math.max(8, item.d * scaleY), 8, PLAN_H);
  const x = PLAN_X + clamp((item.x ?? 0) * scaleX, 0, PLAN_W - w);
  const y = PLAN_Y + clamp((item.y ?? 0) * scaleY, 0, PLAN_H - h);
  return { x, y, w, h };
}

function ParkingStalls({ x, y, w, h }: { x: number; y: number; w: number; h: number }) {
  const count = Math.min(24, Math.max(6, Math.floor(w / 18)));
  const spacing = w / count;
  return (
    <g>
      <line x1={x + 8} x2={x + w - 8} y1={y + h * 0.5} y2={y + h * 0.5} stroke="#111" strokeWidth="2" />
      {Array.from({ length: count + 1 }).map((_, index) => (
        <line
          key={`stall-${x}-${y}-${index}`}
          x1={x + index * spacing}
          x2={x + index * spacing + 10}
          y1={y + 4}
          y2={y + h * 0.5 - 4}
          stroke="#111"
          strokeWidth="1.2"
        />
      ))}
      {Array.from({ length: count + 1 }).map((_, index) => (
        <line
          key={`stall-lower-${x}-${y}-${index}`}
          x1={x + index * spacing + 10}
          x2={x + index * spacing}
          y1={y + h * 0.5 + 4}
          y2={y + h - 4}
          stroke="#111"
          strokeWidth="1.2"
        />
      ))}
    </g>
  );
}

function SheetTable({ x, y, rows }: { x: number; y: number; rows: string[] }) {
  return (
    <g>
      <rect x={x} y={y} width="128" height={rows.length * 17 + 12} fill="#fff" stroke="#111" strokeWidth="1.2" />
      {rows.map((row, index) => (
        <g key={row}>
          <line x1={x} x2={x + 128} y1={y + 12 + index * 17} y2={y + 12 + index * 17} stroke="#111" strokeWidth="0.6" />
          <text x={x + 8} y={y + 24 + index * 17} fontSize="8" fontWeight="700" fill="#111">
            {row}
          </text>
        </g>
      ))}
    </g>
  );
}

function DenseParkingRow({
  x,
  y,
  length,
  stalls = 18,
  vertical = false,
  reverse = false,
}: {
  x: number;
  y: number;
  length: number;
  stalls?: number;
  vertical?: boolean;
  reverse?: boolean;
}) {
  const spacing = length / stalls;
  return (
    <g data-testid="civil-review-sheet-dense-parking">
      {vertical ? (
        <>
          <line x1={x} x2={x} y1={y} y2={y + length} stroke="#111" strokeWidth="1.2" />
          {Array.from({ length: stalls + 1 }).map((_, index) => (
            <line
              key={`vstall-${x}-${y}-${index}`}
              x1={x}
              x2={x + (reverse ? -24 : 24)}
              y1={y + index * spacing}
              y2={y + index * spacing + 8}
              stroke="#111"
              strokeWidth="0.9"
            />
          ))}
        </>
      ) : (
        <>
          <line x1={x} x2={x + length} y1={y} y2={y} stroke="#111" strokeWidth="1.2" />
          {Array.from({ length: stalls + 1 }).map((_, index) => (
            <line
              key={`hstall-${x}-${y}-${index}`}
              x1={x + index * spacing}
              x2={x + index * spacing + 8}
              y1={y}
              y2={y + (reverse ? -24 : 24)}
              stroke="#111"
              strokeWidth="0.9"
            />
          ))}
        </>
      )}
    </g>
  );
}

function DenseBuilding({
  x,
  y,
  w,
  h,
  label = "MULTI-UNIT BUILDING",
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string;
}) {
  return (
    <g data-testid="civil-review-sheet-dense-building">
      <rect x={x} y={y} width={w} height={h} fill="#fff" stroke="#111" strokeWidth="1.6" />
      <rect x={x + 9} y={y + 7} width={w - 18} height={h - 14} fill="none" stroke="#111" strokeWidth="0.55" strokeDasharray="2 3" />
      <text x={x + w / 2} y={y + h / 2 + 3} textAnchor="middle" fontSize="8" fontWeight="700" fill="#111">
        {label}
      </text>
    </g>
  );
}

function DenseCivilPlanContent() {
  const gradeLabels: Array<[number, number, string]> = [
    [132, 118, "22.10"],
    [205, 118, "22.22"],
    [302, 112, "22.38"],
    [440, 126, "22.46"],
    [608, 112, "22.31"],
    [746, 128, "22.18"],
    [190, 275, "21.94"],
    [386, 310, "22.08"],
    [580, 294, "22.21"],
    [725, 354, "21.88"],
    [280, 512, "21.73"],
    [510, 548, "21.85"],
    [675, 505, "21.69"],
  ];
  const structureDots: Array<[number, number]> = [
    [190, 178],
    [366, 208],
    [515, 177],
    [705, 215],
    [232, 374],
    [462, 394],
    [632, 386],
    [758, 452],
    [326, 585],
    [548, 612],
  ];

  return (
    <g data-testid="civil-review-sheet-dense-plan">
      <path d="M 102 118 C 232 86, 393 86, 540 96 C 658 105, 765 93, 862 78" fill="none" stroke="#111" strokeWidth="1.8" />
      <path d="M 95 142 C 230 112, 397 112, 536 121 C 662 130, 758 120, 855 104" fill="none" stroke="#111" strokeWidth="0.9" strokeDasharray="8 5" />
      <path d="M 578 104 L 604 220 L 594 382 L 630 526 L 728 648" fill="none" stroke="#111" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M 578 104 L 604 220 L 594 382 L 630 526 L 728 648" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M 210 142 L 430 154 L 538 206 L 596 266 L 572 355 L 463 408 L 274 390 L 205 326 L 210 142 Z" fill="none" stroke="#111" strokeWidth="8" strokeLinejoin="round" />
      <path d="M 210 142 L 430 154 L 538 206 L 596 266 L 572 355 L 463 408 L 274 390 L 205 326 L 210 142 Z" fill="none" stroke="#fff" strokeWidth="4.4" strokeLinejoin="round" />
      <path d="M 288 433 L 520 438 L 628 492 L 670 596 L 742 649" fill="none" stroke="#111" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M 288 433 L 520 438 L 628 492 L 670 596 L 742 649" fill="none" stroke="#fff" strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round" />

      <DenseBuilding x={156} y={154} w={156} h={44} />
      <DenseBuilding x={336} y={164} w={142} h={42} />
      <DenseBuilding x={624} y={142} w={178} h={46} />
      <DenseBuilding x={628} y={260} w={176} h={48} />
      <DenseBuilding x={610} y={332} w={148} h={42} />
      <DenseBuilding x={214} y={454} w={188} h={46} />
      <DenseBuilding x={420} y={470} w={178} h={44} />
      <DenseBuilding x={348} y={312} w={130} h={130} label="CONDOMINIUM B" />
      <DenseBuilding x={502} y={594} w={95} h={54} label="TENNIS COURT" />

      <DenseParkingRow x={112} y={130} length={250} stalls={24} reverse />
      <DenseParkingRow x={368} y={132} length={174} stalls={17} reverse />
      <DenseParkingRow x={594} y={116} length={236} stalls={22} reverse />
      <DenseParkingRow x={124} y={212} length={190} stalls={18} />
      <DenseParkingRow x={344} y={226} length={220} stalls={22} />
      <DenseParkingRow x={618} y={218} length={214} stalls={20} />
      <DenseParkingRow x={322} y={528} length={286} stalls={28} />
      <DenseParkingRow x={190} y={421} length={230} stalls={22} reverse />
      <DenseParkingRow x={806} y={154} length={220} stalls={22} vertical />
      <DenseParkingRow x={792} y={382} length={236} stalls={22} vertical />
      <DenseParkingRow x={602} y={370} length={164} stalls={15} vertical reverse />
      <DenseParkingRow x={704} y={520} length={120} stalls={12} vertical />

      <g data-testid="civil-review-sheet-dense-utilities">
        <path d="M 116 238 C 284 262, 422 252, 570 286 C 690 314, 770 340, 860 330" fill="none" stroke="#111" strokeWidth="1.4" strokeDasharray="6 4" />
        <path d="M 128 548 C 320 520, 470 558, 612 575 C 720 588, 805 570, 878 530" fill="none" stroke="#111" strokeWidth="1.4" strokeDasharray="2 5" />
        <path d="M 232 110 L 248 258 L 310 400 L 405 532 L 512 654" fill="none" stroke="#111" strokeWidth="1.1" strokeDasharray="10 4 2 4" />
        <path d="M 720 96 L 700 260 L 728 418 L 760 640" fill="none" stroke="#111" strokeWidth="1.1" strokeDasharray="10 4 2 4" />
        {[185, 306, 456, 612, 742, 842].map((cx, index) => (
          <g key={`mh-${cx}`}>
            <circle cx={cx} cy={index % 2 ? 548 : 238} r="5" fill="#fff" stroke="#111" strokeWidth="1.4" />
            <text x={cx + 8} y={(index % 2 ? 548 : 238) + 3} fontSize="6.5" fill="#111">MH</text>
          </g>
        ))}
        {[270, 410, 555, 680, 790].map((cx, index) => (
          <rect key={`inlet-${cx}`} x={cx} y={index % 2 ? 414 : 214} width="10" height="5" fill="#fff" stroke="#111" strokeWidth="1" />
        ))}
      </g>

      <g data-testid="civil-review-sheet-dense-callouts">
        {["SPEED BUMP", "FIRE LANE", "SPEED BUMP", "24' DRIVE AISLE", "ADA ROUTE", "SPEED BUMP"].map((label, index) => {
          const x = 158 + index * 118;
          const y = index % 2 ? 394 : 104;
          return (
            <g key={`${label}-${index}`}>
              <line x1={x - 16} x2={x + 42} y1={y} y2={y - 10} stroke="#111" strokeWidth="0.7" />
              <text x={x} y={y - 14} fontSize="6.7" fontWeight="700" fill="#111">{label}</text>
            </g>
          );
        })}
        <text x="96" y="338" fontSize="7" fontWeight="700" fill="#111" transform="rotate(-90 96 338)">PROPERTY / REVIEW LIMIT</text>
        <text x="842" y="436" fontSize="7" fontWeight="700" fill="#111" transform="rotate(75 842 436)">ACCESS DRIVE</text>
        <text x="230" y="286" fontSize="8" fontWeight="700" fill="#111">CONDOMINIUM A</text>
        <text x="552" y="694" fontSize="8" fontWeight="700" fill="#111">MATCH SHEET 3.3</text>
      </g>

      {gradeLabels.map(([x, y, label]) => (
        <g key={`${x}-${y}-${label}`} data-testid="civil-review-sheet-dense-grade">
          <line x1={x - 11} x2={x + 11} y1={y} y2={y} stroke="#111" strokeWidth="0.7" />
          <text x={x - 10} y={y - 4} fontSize="6.5" fill="#111">{label}</text>
        </g>
      ))}
      {structureDots.map(([cx, cy]) => (
        <rect key={`${cx}-${cy}`} x={cx - 2} y={cy - 2} width="4" height="4" fill="#111" />
      ))}
    </g>
  );
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
  const scaleX = PLAN_W / Math.max(width, 1);
  const scaleY = PLAN_H / Math.max(height, 1);
  const visiblePlacements = placements.filter((item) => !Boolean(item.meta?.ui_hidden));
  const sheetObjects = visiblePlacements.filter((item) => item.type !== "site" && item.placed !== false);
  const utilityObjects = sheetObjects.filter((item) => isUtility(item.type));
  const planObjects = sheetObjects.filter((item) => !isUtility(item.type));
  const useDenseReferenceSheet = planObjects.length < 18;
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
            Blackline plan-sheet style review package preview
          </p>
          <p className="mt-1 max-w-xl text-xs leading-5 text-slate-500">
            Recreates the professional plan-sheet feel: border, dense site plan, right title block, legend, scale, north arrow, and review notes.
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
            aria-label="Civil blackline review sheet preview"
            viewBox={`0 0 ${SHEET_WIDTH} ${SHEET_HEIGHT}`}
            className={`${expanded ? "w-full min-w-[1120px]" : "min-w-[940px]"} bg-white`}
            data-testid="civil-review-sheet-svg"
          >
            <defs>
              <pattern id="civil-blackline-grid" width="34" height="34" patternUnits="userSpaceOnUse">
                <path d="M 34 0 L 0 0 0 34" fill="none" stroke="#e8e8e8" strokeWidth="0.7" />
              </pattern>
              <marker id="civil-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#111" />
              </marker>
            </defs>

            <rect x="20" y="20" width="1160" height="720" fill="#fff" stroke="#111" strokeWidth="3" />
            <rect x="36" y="36" width="1128" height="688" fill="#fff" stroke="#111" strokeWidth="1.4" />
            <rect x={PLAN_X} y={PLAN_Y} width={PLAN_W} height={PLAN_H} fill="url(#civil-blackline-grid)" stroke="#111" strokeWidth="2" />
            <path
              d={`M ${PLAN_X + 24} ${PLAN_Y + 74} C ${PLAN_X + 260} ${PLAN_Y + 28}, ${PLAN_X + 528} ${PLAN_Y + 50}, ${PLAN_X + PLAN_W - 52} ${PLAN_Y + 16} L ${PLAN_X + PLAN_W - 4} ${PLAN_Y + PLAN_H - 48} C ${PLAN_X + 660} ${PLAN_Y + PLAN_H - 4}, ${PLAN_X + 392} ${PLAN_Y + PLAN_H - 36}, ${PLAN_X + 26} ${PLAN_Y + PLAN_H - 18} Z`}
              fill="none"
              stroke="#111"
              strokeWidth="2.4"
              strokeDasharray="8 7"
            />
            <text x={PLAN_X + 392} y={PLAN_Y + PLAN_H - 10} fontSize="12" fontWeight="700" fill="#111">
              MATCH SHEET C-3.3
            </text>

            {useDenseReferenceSheet ? <DenseCivilPlanContent /> : null}

            {!useDenseReferenceSheet && planObjects.map((item) => {
              const rect = toPlanRect(item, scaleX, scaleY);
              const type = item.type || "custom";
              const isBuilding = type.includes("building") || type === "pad";
              const isParking = type === "parking";
              const isRoad = type === "road" || type === "driveway";
              const isBasin = type === "basin";
              return (
                <g key={item.id} data-testid="civil-review-sheet-plan-object">
                  {isRoad ? (
                    <>
                      <path
                        d={`M ${rect.x} ${rect.y + rect.h / 2} L ${rect.x + rect.w} ${rect.y + rect.h / 2}`}
                        stroke="#111"
                        strokeWidth={Math.max(12, rect.h * 0.38)}
                        strokeLinecap="round"
                        fill="none"
                      />
                      <path
                        d={`M ${rect.x} ${rect.y + rect.h / 2} L ${rect.x + rect.w} ${rect.y + rect.h / 2}`}
                        stroke="#fff"
                        strokeWidth={Math.max(6, rect.h * 0.18)}
                        strokeLinecap="round"
                        fill="none"
                      />
                    </>
                  ) : (
                    <rect
                      x={rect.x}
                      y={rect.y}
                      width={rect.w}
                      height={rect.h}
                      rx={isBasin ? 18 : 1}
                      fill="#fff"
                      stroke="#111"
                      strokeWidth={isBuilding ? 1.8 : 1.4}
                    />
                  )}
                  {isBuilding ? (
                    <>
                      <text x={rect.x + rect.w / 2} y={rect.y + rect.h / 2} textAnchor="middle" fontSize="9" fontWeight="700" fill="#111">
                        MULTI-UNIT BUILDING
                      </text>
                      <path d={`M ${rect.x + 12} ${rect.y + rect.h - 10} L ${rect.x + rect.w - 12} ${rect.y + rect.h - 10}`} stroke="#111" strokeWidth="0.8" />
                    </>
                  ) : null}
                  {isParking ? <ParkingStalls x={rect.x} y={rect.y} w={rect.w} h={rect.h} /> : null}
                  {isBasin ? (
                    <>
                      <ellipse cx={rect.x + rect.w / 2} cy={rect.y + rect.h / 2} rx={Math.max(12, rect.w * 0.34)} ry={Math.max(8, rect.h * 0.24)} fill="none" stroke="#111" strokeWidth="1" />
                      <ellipse cx={rect.x + rect.w / 2} cy={rect.y + rect.h / 2} rx={Math.max(8, rect.w * 0.18)} ry={Math.max(5, rect.h * 0.12)} fill="none" stroke="#111" strokeWidth="0.8" />
                    </>
                  ) : null}
                </g>
              );
            })}

            {!useDenseReferenceSheet && utilityObjects.map((item, index) => {
              const rect = toPlanRect(item, scaleX, scaleY);
              const y = rect.y + rect.h / 2 + (index % 4) * 8;
              return (
                <g key={item.id}>
                  <path
                    d={`M ${PLAN_X + 28} ${y} C ${rect.x + 60} ${y - 34}, ${rect.x + rect.w + 80} ${y + 28}, ${PLAN_X + PLAN_W - 36} ${y - 8}`}
                    fill="none"
                    stroke="#111"
                    strokeWidth="1.6"
                    strokeDasharray={index % 2 ? "8 5" : "3 5"}
                  />
                  <circle cx={rect.x + rect.w / 2} cy={rect.y + rect.h / 2} r="5" fill="#fff" stroke="#111" strokeWidth="1.6" />
                </g>
              );
            })}

            {!useDenseReferenceSheet && Array.from({ length: 36 }).map((_, index) => {
              const x = PLAN_X + 58 + (index % 9) * 88;
              const y = PLAN_Y + 80 + Math.floor(index / 9) * 118;
              return <circle key={`spot-${index}`} cx={x} cy={y} r="1.8" fill="#111" />;
            })}

            {!useDenseReferenceSheet && Array.from({ length: 14 }).map((_, index) => {
              const x = PLAN_X + 104 + index * 54;
              const y = PLAN_Y + 42 + (index % 2) * 468;
              return (
                <g key={`grade-${index}`}>
                  <line x1={x - 14} x2={x + 14} y1={y} y2={y} stroke="#111" strokeWidth="0.8" />
                  <text x={x - 8} y={y - 4} fontSize="7" fill="#111">22.{index}</text>
                </g>
              );
            })}

            <g data-testid="civil-review-sheet-plan">
              <text x={PLAN_X + 18} y={PLAN_Y + 20} fontSize="13" fontWeight="800" fill="#111">
                CIVORA SITE / UTILITY REVIEW PLAN
              </text>
              <text x={PLAN_X + 18} y={PLAN_Y + 36} fontSize="8" fontWeight="700" fill="#111">
                REVIEW REQUIRED · SOURCE-BACKED WHERE AVAILABLE · NOT A CONSTRUCTION DOCUMENT
              </text>
            </g>

            <g>
              <path d="M 840 120 L 854 70 L 868 120 Z" fill="#111" />
              <line x1="854" x2="854" y1="76" y2="150" stroke="#111" strokeWidth="2" />
              <text x="854" y="166" textAnchor="middle" fontSize="12" fontWeight="800" fill="#111">N</text>
              <line x1="794" x2="884" y1="206" y2="206" stroke="#111" strokeWidth="4" />
              <line x1="794" x2="794" y1="196" y2="216" stroke="#111" strokeWidth="1.4" />
              <line x1="884" x2="884" y1="196" y2="216" stroke="#111" strokeWidth="1.4" />
              <text x="839" y="192" textAnchor="middle" fontSize="8" fontWeight="700" fill="#111">GRAPHIC SCALE</text>
              <text x="839" y="228" textAnchor="middle" fontSize="8" fill="#111">{formatFt(Math.min(width, height) / 5)}</text>
            </g>

            <g data-testid="civil-review-sheet-legend">
              <SheetTable
                x={TITLE_X - 144}
                y={246}
                rows={["LEGEND", ...(legendTypes.length ? legendTypes : ["site boundary", "draft object", "utility review"]).map(toTitleCase).slice(0, 7)]}
              />
            </g>

            <g data-testid="civil-review-sheet-title-block">
              <rect x={TITLE_X} y="36" width={TITLE_W} height="688" fill="#fff" stroke="#111" strokeWidth="2" />
              <line x1={TITLE_X} x2={TITLE_X + TITLE_W} y1="88" y2="88" stroke="#111" strokeWidth="1.5" />
              <line x1={TITLE_X} x2={TITLE_X + TITLE_W} y1="168" y2="168" stroke="#111" strokeWidth="1.5" />
              <line x1={TITLE_X} x2={TITLE_X + TITLE_W} y1="260" y2="260" stroke="#111" strokeWidth="1.5" />
              <line x1={TITLE_X} x2={TITLE_X + TITLE_W} y1="520" y2="520" stroke="#111" strokeWidth="1.5" />
              <line x1={TITLE_X} x2={TITLE_X + TITLE_W} y1="620" y2="620" stroke="#111" strokeWidth="1.5" />
              <text x={TITLE_X + 22} y="74" fontSize="39" fontWeight="800" fill="#111">CIV</text>
              <text x={TITLE_X + 22} y="120" fontSize="11" fontWeight="800" fill="#111">CIVORA REVIEW PLAN</text>
              <text x={TITLE_X + 22} y="140" fontSize="8" fill="#111">Planning support exhibit</text>
              <text x={TITLE_X + 22} y="190" fontSize="8" fontWeight="700" fill="#111">PROJECT</text>
              <text x={TITLE_X + 22} y="208" fontSize="9" fill="#111">{projectName || "Untitled Project"}</text>
              <text x={TITLE_X + 22} y="228" fontSize="8" fontWeight="700" fill="#111">ADDRESS</text>
              <text x={TITLE_X + 22} y="246" fontSize="8" fill="#111">{addressLabel || "No address applied"}</text>
              <text x={TITLE_X + 22} y="288" fontSize="8" fontWeight="700" fill="#111">GENERAL REVIEW NOTES</text>
              {[
                "Review-only planning exhibit.",
                "Survey/control required before reliance.",
                "Utilities require owner/field proof.",
                "Geometry remains draft until reviewed.",
                "No stamp, seal, approval, or EOR role.",
              ].map((note, index) => (
                <text key={note} x={TITLE_X + 22} y={310 + index * 20} fontSize="7.4" fill="#111">
                  {index + 1}. {note}
                </text>
              ))}
              <text x={TITLE_X + 22} y="546" fontSize="8" fontWeight="700" fill="#111">REVIEW LOG</text>
              <text x={TITLE_X + 22} y="568" fontSize="7.5" fill="#111">DATE: {dateLabel}</text>
              <text x={TITLE_X + 22} y="588" fontSize="7.5" fill="#111">SITE: {formatFt(width)} x {formatFt(height)}</text>
              <text x={TITLE_X + 22} y="608" fontSize="7.5" fill="#111">SRC CANDIDATES: {sourceCandidateCount}</text>
              <text x={TITLE_X + 22} y="656" fontSize="10" fontWeight="800" fill="#111">SHEET NO.</text>
              <text x={TITLE_X + 22} y="700" fontSize="38" fontWeight="900" fill="#111">C-3.2</text>
            </g>

            <g data-testid="civil-review-sheet-profile">
              <rect x="70" y="696" width="850" height="28" fill="#fff" stroke="#111" strokeWidth="1.2" />
              <text x="84" y="714" fontSize="8" fontWeight="800" fill="#111">REVIEW ONLY</text>
              <g data-testid="civil-review-sheet-source-summary">
                <text x="318" y="714" fontSize="8" fill="#111">Source candidates: {sourceCandidateCount}</text>
                <text x="470" y="714" fontSize="8" fill="#111">Missing: {missingSources.slice(0, 2).join(", ") || "none reported"}</text>
                <text x="736" y="714" fontSize="8" fill="#111">Output requires qualified review.</text>
              </g>
            </g>
          </svg>
        </div>
      </div>
    </section>
  );
}
