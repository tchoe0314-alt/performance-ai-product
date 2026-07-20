"use client";

import { useMemo } from "react";
import { Layers, Route, SlidersHorizontal } from "lucide-react";

import type {
  GradingEarthworkUx,
  PlanMeta,
  SourceConfidenceEntry,
} from "../types";

export type SystemGenerationTarget = "roads" | "parking" | "grading" | "drainage" | "utilities" | "full";
export type RoadwayWorkbenchTab = "alignment" | "profile" | "section" | "checks";
export type Civil3DWorkflowTab = "surface" | "profile" | "sections" | "cutfill" | "blockers" | "confidence";

type RoadwayPlotPoint = {
  x: number;
  y: number;
  label?: string;
};

type RoadwayWorkbenchRecord = Record<string, unknown>;

export type RoadwayWorkbenchData = {
  alignments: RoadwayWorkbenchRecord[];
  alignmentPoints: RoadwayPlotPoint[];
  profiles: RoadwayWorkbenchRecord[];
  profilePoints: RoadwayPlotPoint[];
  sections: RoadwayWorkbenchRecord[];
  sectionPoints: RoadwayPlotPoint[];
  crownControls: RoadwayWorkbenchRecord[];
  curbGutterControls: RoadwayWorkbenchRecord[];
  curbReturns: RoadwayWorkbenchRecord[];
  adaChecks: RoadwayWorkbenchRecord[];
};

const roadwayRecord = (value: unknown): RoadwayWorkbenchRecord =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as RoadwayWorkbenchRecord) : {};

const roadwayArray = (value: unknown): RoadwayWorkbenchRecord[] =>
  Array.isArray(value) ? value.map(roadwayRecord).filter((item) => Object.keys(item).length > 0) : [];

const roadwayNumber = (value: unknown): number | null => {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const roadwayLabel = (value: unknown, fallback = "Review"): string => {
  const text = String(value ?? "").trim();
  return text || fallback;
};

const roadwayPercent = (value: unknown): string => {
  const parsed = roadwayNumber(value);
  if (parsed === null) return "n/a";
  const percent = Math.abs(parsed) <= 1 ? parsed * 100 : parsed;
  return `${percent.toFixed(percent < 10 ? 2 : 1)}%`;
};

const roadwayPointFromUnknown = (value: unknown, index: number): RoadwayPlotPoint | null => {
  if (Array.isArray(value)) {
    const x = roadwayNumber(value[0]);
    const y = roadwayNumber(value[1]);
    if (x !== null && y !== null) return { x, y, label: `P${index + 1}` };
  }
  const record = roadwayRecord(value);
  const x =
    roadwayNumber(record.x) ??
    roadwayNumber(record.offset_ft) ??
    roadwayNumber(record.station_ft) ??
    roadwayNumber(record.station);
  const y =
    roadwayNumber(record.y) ??
    roadwayNumber(record.elevation_ft) ??
    roadwayNumber(record.elevation) ??
    roadwayNumber(record.z);
  if (x === null || y === null) return null;
  return {
    x,
    y,
    label: roadwayLabel(record.role ?? record.label ?? record.name, `P${index + 1}`),
  };
};

const roadwayPointsFromRecord = (
  record: RoadwayWorkbenchRecord,
  keys: string[],
): RoadwayPlotPoint[] => {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) {
      const points = value
        .map((item, index) => roadwayPointFromUnknown(item, index))
        .filter((item): item is RoadwayPlotPoint => Boolean(item));
      if (points.length) return points;
    }
    const nested = roadwayRecord(value);
    if (Array.isArray(nested.points)) {
      const points = nested.points
        .map((item, index) => roadwayPointFromUnknown(item, index))
        .filter((item): item is RoadwayPlotPoint => Boolean(item));
      if (points.length) return points;
    }
  }
  return [];
};

export const buildRoadwayWorkbenchData = (meta: PlanMeta): RoadwayWorkbenchData => {
  const metaRecord = roadwayRecord(meta);
  const grading = roadwayRecord(metaRecord.grading);
  const alignments = roadwayArray(metaRecord.alignments).length
    ? roadwayArray(metaRecord.alignments)
    : roadwayArray(metaRecord.road_alignments);
  const profiles = roadwayArray(metaRecord.profiles).length
    ? roadwayArray(metaRecord.profiles)
    : roadwayArray(metaRecord.road_profiles);
  const sections = roadwayArray(metaRecord.cross_sections).length
    ? roadwayArray(metaRecord.cross_sections)
    : roadwayArray(metaRecord.corridor_sections);
  const adaCompliance = roadwayRecord(metaRecord.ada_compliance);
  const adaChecks = [
    ...roadwayArray(adaCompliance.checks),
    ...roadwayArray(adaCompliance.paths),
    ...roadwayArray(metaRecord.ada_paths),
    ...roadwayArray(grading.ada_paths),
  ];

  return {
    alignments,
    alignmentPoints: alignments.length
      ? roadwayPointsFromRecord(alignments[0], ["centerline", "polyline", "points", "geometry"])
      : [],
    profiles,
    profilePoints: profiles.length
      ? roadwayPointsFromRecord(profiles[0], ["profile_points", "samples", "points", "rows"])
      : [],
    sections,
    sectionPoints: sections.length
      ? roadwayPointsFromRecord(sections[0], ["section_points", "samples", "points", "rows"])
      : [],
    crownControls: roadwayArray(grading.road_crown_controls).length
      ? roadwayArray(grading.road_crown_controls)
      : roadwayArray(metaRecord.road_crown_controls ?? metaRecord.road_crowns),
    curbGutterControls: roadwayArray(grading.curb_gutter_controls).length
      ? roadwayArray(grading.curb_gutter_controls)
      : roadwayArray(metaRecord.curb_gutter_controls),
    curbReturns: roadwayArray(metaRecord.curb_returns),
    adaChecks,
  };
};

function RoadwayMiniPlot({
  points,
  variant,
}: {
  points: RoadwayPlotPoint[];
  variant: "plan" | "profile" | "section";
}) {
  const plot = useMemo(() => {
    if (points.length < 2) return null;
    const xs = points.map((point) => point.x);
    const ys = points.map((point) => point.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const width = 280;
    const height = 124;
    const pad = 16;
    const rangeX = Math.max(maxX - minX, 1);
    const rangeY = Math.max(maxY - minY, 1);
    return points.map((point) => ({
      ...point,
      sx: pad + ((point.x - minX) / rangeX) * (width - pad * 2),
      sy: height - pad - ((point.y - minY) / rangeY) * (height - pad * 2),
    }));
  }, [points]);

  if (!plot) {
    return (
      <div className="flex h-32 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 text-center text-xs font-semibold text-slate-500">
        Generate roadway evidence to view this graph.
      </div>
    );
  }

  const stroke = variant === "section" ? "#0f766e" : variant === "profile" ? "#7c3aed" : "#0f172a";
  const path = plot.map((point) => `${point.sx},${point.sy}`).join(" ");

  return (
    <svg viewBox="0 0 280 124" role="img" aria-label={`${variant} viewer`} className="h-32 w-full rounded-lg border border-slate-200 bg-white">
      <line x1="16" y1="108" x2="264" y2="108" stroke="#e2e8f0" strokeWidth="1" />
      <line x1="16" y1="16" x2="16" y2="108" stroke="#e2e8f0" strokeWidth="1" />
      <polyline points={path} fill="none" stroke={stroke} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {plot.map((point, index) => (
        <circle key={`${point.x}-${point.y}-${index}`} cx={point.sx} cy={point.sy} r="3.5" fill="#ffffff" stroke={stroke} strokeWidth="2" />
      ))}
    </svg>
  );
}

export function RoadwayCorridorWorkbench({
  data,
  activeTab,
  onTabChange,
  maxRoadGradePct,
  setMaxRoadGradePct,
  maxAdaCrossSlopePct,
  setMaxAdaCrossSlopePct,
  handleGenerateSystem,
}: {
  data: RoadwayWorkbenchData;
  activeTab: RoadwayWorkbenchTab;
  onTabChange: (tab: RoadwayWorkbenchTab) => void;
  maxRoadGradePct: string;
  setMaxRoadGradePct: (value: string) => void;
  maxAdaCrossSlopePct: string;
  setMaxAdaCrossSlopePct: (value: string) => void;
  handleGenerateSystem: (target: SystemGenerationTarget) => void;
}) {
  const firstAlignment = data.alignments[0] ?? {};
  const firstProfile = data.profiles[0] ?? {};
  const firstSection = data.sections[0] ?? {};
  const firstCrown = data.crownControls[0] ?? {};
  const firstCurbReturn = data.curbReturns[0] ?? {};
  const checkRows = [
    ...data.curbReturns.slice(0, 3).map((row, index) => ({
      label: roadwayLabel(row.id ?? row.name ?? row.intersection_id, `Curb return ${index + 1}`),
      value: row.radius_ft !== undefined ? `${roadwayLabel(row.radius_ft)} ft radius` : roadwayLabel(row.status ?? row.valid, "geometry"),
      valid: row.valid !== false,
    })),
    ...data.adaChecks.slice(0, 3).map((row, index) => ({
      label: roadwayLabel(row.id ?? row.name ?? row.path_id, `ADA check ${index + 1}`),
      value: row.slope !== undefined
        ? roadwayPercent(row.slope)
        : row.cross_slope !== undefined
          ? roadwayPercent(row.cross_slope)
          : roadwayLabel(row.status ?? row.valid, "slope evidence"),
      valid: row.valid !== false && row.status !== "failed",
    })),
  ];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Corridor workbench</p>
          <p className="mt-1 text-sm text-slate-500">Alignment, profile, section, crown, curb return, and ADA review.</p>
        </div>
        <Route className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" />
      </div>

      <div className="mt-4 grid grid-cols-4 gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
        {[
          ["alignment", "Align"],
          ["profile", "Profile"],
          ["section", "Section"],
          ["checks", "Checks"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => onTabChange(key as RoadwayWorkbenchTab)}
            className={`h-9 rounded-md text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
              activeTab === key ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === "alignment" ? (
        <div className="mt-4 space-y-3">
          <RoadwayMiniPlot points={data.alignmentPoints} variant="plan" />
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Alignment", roadwayLabel(firstAlignment.name ?? firstAlignment.id, data.alignments.length ? "Road alignment" : "No alignment")],
              ["PI points", data.alignmentPoints.length || "n/a"],
              ["Station range", firstAlignment.length_ft ? `${roadwayLabel(firstAlignment.length_ft)} ft` : "Needs profile"],
              ["Owner", roadwayLabel(firstAlignment.alignment_owner ?? firstAlignment.owner, "Roadway")],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button type="button" onClick={() => handleGenerateSystem("roads")} className="rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-white hover:bg-slate-800">Rebuild roads</button>
            <button type="button" onClick={() => handleGenerateSystem("parking")} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50">Update parking</button>
          </div>
        </div>
      ) : null}

      {activeTab === "profile" ? (
        <div className="mt-4 space-y-3">
          <RoadwayMiniPlot points={data.profilePoints} variant="profile" />
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
              Road max %
              <input value={maxRoadGradePct} onChange={(event) => setMaxRoadGradePct(event.target.value)} placeholder="Auto" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
            </label>
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs">
              <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">Profile</p>
              <p className="mt-1 font-semibold text-slate-800">{roadwayLabel(firstProfile.name ?? firstProfile.profile_id ?? firstProfile.id, data.profiles.length ? "Road profile" : "No profile")}</p>
            </div>
          </div>
        </div>
      ) : null}

      {activeTab === "section" ? (
        <div className="mt-4 space-y-3">
          <RoadwayMiniPlot points={data.sectionPoints} variant="section" />
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Section", roadwayLabel(firstSection.name ?? firstSection.id, data.sections.length ? "Cross section" : "No section")],
              ["Station", firstSection.station_ft !== undefined ? `${roadwayLabel(firstSection.station_ft)} ft` : "n/a"],
              ["Crown", firstCrown.actual_cross_slope !== undefined ? roadwayPercent(firstCrown.actual_cross_slope) : roadwayPercent(firstCrown.expected_cross_slope)],
              ["Sidewalk max", maxAdaCrossSlopePct ? `${maxAdaCrossSlopePct}%` : "2.00%"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
          <label className="block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
            ADA cross slope %
            <input value={maxAdaCrossSlopePct} onChange={(event) => setMaxAdaCrossSlopePct(event.target.value)} placeholder="2" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm normal-case tracking-normal text-slate-700" />
          </label>
        </div>
      ) : null}

      {activeTab === "checks" ? (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Curb returns", data.curbReturns.length],
              ["ADA checks", data.adaChecks.length],
              ["Curb/gutter", data.curbGutterControls.length],
              ["Return radius", firstCurbReturn.radius_ft !== undefined ? `${roadwayLabel(firstCurbReturn.radius_ft)} ft` : "n/a"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
          <div className="space-y-2">
            {(checkRows.length ? checkRows : [{ label: "Roadway QA", value: "Generate roadway for curb return and ADA evidence", valid: false }]).map((row) => (
              <div key={`${row.label}-${row.value}`} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                <span className="font-semibold text-slate-700">{row.label}</span>
                <span className={`shrink-0 rounded-full px-2 py-1 font-semibold uppercase tracking-[0.1em] ${row.valid ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                  {row.valid ? "Pass" : "Review"}
                </span>
                <span className="min-w-0 flex-1 truncate text-right font-medium text-slate-500">{row.value}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600">
        <SlidersHorizontal className="h-4 w-4 shrink-0" />
        <span>Profile, section, and ADA values remain review evidence until survey/control and standards are accepted.</span>
      </div>
    </div>
  );
}

export function CivilSurfaceCorridorWorkflow({
  activeTab,
  onTabChange,
  roadwayData,
  gradingEarthworkUx,
  sourceConfidenceRows,
  blockers,
  gradingSourceSummary,
  hasTerrainSource,
  hasVerifiedSurveyControl,
  onOpenRoadwayControls,
}: {
  activeTab: Civil3DWorkflowTab;
  onTabChange: (tab: Civil3DWorkflowTab) => void;
  roadwayData: RoadwayWorkbenchData;
  gradingEarthworkUx: GradingEarthworkUx;
  sourceConfidenceRows: SourceConfidenceEntry[];
  blockers: string[];
  gradingSourceSummary: string;
  hasTerrainSource: boolean;
  hasVerifiedSurveyControl: boolean;
  onOpenRoadwayControls: () => void;
}) {
  const hasAlignment = roadwayData.alignments.length > 0 || roadwayData.alignmentPoints.length > 1;
  const hasProfile = roadwayData.profiles.length > 0 || roadwayData.profilePoints.length > 1;
  const hasSections = roadwayData.sections.length > 0 || roadwayData.sectionPoints.length > 1;
  const corridorReviewBlocked = blockers.length > 0 || !hasTerrainSource || !hasAlignment || !hasProfile || !hasSections;
  const highCutFillCells = [...gradingEarthworkUx.heatmapCells]
    .sort((a, b) => Math.abs(b.deltaFt) - Math.abs(a.deltaFt))
    .slice(0, 4);
  const confidencePreviewRows = sourceConfidenceRows.slice(0, 5);
  const workflowSteps = [
    { key: "surface", label: "Surface", status: hasTerrainSource ? "Review" : "Missing" },
    { key: "alignment", label: "Alignment", status: hasAlignment ? "Review" : "Missing" },
    { key: "profile", label: "Profile", status: hasProfile ? "Review" : "Missing" },
    { key: "corridor", label: "Corridor", status: corridorReviewBlocked ? "Needs input" : "Review" },
    { key: "sections", label: "Sections", status: hasSections ? "Review" : "Missing" },
    { key: "cutfill", label: "Cut/Fill", status: gradingEarthworkUx.haulBalance.direction === "unknown" ? "Pending" : "Review" },
  ];
  const sourceLabel = hasVerifiedSurveyControl
    ? "Survey/control uploaded for review"
    : "No verified survey/control attached";

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4" data-testid="civil3d-visual-workflow">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Civil3D visual workflow</p>
          <p className="mt-1 text-sm text-slate-500">Surface, alignment, profile, corridor, sections, and cut/fill linked as review-required evidence.</p>
        </div>
        <Layers className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" />
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {workflowSteps.map((step) => (
          <button
            key={step.key}
            type="button"
            onClick={() => onTabChange(step.key === "alignment" || step.key === "corridor" ? "profile" : (step.key as Civil3DWorkflowTab))}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left hover:bg-white"
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{step.label}</p>
            <p className={`mt-1 text-sm font-semibold ${step.status === "Needs input" || step.status === "Missing" ? "text-amber-700" : "text-slate-800"}`}>
              {step.status}
            </p>
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-1 rounded-lg border border-slate-200 bg-slate-50 p-1">
        {[
          ["surface", "Surface"],
          ["profile", "Profile"],
          ["sections", "Sections"],
          ["cutfill", "Cut/Fill"],
          ["blockers", "Needs"],
          ["confidence", "Sources"],
        ].map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => onTabChange(key as Civil3DWorkflowTab)}
            className={`h-9 rounded-md text-[10px] font-semibold uppercase tracking-[0.1em] transition ${
              activeTab === key ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === "surface" ? (
        <div className="mt-4 space-y-3">
          <div className="relative h-52 overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
            <div className="absolute inset-0 grid grid-cols-6 grid-rows-4">
              {gradingEarthworkUx.heatmapCells.map((cell) => (
                <div
                  key={cell.id}
                  className={
                    cell.mode === "cut"
                      ? "bg-rose-100"
                      : cell.mode === "fill"
                        ? "bg-sky-100"
                        : "bg-emerald-50"
                  }
                  style={{ opacity: Math.min(0.85, 0.25 + Math.abs(cell.deltaFt) / 10) }}
                />
              ))}
            </div>
            {[18, 34, 50, 66, 82].map((top, index) => (
              <div
                key={top}
                className="absolute left-4 right-4 rounded-[50%] border border-slate-500/35"
                style={{
                  top: `${top}%`,
                  height: `${18 + index * 4}%`,
                  transform: `rotate(${-8 + index * 4}deg)`,
                }}
              />
            ))}
            <div className="absolute left-4 top-4 rounded-lg border border-slate-200 bg-white/90 px-3 py-2 text-xs font-semibold text-slate-700">
              Contours / spots / slope
            </div>
            <div className="absolute bottom-4 right-4 rounded-lg border border-slate-200 bg-white/90 px-3 py-2 text-right text-xs font-semibold text-slate-700">
              {gradingEarthworkUx.surfaceComparison.deltaLabel}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Surface source", gradingSourceSummary],
              ["Control", sourceLabel],
              ["Existing", gradingEarthworkUx.surfaceComparison.existing],
              ["Proposed", gradingEarthworkUx.surfaceComparison.proposed],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {activeTab === "profile" ? (
        <div className="mt-4 space-y-3">
          <RoadwayMiniPlot points={roadwayData.profilePoints.length ? roadwayData.profilePoints : roadwayData.alignmentPoints} variant={roadwayData.profilePoints.length ? "profile" : "plan"} />
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Alignment records", roadwayData.alignments.length],
              ["Profile samples", roadwayData.profilePoints.length || "Missing"],
              ["Corridor state", corridorReviewBlocked ? "Needs input for review" : "Linked for review"],
              ["Source label", sourceLabel],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
          <button type="button" onClick={onOpenRoadwayControls} className="w-full rounded-xl border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white hover:bg-slate-800">
            Open roadway controls
          </button>
        </div>
      ) : null}

      {activeTab === "sections" ? (
        <div className="mt-4 space-y-3">
          <RoadwayMiniPlot points={roadwayData.sectionPoints} variant="section" />
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Sections", roadwayData.sections.length || "Missing"],
              ["Section samples", roadwayData.sectionPoints.length || "Missing"],
              ["Crown controls", roadwayData.crownControls.length || "Missing"],
              ["Curb/gutter controls", roadwayData.curbGutterControls.length || "Missing"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {activeTab === "cutfill" ? (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-6 overflow-hidden rounded-xl border border-slate-200">
            {gradingEarthworkUx.heatmapCells.map((cell) => (
              <div
                key={cell.id}
                className={`flex h-14 items-center justify-center text-[10px] font-semibold ${
                  cell.mode === "cut"
                    ? "bg-rose-100 text-rose-800"
                    : cell.mode === "fill"
                      ? "bg-sky-100 text-sky-800"
                      : "bg-emerald-50 text-emerald-700"
                }`}
              >
                {cell.deltaFt > 0 ? "+" : ""}{cell.deltaFt.toFixed(1)}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {[
              ["Haul", gradingEarthworkUx.haulBalance.label],
              ["Net", gradingEarthworkUx.haulBalance.netCf !== null && gradingEarthworkUx.haulBalance.netCf !== undefined ? `${Math.round(gradingEarthworkUx.haulBalance.netCf)} cf` : "Pending"],
              ["Cut", gradingEarthworkUx.haulBalance.cutCf ? `${Math.round(gradingEarthworkUx.haulBalance.cutCf)} cf` : "Pending"],
              ["Fill", gradingEarthworkUx.haulBalance.fillCf ? `${Math.round(gradingEarthworkUx.haulBalance.fillCf)} cf` : "Pending"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <p className="font-semibold uppercase tracking-[0.12em] text-slate-400">{label}</p>
                <p className="mt-1 font-semibold text-slate-800">{value}</p>
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
            <p className="font-semibold text-slate-800">Highest cut/fill deltas</p>
            <p className="mt-1">{highCutFillCells.map((cell) => `${cell.mode} ${cell.deltaFt > 0 ? "+" : ""}${cell.deltaFt.toFixed(1)} ft`).join(" / ")}</p>
          </div>
        </div>
      ) : null}

      {activeTab === "blockers" ? (
        <div className="mt-4 space-y-2">
          {(blockers.length ? blockers : ["No corridor-specific needs are recorded. Review-required status remains until source evidence is checked."]).map((blocker) => (
            <div key={blocker} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900">
              {blocker}
            </div>
          ))}
        </div>
      ) : null}

      {activeTab === "confidence" ? (
        <div className="mt-4 space-y-2">
          <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-700">
            {sourceLabel}. Corridor and earthwork outputs are review-required only.
          </div>
          {(confidencePreviewRows.length ? confidencePreviewRows : []).map((entry) => (
            <div key={entry.entry_id} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm font-semibold text-slate-800">{entry.label || "Source entry"}</p>
                <span className="text-right text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                  {entry.visible_badge || entry.confidence_band || entry.source_type || "Review"}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">{entry.why_low_confidence || entry.next_action || "Source label visible for review."}</p>
            </div>
          ))}
          {!confidencePreviewRows.length ? (
            <p className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900">
              No source confidence entries are recorded yet.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
