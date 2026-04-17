"use client";
/* eslint-disable react-hooks/exhaustive-deps */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Clock3,
  Eye,
  EyeOff,
  FileImage,
  FolderOpen,
  Map,
  Maximize2,
  MessageSquarePlus,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import {
  deleteJson,
  getJson,
  postBinary,
  postForm,
  postJson,
  toApiUrl,
} from "../lib/api";

type UserRecord = {
  user_id: string;
  email: string;
  name: string;
};

type Assumption = {
  field: string;
  value: string;
  reason: string;
};

type Issue = {
  severity: "warning" | "error";
  message: string;
};

type BackendIssue = {
  severity?: string;
  message?: string;
};

type BackendAssumption = {
  field_name?: string;
  field?: string;
  assumed_value?: unknown;
  reason?: string;
};

type ProjectSummary = {
  project_id: string;
  name: string;
  description?: string;
  has_result?: boolean;
  updated_at?: number;
};

type ProjectRecord = {
  project_id: string;
  name: string;
  description?: string;
  updated_at?: number;
  project_input?: ProjectInput;
  latest_result?: PlanResponse;
  metadata?: ProjectMetadata;
  has_result?: boolean;
};

type JobSummary = {
  job_id: string;
  status: string;
  job_type?: string;
  project_id?: string | null;
  updated_at?: number;
  error?: string | null;
  result?: PlanResponse | null;
  stage?: string;
  stage_detail?: string;
  progress?: number;
  queue_position?: number | null;
  queued_count?: number;
  running_count?: number;
};

type WorkflowRunSummary = {
  run_id: string;
  source?: string;
  created_at?: number;
  success?: boolean;
  message?: string;
  input_mode?: string;
  strict_mode?: boolean;
  engineering_status?: {
    success?: boolean;
    status?: string;
    trust_score?: number;
  };
  truth_success?: boolean;
  all_required_complete?: boolean;
  requested_deliverables?: string[];
  produced_deliverables?: string[];
  failed_deliverables?: string[];
  manual_failures?: Array<{
    code?: string;
    message?: string;
    system?: string;
    rule?: string;
    location?: string;
    reason?: string;
  }>;
  coordination_summary?: {
    unresolved_conflicts?: number;
    selected_strategy?: string;
  };
  stage_summary?: {
    statuses?: Record<string, string>;
  };
};

type WorkflowArtifact = {
  artifact_id: string;
  kind?: string;
  filename?: string;
  created_at?: number;
  download_path?: string;
};

type ManualFailure = {
  code?: string;
  message?: string;
  system?: string;
  rule?: string;
  location?: string;
  reason?: string;
};

type IterationRecord = Record<string, unknown> & {
  stage?: string;
  status?: string;
  phase?: string;
};

type MetricValue = number | { value?: number } | null;
type ManagerMetrics = Record<string, MetricValue>;
type QuantityTotals = Record<string, number | null | undefined>;

type PipeSegment = {
  length_ft?: number;
  slope_pct?: number;
  slope_ft_ft?: number;
};

type StormSummary = {
  segments?: PipeSegment[];
  pipe_segments?: PipeSegment[];
  storm_pipe_segments?: PipeSegment[];
  total_system_flow_cfs?: number;
  total_system_capacity_cfs?: number;
};

type PlanExplanation = {
  summary?: string;
  overview?: string;
  why?: string;
  reasoning?: string;
};

type ConvergenceSummary = {
  assumption_summary?: {
    examples?: string[];
  };
  fix_summary?: {
    autofix_actions?: string[];
  };
  blocked_reasons?: string[];
  blocked_exports?: string[];
  unresolved_issue_categories?: string[];
  dominant_issue_categories?: string[];
  unresolved_conflict_count?: number;
};

type PhaseCheckpoint = {
  label?: string;
  status?: string;
  ready?: boolean;
  deliverables?: string[];
  messages?: string[];
  blockers?: string[];
  has_data?: boolean;
  stages?: string[];
  completed_phase_count?: number;
  total_phase_count?: number;
  blocked_exports?: string[];
  blocked_reasons?: string[];
  deliverables_ready?: string[];
  deliverables_extra?: string[];
  note?: string;
  current_stage?: string;
  current_status?: string;
  job_progress?: number;
};

type PlanMeta = {
  explanation?: PlanExplanation;
  convergence_summary?: ConvergenceSummary;
  deliverables?: {
    produced?: string[];
    failed?: string[];
  };
  produced_deliverables?: string[];
  failed_deliverables?: string[];
  release_review?: PreviewReview;
  release_status?: string;
  release_note?: string;
  phase_checkpoints?: Record<string, PhaseCheckpoint>;
  runtime_phase_checkpoint?: {
    stage_name?: string;
  };
  engineering_status?: {
    success?: boolean;
    status?: string;
    trust_score?: number;
  };
  manager_export?: {
    metrics?: ManagerMetrics;
  };
  quantities?: {
    totals?: QuantityTotals;
  };
  storm_pipes?: StormSummary;
  drainage?: Record<string, unknown>;
  grading?: Record<string, unknown>;
  utilities?: Record<string, unknown>;
  truth_audit?: {
    success?: boolean;
  };
  manual_validation?: {
    failures?: ManualFailure[];
  };
  coordination?: Record<string, unknown>;
  iterations?: IterationRecord[];
};

type PlanAction = {
  geometry?: {
    origin?: [number, number];
    width?: number;
    height?: number;
  };
  label?: string;
  layer?: string;
};

type PlanResponse = {
  final_plan?: {
    meta?: PlanMeta;
    actions?: PlanAction[];
  };
  assumptions?: BackendAssumption[];
  issues?: BackendIssue[];
  message?: string;
  metadata?: {
    iterations?: IterationRecord[];
  };
  job_progress?: {
    stage?: string;
    [key: string]: unknown;
  };
};

type SurveyFileInput = {
  filename?: string;
  stored_filename?: string;
  survey_url?: string;
};

type MapSnapshotInput = {
  filename?: string;
  stored_filename?: string;
  image_path?: string;
  image_url?: string;
};

type MapAnalysis = Record<string, unknown>;

type SiteInputs = {
  map_snapshot?: MapSnapshotInput;
  map_analysis?: MapAnalysis;
  survey_file?: SurveyFileInput;
  slope_estimate?: SurveySlopeResponse | null;
};

type ProjectInputMeta = Record<string, unknown> & {
  site_inputs?: SiteInputs;
  chat_thread?: ChatMessage[];
  auto_named?: boolean;
  auto_file_named?: boolean;
};

type ManualFields = {
  project_name?: string;
  file_name?: string;
  units?: string;
  project_type?: string;
  lot?: { x: number; y: number; w: number; h: number };
  setback?: number;
  building_width?: number;
  building_depth?: number;
  buildings?: Array<{ name: string; w?: number; d?: number }>;
  site_plan?: { parking_count?: number };
  grading?: {
    min_slope_pct?: number;
    max_parking_slope_pct?: number;
    max_road_grade_pct?: number;
    max_ada_cross_slope_pct?: number;
  };
  drainage?: {
    min_pipe_slope_pct?: number;
  };
  disciplines?: string[];
  terrain?: string;
};

type ProjectInput = {
  project_id?: string | null;
  full_design_mode?: boolean;
  input_mode?: StrategyMode;
  strict_mode?: boolean;
  prompt_text?: string | null;
  image_path?: string | null;
  manual_fields?: ManualFields;
  allow_ai_fill_for_blanks?: boolean;
  meta?: ProjectInputMeta;
};

type ProjectMetadata = Record<string, unknown> & {
  workflow?: {
    runs?: WorkflowRunSummary[];
    artifacts?: WorkflowArtifact[];
  };
};

type PlanRequestPayload = Record<string, unknown> & {
  project_id?: string | null;
  full_design_mode?: boolean;
  input_mode?: StrategyMode;
  strict_mode?: boolean;
  prompt_text?: string | null;
  image_path?: string | null;
  manual_fields?: ManualFields;
  allow_ai_fill_for_blanks?: boolean;
  optimize_goal?: string | null;
  meta?: ProjectInputMeta;
};

type PreviewRequestPayload = Record<string, unknown> & {
  project_id?: string | null;
  result?: PlanResponse;
  filename_stem?: string;
};

type PhaseMetric = {
  label: string;
  value: number | null;
  unit: string;
  format?: "count";
};

type PhaseStats = {
  layout: PhaseMetric[];
  grading: PhaseMetric[];
  drainage_storm: PhaseMetric[];
  utilities: PhaseMetric[];
  coordination_validation: PhaseMetric[];
};

type AuthStatus = {
  auth_enabled: boolean;
  user_count: number;
};

type DisciplineToggle = {
  label: string;
  checked: boolean;
  setter: React.Dispatch<React.SetStateAction<boolean>>;
  desc: string;
};

type PreviewResponse = {
  success: boolean;
  preview_image_data_url: string;
  preview_annotations?: {
    profile?: string;
    labels?: {
      label: string;
      layer: string;
      x: number;
      y: number;
      bounds?: { x1: number; y1: number; x2: number; y2: number };
    }[];
  };
  summary?: {
    project_name?: string;
    units?: string;
    action_count?: number;
    review?: {
      trust_score?: number;
      converged?: boolean;
      passes_run?: number;
      unresolved_conflict_count?: number;
      assumption_count?: number;
      assumption_categories?: string[];
      assumption_examples?: string[];
      autofix_actions?: string[];
      dominant_fix_targets?: string[];
      review_categories?: string[];
      blocked_exports?: string[];
      blocked_reasons?: string[];
      requested_deliverables?: string[];
      ready_deliverables?: string[];
      produced_deliverables?: string[];
      extra_deliverables?: string[];
      failed_deliverables?: string[];
      rerun_total?: number;
      rerun_stages?: string[];
      rerun_reasons?: string[];
      phase_checkpoints?: Record<
        string,
        {
          label?: string;
          status?: string;
          ready?: boolean;
          deliverables?: string[];
          messages?: string[];
          blockers?: string[];
          has_data?: boolean;
          stages?: string[];
          completed_phase_count?: number;
          total_phase_count?: number;
          blocked_exports?: string[];
          blocked_reasons?: string[];
          deliverables_ready?: string[];
          deliverables_extra?: string[];
          note?: string;
          current_stage?: string;
          current_status?: string;
          job_progress?: number;
        }
      >;
      release_status?: "ready" | "review" | "blocked" | string;
      release_note?: string;
    };
  };
};

type PreviewReview = NonNullable<PreviewResponse["summary"]>["review"];

type UploadImageResponse = {
  success: boolean;
  image_path?: string;
  image_url?: string;
  filename?: string;
};

type UploadSurveyResponse = {
  success: boolean;
  filename?: string;
  stored_filename?: string;
  survey_url?: string;
};

type SurveySlopeResponse = {
  success: boolean;
  slope_ratio?: number;
  slope_percent?: number;
  downhill_dx?: number;
  downhill_dy?: number;
  direction?: string;
  point_count?: number;
};

type PlanToolMode = "run" | "fix" | "improve";
type StrategyMode = "manual" | "assisted";
type ControlOverrides = Partial<{
  strategyMode: StrategyMode;
  projectType: string;
  units: string;
  roads: boolean;
  grading: boolean;
  drainage: boolean;
  utilities: boolean;
  siteName: string;
  fileName: string;
  lotWidth: string | number;
  lotHeight: string | number;
  buildingWidth: string | number;
  buildingDepth: string | number;
  buildingCount: string | number;
  setback: string | number;
  parkingCount: string | number;
  minSlopePct: string | number;
  pipeMinSlopePct: string | number;
  maxParkingSlopePct: string | number;
  maxRoadGradePct: string | number;
  maxAdaCrossSlopePct: string | number;
}>;
type ChatDecisionIntent =
  | "conversation"
  | "settings"
  | "design"
  | "explain"
  | "fix"
  | "improve";
type ChatDecisionResponse = {
  success: boolean;
  intent: ChatDecisionIntent;
  assistant_message: string;
  run_mode: "none" | "run" | "fix" | "improve";
  design_prompt: string;
  needs_clarification: boolean;
  reason: string;
  confidence: number;
  control_overrides: ControlOverrides;
};
type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: number;
  kind?: "message" | "status" | "explanation" | "action";
  feedback?: "up" | "down";
};
type LearningReport = {
  feedback?: {
    up?: number;
    down?: number;
    total?: number;
    score_percent?: number;
  };
  training_examples?: {
    count?: number;
    synthetic?: number;
    feedback_based?: number;
    interaction?: number;
  };
};

const defaultAssumptions: Assumption[] = [
  {
    field: "project_type",
    value: "commercial_pad",
    reason:
      "AI filled this because the prompt described a general commercial site concept.",
  },
  {
    field: "lot",
    value: "estimated from sketch extents",
    reason: "No exact lot dimensions were provided in the form.",
  },
];

const defaultIssues: Issue[] = [
  {
    severity: "warning",
    message: "No confirmed scale reference is set for the uploaded image.",
  },
];

function createChatMessage(
  role: ChatMessage["role"],
  content: string,
  kind: ChatMessage["kind"] = "message",
  feedback?: ChatMessage["feedback"],
): ChatMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    createdAt: Date.now(),
    kind,
    feedback,
  };
}

function createWelcomeMessage(): ChatMessage {
  return createChatMessage(
    "assistant",
    "Hi, I’m Civora. I can help you think through a site, answer questions, and turn design requests into a plan when you’re ready. Tell me what you want to change, or just ask me a question first.",
  );
}

function formatChatTimestamp(value: number) {
  try {
    return new Date(value).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function toReadableLabel(value: string): string {
  const normalized = value
    .replace(/design_defaults/gi, "design defaults")
    .replace(/^qa$/i, "validation")
    .replace(/^general$/i, "design")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return normalized
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function joinNatural(items: string[], limit = 3): string {
  const filtered = items
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, limit);
  if (!filtered.length) {
    return "";
  }
  if (filtered.length === 1) {
    return filtered[0];
  }
  if (filtered.length === 2) {
    return `${filtered[0]} and ${filtered[1]}`;
  }
  return `${filtered.slice(0, -1).join(", ")}, and ${filtered[filtered.length - 1]}`;
}

function toArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function toMetricValue(value: number | null | undefined): number | null {
  return value ?? null;
}

function readPositiveNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value) && value > 0) {
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return null;
}

function parsePositiveNumber(value: string | number | null | undefined): number | null {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
}

function extractDesignMemory(thread: ChatMessage[]): {
  preferences: string[];
  constraints: string[];
} {
  const preferences: string[] = [];
  const constraints: string[] = [];
  const seen = new Set<string>();

  for (const message of thread) {
    if (message.role !== "user") continue;
    const clauses = message.content.split(/[.!?\n;]+/);
    for (const clause of clauses) {
      const clean = clause.replace(/\s+/g, " ").trim();
      if (!clean || clean.length < 8) continue;
      const lowered = clean.toLowerCase();
      const key = lowered.slice(0, 160);
      if (seen.has(key)) continue;

      if (
        lowered.includes("make sure") ||
        lowered.includes("remember to") ||
        lowered.includes("prefer ") ||
        lowered.includes("keep ") ||
        lowered.includes("stay in ")
      ) {
        preferences.push(clean);
        seen.add(key);
        continue;
      }

      if (
        lowered.includes("do not") ||
        lowered.includes("don't") ||
        lowered.includes("dont") ||
        lowered.includes("never ") ||
        lowered.includes("without ") ||
        lowered.includes("no guessing") ||
        lowered.includes("ask for clarification")
      ) {
        constraints.push(clean);
        seen.add(key);
      }
    }
  }

  return {
    preferences: preferences.slice(-8),
    constraints: constraints.slice(-8),
  };
}

function computeLearningScore(thread: ChatMessage[]): { score: number; total: number } {
  let up = 0;
  let down = 0;
  for (const message of thread) {
    if (message.role !== "assistant") continue;
    if (message.feedback === "up") up += 1;
    if (message.feedback === "down") down += 1;
  }
  const total = up + down;
  if (total === 0) {
    return { score: 0, total: 0 };
  }
  return { score: Math.round((up / total) * 100), total };
}

function readMetricValue(value: MetricValue | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "object" && typeof value.value === "number" && Number.isFinite(value.value)) {
    return value.value;
  }
  return null;
}

function formatMetric(value: number | null, unit: string): string {
  if (value == null || !Number.isFinite(value)) return "Pending";
  return `${value.toFixed(1)} ${unit}`;
}

function formatCount(value: number | null, unit?: string): string {
  if (value == null || !Number.isFinite(value)) return "Pending";
  const rounded = Math.round(value);
  return unit ? `${rounded.toLocaleString()} ${unit}` : rounded.toLocaleString();
}

type Preview3DItem = {
  x: number;
  y: number;
  w: number;
  h: number;
  height: number;
  color: string;
  label: string;
  layer: string;
};

function Preview3DCanvas({
  items,
  interactive,
}: {
  items: Preview3DItem[];
  interactive: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [rotation, setRotation] = useState({ x: 0.75, z: -0.8 });
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const width = parent.clientWidth;
    const height = parent.clientHeight;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);

    if (!items.length) {
      ctx.fillStyle = "#94a3b8";
      ctx.font = "14px ui-sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("No geometry to render yet.", width / 2, height / 2);
      return;
    }

    const minX = Math.min(...items.map((item) => item.x));
    const minY = Math.min(...items.map((item) => item.y));
    const maxX = Math.max(...items.map((item) => item.x + item.w));
    const maxY = Math.max(...items.map((item) => item.y + item.h));
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const scale = Math.min(width / spanX, height / spanY) * 0.65;
    const centerX = width / 2;
    const centerY = height / 2 + 20;

    const project = (x: number, y: number, z: number) => {
      const cx = x - (minX + spanX / 2);
      const cy = y - (minY + spanY / 2);
      const cosZ = Math.cos(rotation.z);
      const sinZ = Math.sin(rotation.z);
      const rx = cx * cosZ - cy * sinZ;
      const ry = cx * sinZ + cy * cosZ;
      const cosX = Math.cos(rotation.x);
      const sinX = Math.sin(rotation.x);
      const ry2 = ry * cosX - z * sinX;
      return {
        x: centerX + rx * scale,
        y: centerY + ry2 * scale,
      };
    };

    ctx.fillStyle = "#eef2f7";
    ctx.fillRect(0, 0, width, height);

    const drawFace = (points: { x: number; y: number }[], color: string) => {
      ctx.beginPath();
      points.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      });
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = "rgba(15,23,42,0.15)";
      ctx.stroke();
    };

    const sorted = [...items].sort((a, b) => (a.x + a.y) - (b.x + b.y));
    for (const item of sorted) {
      const base = [
        project(item.x, item.y, 0),
        project(item.x + item.w, item.y, 0),
        project(item.x + item.w, item.y + item.h, 0),
        project(item.x, item.y + item.h, 0),
      ];
      const top = [
        project(item.x, item.y, item.height),
        project(item.x + item.w, item.y, item.height),
        project(item.x + item.w, item.y + item.h, item.height),
        project(item.x, item.y + item.h, item.height),
      ];
      const sideDark = item.layer === "BUILDING" ? "#94a3b8" : "#cbd5f5";
      const sideLight = item.layer === "BUILDING" ? "#bfc7d4" : "#dbe5ff";
      drawFace([base[0], base[1], top[1], top[0]], sideDark);
      drawFace([base[1], base[2], top[2], top[1]], sideLight);
      drawFace([top[0], top[1], top[2], top[3]], item.color);
    }
  }, [items, rotation]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !interactive) return;
    const onPointerDown = (event: PointerEvent) => {
      dragRef.current = { x: event.clientX, y: event.clientY };
    };
    const onPointerMove = (event: PointerEvent) => {
      if (!dragRef.current) return;
      const dx = event.clientX - dragRef.current.x;
      const dy = event.clientY - dragRef.current.y;
      dragRef.current = { x: event.clientX, y: event.clientY };
      setRotation((prev) => ({
        x: Math.max(0.2, Math.min(1.2, prev.x + dy * 0.005)),
        z: prev.z + dx * 0.005,
      }));
    };
    const onPointerUp = () => {
      dragRef.current = null;
    };
    canvas.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      canvas.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [interactive]);

  return (
    <div className="relative h-[520px] w-full overflow-hidden rounded-[20px] bg-white">
      <canvas ref={canvasRef} className="h-full w-full" />
      {interactive ? (
        <div className="pointer-events-none absolute right-4 top-4 rounded-full bg-slate-900/70 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-white">
          Drag to rotate
        </div>
      ) : null}
    </div>
  );
}

function summarizePlanResponse(
  data: PlanResponse,
  mode: PlanToolMode,
): string {
  const plan = data?.final_plan ?? {};
  const meta = plan?.meta ?? {};
  const explanation = meta?.explanation;
  const convergence = meta?.convergence_summary ?? {};
  const assumptionSummary = convergence?.assumption_summary ?? {};
  const producedDeliverables = Array.isArray(meta?.deliverables?.produced)
    ? meta.deliverables.produced
    : Array.isArray(meta?.produced_deliverables)
      ? meta.produced_deliverables
      : [];
  const failedDeliverables = Array.isArray(meta?.deliverables?.failed)
    ? meta.deliverables.failed
    : Array.isArray(meta?.failed_deliverables)
      ? meta.failed_deliverables
      : [];
  const assumptions = Array.isArray(data?.assumptions)
    ? data.assumptions
    : Array.isArray(assumptionSummary?.examples)
      ? assumptionSummary.examples.map((example) => ({
          field_name: "assumption",
          reason: String(example || ""),
        }))
      : [];
  const issues = Array.isArray(data?.issues) ? data.issues : [];
  const assumptionExamples = (() => {
    const seen = new Set<string>();
    const isInternalAssumption = (value: string) => {
      const lowered = value.toLowerCase();
      return (
        lowered === "plan" ||
        lowered === "assumption" ||
        lowered.includes("planner execution assumption") ||
        lowered.includes("projectmanager as active lifecycle state") ||
        lowered.includes("action geometry is treated as output packaging") ||
        lowered.includes("quantities prefer canonical projectmanager metrics") ||
        lowered.includes("planner executed model-first workflow") ||
        lowered.includes("prompt was parsed with deterministic fast-path rules") ||
        lowered.includes("autofix site layout") ||
        lowered.includes("autofix_site_layout")
      );
    };
    const formatted = assumptions
      .map((assumption) => {
        const fallbackField =
          "field_name" in assumption
            ? assumption.field_name
            : (assumption as BackendAssumption | null)?.field;
        const field = String(fallbackField || "an input")
          .replace(/_/g, " ")
          .trim();
        const reason = String(assumption?.reason || "").trim();
        const loweredField = field.toLowerCase();
        if (
          loweredField === "plan" ||
          loweredField === "assumption" ||
          isInternalAssumption(reason)
        ) {
          return null;
        }
        const normalized = `${field}::${reason}`.toLowerCase();
        if (seen.has(normalized)) {
          return null;
        }
        seen.add(normalized);
        return reason ? `${field} (${reason})` : field;
      })
      .filter(Boolean);
    if (formatted.length) {
      return formatted.slice(0, 3);
    }
    const fallbackExamples = Array.isArray(assumptionSummary?.examples)
      ? assumptionSummary.examples
          .map((example) => String(example || "").trim())
          .filter((example: string) => Boolean(example) && !isInternalAssumption(example))
      : [];
    return fallbackExamples.slice(0, 3);
  })();
  const fixSummary = convergence?.fix_summary ?? {};
  const blockedReasons = Array.isArray(convergence?.blocked_reasons)
    ? convergence.blocked_reasons
    : [];
  const blockedExports = Array.isArray(convergence?.blocked_exports)
    ? convergence.blocked_exports
    : [];
  const reviewCategories = Array.isArray(convergence?.unresolved_issue_categories)
    ? convergence.unresolved_issue_categories
    : [];
  const autofixActions = Array.isArray(fixSummary?.autofix_actions)
    ? fixSummary.autofix_actions
    : [];
  const dominantFixTargets = Array.isArray(convergence?.dominant_issue_categories)
    ? convergence.dominant_issue_categories
    : [];
  const unresolved = Number(convergence?.unresolved_conflict_count ?? 0);
  const headline =
    (typeof explanation?.summary === "string"
      ? explanation.summary
      : typeof explanation?.overview === "string"
        ? explanation.overview
        : typeof data?.message === "string"
          ? data.message
          : mode === "fix"
            ? "I ran a focused fix pass and updated the active design."
            : mode === "improve"
              ? "I ran an improvement pass and updated the active design."
              : "I updated the active design workspace.");
  const why =
    typeof explanation?.why === "string"
      ? explanation.why
      : typeof explanation?.reasoning === "string"
        ? explanation.reasoning
        : null;

  const readableAutofixActions = autofixActions
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableFixTargets = dominantFixTargets
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableReviewCategories = reviewCategories
    .map((item) => toReadableLabel(String(item || "")))
    .filter(
      (item: string) =>
        Boolean(item) &&
        item.toLowerCase() !== "uncategorized" &&
        item.toLowerCase() !== "general",
    );
  const readableBlockedReasons = blockedReasons
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableBlockedExports = blockedExports
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableProduced = producedDeliverables
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableFailed = failedDeliverables
    .map((item) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const issueMessages = issues
    .slice(0, 2)
    .map((issue) => String(issue?.message || "").trim())
    .filter(Boolean);

  const assumptionList = assumptionExamples.filter(
    (item): item is string => Boolean(item),
  );

  const notes = [
    assumptionList.length
      ? `I used assisted assumptions for ${joinNatural(assumptionList)}.`
      : "I did not need to record any explicit assisted assumptions on this run.",
    readableAutofixActions.length || readableFixTargets.length
      ? `I applied fixes around ${joinNatural(
          readableAutofixActions.length ? readableAutofixActions : readableFixTargets,
        )}.`
      : "I did not need to record any corrective fix actions on this run.",
    readableReviewCategories.length || issueMessages.length || unresolved > 0
      ? `You should still review ${joinNatural(
          readableReviewCategories.length
            ? readableReviewCategories
            : issueMessages.length
              ? issueMessages
              : [`${unresolved} unresolved conflicts`],
        )}.`
      : "I don’t see any active review items recorded right now.",
    readableBlockedReasons.length || readableBlockedExports.length || readableFailed.length
      ? `What is still blocked: ${joinNatural(
          readableBlockedReasons.length
            ? readableBlockedReasons
            : readableBlockedExports.length
              ? readableBlockedExports
              : readableFailed,
        )}.`
      : "Nothing is explicitly blocked right now.",
    producedDeliverables.length
      ? `I produced ${joinNatural(readableProduced, 4)}.`
      : null,
    why,
  ].filter(Boolean);

  return [headline, ...notes].join(" ");
}

function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-[28px] border border-slate-200/80 bg-white/92 shadow-[0_20px_60px_-28px_rgba(15,23,42,0.28)] backdrop-blur ${className}`}
    >
      {children}
    </div>
  );
}

function CardHeader({ children }: { children: React.ReactNode }) {
  return <div className="p-6 pb-4">{children}</div>;
}

function CardContent({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`p-6 pt-0 ${className}`}>{children}</div>;
}

function SectionTitle({
  icon: Icon,
  title,
  desc,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="rounded-2xl border border-slate-200 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] p-2.5 shadow-[0_10px_30px_-20px_rgba(15,23,42,0.45)]">
        <Icon className="h-5 w-5 text-slate-800" />
      </div>
      <div>
        <h3 className="text-[15px] font-semibold tracking-tight text-slate-950">
          {title}
        </h3>
        <p className="mt-1 text-sm leading-6 text-slate-500">{desc}</p>
      </div>
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600">
      {children}
    </span>
  );
}

function SmallButton({
  children,
  onClick,
  variant = "primary",
  disabled = false,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
}) {
  const styles =
    variant === "primary"
      ? "border border-slate-900 bg-slate-950 text-white hover:bg-slate-800"
      : "border border-slate-200 bg-white text-slate-900 hover:border-slate-300 hover:bg-slate-50";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center rounded-2xl px-4 py-2.5 text-sm font-medium shadow-[0_12px_30px_-22px_rgba(15,23,42,0.55)] transition duration-200 ${styles} ${
        disabled ? "cursor-not-allowed opacity-60" : "hover:-translate-y-0.5"
      }`}
    >
      {children}
    </button>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
        {label}
      </label>
      {children}
    </div>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] placeholder:text-slate-400 outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70 ${
        props.className ?? ""
      }`}
    />
  );
}

function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`min-h-[168px] max-h-[280px] w-full resize-none overflow-y-auto rounded-[24px] border border-slate-200 bg-white px-4 py-3.5 text-sm leading-6 text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.85)] placeholder:text-slate-400 outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70 ${
        props.className ?? ""
      }`}
    />
  );
}

const TOKEN_KEY = "civora-ai-token";
const LEGACY_TOKEN_KEY = "performance-ai-token";

function getStoredToken() {
  if (typeof window === "undefined") {
    return "";
  }
  return (
    window.localStorage.getItem(TOKEN_KEY) ??
    window.localStorage.getItem(LEGACY_TOKEN_KEY) ??
    ""
  );
}

function setStoredToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(TOKEN_KEY, token);
}

function clearStoredToken() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
}

function uploadedImageSrc(pathOrUrl: string, token: string): string {
  const safeToken = encodeURIComponent(token);
  if (!pathOrUrl || !token) {
    return "";
  }

  if (pathOrUrl.startsWith("/api/uploads/")) {
    return `${toApiUrl(pathOrUrl)}?access_token=${safeToken}`;
  }

  const filename = pathOrUrl.split("/").pop();
  if (!filename) {
    return "";
  }

  return `${toApiUrl(`/api/uploads/${filename}`)}?access_token=${safeToken}`;
}

function formatTimestamp(value?: number): string {
  if (!value) return "Unknown time";
  try {
    return new Date(value * 1000).toLocaleString();
  } catch {
    return "Unknown time";
  }
}

function isLikelyStaleJob(job: JobSummary | null, nowMs: number): boolean {
  if (!job?.updated_at) return false;
  const status = String(job.status || "").toLowerCase();
  if (!["queued", "running", "cancelling"].includes(status)) {
    return false;
  }
  const updatedAtMs = Number(job.updated_at) * 1000;
  if (!Number.isFinite(updatedAtMs) || updatedAtMs <= 0) {
    return false;
  }
  const staleThresholdMs = status === "queued" ? 90_000 : 60_000;
  return nowMs - updatedAtMs > staleThresholdMs;
}

function buildThinkingState({
  busy,
  activePlanTool,
  activeJobStatus,
  activeJobStage,
  activeJobDetail,
  activeJobProgress,
  activeJobUpdatedAt,
  activeJobQueuePosition,
  activeJobQueuedCount,
  activeJobRunningCount,
  staleJob,
  statusMessage,
}: {
  busy: boolean;
  activePlanTool: PlanToolMode;
  activeJobStatus?: string;
  activeJobStage?: string;
  activeJobDetail?: string;
  activeJobProgress?: number;
  activeJobUpdatedAt?: number;
  activeJobQueuePosition?: number | null;
  activeJobQueuedCount?: number;
  activeJobRunningCount?: number;
  staleJob?: boolean;
  statusMessage: string;
}) {
  const normalizedJobStatus = String(activeJobStatus || "").trim().toLowerCase();
  const normalizedStatus = statusMessage.toLowerCase();
  const stageLabel = String(activeJobStage || "").trim();
  const stageDetail = String(activeJobDetail || "").trim();
  const numericProgress =
    typeof activeJobProgress === "number" && Number.isFinite(activeJobProgress)
      ? Math.max(0, Math.min(100, Math.round(activeJobProgress)))
      : null;
  const lastUpdateText =
    activeJobUpdatedAt && Number.isFinite(activeJobUpdatedAt)
      ? `Last backend update: ${formatTimestamp(activeJobUpdatedAt)}.`
      : "";
  const queuePosition =
    typeof activeJobQueuePosition === "number" && Number.isFinite(activeJobQueuePosition)
      ? Math.max(1, Math.round(activeJobQueuePosition))
      : null;
  const queuedCount =
    typeof activeJobQueuedCount === "number" && Number.isFinite(activeJobQueuedCount)
      ? Math.max(0, Math.round(activeJobQueuedCount))
      : 0;
  const runningCount =
    typeof activeJobRunningCount === "number" && Number.isFinite(activeJobRunningCount)
      ? Math.max(0, Math.round(activeJobRunningCount))
      : 0;
  const queueDetail = queuePosition
    ? `Civora queued the run. Queue position: ${queuePosition}${queuedCount > 0 ? ` of ${queuedCount}` : ""}. ${runningCount > 0 ? `${runningCount} worker${runningCount === 1 ? "" : "s"} active.` : ""}`.trim()
    : "Civora queued the run and is waiting for a worker to pick it up.";

  if (normalizedJobStatus && staleJob) {
    return {
      label: normalizedJobStatus === "queued" ? "Queue Delayed" : "Check Run Status",
      detail:
        stageDetail ||
        `Civora has not received a fresh backend update for this ${normalizedJobStatus} job recently. ${lastUpdateText}`.trim(),
      progress:
        numericProgress ??
        (normalizedJobStatus === "queued" ? 18 : normalizedJobStatus === "cancelling" ? 68 : 72),
    };
  }

  if (normalizedJobStatus && stageLabel) {
    return {
      label: stageLabel,
      detail:
        stageDetail ||
        (normalizedJobStatus === "queued"
          ? queueDetail
          : "Civora is processing the design in the background now."),
      progress: numericProgress ?? (normalizedJobStatus === "queued" ? 12 : 48),
    };
  }

  if (normalizedJobStatus === "queued") {
    return {
      label: "Queued",
      detail: queueDetail,
      progress: 18,
    };
  }
  if (normalizedJobStatus === "awaiting_approval") {
    return {
      label: stageLabel || "Awaiting Approval",
      detail:
        stageDetail ||
        "Civora saved the current phase result and is waiting for your approval to continue.",
      progress: numericProgress ?? 60,
    };
  }
  if (normalizedJobStatus === "running") {
    return {
      label: "Running",
      detail: "Civora is processing the design in the background now.",
      progress: 68,
    };
  }
  if (normalizedJobStatus === "cancelling") {
    return {
      label: "Cancelling",
      detail:
        stageDetail ||
        "Civora is stopping the background run and cleaning up the active job.",
      progress: numericProgress ?? 68,
    };
  }
  if (busy && activePlanTool === "fix") {
    return {
      label: "Fixing",
      detail: "Applying a focused fix pass to the active design.",
      progress: 62,
    };
  }
  if (busy && activePlanTool === "improve") {
    return {
      label: "Improving",
      detail: "Improving the current design while preserving the main intent.",
      progress: 62,
    };
  }
  if (busy && normalizedStatus.includes("reviewing your request")) {
    return {
      label: "Reading Request",
      detail: "Reviewing your prompt and preparing the run.",
      progress: 22,
    };
  }
  if (busy && normalizedStatus.includes("starting the engineering run")) {
    return {
      label: "Engineering Run",
      detail: "Starting the core design pipeline and waiting for the first engineering result.",
      progress: 34,
    };
  }
  return {
    label: "Thinking",
    detail:
      statusMessage ||
      "Civora is building the design, checking engineering constraints, and preparing the next result.",
    progress: 42,
  };
}

export default function PerformanceAIDashboard() {
  const [token, setToken] = useState("");
  const [user, setUser] = useState<UserRecord | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authStatusError, setAuthStatusError] = useState("");

  const [strategyMode, setStrategyMode] = useState<StrategyMode>("assisted");
  const [projectType, setProjectType] = useState("");
  const [units, setUnits] = useState("ft");
  const [prompt, setPrompt] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    createWelcomeMessage(),
  ]);
  const [learningReport, setLearningReport] = useState<LearningReport | null>(null);
  const [learningReportUpdatedAt, setLearningReportUpdatedAt] = useState<number | null>(null);
  const [imageName, setImageName] = useState("");
  const [siteName, setSiteName] = useState("");
  const [fileName, setFileName] = useState("");
  const [siteNameAuto, setSiteNameAuto] = useState(false);
  const [fileNameAuto, setFileNameAuto] = useState(false);
  const [lotWidth, setLotWidth] = useState("");
  const [lotHeight, setLotHeight] = useState("");
  const [buildingWidth, setBuildingWidth] = useState("");
  const [buildingDepth, setBuildingDepth] = useState("");
  const [buildingCount, setBuildingCount] = useState("");
  const [setback, setSetback] = useState("");
  const [parkingCount, setParkingCount] = useState("");
  const [minSlopePct, setMinSlopePct] = useState("");
  const [pipeMinSlopePct, setPipeMinSlopePct] = useState("");
  const [maxParkingSlopePct, setMaxParkingSlopePct] = useState("");
  const [maxRoadGradePct, setMaxRoadGradePct] = useState("");
  const [maxAdaCrossSlopePct, setMaxAdaCrossSlopePct] = useState("");
  const [roads, setRoads] = useState(true);
  const [grading, setGrading] = useState(true);
  const [drainage, setDrainage] = useState(true);
  const [utilities, setUtilities] = useState(true);

  const [assumptions, setAssumptions] =
    useState<Assumption[]>(defaultAssumptions);
  const [issues, setIssues] = useState<Issue[]>(defaultIssues);
  const [backendResult, setBackendResult] = useState<PlanResponse | null>(null);
  const [uploadedImagePreviewUrl, setUploadedImagePreviewUrl] = useState("");
  const [uploadedImageApiUrl, setUploadedImageApiUrl] = useState("");
  const [surveyFileName, setSurveyFileName] = useState("");
  const [surveySlopeEstimate, setSurveySlopeEstimate] = useState<SurveySlopeResponse | null>(null);
  const [mapSnapshotPath, setMapSnapshotPath] = useState("");
  const [mapAnalysis, setMapAnalysis] = useState<MapAnalysis | null>(null);
  const [planPreviewUrl, setPlanPreviewUrl] = useState("");
  const [planPreviewSummary, setPlanPreviewSummary] =
    useState<PreviewResponse["summary"] | null>(null);
  const [planPreviewAnnotations, setPlanPreviewAnnotations] =
    useState<PreviewResponse["preview_annotations"] | null>(null);
  const [previewMode, setPreviewMode] = useState<"2d" | "3d">("2d");
  const [previewInteraction, setPreviewInteraction] = useState<"static" | "interactive">("interactive");
  const [previewQuality, setPreviewQuality] = useState<"standard" | "high">("standard");
  const [showMeasurements, setShowMeasurements] = useState(false);
  const [showCalculations, setShowCalculations] = useState(false);
  const [autoAdvancePhases, setAutoAdvancePhases] = useState(false);
  const [revisePhaseTarget, setRevisePhaseTarget] = useState<
    "layout" | "grading" | "drainage_storm" | "utilities" | "coordination_validation"
  >("layout");
  const [previewLayers, setPreviewLayers] = useState({
    buildings: true,
    roads: true,
    grading: true,
    drainage: true,
    utilities: true,
    structures: true,
    lots: false,
  });
  const [quantityRollupsEnabled, setQuantityRollupsEnabled] = useState(true);
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);
  const [previewFullscreenOpen, setPreviewFullscreenOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectRecord | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activePlanTool, setActivePlanTool] = useState<PlanToolMode>("run");
  const [jobClockMs, setJobClockMs] = useState(() => Date.now());
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const mapSnapshotInputRef = useRef<HTMLInputElement | null>(null);
  const surveyInputRef = useRef<HTMLInputElement | null>(null);
  const runSubmissionRef = useRef(false);
  const directRunAbortRef = useRef<AbortController | null>(null);
  const draftProjectPromiseRef = useRef<Promise<ProjectRecord | null> | null>(null);
  const resolvedProjectIdRef = useRef("");
  const projectLoadRequestRef = useRef(0);
  const projectResultLoadRequestRef = useRef(0);
  const activeJobProjectSyncRef = useRef("");
  const lastJobStatusRef = useRef<Record<string, string>>({});
  const lastJobPhaseSignatureRef = useRef<Record<string, string>>({});
  const lastStaleJobWarningRef = useRef<Record<string, boolean>>({});
  const lastProjectResultRefreshRef = useRef<Record<string, number>>({});
  const lastJobPartialResultRefreshRef = useRef<Record<string, number>>({});
  const chatMessagesRef = useRef<ChatMessage[]>([createWelcomeMessage()]);
  const suppressProjectAutoLoadRef = useRef(false);
  const chatAutosaveTimeoutRef = useRef<number | null>(null);
  const autosaveSuspendRef = useRef(false);
  const lastProjectNameSignatureRef = useRef<string>("");
  const autoAdvanceByJobRef = useRef<Record<string, boolean>>({});
  const previewRecoveryKeyRef = useRef("");
  const lastSiteInputProjectRef = useRef("");
  const controlAutosaveTimeoutRef = useRef<number | null>(null);

  const disciplineToggles: DisciplineToggle[] = [
    {
      label: "Roads",
      checked: roads,
      setter: setRoads,
      desc: "Corridor / access layout",
    },
    {
      label: "Grading",
      checked: grading,
      setter: setGrading,
      desc: "Pads, slopes, tie-ins",
    },
    {
      label: "Drainage",
      checked: drainage,
      setter: setDrainage,
      desc: "Inlets, ponds, routing",
    },
    {
      label: "Utilities",
      checked: utilities,
      setter: setUtilities,
      desc: "Water, sanitary, utility",
    },
  ];

  const buildManualFields = useCallback(({
    strategy,
    nextSiteName,
    nextFileName,
    nextUnits,
    nextProjectType,
    nextLotWidth,
    nextLotHeight,
    nextSetback,
    nextBuildingWidth,
    nextBuildingDepth,
    nextBuildingCount,
    nextParkingCount,
    nextMinSlopePct,
    nextPipeMinSlopePct,
    nextMaxParkingSlopePct,
    nextMaxRoadGradePct,
    nextMaxAdaCrossSlopePct,
    nextRoads,
    nextGrading,
    nextDrainage,
    nextUtilities,
  }: {
    strategy: "manual" | "assisted";
    nextSiteName: string;
    nextFileName: string;
    nextUnits: string;
    nextProjectType: string;
    nextLotWidth: string | number | null | undefined;
    nextLotHeight: string | number | null | undefined;
    nextSetback: string | number | null | undefined;
    nextBuildingWidth: string | number | null | undefined;
    nextBuildingDepth: string | number | null | undefined;
    nextBuildingCount: string | number | null | undefined;
    nextParkingCount: string | number | null | undefined;
    nextMinSlopePct: string | number | null | undefined;
    nextPipeMinSlopePct: string | number | null | undefined;
    nextMaxParkingSlopePct: string | number | null | undefined;
    nextMaxRoadGradePct: string | number | null | undefined;
    nextMaxAdaCrossSlopePct: string | number | null | undefined;
    nextRoads: boolean;
    nextGrading: boolean;
    nextDrainage: boolean;
    nextUtilities: boolean;
  }) => {
    const lotWidthValue = parsePositiveNumber(nextLotWidth);
    const lotHeightValue = parsePositiveNumber(nextLotHeight);
    const setbackValue = parsePositiveNumber(nextSetback);
    const buildingWidthValue = parsePositiveNumber(nextBuildingWidth);
    const buildingDepthValue = parsePositiveNumber(nextBuildingDepth);
    const buildingCountValue = parsePositiveNumber(nextBuildingCount);
    const parkingCountValue = parsePositiveNumber(nextParkingCount);
    const minSlopeValue = parsePositiveNumber(nextMinSlopePct);
    const pipeMinSlopeValue = parsePositiveNumber(nextPipeMinSlopePct);
    const maxParkingSlopeValue = parsePositiveNumber(nextMaxParkingSlopePct);
    const maxRoadGradeValue = parsePositiveNumber(nextMaxRoadGradePct);
    const maxAdaSlopeValue = parsePositiveNumber(nextMaxAdaCrossSlopePct);

    const manualFields: ManualFields = {
      project_name: nextSiteName,
      file_name: nextFileName,
      units: nextUnits,
      project_type: nextProjectType,
      disciplines: [
        nextRoads ? "corridor" : null,
        nextGrading ? "grading" : null,
        nextDrainage ? "drainage" : null,
        nextUtilities ? "utility" : null,
      ].filter((item): item is string => Boolean(item)),
    };

    if (lotWidthValue !== null && lotHeightValue !== null) {
      manualFields.lot = {
        x: 0,
        y: 0,
        w: lotWidthValue,
        h: lotHeightValue,
      };
    } else if (strategy === "manual") {
      manualFields.lot = { x: 0, y: 0, w: 0, h: 0 };
    }

    if (setbackValue !== null) {
      manualFields.setback = setbackValue;
    } else if (strategy === "manual") {
      manualFields.setback = 0;
    }

    if (buildingWidthValue !== null) {
      manualFields.building_width = buildingWidthValue;
    } else if (strategy === "manual") {
      manualFields.building_width = 0;
    }

    if (buildingDepthValue !== null) {
      manualFields.building_depth = buildingDepthValue;
    } else if (strategy === "manual") {
      manualFields.building_depth = 0;
    }

    if (buildingCountValue !== null) {
      manualFields.buildings = Array.from({ length: Math.max(1, Math.round(buildingCountValue)) }).map(
        (_, idx) => ({
          name: `Building ${idx + 1}`,
          w: buildingWidthValue ?? undefined,
          d: buildingDepthValue ?? undefined,
        }),
      );
    }

    if (parkingCountValue !== null) {
      manualFields.site_plan = { parking_count: parkingCountValue };
    } else if (strategy === "manual") {
      manualFields.site_plan = { parking_count: 0 };
    }

    if (minSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        min_slope_pct: minSlopeValue,
      };
    }

    if (maxParkingSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_parking_slope_pct: maxParkingSlopeValue,
      };
    }

    if (maxRoadGradeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_road_grade_pct: maxRoadGradeValue,
      };
    }

    if (maxAdaSlopeValue !== null) {
      manualFields.grading = {
        ...(manualFields.grading ?? {}),
        max_ada_cross_slope_pct: maxAdaSlopeValue,
      };
    }

    if (pipeMinSlopeValue !== null) {
      manualFields.drainage = {
        ...(manualFields.drainage ?? {}),
        min_pipe_slope_pct: pipeMinSlopeValue,
      };
    }

    return manualFields;
  }, []);

  const payloadPreview = useMemo(
    () => ({
      project_id: projectId || null,
      full_design_mode: true,
      input_mode: strategyMode,
      strict_mode: strategyMode === "manual",
      prompt_text: prompt || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
      },
      manual_fields: buildManualFields({
        strategy: strategyMode,
        nextSiteName: siteName,
        nextFileName: fileName,
        nextUnits: units,
        nextProjectType: projectType,
        nextLotWidth: lotWidth,
        nextLotHeight: lotHeight,
        nextSetback: setback,
        nextBuildingWidth: buildingWidth,
        nextBuildingDepth: buildingDepth,
        nextBuildingCount: buildingCount,
        nextParkingCount: parkingCount,
        nextMinSlopePct: minSlopePct,
        nextPipeMinSlopePct: pipeMinSlopePct,
        nextMaxParkingSlopePct: maxParkingSlopePct,
        nextMaxRoadGradePct: maxRoadGradePct,
        nextMaxAdaCrossSlopePct: maxAdaCrossSlopePct,
        nextRoads: roads,
        nextGrading: grading,
        nextDrainage: drainage,
        nextUtilities: utilities,
      }),
      allow_ai_fill_for_blanks: strategyMode !== "manual",
    }),
    [
      projectId,
      strategyMode,
      prompt,
      imageName,
      siteName,
      fileName,
      units,
      projectType,
      lotWidth,
      lotHeight,
      setback,
      buildingWidth,
      buildingDepth,
      buildingCount,
      parkingCount,
    minSlopePct,
    pipeMinSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    maxAdaCrossSlopePct,
    roads,
      grading,
      drainage,
      utilities,
      currentProject,
      buildManualFields,
    ],
  );

  const artifactPayload = useMemo(() => {
    if (
      backendResult &&
      typeof backendResult === "object" &&
      Object.keys(backendResult).length
    ) {
      return {
        project_id: projectId || currentProject?.project_id || null,
        result: backendResult,
        filename_stem: fileName || siteName,
      };
    }

    return {
      project_id: projectId || currentProject?.project_id || null,
      filename_stem: fileName || siteName,
    };
  }, [backendResult, currentProject?.project_id, fileName, projectId, siteName]);

  const workflowRuns = useMemo<WorkflowRunSummary[]>(
    () =>
      Array.isArray(currentProject?.metadata?.workflow?.runs)
        ? currentProject?.metadata?.workflow?.runs
        : [],
    [currentProject],
  );

  const selectedRun = useMemo<WorkflowRunSummary | null>(() => {
    if (!workflowRuns.length) return null;
    return (
      workflowRuns.find((run) => run.run_id === selectedRunId) ?? workflowRuns[0]
    );
  }, [workflowRuns, selectedRunId]);
  const activeJob = useMemo(
    () => jobs.find((job) => job.job_id === activeJobId) ?? null,
    [jobs, activeJobId],
  );
  const currentProjectActiveJob = useMemo(
    () =>
      jobs.find(
        (job) =>
          Boolean(projectId) &&
          job.project_id === projectId &&
          ["queued", "running", "awaiting_approval", "cancelling"].includes(String(job.status || "").toLowerCase()),
      ) ?? null,
    [jobs, projectId],
  );
  const visibleActiveJob = useMemo(() => {
    if (activeJobId) {
      return activeJob;
    }
    return projectId ? currentProjectActiveJob : activeJob;
  }, [activeJob, activeJobId, currentProjectActiveJob, projectId]);
  const hasDirectRunInFlight = busy && !visibleActiveJob && Boolean(directRunAbortRef.current);
  const visibleActiveJobStale = useMemo(
    () => isLikelyStaleJob(visibleActiveJob, jobClockMs),
    [visibleActiveJob, jobClockMs],
  );
  const thinkingState = useMemo(
    () =>
      buildThinkingState({
        busy,
        activePlanTool,
        activeJobStatus: visibleActiveJob?.status,
        activeJobStage: visibleActiveJob?.stage,
        activeJobDetail: visibleActiveJob?.stage_detail,
        activeJobProgress: visibleActiveJob?.progress,
        activeJobUpdatedAt: visibleActiveJob?.updated_at,
        activeJobQueuePosition: visibleActiveJob?.queue_position,
        activeJobQueuedCount: visibleActiveJob?.queued_count,
        activeJobRunningCount: visibleActiveJob?.running_count,
        staleJob: visibleActiveJobStale,
        statusMessage,
      }),
    [busy, visibleActiveJob?.status, visibleActiveJob?.stage, visibleActiveJob?.stage_detail, visibleActiveJob?.progress, visibleActiveJob?.updated_at, visibleActiveJob?.queue_position, visibleActiveJob?.queued_count, visibleActiveJob?.running_count, visibleActiveJobStale, activePlanTool, statusMessage],
  );
  const currentPlanMeta = useMemo<PlanMeta>(() => backendResult?.final_plan?.meta ?? {}, [backendResult]);
  const managerMetrics = useMemo<ManagerMetrics>(
    () => currentPlanMeta?.manager_export?.metrics ?? {},
    [currentPlanMeta],
  );
  const quantityTotals = useMemo<QuantityTotals>(
    () => currentPlanMeta?.quantities?.totals ?? {},
    [currentPlanMeta],
  );
  const stormSummary = useMemo<StormSummary>(() => currentPlanMeta?.storm_pipes ?? {}, [currentPlanMeta]);
  const drainageSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.drainage ?? {}, [currentPlanMeta]);
  const gradingSummary = useMemo<Record<string, unknown>>(() => currentPlanMeta?.grading ?? {}, [currentPlanMeta]);

  const previewLabels = useMemo(
    () => planPreviewAnnotations?.labels ?? [],
    [planPreviewAnnotations],
  );
  const issueTargets = useMemo(() => {
    const keywordMap = [
      { key: "pipe", token: "PIPE" },
      { key: "drain", token: "DRAIN" },
      { key: "storm", token: "STORM" },
      { key: "basin", token: "BASIN" },
      { key: "parking", token: "PARK" },
      { key: "ada", token: "ADA" },
      { key: "road", token: "ROAD" },
      { key: "utility", token: "UTIL" },
      { key: "water", token: "WATER" },
      { key: "sanitary", token: "SAN" },
    ];
    return (issues.length ? issues : defaultIssues).map((issue, idx) => {
      const lowered = issue.message.toLowerCase();
      const matched = keywordMap.find((item) => lowered.includes(item.key));
      const labelMatch = matched
        ? previewLabels.find((label) => label.label.toLowerCase().includes(matched.key))
        : null;
      return {
        id: `${issue.message}-${idx}`,
        label: labelMatch?.label ?? "",
      };
    });
  }, [issues, previewLabels]);

  const selectedIssueLabel = issueTargets.find((item) => item.id === selectedIssueId)?.label ?? "";

  const pipeSegments = useMemo<PipeSegment[]>(() => {
    const segments =
      stormSummary?.segments ||
      stormSummary?.pipe_segments ||
      stormSummary?.storm_pipe_segments ||
      [];
    return Array.isArray(segments) ? segments : [];
  }, [stormSummary]);

  const totalPipeLength =
    readMetricValue(managerMetrics.storm_pipe_length_ft) ??
    (pipeSegments.length
      ? pipeSegments.reduce((sum, seg) => sum + Number(seg.length_ft || 0), 0)
      : null);
  const maxSlope = pipeSegments.length
    ? Math.max(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const minSlope = pipeSegments.length
    ? Math.min(
        ...pipeSegments.map((seg) =>
          Number(seg.slope_pct ?? (seg.slope_ft_ft ?? 0) * 100),
        ),
      )
    : null;
  const flowCfs =
    readMetricValue(managerMetrics.pipe_capacity_total_cfs) ??
    readMetricValue(stormSummary.total_system_flow_cfs) ??
    readMetricValue(stormSummary.total_system_capacity_cfs) ??
    null;
  const cutFillNet =
    readMetricValue(managerMetrics.earthwork_net_cf) ??
    readMetricValue((gradingSummary as { earthwork?: { net_cf?: number } })?.earthwork?.net_cf) ??
    null;
  const basinSize =
    (Array.isArray(drainageSummary?.basins) && drainageSummary.basins[0]?.area_sf) ||
    (Array.isArray(drainageSummary?.basins) && drainageSummary.basins[0]?.footprint_area_sf) ||
    null;
  const quantityRows = useMemo(() => {
    const rows = [
      { label: "Lot area", value: quantityTotals.lot_area_sf, unit: "sf" },
      { label: "Building area", value: quantityTotals.building_area_sf, unit: "sf" },
      { label: "Parking area", value: quantityTotals.parking_area_sf, unit: "sf" },
      { label: "Road area", value: quantityTotals.road_area_sf, unit: "sf" },
      { label: "Impervious area", value: quantityTotals.estimated_impervious_area_sf, unit: "sf" },
      { label: "Parking stalls", value: quantityTotals.estimated_parking_stalls, unit: "stalls" },
      { label: "Road length", value: quantityTotals.road_length_ft, unit: "ft" },
      { label: "Sidewalk length", value: quantityTotals.sidewalk_length_ft, unit: "ft" },
      { label: "Pipe length", value: quantityTotals.pipe_length_ft, unit: "ft" },
      { label: "Utility length", value: quantityTotals.utility_length_ft, unit: "ft" },
      { label: "Sanitary length", value: quantityTotals.sanitary_length_ft, unit: "ft" },
      { label: "Drainage flow length", value: quantityTotals.drainage_flow_length_ft, unit: "ft" },
      { label: "Pond count", value: quantityTotals.pond_count, unit: "ea" },
      { label: "Inlet count", value: quantityTotals.inlet_count, unit: "ea" },
      { label: "Bridge area", value: quantityTotals.bridge_area_sf, unit: "sf" },
      { label: "Pool area", value: quantityTotals.pool_area_sf, unit: "sf" },
      { label: "Lot count", value: quantityTotals.lot_feature_count, unit: "ea" },
    ];
    return rows.filter((row) => Number(row.value || 0) > 0);
  }, [quantityTotals]);
  const measurementOverlayStats = useMemo(
    () => [
      { label: "Lot area", value: quantityTotals.lot_area_sf, unit: "sf" },
      { label: "Building area", value: quantityTotals.building_area_sf, unit: "sf" },
      { label: "Parking area", value: quantityTotals.parking_area_sf, unit: "sf" },
      { label: "Road length", value: quantityTotals.road_length_ft, unit: "ft" },
      { label: "Impervious area", value: quantityTotals.estimated_impervious_area_sf, unit: "sf" },
      { label: "Parking stalls", value: quantityTotals.estimated_parking_stalls, unit: "stalls" },
    ],
    [quantityTotals],
  );
  const calculationOverlayStats = useMemo(
    () => [
      { label: "Total pipe length", value: totalPipeLength, unit: "ft" },
      { label: "Max slope", value: maxSlope, unit: "%" },
      { label: "Min slope", value: minSlope, unit: "%" },
      { label: "Flow (CFS)", value: flowCfs, unit: "cfs" },
      { label: "Cut / fill net", value: cutFillNet, unit: "cf" },
      { label: "Pond size", value: basinSize, unit: "sf" },
    ],
    [totalPipeLength, maxSlope, minSlope, flowCfs, cutFillNet, basinSize],
  );
  const currentTruthAudit = useMemo(
    () => currentPlanMeta?.truth_audit ?? {},
    [currentPlanMeta],
  );
  const currentManualFailures = useMemo<ManualFailure[]>(
    () =>
      Array.isArray(currentPlanMeta?.manual_validation?.failures)
        ? currentPlanMeta.manual_validation.failures
        : [],
    [currentPlanMeta],
  );
  const currentExplanation = useMemo<PlanExplanation>(
    () => currentPlanMeta?.explanation ?? {},
    [currentPlanMeta],
  );
  const suggestedImproveGoal = useMemo(() => {
    const failureBlob = [
      ...currentManualFailures.map((failure) =>
        [failure.code, failure.message, failure.system, failure.rule]
          .filter(Boolean)
          .join(" "),
      ),
      ...issues.map((issue) => issue.message),
    ]
      .join(" ")
      .toLowerCase();

    if (failureBlob.includes("drain") || failureBlob.includes("inlet")) {
      return "improve_drainage";
    }
    if (failureBlob.includes("pipe")) {
      return "reduce_pipe_length";
    }
    if (
      failureBlob.includes("grade") ||
      failureBlob.includes("earthwork") ||
      failureBlob.includes("slope")
    ) {
      return "reduce_grading";
    }
    if (failureBlob.includes("parking")) {
      return "maximize_parking";
    }
    return undefined;
  }, [currentManualFailures, issues]);

  const applyBackendResult = (data: PlanResponse) => {
    setBackendResult(data);
    if (Array.isArray(data?.assumptions)) {
      setAssumptions(
        data.assumptions.map((item: BackendAssumption) => ({
          field: item.field_name ?? "unknown",
          value:
            typeof item.assumed_value === "string"
              ? item.assumed_value
              : JSON.stringify(item.assumed_value),
          reason: item.reason ?? "",
        })),
      );
    } else {
      setAssumptions(defaultAssumptions);
    }

    if (Array.isArray(data?.issues)) {
      setIssues(
        data.issues.map((item: BackendIssue) => ({
          severity: item.severity === "error" ? "error" : "warning",
          message: item.message ?? "Unknown issue",
        })),
      );
    } else {
      setIssues(defaultIssues);
    }
  };

  const appendChatMessage = (
    role: ChatMessage["role"],
    content: string,
    kind: ChatMessage["kind"] = "message",
    feedback?: ChatMessage["feedback"],
  ) => {
    setChatMessages((current) => {
      const next = [...current, createChatMessage(role, content, kind, feedback)];
      chatMessagesRef.current = next;
      return next;
    });
  };

  const refreshLearningReport = async () => {
    if (!token) return;
    try {
      const data = await getJson<{ success: boolean; report: LearningReport | null }>(
        "/api/chat/learning-report",
        { token },
      );
      setLearningReport(data.report ?? null);
      setLearningReportUpdatedAt(Date.now());
    } catch {
      // Ignore learning report failures.
    }
  };

  const setMessageFeedback = async (
    messageId: string,
    feedback: ChatMessage["feedback"],
  ) => {
    if (!token || !feedback) return;
    const thread = chatMessagesRef.current;
    const idx = thread.findIndex((message) => message.id === messageId);
    if (idx < 0) return;
    const target = thread[idx];
    const prevUser = [...thread]
      .slice(0, idx)
      .reverse()
      .find((message) => message.role === "user");
    const userMessage = prevUser?.content ?? "";

    setChatMessages((current) => {
      const next = current.map((message) =>
        message.id === messageId ? { ...message, feedback } : message,
      );
      chatMessagesRef.current = next;
      return next;
    });

    try {
      await postJson<{ success: boolean }>(
        "/api/chat/feedback",
        {
          project_id: currentProject?.project_id ?? null,
          message_id: messageId,
          feedback,
          message: userMessage,
          assistant_message: target.content,
          context: buildChatDecisionContext({}, userMessage),
        },
        { token },
      );
    } catch {
      // Feedback logging should never block chat UX.
    }
  };

  useEffect(() => {
    const node = chatScrollRef.current;
    if (!node) return;
    node.scrollTo({
      top: node.scrollHeight,
      behavior: "smooth",
    });
  }, [chatMessages]);

  useEffect(() => {
    chatMessagesRef.current = chatMessages;
  }, [chatMessages]);

  useEffect(() => {
    return () => {
      if (chatAutosaveTimeoutRef.current !== null) {
        window.clearTimeout(chatAutosaveTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!token) return;
    void refreshLearningReport();
  }, [token]);

  useEffect(() => {
    if (autosaveSuspendRef.current) return;
    const signature = `${siteName}::${fileName}`;
    if (!lastProjectNameSignatureRef.current) {
      lastProjectNameSignatureRef.current = signature;
      return;
    }
    if (signature === lastProjectNameSignatureRef.current) return;
    lastProjectNameSignatureRef.current = signature;
    if (prompt.trim()) {
      if (directRunAbortRef.current) {
        directRunAbortRef.current.abort();
        directRunAbortRef.current = null;
        runSubmissionRef.current = false;
        setBusy(false);
      }
      setPrompt("");
      appendChatMessage(
        "assistant",
        "I cleared the draft prompt because the project name changed. Paste it back if you still want to run it.",
        "status",
      );
    }
  }, [siteName, fileName, prompt]);

  const applyProjectInput = (projectInput: ProjectInput) => {
    if (!projectInput || typeof projectInput !== "object") {
      return;
    }

    const manualFields = projectInput.manual_fields ?? {};
    const lot = (manualFields.lot ?? {}) as { w?: number; h?: number };
    const sitePlan = (manualFields.site_plan ?? {}) as { parking_count?: number };
    const gradingFields = (manualFields.grading ?? {}) as {
      min_slope_pct?: number;
      max_parking_slope_pct?: number;
      max_road_grade_pct?: number;
      max_ada_cross_slope_pct?: number;
    };
    const drainageFields = (manualFields.drainage ?? {}) as { min_pipe_slope_pct?: number };
    const disciplines = toArray(manualFields.disciplines);
    const buildingsList = Array.isArray(manualFields.buildings) ? manualFields.buildings : [];
    const restoredThread: ChatMessage[] = Array.isArray(projectInput.meta?.chat_thread)
      ? projectInput.meta.chat_thread
          .filter((message) => message && typeof message.content === "string")
          .map((message): ChatMessage => ({
            id:
              typeof message.id === "string"
                ? message.id
                : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            role:
              message.role === "user" ||
              message.role === "assistant" ||
              message.role === "system"
                ? message.role
                : "assistant",
            content: message.content,
            createdAt:
              typeof message.createdAt === "number"
                ? message.createdAt
                : Date.now(),
            kind:
              message.kind === "status" ||
              message.kind === "explanation" ||
              message.kind === "action"
                ? message.kind
                : "message",
            feedback:
              message.feedback === "up" || message.feedback === "down"
                ? message.feedback
                : undefined,
          }))
      : [];
    const autoNamed = Boolean(projectInput.meta?.auto_named);
    const autoFileNamed = Boolean(projectInput.meta?.auto_file_named);

    const nextMode = projectInput.input_mode ?? (projectInput.strict_mode ? "manual" : "assisted");
    setStrategyMode(nextMode === "manual" ? "manual" : "assisted");
    setPrompt(projectInput.prompt_text ?? "");
    setImageName(projectInput.image_path ?? "");
    setUploadedImageApiUrl(
      projectInput.image_path ? uploadedImageSrc(projectInput.image_path, token) : "",
    );
    setUploadedImagePreviewUrl("");
    setSiteName(manualFields.project_name ?? "");
    setFileName(manualFields.file_name ?? "");
    setSiteNameAuto(autoNamed || !manualFields.project_name);
    setFileNameAuto(autoFileNamed || !(manualFields.file_name ?? manualFields.project_name));
    setUnits(manualFields.units ?? "ft");
    setProjectType(manualFields.project_type ?? "");
    setLotWidth(String(lot.w ?? ""));
    setLotHeight(String(lot.h ?? ""));
    setSetback(String(manualFields.setback ?? ""));
    setBuildingWidth(String(manualFields.building_width ?? ""));
    setBuildingDepth(String(manualFields.building_depth ?? ""));
    setBuildingCount(buildingsList.length ? String(buildingsList.length) : "");
    setParkingCount(String(sitePlan.parking_count ?? ""));
    setMinSlopePct(String(gradingFields.min_slope_pct ?? ""));
    setPipeMinSlopePct(String(drainageFields.min_pipe_slope_pct ?? ""));
    setMaxParkingSlopePct(String(gradingFields.max_parking_slope_pct ?? ""));
    setMaxRoadGradePct(String(gradingFields.max_road_grade_pct ?? ""));
    setMaxAdaCrossSlopePct(String(gradingFields.max_ada_cross_slope_pct ?? ""));
    setRoads(disciplines.includes("corridor"));
    setGrading(disciplines.includes("grading"));
    setDrainage(disciplines.includes("drainage"));
    setUtilities(disciplines.includes("utility"));
    const nextThread = restoredThread.length ? restoredThread : [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
  };

  const applyControlOverrides = (overrides: ControlOverrides) => {
    if (overrides.strategyMode) {
      setStrategyMode(overrides.strategyMode);
    }
    if (overrides.projectType) setProjectType(overrides.projectType);
    if (overrides.units) setUnits(overrides.units);
    if (typeof overrides.roads === "boolean") setRoads(overrides.roads);
    if (typeof overrides.grading === "boolean") setGrading(overrides.grading);
    if (typeof overrides.drainage === "boolean") setDrainage(overrides.drainage);
    if (typeof overrides.utilities === "boolean") setUtilities(overrides.utilities);
    if (typeof overrides.siteName === "string") setSiteName(overrides.siteName);
    if (typeof overrides.fileName === "string") setFileName(overrides.fileName);
    if (typeof overrides.lotWidth === "string" || typeof overrides.lotWidth === "number") {
      setLotWidth(String(overrides.lotWidth));
    }
    if (typeof overrides.lotHeight === "string" || typeof overrides.lotHeight === "number") {
      setLotHeight(String(overrides.lotHeight));
    }
    if (typeof overrides.buildingWidth === "string" || typeof overrides.buildingWidth === "number") {
      setBuildingWidth(String(overrides.buildingWidth));
    }
    if (typeof overrides.buildingDepth === "string" || typeof overrides.buildingDepth === "number") {
      setBuildingDepth(String(overrides.buildingDepth));
    }
    if (typeof overrides.buildingCount === "string" || typeof overrides.buildingCount === "number") {
      setBuildingCount(String(overrides.buildingCount));
    }
    if (typeof overrides.setback === "string" || typeof overrides.setback === "number") {
      setSetback(String(overrides.setback));
    }
    if (typeof overrides.parkingCount === "string" || typeof overrides.parkingCount === "number") {
      setParkingCount(String(overrides.parkingCount));
    }
    if (typeof overrides.minSlopePct === "string" || typeof overrides.minSlopePct === "number") {
      setMinSlopePct(String(overrides.minSlopePct));
    }
    if (typeof overrides.pipeMinSlopePct === "string" || typeof overrides.pipeMinSlopePct === "number") {
      setPipeMinSlopePct(String(overrides.pipeMinSlopePct));
    }
    if (typeof overrides.maxParkingSlopePct === "string" || typeof overrides.maxParkingSlopePct === "number") {
      setMaxParkingSlopePct(String(overrides.maxParkingSlopePct));
    }
    if (typeof overrides.maxRoadGradePct === "string" || typeof overrides.maxRoadGradePct === "number") {
      setMaxRoadGradePct(String(overrides.maxRoadGradePct));
    }
    if (typeof overrides.maxAdaCrossSlopePct === "string" || typeof overrides.maxAdaCrossSlopePct === "number") {
      setMaxAdaCrossSlopePct(String(overrides.maxAdaCrossSlopePct));
    }
  };

  const buildChatDecisionContext = (
    overrides: ControlOverrides = {},
    message: string,
  ) => {
    const nextStrategy = overrides.strategyMode ?? strategyMode;
    const liveThread = chatMessagesRef.current;
    const designMemory = extractDesignMemory(liveThread);
    const storedMemory =
      currentProject?.project_input?.meta?.chat_memory &&
      typeof currentProject.project_input.meta.chat_memory === "object"
        ? currentProject.project_input.meta.chat_memory
        : null;
    const mergedPreferences = [
      ...toArray((storedMemory as { preferences?: string[] } | null)?.preferences),
      ...designMemory.preferences,
    ].slice(-8);
    const mergedConstraints = [
      ...toArray((storedMemory as { constraints?: string[] } | null)?.constraints),
      ...designMemory.constraints,
    ].slice(-8);
    return {
      strategy_mode: nextStrategy,
      site_name: overrides.siteName ?? siteName,
      file_name: overrides.fileName ?? fileName,
      project_type: overrides.projectType ?? projectType,
      units: overrides.units ?? units,
      lot_width: overrides.lotWidth ?? lotWidth,
      lot_height: overrides.lotHeight ?? lotHeight,
      building_width: overrides.buildingWidth ?? buildingWidth,
      building_depth: overrides.buildingDepth ?? buildingDepth,
      setback: overrides.setback ?? setback,
      building_count: overrides.buildingCount ?? buildingCount,
      parking_count: overrides.parkingCount ?? parkingCount,
      min_slope_pct: overrides.minSlopePct ?? minSlopePct,
      pipe_min_slope_pct: overrides.pipeMinSlopePct ?? pipeMinSlopePct,
      max_parking_slope_pct: overrides.maxParkingSlopePct ?? maxParkingSlopePct,
      max_road_grade_pct: overrides.maxRoadGradePct ?? maxRoadGradePct,
      max_ada_cross_slope_pct: overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct,
      roads: overrides.roads ?? roads,
      grading: overrides.grading ?? grading,
      drainage: overrides.drainage ?? drainage,
      utilities: overrides.utilities ?? utilities,
      has_plan: Boolean(backendResult?.final_plan),
      has_preview: Boolean(planPreviewUrl),
      current_project: currentProject
        ? {
            project_id: currentProject.project_id,
            name: currentProject.name,
          }
        : null,
      current_explanation: currentExplanation,
      current_truth_audit: currentTruthAudit,
      engineering_status: currentPlanMeta?.engineering_status ?? {},
      convergence_summary: currentPlanMeta?.convergence_summary ?? {},
      manual_failures: currentManualFailures,
      assumptions,
      produced_deliverables: Array.isArray(currentPlanMeta?.deliverables?.produced)
        ? currentPlanMeta.deliverables.produced
        : [],
      issues,
      memory_summary: {
        preferences: mergedPreferences,
        constraints: mergedConstraints,
        open_questions: toArray((storedMemory as { open_questions?: string[] } | null)?.open_questions).slice(-6),
        examples: [...mergedPreferences, ...mergedConstraints].slice(-8),
      },
      current_phase:
        String(visibleActiveJob?.stage || "") ||
        String((currentPlanMeta?.runtime_phase_checkpoint as { stage_name?: string } | undefined)?.stage_name || ""),
      current_phase_detail: String(visibleActiveJob?.stage_detail || ""),
      chat_thread: [
        ...liveThread,
        createChatMessage("user", message),
      ].map(({ role, content, kind }) => ({ role, content, kind })),
    };
  };

  const buildPayloadFromOverrides = (
    overrides: ControlOverrides = {},
    promptOverride?: string,
    projectIdOverride?: string | null,
  ): PlanRequestPayload => {
    const nextStrategy = overrides.strategyMode ?? strategyMode;
    const nextSiteName = overrides.siteName ?? siteName;
    const nextFileName = overrides.fileName ?? fileName;
    const nextUnits = overrides.units ?? units;
    const nextProjectType = overrides.projectType ?? projectType;
    const nextRoads = overrides.roads ?? roads;
    const nextGrading = overrides.grading ?? grading;
    const nextDrainage = overrides.drainage ?? drainage;
    const nextUtilities = overrides.utilities ?? utilities;
    const nextBuildingCount = overrides.buildingCount ?? buildingCount;
    const nextMinSlopePct = overrides.minSlopePct ?? minSlopePct;
    const nextPipeMinSlopePct = overrides.pipeMinSlopePct ?? pipeMinSlopePct;
    const nextMaxParkingSlopePct = overrides.maxParkingSlopePct ?? maxParkingSlopePct;
    const nextMaxRoadGradePct = overrides.maxRoadGradePct ?? maxRoadGradePct;
    const nextMaxAdaCrossSlopePct = overrides.maxAdaCrossSlopePct ?? maxAdaCrossSlopePct;

    return {
      project_id:
        projectIdOverride !== undefined ? projectIdOverride : projectId || null,
      full_design_mode: true,
      input_mode: nextStrategy,
      strict_mode: nextStrategy === "manual",
      prompt_text: (promptOverride ?? prompt) || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
        site_inputs: currentProject?.project_input?.meta?.site_inputs ?? {},
      },
      manual_fields: buildManualFields({
        strategy: nextStrategy,
        nextSiteName,
        nextFileName,
        nextUnits,
        nextProjectType,
        nextLotWidth: overrides.lotWidth ?? lotWidth,
        nextLotHeight: overrides.lotHeight ?? lotHeight,
        nextSetback: overrides.setback ?? setback,
        nextBuildingWidth: overrides.buildingWidth ?? buildingWidth,
        nextBuildingDepth: overrides.buildingDepth ?? buildingDepth,
        nextBuildingCount,
        nextParkingCount: overrides.parkingCount ?? parkingCount,
        nextMinSlopePct,
        nextPipeMinSlopePct,
        nextMaxParkingSlopePct,
        nextMaxRoadGradePct,
        nextMaxAdaCrossSlopePct,
        nextRoads,
        nextGrading,
        nextDrainage,
        nextUtilities,
      }),
      allow_ai_fill_for_blanks: nextStrategy !== "manual",
    };
  };

  const isConnectivityFailureMessage = (message: string) =>
    message.includes("could not reach the backend") ||
    message.includes("Failed to fetch") ||
    message.includes("Load failed") ||
    message.includes("NetworkError");

  const executePlanAction = async ({
    mode,
    requestPayload,
    resolvedProjectId,
    assistantPrefix,
    clearPromptOnSuccess = false,
    signal,
  }: {
    mode: PlanToolMode;
    requestPayload: PlanRequestPayload;
    resolvedProjectId?: string | null;
    assistantPrefix?: string | null;
    clearPromptOnSuccess?: boolean;
    signal?: AbortSignal;
  }) => {
    setBusy(true);
    setActivePlanTool(mode);
    setStatusMessage(
      mode === "fix"
        ? "Civora AI is starting the fix run."
        : mode === "improve"
          ? "Civora AI is starting the improvement run."
          : "Civora AI is starting the engineering run.",
    );
    const shouldQueueStagedRun = Boolean(requestPayload?.full_design_mode && token);
    if (shouldQueueStagedRun) {
      try {
        const queued = await postJson<{ job: JobSummary }>(
          "/api/jobs/orchestrate",
          {
            project_id:
              resolvedProjectId !== undefined
                ? resolvedProjectId
                : ((requestPayload?.project_id ?? projectId) || null),
            request: requestPayload,
          },
          { token },
        );
        setActiveJobId(queued.job.job_id);
        appendChatMessage(
          "assistant",
          [
            assistantPrefix,
            `I queued the full staged design workflow as ${queued.job.job_id} so each phase can save, pause for approval, and continue on the same project.`,
          ]
            .filter(Boolean)
            .join(" "),
          "status",
        );
        setStatusMessage(`Queued staged run ${queued.job.job_id}.`);
        if (clearPromptOnSuccess) {
          setPrompt("");
        }
        return;
      } catch (queueError) {
        const queueMessage =
          queueError instanceof Error ? queueError.message : "Job queue failed.";
        appendChatMessage("assistant", queueMessage, "status");
        setStatusMessage(queueMessage);
        return;
      } finally {
        setBusy(false);
      }
    }
    const liveRunController = new AbortController();
    const liveRunTimeoutMs = 12_000;
    let timedOut = false;
    const handleAbort = () => liveRunController.abort();
    signal?.addEventListener("abort", handleAbort, { once: true });
    const timeoutId = window.setTimeout(() => {
      timedOut = true;
      liveRunController.abort();
    }, liveRunTimeoutMs);
    try {
      const data = await postJson<PlanResponse>("/api/orchestrate", requestPayload, {
        token,
        signal: liveRunController.signal,
      });
      applyBackendResult(data);
      appendChatMessage(
        "assistant",
        [assistantPrefix, summarizePlanResponse(data, mode)].filter(Boolean).join(" "),
      );
      await requestPreview(
        {
          project_id: projectId || currentProject?.project_id || null,
          result: data,
          filename_stem: fileName || siteName || "civora-ai-plan",
        },
        { silent: true },
      );
      setStatusMessage(
        mode === "fix"
          ? "Civora AI ran a focused fix pass."
          : mode === "improve"
            ? "Civora AI generated an improved plan."
            : "Plan run completed.",
      );
      if (clearPromptOnSuccess) {
        setPrompt("");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (timedOut && token) {
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id:
                resolvedProjectId !== undefined
                  ? resolvedProjectId
                  : ((requestPayload?.project_id ?? projectId) || null),
              request: requestPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            [
              assistantPrefix,
              "The live run took too long to stay on the direct connection, so I queued it in the background instead.",
              `Job ${queued.job.job_id} is now running and I’ll pick it up when it finishes.`,
            ]
              .filter(Boolean)
              .join(" "),
            "status",
          );
          setStatusMessage(
            `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
          );
          return;
        } catch (queueError) {
          const queueMessage =
            queueError instanceof Error ? queueError.message : "Job queue failed.";
          appendChatMessage("assistant", queueMessage, "status");
          setStatusMessage(queueMessage);
          return;
        }
      }
      if (error instanceof Error && error.name === "AbortError") {
        appendChatMessage(
          "assistant",
          "I stopped the live request before it finished.",
          "status",
        );
        setStatusMessage("Cancelled the live request.");
        return;
      }
      const looksLikeConnectivityFailure = isConnectivityFailureMessage(errorMessage);
      if (looksLikeConnectivityFailure && token) {
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id:
                resolvedProjectId !== undefined
                  ? resolvedProjectId
                  : ((requestPayload?.project_id ?? projectId) || null),
              request: requestPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            [
              assistantPrefix,
              "The live run took too long to stay on the direct connection, so I queued it in the background instead.",
              `Job ${queued.job.job_id} is now running and I’ll pick it up when it finishes.`,
            ]
              .filter(Boolean)
              .join(" "),
            "status",
          );
          setStatusMessage(
            `The live run was queued as ${queued.job.job_id} because the direct request took too long.`,
          );
          return;
        } catch (queueError) {
          const queueMessage =
            queueError instanceof Error ? queueError.message : "Job queue failed.";
          appendChatMessage(
            "assistant",
            queueMessage,
            "status",
          );
          setStatusMessage(queueMessage);
          return;
        }
      }
      appendChatMessage(
        "assistant",
        error instanceof Error
          ? error.message
          : mode === "fix"
            ? "I couldn’t complete the fix pass."
            : mode === "improve"
              ? "I couldn’t complete the improvement pass."
              : "I couldn’t update the design.",
        "status",
      );
      setStatusMessage(
        error instanceof Error
          ? error.message
          : mode === "fix"
            ? "Fix pass failed."
            : mode === "improve"
              ? "Improve pass failed."
              : "Planner run failed.",
      );
    } finally {
      window.clearTimeout(timeoutId);
      signal?.removeEventListener("abort", handleAbort);
      setBusy(false);
      setActivePlanTool("run");
      directRunAbortRef.current = null;
    }
  };

  const loadMe = async (authToken: string) => {
    const data = await getJson<{ user: UserRecord }>("/api/auth/me", {
      token: authToken,
    });
    setUser(data.user);
  };

  const loadAuthStatus = async () => {
    try {
      const data = await getJson<AuthStatus>("/api/auth/status");
      setAuthStatus(data);
      setAuthStatusError("");
      if ((data.user_count ?? 0) > 0) {
        setAuthMode("login");
      }
    } catch (error) {
      setAuthStatus(null);
      setAuthStatusError(
        error instanceof Error
          ? error.message
          : "Civora AI could not load backend status.",
      );
    }
  };

  const refreshProjects = async (authToken = token) => {
    if (!authToken) return;
    const data = await getJson<{ projects: ProjectSummary[] }>("/api/projects", {
      token: authToken,
    });
    const nextProjects = Array.isArray(data.projects) ? data.projects : [];
    nextProjects.sort((a, b) => {
      const aSaved = a.has_result ? 1 : 0;
      const bSaved = b.has_result ? 1 : 0;
      if (aSaved !== bSaved) return bSaved - aSaved;
      return (b.updated_at ?? 0) - (a.updated_at ?? 0);
    });
    setProjects(nextProjects);
  };

  const upsertProjectSummary = (project: ProjectRecord | ProjectSummary) => {
    const summary: ProjectSummary = {
      project_id: project.project_id,
      name: project.name || "Untitled Project",
      description: project.description ?? "",
      has_result:
        typeof project.has_result === "boolean"
          ? project.has_result
          : Boolean((project as ProjectRecord).latest_result),
      updated_at: project.updated_at,
    };
    setProjects((current) => {
      const existingIndex = current.findIndex(
        (item) => item.project_id === summary.project_id,
      );
      if (existingIndex < 0) {
        return [summary, ...current];
      }
      const next = [...current];
      next[existingIndex] = { ...next[existingIndex], ...summary };
      next.sort((a, b) => (b.updated_at ?? 0) - (a.updated_at ?? 0));
      return next;
    });
  };

  const removeProjectSummary = (projectIdToRemove: string) => {
    setProjects((current) =>
      current.filter((item) => item.project_id !== projectIdToRemove),
    );
  };

  const hasTrackedJobs = useMemo(
    () =>
      Boolean(activeJobId) ||
      jobs.some((job) =>
        ["queued", "running", "awaiting_approval", "cancelling"].includes(
          String(job.status || "").toLowerCase(),
        ),
      ),
    [activeJobId, jobs],
  );

  const refreshJobs = async (
    authToken = token,
    {
      suppressError = false,
      force = false,
    }: { suppressError?: boolean; force?: boolean } = {},
  ) => {
    if (!authToken) return;
    if (!force && !hasTrackedJobs) return;
    try {
      const data = await getJson<{ jobs: JobSummary[] }>("/api/jobs", {
        token: authToken,
      });
      setJobs(Array.isArray(data.jobs) ? data.jobs : []);
    } catch (error) {
      if (!suppressError) {
        throw error;
      }
    }
  };

  const handleRefreshWorkspace = async () => {
    if (!token) return;
    const results = await Promise.allSettled([
      refreshProjects(),
      refreshJobs(token, { suppressError: true, force: true }),
    ]);
    const projectsFailed = results[0].status === "rejected";
    const jobsFailed = results[1].status === "rejected";
    if (!projectsFailed && !jobsFailed) {
      setStatusMessage("Workspace refreshed.");
      return;
    }
    if (!projectsFailed && jobsFailed) {
      setStatusMessage("Projects refreshed. Jobs could not be refreshed right now.");
      return;
    }
    if (projectsFailed && !jobsFailed) {
      const reason = results[0].status === "rejected" ? results[0].reason : null;
      setStatusMessage(
        reason instanceof Error ? reason.message : "Project refresh failed.",
      );
      return;
    }
    setStatusMessage("Workspace refresh failed.");
  };

  const handleAuth = async () => {
    setAuthLoading(true);
    setAuthError("");
    try {
      const path =
        authMode === "register" ? "/api/auth/register" : "/api/auth/login";
      const body =
        authMode === "register"
          ? {
              name: authName,
              email: authEmail,
              password: authPassword,
            }
          : {
              email: authEmail,
              password: authPassword,
            };
      const data = await postJson<{ token: string; user: UserRecord }>(
        path,
        body,
      );
      setToken(data.token);
      setStoredToken(data.token);
      setUser(data.user);
      await refreshProjects(data.token);
      await refreshJobs(data.token, { suppressError: true });
      setStatusMessage(`Signed in to Civora AI as ${data.user.name}.`);
    } catch (error) {
      setAuthError(
        error instanceof Error ? error.message : "Authentication failed.",
      );
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      if (token) {
        await postJson("/api/auth/logout", {}, { token });
      }
    } catch {
      // Ignore logout API errors and clear local state anyway.
    }
    clearStoredToken();
    setToken("");
    setUser(null);
    setProjects([]);
    setJobs([]);
    setCurrentProject(null);
    setProjectId("");
    setStatusMessage("Signed out.");
  };

  const runOrchestrator = async (mode: PlanToolMode = "run") => {
    if (!token) return;
    if (
      runSubmissionRef.current ||
      Boolean(
        currentProjectActiveJob &&
          ["queued", "running", "awaiting_approval", "cancelling"].includes(
            String(currentProjectActiveJob.status || "").toLowerCase(),
          ),
      )
    ) {
      setStatusMessage("Civora AI is already working on your last request.");
      return;
    }
    const trimmedPrompt = prompt.trim();
    if (mode === "run" && !trimmedPrompt && !imageName) {
      setStatusMessage("Add a request or image so Civora AI has something to work from.");
      return;
    }
    if (mode !== "run") {
      if (mode === "fix") {
        appendChatMessage(
          "system",
          "Fix the active design and focus on the most important engineering blockers.",
          "action",
        );
      } else if (mode === "improve") {
        appendChatMessage(
          "system",
          "Improve the active design while preserving the current project intent.",
          "action",
        );
      }
      const basePayload = buildPayloadFromOverrides({}, undefined, projectId || null);
      await executePlanAction({
        mode,
        requestPayload: {
          ...basePayload,
          full_design_mode: true,
          optimize_goal:
            mode === "fix"
              ? suggestedImproveGoal ?? "reduce_pipe_length"
              : suggestedImproveGoal,
          meta: {
            ...(basePayload.meta ?? {}),
            requested_plan_tool: mode,
          },
        },
        resolvedProjectId: projectId || null,
      });
      return;
    }

    const runController = new AbortController();
    directRunAbortRef.current = runController;
    runSubmissionRef.current = true;
    setBusy(true);
    setActivePlanTool("run");
    setPrompt("");
    appendChatMessage("user", trimmedPrompt);
    setStatusMessage("Civora AI is reviewing your request and starting the design run.");
    try {
      const resolvedProjectId =
        ((await ensureProjectDraft()) ?? projectId) || null;
      const decision = await postJson<ChatDecisionResponse>(
        "/api/chat/decide",
        {
          message: trimmedPrompt,
          context: buildChatDecisionContext({}, trimmedPrompt),
        },
        { token, signal: runController.signal },
      );
      const overrides = decision.control_overrides ?? {};
      applyControlOverrides(overrides);
      const nextStrategy = overrides.strategyMode ?? strategyMode;
      const shouldAutoName = false;
      const shouldAutoFileName = false;
      const generatedTitle = siteName.trim();
      const generatedFileName = fileName.trim();

      if (
        decision.needs_clarification ||
        decision.intent === "conversation" ||
        decision.intent === "settings" ||
        decision.intent === "explain"
      ) {
        appendChatMessage(
          "assistant",
          decision.intent === "explain" && !decision.assistant_message
            ? "I can explain the current design once there’s a plan in the workspace."
            : decision.assistant_message,
          decision.intent === "explain" ? "explanation" : "message",
        );
        setStatusMessage(
          decision.needs_clarification
            ? "Civora AI is asking for a little more detail before running a design."
            : "Civora AI responded in chat without rerunning the planner.",
        );
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        setBusy(false);
        setActivePlanTool("run");
        return;
      }

      const resolvedMode: PlanToolMode =
        decision.run_mode === "fix"
          ? "fix"
          : decision.run_mode === "improve"
            ? "improve"
            : "run";

      if (resolvedMode !== "run") {
        const basePayload = buildPayloadFromOverrides(overrides, undefined, resolvedProjectId);
        await executePlanAction({
          mode: resolvedMode,
          requestPayload: {
            ...basePayload,
            full_design_mode: true,
            optimize_goal:
              resolvedMode === "fix"
                ? suggestedImproveGoal ?? "reduce_pipe_length"
                : suggestedImproveGoal,
            meta: {
              ...(basePayload.meta ?? {}),
              requested_plan_tool: resolvedMode,
              chat_decision_reason: decision.reason,
            },
          },
          resolvedProjectId,
          assistantPrefix: decision.assistant_message,
          clearPromptOnSuccess: true,
          signal: runController.signal,
        });
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        return;
      }

      if (!decision.design_prompt && !imageName) {
        appendChatMessage(
          "assistant",
          decision.assistant_message || "Tell me what you want me to design or change.",
        );
        setStatusMessage(
          nextStrategy === "manual"
            ? "Civora AI needs a more explicit design request before running in Manual mode."
            : "Civora AI needs a little more direction before generating a design.",
        );
        await saveProject({
          silent: true,
          projectIdOverride: resolvedProjectId,
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        setBusy(false);
        setActivePlanTool("run");
        return;
      }

      const basePayload = buildPayloadFromOverrides(
        overrides,
        decision.design_prompt || trimmedPrompt,
        resolvedProjectId,
      );
      await executePlanAction({
        mode: "run",
        requestPayload: {
          ...basePayload,
          meta: {
            ...(basePayload.meta ?? {}),
            chat_decision_reason: decision.reason,
            chat_decision_confidence: decision.confidence,
          },
        },
        resolvedProjectId,
        assistantPrefix: decision.assistant_message,
        clearPromptOnSuccess: true,
        signal: runController.signal,
      });
      await saveProject({
        silent: true,
        projectIdOverride: resolvedProjectId,
        nameOverride: generatedTitle || undefined,
        fileNameOverride: generatedFileName || undefined,
        autoNamedOverride: shouldAutoName,
        autoFileNamedOverride: shouldAutoFileName,
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (error instanceof Error && error.name === "AbortError") {
        appendChatMessage(
          "assistant",
          "I stopped the live request before it finished.",
          "status",
        );
        setStatusMessage("Cancelled the live request.");
        setBusy(false);
        setActivePlanTool("run");
        directRunAbortRef.current = null;
        return;
      }
      if (token && isConnectivityFailureMessage(errorMessage)) {
        try {
          const resolvedProjectId =
            projectId || (await ensureProjectDraft()) || null;
          const fallbackPayload = buildPayloadFromOverrides(
            {},
            trimmedPrompt,
            resolvedProjectId,
          );
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id: resolvedProjectId,
              request: fallbackPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            `The live request could not stay connected long enough to finish the first pass, so I queued it in the background instead. Job ${queued.job.job_id} is queued and I’ll pick it up when it starts reporting progress.`,
            "status",
          );
          setStatusMessage(
            `The live request was queued as ${queued.job.job_id} because the direct connection dropped.`,
          );
          return;
        } catch (queueError) {
          appendChatMessage(
            "assistant",
            queueError instanceof Error ? queueError.message : "I couldn’t queue the design request either.",
            "status",
          );
          setStatusMessage(
            queueError instanceof Error ? queueError.message : "Queued fallback failed.",
          );
          return;
        }
      }
      appendChatMessage(
        "assistant",
        error instanceof Error ? error.message : "I couldn’t process that message.",
        "status",
      );
      setStatusMessage(
        error instanceof Error ? error.message : "Civora AI could not process that message.",
      );
      setBusy(false);
      setActivePlanTool("run");
    } finally {
      runSubmissionRef.current = false;
      directRunAbortRef.current = null;
    }
  };

  const handleSendMessage = () => {
    const trimmed = prompt.trim();
    if (!trimmed && !imageName) return;
    if (busy || visibleActiveJob) {
      appendChatMessage("user", trimmed || "Uploaded an image.");
      appendChatMessage(
        "assistant",
        "Got it. I saved that note and will apply it after the current phase finishes or once you approve the next phase.",
        "status",
      );
      setPrompt("");
      return;
    }
    void runOrchestrator("run");
  };

  const handleCancelActiveJob = async () => {
    if (visibleActiveJob?.job_id && token) {
      try {
        const data = await postJson<{ job: JobSummary }>(
          `/api/jobs/${visibleActiveJob.job_id}/cancel`,
          {},
          { token },
        );
        setJobs((current) => {
          const next = [...current];
          const index = next.findIndex((job) => job.job_id === data.job.job_id);
          if (index >= 0) {
            next[index] = { ...next[index], ...data.job };
          } else {
            next.unshift(data.job);
          }
          return next;
        });
        appendChatMessage("assistant", `Job ${data.job.job_id} was cancelled.`, "status");
        setStatusMessage(`Cancelled job ${data.job.job_id}.`);
        if (activeJobId === data.job.job_id) {
          setActiveJobId("");
        }
        setBusy(false);
        runSubmissionRef.current = false;
      } catch (error) {
        setStatusMessage(
          error instanceof Error ? error.message : "Job cancel failed.",
        );
      }
      return;
    }
    if (directRunAbortRef.current) {
      directRunAbortRef.current.abort();
      directRunAbortRef.current = null;
      runSubmissionRef.current = false;
      setBusy(false);
      setActivePlanTool("run");
      setStatusMessage("Cancelling the live request...");
      return;
    }
  };

  const handleContinueActiveJob = async () => {
    if (!visibleActiveJob?.job_id || !token) return;
    try {
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${visibleActiveJob.job_id}/continue`,
        {},
        { token },
      );
      setJobs((current) => {
        const next = [...current];
        const index = next.findIndex((job) => job.job_id === data.job.job_id);
        if (index >= 0) {
          next[index] = { ...next[index], ...data.job };
        } else {
          next.unshift(data.job);
        }
        return next;
      });
      appendChatMessage(
        "assistant",
        `Approved job ${data.job.job_id}. Civora queued the next phase.`,
        "status",
      );
      setStatusMessage(`Approved ${data.job.job_id}. Continuing with the next phase.`);
      if (data.job.job_id) {
        setActiveJobId(data.job.job_id);
      }
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Could not continue the staged run.",
      );
    }
  };

  useEffect(() => {
    const jobId = visibleActiveJob?.job_id;
    if (!jobId) return;
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") {
      autoAdvanceByJobRef.current[jobId] = false;
    }
  }, [visibleActiveJob?.job_id, visibleActiveJob?.status]);

  useEffect(() => {
    if (!autoAdvancePhases) return;
    const jobId = visibleActiveJob?.job_id;
    if (!jobId) return;
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") return;
    if (autoAdvanceByJobRef.current[jobId]) return;
    autoAdvanceByJobRef.current[jobId] = true;
    const timeoutId = window.setTimeout(() => {
      handleContinueActiveJob();
    }, 1200);
    return () => window.clearTimeout(timeoutId);
  }, [autoAdvancePhases, visibleActiveJob?.job_id, visibleActiveJob?.status]);

  const handleReviseActiveJob = async () => {
    if (!visibleActiveJob?.job_id || !token) return;
    try {
      const targetProjectId =
        projectId || visibleActiveJob.project_id || currentProject?.project_id || null;
      if (targetProjectId) {
        await saveProject({
          silent: true,
          projectIdOverride: targetProjectId,
        });
      }
      const data = await postJson<{ job: JobSummary }>(
        `/api/jobs/${visibleActiveJob.job_id}/revise`,
        { target_phase: revisePhaseTarget },
        { token },
      );
      setJobs((current) => {
        const next = [...current];
        const index = next.findIndex((job) => job.job_id === data.job.job_id);
        if (index >= 0) {
          next[index] = { ...next[index], ...data.job };
        } else {
          next.unshift(data.job);
        }
        return next;
      });
      appendChatMessage(
        "assistant",
        `Saved your changes and requeued ${data.job.job_id} to revise ${toReadableLabel(revisePhaseTarget)}.`,
        "status",
      );
      setStatusMessage(
        `Saved your changes. Requeued ${data.job.job_id} to revise ${toReadableLabel(revisePhaseTarget)}.`,
      );
      if (data.job.job_id) {
        setActiveJobId(data.job.job_id);
      }
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Could not revise the current phase.",
      );
    }
  };

  const saveProject = async ({
    silent = false,
    projectIdOverride,
    nameOverride,
    fileNameOverride,
    projectInputOverride,
    latestResultOverride,
    autoNamedOverride,
    autoFileNamedOverride,
  }: {
    silent?: boolean;
    projectIdOverride?: string | null;
    nameOverride?: string;
    fileNameOverride?: string;
    projectInputOverride?: ProjectInput;
    latestResultOverride?: PlanResponse;
    autoNamedOverride?: boolean;
    autoFileNamedOverride?: boolean;
  } = {}): Promise<ProjectRecord | null> => {
    if (!token) return null;
    if (!silent) setBusy(true);
    const effectiveProjectId =
      projectIdOverride !== undefined
        ? projectIdOverride
        : resolvedProjectIdRef.current || projectId || currentProject?.project_id || null;
    const resolvedName = (nameOverride ?? siteName).trim();
    const resolvedFileName = (fileNameOverride ?? fileName).trim();
    const liveChatThread = chatMessagesRef.current;
    const projectInputToSave = projectInputOverride
      ? {
          ...projectInputOverride,
          manual_fields: {
            ...(projectInputOverride.manual_fields ?? {}),
            project_name: resolvedName,
            file_name: resolvedFileName,
          },
          meta: {
            ...(projectInputOverride.meta ?? {}),
            chat_thread: liveChatThread,
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
          },
        }
      : {
          ...payloadPreview,
          manual_fields: {
            ...(payloadPreview.manual_fields ?? {}),
            project_name: resolvedName,
            file_name: resolvedFileName,
          },
          meta: {
            ...(payloadPreview.meta ?? {}),
            chat_thread: liveChatThread,
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
          },
        };
    const latestResultToSave =
      latestResultOverride !== undefined ? latestResultOverride : undefined;
    try {
      const requestBody: Record<string, unknown> = {
        project_id: effectiveProjectId,
        name: resolvedName,
        project_input: projectInputToSave,
        metadata: {
          auto_named: autoNamedOverride ?? siteNameAuto,
          auto_file_named: autoFileNamedOverride ?? fileNameAuto,
        },
      };
      if (latestResultToSave !== undefined) {
        requestBody.latest_result = latestResultToSave;
      }
      const data = await postJson<{ project: ProjectRecord }>(
        "/api/projects",
        requestBody,
        { token },
      );
      resolvedProjectIdRef.current = data.project.project_id;
      setProjectId(data.project.project_id);
      setCurrentProject(data.project);
      upsertProjectSummary(data.project);
      if (!silent) {
        setStatusMessage(
          `Saved project "${data.project.name || resolvedName || "Untitled Project"}".`,
        );
      }
      return data.project;
    } catch (error) {
      if (!silent) {
        setStatusMessage(
          error instanceof Error ? error.message : "Project save failed.",
        );
      }
      return null;
    } finally {
      if (!silent) setBusy(false);
    }
  };

  useEffect(() => {
    const activeProjectId =
      resolvedProjectIdRef.current || projectId || currentProject?.project_id || "";
    if (!token || !activeProjectId || !currentProject) return;
    if (autosaveSuspendRef.current) return;
    const savedThread = Array.isArray(currentProject?.project_input?.meta?.chat_thread)
      ? currentProject.project_input.meta.chat_thread
      : [];
    const currentThread = chatMessagesRef.current.map(
      ({ role, content, kind, createdAt, id }) => ({
        role,
        content,
        kind,
        createdAt,
        id,
      }),
    );
    const savedPrompt = String(currentProject?.project_input?.prompt_text ?? "");
    const currentPrompt = String(prompt ?? "");
    const threadChanged =
      JSON.stringify(savedThread) !== JSON.stringify(currentThread);
    const promptChanged = savedPrompt !== currentPrompt;
    if (!threadChanged && !promptChanged) {
      return;
    }
    if (chatAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(chatAutosaveTimeoutRef.current);
    }
    chatAutosaveTimeoutRef.current = window.setTimeout(() => {
      void saveProject({ silent: true, projectIdOverride: activeProjectId });
    }, 700);
  }, [chatMessages, prompt, token, projectId, currentProject]);

  useEffect(() => {
    if (!token || !currentProject?.project_id) return;
    if (autosaveSuspendRef.current) return;
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
    }
    controlAutosaveTimeoutRef.current = window.setTimeout(() => {
      void saveProject({ silent: true });
    }, 700);
  }, [
    token,
    currentProject?.project_id,
    siteName,
    fileName,
    units,
    projectType,
    lotWidth,
    lotHeight,
    buildingWidth,
    buildingDepth,
    buildingCount,
    setback,
    parkingCount,
    minSlopePct,
    pipeMinSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    maxAdaCrossSlopePct,
    roads,
    grading,
    drainage,
    utilities,
  ]);

  useEffect(() => {
    if (!currentProject?.project_id) return;
    if (lastSiteInputProjectRef.current === currentProject.project_id) return;
    lastSiteInputProjectRef.current = currentProject.project_id;
    const siteInputs =
      currentProject?.project_input?.meta?.site_inputs &&
      typeof currentProject.project_input.meta.site_inputs === "object"
        ? currentProject.project_input.meta.site_inputs
        : {};
    const mapSnapshot = siteInputs?.map_snapshot ?? {};
    const mapAnalysisResult = siteInputs?.map_analysis ?? null;
    const surveyFile = siteInputs?.survey_file ?? {};
    const slopeEstimate = siteInputs?.slope_estimate ?? null;
    setSurveyFileName(String(surveyFile?.stored_filename || ""));
    setSurveySlopeEstimate(slopeEstimate || null);
    const mapUrl = String(mapSnapshot?.image_url || "");
    if (mapUrl) {
      setUploadedImageApiUrl(uploadedImageSrc(mapUrl, token));
    }
    setMapSnapshotPath(String(mapSnapshot?.image_path || ""));
    setMapAnalysis(mapAnalysisResult || null);
  }, [currentProject, token]);

  const loadProject = async (id: string) => {
    if (!token) return;
    autosaveSuspendRef.current = true;
    if (chatAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(chatAutosaveTimeoutRef.current);
      chatAutosaveTimeoutRef.current = null;
    }
    if (controlAutosaveTimeoutRef.current !== null) {
      window.clearTimeout(controlAutosaveTimeoutRef.current);
      controlAutosaveTimeoutRef.current = null;
    }
    const requestId = projectLoadRequestRef.current + 1;
    projectLoadRequestRef.current = requestId;
    try {
      setStatusMessage("Loading project...");
      const data = await getJson<{ project: ProjectRecord }>(
        `/api/projects/${id}`,
        { token },
      );
      if (projectLoadRequestRef.current !== requestId) {
        return;
      }
      const project = data.project;
      resolvedProjectIdRef.current = project.project_id;
      setCurrentProject(project);
      setProjectId(project.project_id);
      setSiteName(project.name ?? "");
      applyProjectInput(project.project_input ?? {});
      setBackendResult(null);
      setPlanPreviewUrl("");
      setPlanPreviewSummary(null);
      setStatusMessage(`Loaded project "${project.name}".`);
      loadProjectResultInBackground(project);
      if (activeJobId && (!projectId || currentProjectActiveJob?.project_id === id || activeJob?.project_id === id)) {
        void loadJob(activeJobId);
      }
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Project load failed.",
      );
    } finally {
      autosaveSuspendRef.current = false;
    }
  };

  const ensureProjectDraft = async (): Promise<string | null> => {
    if (!token) return null;
    if (resolvedProjectIdRef.current) return resolvedProjectIdRef.current;
    if (projectId) return projectId;
    if (currentProject?.project_id) return currentProject.project_id;
    if (draftProjectPromiseRef.current) {
      const inFlightProject = await draftProjectPromiseRef.current;
      return inFlightProject?.project_id ?? null;
    }
    draftProjectPromiseRef.current = saveProject({
      silent: true,
      projectIdOverride: null,
      nameOverride: siteName.trim(),
      fileNameOverride: fileName.trim(),
      autoNamedOverride: false,
      autoFileNamedOverride: false,
    });
    try {
      const savedProject = await draftProjectPromiseRef.current;
      return savedProject?.project_id ?? null;
    } finally {
      draftProjectPromiseRef.current = null;
    }
  };

  const deleteProject = async (id: string) => {
    if (!token) return;
    try {
      await deleteJson(`/api/projects/${id}`, { token });
      removeProjectSummary(id);
      if (projectId === id) {
        setProjectId("");
        setCurrentProject(null);
      }
      setStatusMessage("Project deleted.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Project delete failed.",
      );
    }
  };

  const loadJob = async (id: string) => {
    if (!token) return;
    try {
      const data = await getJson<{ job: JobSummary }>(`/api/jobs/${id}`, { token });
      const job = data.job;
      const jobProjectId = String(job.project_id || "").trim();
      const activeJobProjectSignature = `${job.job_id}:${jobProjectId}`;
      const activeTrackedProjectId =
        jobProjectId ||
        resolvedProjectIdRef.current ||
        projectId ||
        currentProject?.project_id ||
        "";
      if (jobProjectId) {
        resolvedProjectIdRef.current = jobProjectId;
        upsertProjectSummary({
          project_id: jobProjectId,
          name: currentProject?.project_id === jobProjectId
            ? currentProject.name || siteName || "Untitled Project"
            : siteName || "Untitled Project",
          description:
            currentProject?.project_id === jobProjectId
              ? currentProject.description ?? ""
              : "",
          has_result:
            Boolean(job.result && Object.keys(job.result).length) ||
            ["awaiting_approval", "completed"].includes(
              String(job.status || "").toLowerCase(),
            ),
          updated_at:
            typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
              ? job.updated_at
              : Date.now() / 1000,
        });
        if (projectId !== jobProjectId) {
          setProjectId(jobProjectId);
        }
        if (!currentProject || currentProject.project_id !== jobProjectId) {
          setCurrentProject((existing) => {
            if (existing?.project_id === jobProjectId) {
              return existing;
            }
            return {
              project_id: jobProjectId,
              name: existing?.name || siteName || "Untitled Project",
              description: existing?.description ?? "",
              has_result: true,
            } as ProjectRecord;
          });
        }
        const shouldSyncActiveJobProject =
          (currentProject?.project_id !== jobProjectId ||
            projectId !== jobProjectId) &&
          activeJobProjectSyncRef.current !== activeJobProjectSignature;
        if (shouldSyncActiveJobProject) {
          activeJobProjectSyncRef.current = activeJobProjectSignature;
          const requestId = projectLoadRequestRef.current + 1;
          projectLoadRequestRef.current = requestId;
          autosaveSuspendRef.current = true;
          void getJson<{ project: ProjectRecord }>(`/api/projects/${jobProjectId}`, {
            token,
          })
            .then((projectData) => {
              if (projectLoadRequestRef.current !== requestId) {
                autosaveSuspendRef.current = false;
                return;
              }
              const syncedProject = projectData.project;
              resolvedProjectIdRef.current = syncedProject.project_id;
              setCurrentProject(syncedProject);
              setProjectId(syncedProject.project_id);
              setSiteName(syncedProject.name ?? "");
              applyProjectInput(syncedProject.project_input ?? {});
              upsertProjectSummary(syncedProject);
              loadProjectResultInBackground(syncedProject);
              autosaveSuspendRef.current = false;
            })
            .catch((error) => {
              setStatusMessage(
                error instanceof Error
                  ? error.message
                  : "Project sync from active job failed.",
              );
              autosaveSuspendRef.current = false;
            });
        }
      }
      setJobs((current) => {
        const next = [...current];
        const existingIndex = next.findIndex((item) => item.job_id === job.job_id);
        if (existingIndex >= 0) {
          next[existingIndex] = { ...next[existingIndex], ...job };
        } else {
          next.unshift(job);
        }
        return next;
      });
      setActiveJobId(job.job_id);
      const previousStatus = lastJobStatusRef.current[job.job_id];
      const normalizedStatus = String(job.status || "").toLowerCase();
      const stageLabel = String(job.stage || "").trim() || "Engineering Run";
      const stageDetail = String(job.stage_detail || "").trim();
      const phaseSignature = `${normalizedStatus}|${stageLabel}|${stageDetail}`;
      if (previousStatus !== job.status) {
        lastJobStatusRef.current[job.job_id] = job.status;
        if (job.status === "queued") {
          const queuePosition =
            typeof job.queue_position === "number" && Number.isFinite(job.queue_position)
              ? Math.max(1, Math.round(job.queue_position))
              : null;
          const queuedCount =
            typeof job.queued_count === "number" && Number.isFinite(job.queued_count)
              ? Math.max(0, Math.round(job.queued_count))
              : 0;
          const runningCount =
            typeof job.running_count === "number" && Number.isFinite(job.running_count)
              ? Math.max(0, Math.round(job.running_count))
              : 0;
          appendChatMessage(
            "assistant",
            queuePosition
              ? `Job ${job.job_id} is queued in the background. Position ${queuePosition}${queuedCount > 0 ? ` of ${queuedCount}` : ""}. ${runningCount > 0 ? `${runningCount} worker${runningCount === 1 ? "" : "s"} active.` : ""}`.trim()
              : `Job ${job.job_id} is queued and waiting to run in the background.`,
            "status",
          );
        } else if (job.status === "running") {
          appendChatMessage(
            "assistant",
            stageDetail
              ? `Job ${job.job_id} is working on ${stageLabel}. ${stageDetail}`
              : `Job ${job.job_id} is working on ${stageLabel}.`,
            "status",
          );
        } else if (job.status === "awaiting_approval") {
          appendChatMessage(
            "assistant",
            stageDetail
              ? `Job ${job.job_id} is waiting for your approval. ${stageDetail}`
              : `Job ${job.job_id} is waiting for your approval to continue to the next phase.`,
            "status",
          );
        } else if (job.status === "cancelling") {
          appendChatMessage(
            "assistant",
            `Job ${job.job_id} is cancelling now.`,
            "status",
          );
        }
        lastJobPhaseSignatureRef.current[job.job_id] = phaseSignature;
      } else if (
        ["running", "awaiting_approval", "queued"].includes(normalizedStatus) &&
        lastJobPhaseSignatureRef.current[job.job_id] !== phaseSignature
      ) {
        lastJobPhaseSignatureRef.current[job.job_id] = phaseSignature;
        if (normalizedStatus === "running") {
          appendChatMessage(
            "assistant",
            stageDetail
              ? `Job ${job.job_id} moved to ${stageLabel}. ${stageDetail}`
              : `Job ${job.job_id} moved to ${stageLabel}.`,
            "status",
          );
        } else if (normalizedStatus === "awaiting_approval") {
          appendChatMessage(
            "assistant",
            stageDetail
              ? `Job ${job.job_id} paused for approval after ${stageLabel}. ${stageDetail}`
              : `Job ${job.job_id} paused for approval after ${stageLabel}.`,
            "status",
          );
        }
      }
      if (
        activeTrackedProjectId &&
        ["queued", "running", "awaiting_approval"].includes(String(job.status || "").toLowerCase())
      ) {
        const refreshStamp =
          typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
            ? job.updated_at
            : Date.now() / 1000;
        const previousRefresh = lastProjectResultRefreshRef.current[job.job_id] ?? 0;
        if (refreshStamp > previousRefresh) {
          lastProjectResultRefreshRef.current[job.job_id] = refreshStamp;
          loadProjectResultInBackground({
            project_id: activeTrackedProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
          } as ProjectRecord);
        }
      }
      if (
        job.result &&
        Object.keys(job.result).length &&
        activeTrackedProjectId &&
        ["queued", "running", "awaiting_approval"].includes(String(job.status || "").toLowerCase())
      ) {
        const partialRefreshStamp =
          typeof job.updated_at === "number" && Number.isFinite(job.updated_at)
            ? job.updated_at
            : Date.now() / 1000;
        const previousPartialRefresh =
          lastJobPartialResultRefreshRef.current[job.job_id] ?? 0;
        if (partialRefreshStamp > previousPartialRefresh) {
          lastJobPartialResultRefreshRef.current[job.job_id] = partialRefreshStamp;
          applyBackendResult(job.result);
          requestPreviewInBackground(
            {
              project_id: activeTrackedProjectId || null,
              result: job.result,
              filename_stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
            },
            {
              silentStatus: true,
            },
          );
        }
      }
      if (job.status === "completed" && job.result) {
        applyBackendResult(job.result);
        requestPreviewInBackground(
          {
            project_id: activeTrackedProjectId || null,
            result: job.result,
            filename_stem: fileName || siteName,
          },
          {
            loadingMessage:
              projectId && job.project_id === projectId
                ? `Job ${job.job_id} completed. Refreshing preview...`
                : undefined,
            successMessage: `Job ${job.job_id} completed.`,
          },
        );
        appendChatMessage(
          "assistant",
          summarizePlanResponse(job.result, "run"),
          "message",
        );
        setActiveJobId("");
        if (jobProjectId) {
          upsertProjectSummary({
            project_id: jobProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
            description: currentProject?.description ?? "",
            has_result: true,
            updated_at: Date.now() / 1000,
          });
        }
        if (activeTrackedProjectId) {
          loadProjectResultInBackground({
            project_id: activeTrackedProjectId,
            name: currentProject?.name || siteName || "Untitled Project",
          } as ProjectRecord);
        }
      } else if (job.status === "failed") {
        appendChatMessage(
          "assistant",
          job.error ?? "The background job failed before Civora could finish the design.",
          "status",
        );
        setStatusMessage(job.error ?? "Job failed.");
        setActiveJobId("");
      } else if (job.status === "cancelled") {
        appendChatMessage(
          "assistant",
          `Job ${job.job_id} was cancelled before completion.`,
          "status",
        );
        setStatusMessage(`Job ${job.job_id} was cancelled.`);
        setActiveJobId("");
      } else {
        setStatusMessage(
          job.stage_detail
            ? `${job.stage || "Running"}: ${job.stage_detail}`
            : `Job ${job.job_id} is ${job.status}.`,
        );
      }
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Job load failed.");
    }
  };

  const uploadImage = async (file: File) => {
    if (!token) return;
    const localPreviewUrl = URL.createObjectURL(file);
    setUploadedImagePreviewUrl(localPreviewUrl);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadImageResponse>("/api/upload-image", formData, {
        token,
      });
      setImageName(data.image_path || file.name);
      setUploadedImageApiUrl(
        data.image_url ? uploadedImageSrc(data.image_url, token) : "",
      );
      setMapSnapshotPath(data.image_path || "");
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_snapshot: {
          filename: data.filename || file.name,
          stored_filename: data.image_path || file.name,
          image_path: data.image_path || "",
          image_url: data.image_url || "",
        },
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Image uploaded.");
    } catch (error) {
      setImageName(file.name);
      setStatusMessage(
        error instanceof Error ? error.message : "Image upload failed.",
      );
    }
  };

  const uploadSurvey = async (file: File) => {
    if (!token) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadSurveyResponse>("/api/upload-survey", formData, {
        token,
      });
      const storedFilename = data.stored_filename || file.name;
      setSurveyFileName(storedFilename);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        survey_file: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          survey_url: data.survey_url || "",
        },
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Survey uploaded.");
    } catch (error) {
      setSurveyFileName(file.name);
      setStatusMessage(
        error instanceof Error ? error.message : "Survey upload failed.",
      );
    }
  };

  const estimateSurveySlope = async () => {
    if (!token || !surveyFileName) return;
    try {
      const data = await postJson<SurveySlopeResponse>(
        "/api/survey/estimate-slope",
        { filename: surveyFileName },
        { token },
      );
      setSurveySlopeEstimate(data);
      if (data.slope_percent) {
        setMinSlopePct(String(data.slope_percent.toFixed(2)));
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        slope_estimate: data,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          manual_fields: {
            ...(currentInput?.manual_fields ?? {}),
            grading: {
              ...(currentInput?.manual_fields?.grading ?? {}),
              min_slope_pct: data.slope_percent ?? currentInput?.manual_fields?.grading?.min_slope_pct,
            },
            terrain: data.direction && data.slope_percent
              ? `Estimated ${data.slope_percent.toFixed(2)}% slope toward ${data.direction}`
              : currentInput?.manual_fields?.terrain,
          },
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Slope estimated from survey.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Slope estimation failed.",
      );
    }
  };

  const analyzeMapSnapshot = async () => {
    if (!token || !mapSnapshotPath) return;
    try {
      const data = await postJson<MapAnalysis>(
        "/api/image/analyze",
        {
          image_path: mapSnapshotPath,
          source_name: "map_snapshot",
          source_type: "map",
        },
        { token },
      );
      setMapAnalysis(data);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_analysis: data,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Map snapshot analyzed.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Map snapshot analysis failed.",
      );
    }
  };

  const requestPreview = async (
    payload: PreviewRequestPayload,
    options?: { silent?: boolean },
  ) => {
    if (!token) return;
    const previewPayload = {
      ...payload,
      preview_quality: previewQuality,
      render_labels: false,
      preview_layers: previewLayerList,
    };
    const data = await postJson<PreviewResponse>("/api/preview", previewPayload, {
      token,
    });
    setPlanPreviewUrl(data.preview_image_data_url);
    setPlanPreviewSummary(data.summary ?? null);
    setPlanPreviewAnnotations(data.preview_annotations ?? null);
    if (!options?.silent) {
      setStatusMessage("Plan preview generated.");
    }
  };

  const requestPreviewInBackground = (
    payload: PreviewRequestPayload,
    options?: { loadingMessage?: string; successMessage?: string; silentStatus?: boolean },
  ) => {
    if (!token) return;
    if (options?.loadingMessage && !options?.silentStatus) {
      setStatusMessage(options.loadingMessage);
    }
    void requestPreview(payload, { silent: true })
      .then(() => {
        if (options?.successMessage && !options?.silentStatus) {
          setStatusMessage(options.successMessage);
        }
      })
      .catch((error) => {
        if (!options?.silentStatus) {
          setStatusMessage(
            error instanceof Error ? error.message : "Preview generation failed.",
          );
        }
      });
  };

  useEffect(() => {
    if (!token || !backendResult) return;
    const finalPlan =
      backendResult?.final_plan && typeof backendResult.final_plan === "object"
        ? backendResult.final_plan
        : {};
    const finalMeta =
      finalPlan?.meta && typeof finalPlan.meta === "object" ? finalPlan.meta : {};
    const actions = Array.isArray(finalPlan?.actions)
      ? finalPlan.actions.filter((item: unknown) => item && typeof item === "object")
      : [];
    const phaseCheckpoints =
      finalMeta?.phase_checkpoints && typeof finalMeta.phase_checkpoints === "object"
        ? finalMeta.phase_checkpoints
        : {};
    const runtimeCheckpoint =
      finalMeta?.runtime_phase_checkpoint && typeof finalMeta.runtime_phase_checkpoint === "object"
        ? finalMeta.runtime_phase_checkpoint
        : {};
    const jobProgress =
      backendResult?.job_progress && typeof backendResult.job_progress === "object"
        ? backendResult.job_progress
        : {};
    const hasRecoverablePreviewState =
      actions.length > 0 ||
      Object.keys(phaseCheckpoints).length > 0 ||
      Object.keys(runtimeCheckpoint).length > 0 ||
      Boolean(jobProgress.stage);

    if (!hasRecoverablePreviewState) return;

    const recoveryKey = JSON.stringify({
      projectId,
      actionCount: actions.length,
      phaseKeys: Object.keys(phaseCheckpoints),
      checkpointStage: String(runtimeCheckpoint.stage_name || ""),
      jobStage: String(jobProgress.stage || ""),
      stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
    });

    if (previewRecoveryKeyRef.current === recoveryKey) return;
    previewRecoveryKeyRef.current = recoveryKey;

    requestPreviewInBackground(
      {
        project_id: projectId || currentProject?.project_id || null,
        result: backendResult,
        filename_stem: fileName || currentProject?.name || siteName || "civora-ai-plan",
      },
      {
        silentStatus: true,
      },
    );
  }, [token, backendResult, projectId, fileName, currentProject?.name, siteName]);

  const loadProjectResultInBackground = (project: ProjectRecord) => {
    if (!token) return;
    const requestId = projectResultLoadRequestRef.current + 1;
    projectResultLoadRequestRef.current = requestId;
    void getJson<{ project_id: string; latest_result: PlanResponse }>(
      `/api/projects/${project.project_id}/result`,
      { token },
    )
      .then((data) => {
        if (projectResultLoadRequestRef.current !== requestId) {
          return;
        }
        const latestResult = data.latest_result ?? {};
        if (latestResult && Object.keys(latestResult).length) {
          applyBackendResult(latestResult);
          requestPreviewInBackground(
            {
              project_id: project.project_id,
              result: latestResult,
              filename_stem: fileName || project.name || "civora-ai-plan",
            },
            {
              silentStatus: true,
            },
          );
        } else {
          const activeProjectForPreview =
            visibleActiveJob?.project_id ||
            resolvedProjectIdRef.current ||
            projectId ||
            currentProject?.project_id ||
            "";
          if (activeProjectForPreview && activeProjectForPreview !== project.project_id) {
            return;
          }
          const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
          const shouldPreserveCurrentPreview =
            project.project_id &&
            activeProjectForPreview === project.project_id &&
            (activeStatus === "running" ||
              activeStatus === "queued" ||
              activeStatus === "awaiting_approval");
          if (shouldPreserveCurrentPreview && (planPreviewUrl || backendResult)) {
            return;
          }
          setBackendResult(null);
          setPlanPreviewUrl("");
          setPlanPreviewSummary(null);
        }
      })
      .catch((error) => {
        setStatusMessage(
          error instanceof Error ? error.message : "Project result load failed.",
        );
      });
  };

  useEffect(() => {
    if (!token) return;
    const activeStatus = String(visibleActiveJob?.status || "").toLowerCase();
    if (activeStatus !== "awaiting_approval") return;
    const targetProjectId =
      visibleActiveJob?.project_id || currentProject?.project_id || projectId || "";
    if (!targetProjectId) return;

    const targetProject = {
      project_id: targetProjectId,
      name: currentProject?.name || siteName || "Untitled Project",
    } as ProjectRecord;

    loadProjectResultInBackground(targetProject);
    const interval = window.setInterval(() => {
      loadProjectResultInBackground(targetProject);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [
    token,
    planPreviewUrl,
    visibleActiveJob?.status,
    visibleActiveJob?.project_id,
    currentProject?.project_id,
    currentProject?.name,
    projectId,
    siteName,
  ]);

  const handlePreviewPlan = async () => {
    if (!token) return;
    if (!backendResult && !projectId) {
      setStatusMessage("Run the planner first so there is something to preview.");
      return;
    }
    setStatusMessage("Refreshing preview...");
    setBusy(true);
    try {
      await requestPreview(artifactPayload);
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Preview generation failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleExplainPlan = () => {
    const explanationText =
      typeof currentExplanation?.summary === "string"
        ? currentExplanation.summary
        : typeof currentExplanation?.overview === "string"
          ? currentExplanation.overview
          : typeof selectedRun?.message === "string"
            ? selectedRun.message
            : "";
    const fallbackDetails = [
      currentManualFailures.length
        ? `Current blockers: ${currentManualFailures
            .slice(0, 3)
            .map((failure) => failure.code || failure.message || "manual validation issue")
            .join(", ")}.`
        : null,
      issues.length
        ? `Current warnings: ${issues
            .slice(0, 3)
            .map((issue) => issue.message)
            .join("; ")}.`
        : null,
      currentTruthAudit?.success === true
        ? "Truth checks are currently passing."
        : currentTruthAudit?.success === false
          ? "Truth checks still need review."
          : null,
    ]
      .filter(Boolean)
      .join(" ");

    if (!explanationText && !fallbackDetails) {
      setStatusMessage("Run Civora AI first so there is a plan to explain.");
      return;
    }

    appendChatMessage(
      "assistant",
      [
        explanationText || "Here’s where the current design stands.",
        typeof currentExplanation?.why === "string" ? currentExplanation.why : null,
        fallbackDetails || null,
      ]
        .filter(Boolean)
        .join(" "),
      "explanation",
    );
    setStatusMessage("Added the latest plan explanation to the conversation.");
  };

  const handleNewProject = async () => {
    projectLoadRequestRef.current += 1;
    suppressProjectAutoLoadRef.current = true;
    draftProjectPromiseRef.current = null;
    resolvedProjectIdRef.current = "";
    setProjectId("");
    setCurrentProject(null);
    setSelectedRunId("");
    setActiveJobId("");
    setPrompt("");
    setImageName("");
    setUploadedImageApiUrl("");
    setUploadedImagePreviewUrl("");
    setSurveyFileName("");
    setSurveySlopeEstimate(null);
    setMapSnapshotPath("");
    setMapAnalysis(null);
    setBackendResult(null);
    setPlanPreviewUrl("");
    setPlanPreviewSummary(null);
    setAssumptions(defaultAssumptions);
    setIssues(defaultIssues);
    setSiteName("");
    setFileName("");
    setSiteNameAuto(false);
    setFileNameAuto(false);
    setProjectType("");
    setUnits("ft");
    setLotWidth("");
    setLotHeight("");
    setBuildingWidth("");
    setBuildingDepth("");
    setBuildingCount("");
    setSetback("");
    setParkingCount("");
    setMinSlopePct("");
    setPipeMinSlopePct("");
    setMaxParkingSlopePct("");
    setMaxRoadGradePct("");
    setMaxAdaCrossSlopePct("");
    setRoads(true);
    setGrading(true);
    setDrainage(true);
    setUtilities(true);
    setStrategyMode("assisted");
    const nextThread = [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
    setStatusMessage("Started a new project.");
    try {
      if (token) {
        draftProjectPromiseRef.current = saveProject({
          silent: true,
          projectIdOverride: null,
          nameOverride: "",
          fileNameOverride: "",
          projectInputOverride: {
            input_mode: "assisted",
            strict_mode: false,
            prompt_text: null,
            image_path: null,
            meta: {
              chat_thread: [createWelcomeMessage()],
              auto_named: false,
              auto_file_named: false,
            },
            manual_fields: {
              project_name: "",
              file_name: "",
              units: "ft",
              project_type: "",
              lot: { x: 0, y: 0, w: 0, h: 0 },
              setback: 0,
              building_width: 0,
              building_depth: 0,
              site_plan: { parking_count: 0 },
              disciplines: ["corridor", "grading", "drainage", "utility"],
            },
            allow_ai_fill_for_blanks: true,
          },
          latestResultOverride: {},
          autoNamedOverride: false,
          autoFileNamedOverride: false,
        });
        const createdProject = await draftProjectPromiseRef.current;
        if (createdProject?.project_id) {
          resolvedProjectIdRef.current = createdProject.project_id;
          setProjectId(createdProject.project_id);
        }
      }
    } finally {
      draftProjectPromiseRef.current = null;
      suppressProjectAutoLoadRef.current = false;
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleExportDxf = async () => {
    if (!token) return;
    if (!backendResult && !projectId) {
      setStatusMessage("Run the planner first so there is something to export.");
      return;
    }
    setBusy(true);
    try {
      const { blob, filename } = await postBinary(
        "/api/export/dxf",
        artifactPayload,
        { token },
      );
      downloadBlob(blob, filename ?? "civora-ai-plan.dxf");
      setStatusMessage("DXF export downloaded.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "DXF export failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleExportReport = async () => {
    if (!token) return;
    if (!backendResult && !projectId) {
      setStatusMessage("Run the planner first so there is something to export.");
      return;
    }
    setBusy(true);
    try {
      const { blob, filename } = await postBinary(
        "/api/export/report",
        artifactPayload,
        { token },
      );
      downloadBlob(blob, filename ?? "civora-ai-report.json");
      setStatusMessage("Report export downloaded.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Report export failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void loadAuthStatus();
    const stored = getStoredToken();
    if (!stored) return;
    setToken(stored);
    void loadMe(stored)
      .then(async () => {
        await refreshProjects(stored);
        await refreshJobs(stored, { suppressError: true });
      })
      .catch(() => {
        clearStoredToken();
        setToken("");
      });
  }, []);

  useEffect(() => {
    if (!token || !activeJobId) return;
    void loadJob(activeJobId);
    void refreshJobs(token, { suppressError: true, force: true });
    const interval = window.setInterval(() => {
      void loadJob(activeJobId);
      void refreshJobs(token, { suppressError: true, force: true });
    }, 3000);
    return () => window.clearInterval(interval);
  }, [token, activeJobId]);

  useEffect(() => {
    if (!currentProjectActiveJob) {
      return;
    }
    if (!activeJobId) {
      setActiveJobId(currentProjectActiveJob.job_id);
    }
  }, [activeJobId, currentProjectActiveJob]);

  useEffect(() => {
    if (!visibleActiveJob) return;
    const interval = window.setInterval(() => {
      setJobClockMs(Date.now());
    }, 5000);
    return () => window.clearInterval(interval);
  }, [visibleActiveJob]);

  useEffect(() => {
    if (!visibleActiveJob?.job_id) return;
    const normalizedStatus = String(visibleActiveJob.status || "").toLowerCase();
    if (!visibleActiveJobStale || normalizedStatus !== "running") {
      delete lastStaleJobWarningRef.current[visibleActiveJob.job_id];
      return;
    }
    if (lastStaleJobWarningRef.current[visibleActiveJob.job_id]) {
      return;
    }
    lastStaleJobWarningRef.current[visibleActiveJob.job_id] = true;
    setStatusMessage(
      `Job ${visibleActiveJob.job_id} has not reported a fresh backend update recently. It may still be running, but the status could be stalled.`,
    );
    appendChatMessage(
      "assistant",
      `Job ${visibleActiveJob.job_id} has not reported a fresh backend update recently. It may still be running, but the status may be stalled.`,
      "status",
    );
  }, [visibleActiveJob?.job_id, visibleActiveJob?.status, visibleActiveJobStale]);

  useEffect(() => {
    if (!workflowRuns.length) {
      setSelectedRunId("");
      return;
    }
    setSelectedRunId((current) =>
      current && workflowRuns.some((run) => run.run_id === current)
        ? current
        : workflowRuns[0].run_id,
    );
  }, [workflowRuns]);

  useEffect(() => {
    if (!token || projectId || projects.length === 0 || suppressProjectAutoLoadRef.current) return;
    const preferredProject =
      projects.find((project) => project.has_result) ?? projects[0];
    if (!preferredProject) return;
    void loadProject(preferredProject.project_id);
  }, [token, projectId, projects]);

  const previewReview: PreviewReview | null = (() => {
    const resultReleaseReview =
      currentPlanMeta?.release_review && typeof currentPlanMeta.release_review === "object"
        ? currentPlanMeta.release_review
        : null;
    const resultPhaseCheckpoints =
      currentPlanMeta?.phase_checkpoints && typeof currentPlanMeta.phase_checkpoints === "object"
        ? currentPlanMeta.phase_checkpoints
        : null;
    const summaryReview =
      planPreviewSummary?.review && typeof planPreviewSummary.review === "object"
        ? planPreviewSummary.review
        : null;

    const hasResultReviewSignal = Boolean(
      resultReleaseReview &&
        (Object.keys(resultReleaseReview).length ||
          Object.keys(resultPhaseCheckpoints || {}).length ||
          currentPlanMeta?.release_status),
    );

    if (!hasResultReviewSignal) {
      return summaryReview;
    }

    return {
      ...(summaryReview || {}),
      ...(resultReleaseReview || {}),
      phase_checkpoints:
        resultReleaseReview?.phase_checkpoints && typeof resultReleaseReview.phase_checkpoints === "object"
          ? resultReleaseReview.phase_checkpoints
          : resultPhaseCheckpoints || summaryReview?.phase_checkpoints || {},
      release_status:
        String(resultReleaseReview?.release_status || currentPlanMeta?.release_status || "").trim() ||
        summaryReview?.release_status ||
        "review",
      release_note:
        String(resultReleaseReview?.release_note || "").trim() ||
        String(currentPlanMeta?.release_note || "").trim() ||
        summaryReview?.release_note ||
        "",
    };
  })();
  const previewAssumptionCategories = toArray(previewReview?.assumption_categories)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const previewFixActions = toArray(previewReview?.autofix_actions)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const previewFixTargets = toArray(previewReview?.dominant_fix_targets)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const previewReviewCategories = toArray(previewReview?.review_categories)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter((item: string | null | undefined) => {
      const normalized = String(item || "").toLowerCase();
      return Boolean(item) && normalized !== "uncategorized" && normalized !== "general";
    });
  const previewBlockedReasons = toArray(previewReview?.blocked_reasons)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const previewFailedDeliverables = toArray(previewReview?.failed_deliverables)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const previewExtraDeliverables = toArray(previewReview?.extra_deliverables)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const previewReadyDeliverables = toArray(previewReview?.ready_deliverables)
    .map((item: unknown) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const previewPhaseEntries = (
    [
      "layout",
      "grading",
      "drainage_storm",
      "utilities",
      "coordination_validation",
      "combined_view",
    ] as const
  )
    .map((key) => {
      const phase = previewReview?.phase_checkpoints?.[key];
      if (!phase) {
        return null;
      }
      const label = toReadableLabel(String(phase.label || key || "")) || "Phase";
      const status = String(phase.status || (phase.ready ? "ready" : "review") || "review");
      const deliverables = toArray(phase.deliverables)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean);
      const blockers = [
        ...toArray(phase.blockers),
        ...toArray(phase.blocked_reasons),
      ]
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean);
      const messages = toArray(phase.messages)
        .map((item: unknown) => String(item || "").trim())
        .filter(Boolean);
      const note = String(phase.note || "").trim();
      const currentStage = toReadableLabel(String(phase.current_stage || ""));
      const currentStatus = String(phase.current_status || "").trim();
      const phaseSummary =
        key === "combined_view" && (phase.total_phase_count || phase.completed_phase_count)
          ? (() => {
              const countSummary = `${phase.completed_phase_count ?? 0}/${phase.total_phase_count ?? 0} phases complete`;
              if (currentStage && currentStatus && currentStatus.toLowerCase() !== "complete") {
                return `${countSummary} • ${currentStage} ${toReadableLabel(currentStatus)}`.trim();
              }
              return countSummary;
            })()
          : messages[0] ||
            note ||
            (deliverables.length
              ? `Ready: ${joinNatural(deliverables, 3)}`
              : blockers.length
                ? `Watch: ${joinNatural(blockers, 3)}`
                : phase.ready
                  ? "Phase outputs are saved."
                  : "Phase is still under review.");
      return {
        key,
        label,
        status,
        ready: Boolean(phase.ready),
        summary: phaseSummary,
        currentStage,
        currentStatus,
      };
    })
    .filter(Boolean) as Array<{
    key: string;
    label: string;
    status: string;
    ready: boolean;
    summary: string;
    currentStage: string;
    currentStatus: string;
  }>;
  const activePreviewPhase =
    previewPhaseEntries.find(
      (phase) =>
        phase.status.toLowerCase() === "running" ||
        phase.currentStatus.toLowerCase() === "running",
    ) ??
    previewPhaseEntries.find((phase) => phase.key === "combined_view") ??
    null;
  const effectivePreviewUnresolvedCount =
    previewReview?.release_status === "ready" &&
    !toArray(previewReview?.blocked_reasons).length &&
    !toArray(previewReview?.failed_deliverables).length
      ? 0
      : previewReview?.unresolved_conflict_count ?? 0;
  const combinedPreviewPhase =
    previewPhaseEntries.find((phase) => phase.key === "combined_view") ?? null;
  const phaseOnlyEntries = previewPhaseEntries.filter(
    (phase) => phase.key !== "combined_view",
  );
  const previewCompletedPhaseCount = (() => {
    const explicitCount = Number(
      previewReview?.phase_checkpoints?.combined_view?.completed_phase_count ?? NaN,
    );
    if (Number.isFinite(explicitCount) && explicitCount >= 0) {
      return explicitCount;
    }
    return phaseOnlyEntries.filter((phase) =>
      ["ready", "complete"].includes(phase.status.toLowerCase()),
    ).length;
  })();
  const previewTotalPhaseCount = (() => {
    const explicitTotal = Number(
      previewReview?.phase_checkpoints?.combined_view?.total_phase_count ?? NaN,
    );
    if (Number.isFinite(explicitTotal) && explicitTotal > 0) {
      return explicitTotal;
    }
    return phaseOnlyEntries.length;
  })();
  const previewRunningPhase =
    phaseOnlyEntries.find((phase) =>
      ["running"].includes(phase.status.toLowerCase()) ||
      phase.currentStatus.toLowerCase() === "running",
    ) ?? null;
  const previewNextPendingPhase =
    phaseOnlyEntries.find((phase) =>
      ["pending", "partial", "review"].includes(phase.status.toLowerCase()),
    ) ?? null;
  const gatingPhaseKey =
    !autoAdvancePhases &&
    String(visibleActiveJob?.status || "").toLowerCase() === "awaiting_approval"
      ? previewRunningPhase?.key || previewNextPendingPhase?.key || revisePhaseTarget
      : null;

  const previewLayersEffective = useMemo(() => {
    if (!gatingPhaseKey) return previewLayers;
    switch (gatingPhaseKey) {
      case "layout":
        return { ...previewLayers, grading: false, drainage: false, utilities: false };
      case "grading":
        return { ...previewLayers, drainage: false, utilities: false };
      case "drainage_storm":
        return { ...previewLayers, grading: false, utilities: false };
      case "utilities":
        return { ...previewLayers, grading: false, drainage: false };
      default:
        return previewLayers;
    }
  }, [gatingPhaseKey, previewLayers]);

  const previewLayerList = useMemo(() => {
    const layers = new Set<string>();
    if (previewLayersEffective.buildings) {
      ["BUILDING", "STRUCTURE", "PAD"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.roads) {
      ["ROAD", "PAVEMENT", "PARKING", "WALK"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.grading) {
      ["SURFACE", "FG_CONTOUR", "EG_CONTOUR", "SPOT_FG", "DRAIN_FLOW", "FLOW_ARROW"].forEach((layer) =>
        layers.add(layer),
      );
    }
    if (previewLayersEffective.drainage) {
      ["DRAIN", "PIPE", "STORM", "BASIN_BOUNDARY"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.utilities) {
      ["UTILITY", "WATER", "SAN"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.structures) {
      ["BRIDGE", "POOL", "STRUCTURE"].forEach((layer) => layers.add(layer));
    }
    if (previewLayersEffective.lots) {
      ["LOT", "OPEN_SPACE", "EASEMENT"].forEach((layer) => layers.add(layer));
    }
    return Array.from(layers);
  }, [previewLayersEffective]);

  useEffect(() => {
    if (!planPreviewUrl || !token) return;
    requestPreviewInBackground(artifactPayload, { silentStatus: true });
  }, [previewQuality, previewLayerList, planPreviewUrl, token, artifactPayload]);

  const preview3DItems = useMemo<Preview3DItem[]>(() => {
    const actions = Array.isArray(backendResult?.final_plan?.actions)
      ? backendResult.final_plan.actions
      : [];
    const items: Preview3DItem[] = [];
    for (const action of actions) {
      if (!action || typeof action !== "object") continue;
      const geometry =
        (action as PlanAction).geometry ?? (action as Record<string, unknown>);
      if (!geometry || typeof geometry !== "object") continue;
      const layer = String(action.layer || "").toUpperCase();
      const width = Number((geometry as { width?: number }).width || 0);
      const height = Number((geometry as { height?: number }).height || 0);
      const origin = Array.isArray((geometry as { origin?: unknown }).origin)
        ? (geometry as { origin?: number[] }).origin || []
        : [];
      if (!width || !height || origin.length < 2) continue;
      const x = Number(origin[0] || 0);
      const y = Number(origin[1] || 0);
      const label = String(action.label || "");
      const isBuilding =
        layer === "BUILDING" || label.toLowerCase().includes("build");
      const isRoad =
        layer === "ROAD" || layer === "PAVEMENT" || label.toLowerCase().includes("road");
      const isParking =
        layer === "PARKING" || label.toLowerCase().includes("park");
      const isStructure = layer === "BRIDGE" || layer === "POOL" || layer === "STRUCTURE";

      if (isBuilding && !previewLayersEffective.buildings) continue;
      if ((isRoad || isParking) && !previewLayersEffective.roads) continue;
      if (isStructure && !previewLayersEffective.structures) continue;

      const color = isBuilding
        ? "#e2e8f0"
        : isStructure
          ? "#fde68a"
          : isRoad
            ? "#c7d2fe"
            : "#dbeafe";
      const heightFt = isBuilding ? 28 : isStructure ? 10 : isRoad ? 2 : 1;
      items.push({
        x,
        y,
        w: width,
        h: height,
        height: heightFt,
        color,
        label: label || layer,
        layer: isBuilding ? "BUILDING" : isStructure ? "STRUCTURE" : isRoad ? "ROAD" : "PARKING",
      });
    }
    return items;
  }, [backendResult, previewLayersEffective]);
  useEffect(() => {
    const status = String(visibleActiveJob?.status || "").toLowerCase();
    if (status !== "awaiting_approval") return;
    const nextKey =
      previewRunningPhase?.key ||
      previewNextPendingPhase?.key ||
      revisePhaseTarget;
    if (nextKey) {
      setRevisePhaseTarget(nextKey as typeof revisePhaseTarget);
    }
  }, [visibleActiveJob?.status, previewRunningPhase?.key, previewNextPendingPhase?.key, revisePhaseTarget]);
  const previewPhaseProgressPercent = (() => {
    if (!previewTotalPhaseCount) return 0;
    const explicitJobProgress = Number(
      previewReview?.phase_checkpoints?.combined_view?.job_progress ?? NaN,
    );
    const base = Math.max(
      0,
      Math.min(1, previewCompletedPhaseCount / previewTotalPhaseCount),
    );
    if (Number.isFinite(explicitJobProgress) && previewRunningPhase) {
      const perPhase = 1 / previewTotalPhaseCount;
      const runningFraction = Math.max(0, Math.min(1, explicitJobProgress / 100));
      return Math.round(
        Math.max(
          base,
          Math.min(1, base + perPhase * runningFraction),
        ) * 100,
      );
    }
    if (previewRunningPhase) {
      return Math.round(
        Math.min(1, base + 0.5 / previewTotalPhaseCount) * 100,
      );
    }
    return Math.round(base * 100);
  })();
  const previewPhaseHeadline = previewRunningPhase
    ? `Continuing with ${previewRunningPhase.label}`
    : previewNextPendingPhase
      ? `Waiting to continue with ${previewNextPendingPhase.label}`
      : previewTotalPhaseCount > 0
        ? `${previewCompletedPhaseCount}/${previewTotalPhaseCount} phases complete`
        : "";
  const previewRerunSignals = [
    ...toArray(previewReview?.rerun_stages).map((item: unknown) =>
      toReadableLabel(String(item || "")),
    ),
    ...toArray(previewReview?.rerun_reasons).map((item: unknown) =>
      toReadableLabel(String(item || "")),
    ),
  ].filter(Boolean);
  const phaseStats = useMemo<PhaseStats>(() => {
    const layoutStats: PhaseMetric[] = [
      { label: "Buildings", value: toMetricValue(quantityTotals.building_count), unit: "ea", format: "count" as const },
      { label: "Building area", value: toMetricValue(quantityTotals.building_area_sf), unit: "sf" },
      {
        label: "Parking stalls",
        value: toMetricValue(quantityTotals.estimated_parking_stalls),
        unit: "stalls",
        format: "count" as const,
      },
      { label: "Parking area", value: toMetricValue(quantityTotals.parking_area_sf), unit: "sf" },
    ];
    const gradingStats: PhaseMetric[] = [
      { label: "Cut volume", value: readMetricValue(managerMetrics.earthwork_cut_cf), unit: "cf" },
      { label: "Fill volume", value: readMetricValue(managerMetrics.earthwork_fill_cf), unit: "cf" },
      { label: "Net earthwork", value: readMetricValue(managerMetrics.earthwork_net_cf), unit: "cf" },
      { label: "FG contours", value: toMetricValue(quantityTotals.fg_contour_count), unit: "ea", format: "count" as const },
    ];
    const drainageStats: PhaseMetric[] = [
      { label: "Pipe length", value: totalPipeLength, unit: "ft" },
      { label: "Min slope", value: minSlope, unit: "%" },
      { label: "Max slope", value: maxSlope, unit: "%" },
      { label: "Ponds", value: toMetricValue(quantityTotals.pond_count), unit: "ea", format: "count" as const },
    ];
    const utilityStats: PhaseMetric[] = [
      {
        label: "Utility length",
        value: toMetricValue(
          readMetricValue(managerMetrics.utility_total_length_ft) ??
            quantityTotals.utility_length_ft,
        ),
        unit: "ft",
      },
      {
        label: "Sanitary length",
        value: toMetricValue(
          readMetricValue(managerMetrics.sanitary_total_length_ft) ??
            quantityTotals.sanitary_length_ft,
        ),
        unit: "ft",
      },
      { label: "Sanitary manholes", value: toMetricValue(quantityTotals.sanitary_manhole_count), unit: "ea", format: "count" as const },
      { label: "Sanitary services", value: toMetricValue(quantityTotals.sanitary_service_count), unit: "ea", format: "count" as const },
    ];
    const coordinationStats: PhaseMetric[] = [
      { label: "Unresolved conflicts", value: toMetricValue(previewReview?.unresolved_conflict_count), unit: "ea", format: "count" as const },
      { label: "QA errors", value: readMetricValue(managerMetrics.qa_error_count), unit: "ea", format: "count" as const },
      { label: "QA warnings", value: readMetricValue(managerMetrics.qa_warning_count), unit: "ea", format: "count" as const },
      { label: "Reruns", value: toMetricValue(previewReview?.rerun_total), unit: "ea", format: "count" as const },
    ];
    return {
      layout: layoutStats,
      grading: gradingStats,
      drainage_storm: drainageStats,
      utilities: utilityStats,
      coordination_validation: coordinationStats,
    };
  }, [
    managerMetrics,
    quantityTotals,
    totalPipeLength,
    minSlope,
    maxSlope,
    previewReview,
  ]);
  const whatYouNeedSummary = (() => {
    const manualFields =
      currentProject?.project_input?.manual_fields && typeof currentProject.project_input.manual_fields === "object"
        ? currentProject.project_input.manual_fields
        : {};
    const lot = (manualFields.lot && typeof manualFields.lot === "object" ? manualFields.lot : {}) as {
      w?: number;
      h?: number;
    };
    const sitePlan =
      (manualFields.site_plan && typeof manualFields.site_plan === "object"
        ? manualFields.site_plan
        : {}) as { parking_count?: number };
    const projectTypeValue = String(
      manualFields.project_type || projectType || "",
    ).trim();
    const lotWidthValue = readPositiveNumber(lot.w ?? lotWidth);
    const lotHeightValue = readPositiveNumber(lot.h ?? lotHeight);
    const parkingValue = readPositiveNumber(sitePlan.parking_count ?? parkingCount);
    const buildingWidthValue = readPositiveNumber(manualFields.building_width ?? buildingWidth);
    const buildingDepthValue = readPositiveNumber(manualFields.building_depth ?? buildingDepth);
    const requestedDeliverables = new Set(
      toArray(previewReview?.requested_deliverables)
        .map((item: unknown) => String(item || "").trim())
        .filter(Boolean),
    );
    const disciplineSet = new Set(
      [
        ...toArray(manualFields.disciplines),
        roads ? "corridor" : null,
        grading ? "grading" : null,
        drainage ? "drainage" : null,
        utilities ? "utility" : null,
      ]
        .map((item: unknown) => String(item || "").trim().toLowerCase())
        .filter(Boolean),
    );
    const neededNow: string[] = [];
    const supporting: string[] = [];
    const inScope: string[] = [];

    if (!projectTypeValue) {
      neededNow.push("site type or land use");
    }
    if (!lotWidthValue || !lotHeightValue) {
      neededNow.push("lot size or boundary dimensions");
    }
    if (!buildingWidthValue || !buildingDepthValue) {
      neededNow.push("building footprint dimensions");
    }
    if (!parkingValue) {
      neededNow.push("parking target or building program");
    }

    if (disciplineSet.has("corridor") || requestedDeliverables.has("site_plan")) {
      inScope.push("roads and site access");
      supporting.push("frontage access constraints");
    }
    if (disciplineSet.has("grading") || requestedDeliverables.has("grading_plan")) {
      inScope.push("grading");
      supporting.push("survey, slope, or benchmark elevations");
    }
    if (disciplineSet.has("drainage") || requestedDeliverables.has("storm_pipe_plan")) {
      inScope.push("drainage and storm");
      supporting.push("storm outfall or drainage direction");
      supporting.push("existing drainage patterns");
    }
    if (disciplineSet.has("utility") || requestedDeliverables.has("utility_plan")) {
      inScope.push("utilities");
      supporting.push("water and sanitary tie-in points");
      supporting.push("utility maps or known connection locations");
    }

    const blocked = previewBlockedReasons.filter(Boolean);
    const note =
      blocked.length > 0
        ? `The current blockers are ${joinNatural(blocked, 3)}.`
        : previewReview?.release_status === "ready"
          ? "The core design inputs look complete enough for release-ready review."
          : neededNow.length
            ? "Filling the missing inputs below will make the next run more reliable."
            : "The core design inputs are already in place. The supporting items below would sharpen the engineering output.";

    return {
      neededNow: Array.from(new Set(neededNow)),
      supporting: Array.from(new Set(supporting)).filter((item) => !neededNow.includes(item)),
      inScope: Array.from(new Set(inScope)),
      note,
    };
  })();

  if (!user) {
    return (
      <div className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#e2e8f0_100%)] p-6">
        <div className="mx-auto grid min-h-[90vh] max-w-6xl items-center gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-6"
          >
            <div className="space-y-4">
              <Pill>Beta Control Room</Pill>
              <h1 className="max-w-2xl text-5xl font-semibold tracking-tight text-slate-950">
                Civora AI — Autonomous Civil Engineering Design
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-slate-600">
                Sign in to run civil site concepts, review clear engineering
                outcomes, and export readable plans from one clean workflow.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              <Card className="rounded-2xl">
                <CardContent className="p-5">
                  <FolderOpen className="h-5 w-5 text-slate-900" />
                  <p className="mt-3 text-sm font-medium text-slate-900">Projects</p>
                  <p className="mt-1 text-sm text-slate-500">Open, rerun, and review real project history.</p>
                </CardContent>
              </Card>
              <Card className="rounded-2xl">
                <CardContent className="p-5">
                  <Clock3 className="h-5 w-5 text-slate-900" />
                  <p className="mt-3 text-sm font-medium text-slate-900">Runs</p>
                  <p className="mt-1 text-sm text-slate-500">See what passed, what failed, and why it matters.</p>
                </CardContent>
              </Card>
              <Card className="rounded-2xl">
                <CardContent className="p-5">
                  <Map className="h-5 w-5 text-slate-900" />
                  <p className="mt-3 text-sm font-medium text-slate-900">Deliverables</p>
                  <p className="mt-1 text-sm text-slate-500">Preview, download, and share readable civil outputs.</p>
                </CardContent>
              </Card>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="rounded-[28px]">
              <CardHeader>
                <SectionTitle
                  icon={Sparkles}
                  title={authMode === "register" ? "Create Account" : "Sign In"}
                  desc="Auth is now user-scoped so projects and jobs are private per beta tester."
                />
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="inline-flex rounded-2xl border border-black/10 bg-slate-100 p-1">
                  <button
                    type="button"
                    onClick={() => setAuthMode("login")}
                    className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                      authMode === "login" ? "bg-white shadow-sm text-slate-900" : "text-slate-600"
                    }`}
                  >
                    Sign In
                  </button>
                  <button
                    type="button"
                    onClick={() => setAuthMode("register")}
                    className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                      authMode === "register" ? "bg-white shadow-sm text-slate-900" : "text-slate-600"
                    }`}
                  >
                    Create Account
                  </button>
                </div>
                <div className="rounded-2xl border border-black/10 bg-slate-50 p-4 text-sm text-slate-600">
                  {authStatus ? (
                    authStatus.user_count > 0 ? (
                      <span>
                        {authStatus.user_count} Civora AI beta account
                        {authStatus.user_count === 1 ? "" : "s"} already exist in this
                        workspace. Use <strong>Sign In</strong> if you made one before,
                        or create another account.
                      </span>
                    ) : (
                      <span>No Civora AI beta accounts exist yet. Create the first one here.</span>
                    )
                  ) : (
                    <span>Account status will appear here once the Civora AI backend responds.</span>
                  )}
                </div>
                {authStatusError ? (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                    {authStatusError}
                  </div>
                ) : null}
                {authMode === "register" ? (
                  <Field label="Name">
                    <TextInput
                      value={authName}
                      onChange={(e) => setAuthName(e.target.value)}
                      placeholder="Jane Engineer"
                    />
                  </Field>
                ) : null}
                <Field label="Email">
                  <TextInput
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                    placeholder="you@example.com"
                    autoComplete="email"
                  />
                </Field>
                <Field label="Password">
                  <div className="relative">
                    <TextInput
                      type={showPassword ? "text" : "password"}
                      value={authPassword}
                      onChange={(e) => setAuthPassword(e.target.value)}
                      placeholder="At least 8 characters"
                      autoComplete={
                        authMode === "register" ? "new-password" : "current-password"
                      }
                      className="pr-12"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((value) => !value)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </Field>
                {authError ? (
                  <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                    {authError}
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-3">
                  <SmallButton onClick={handleAuth} disabled={authLoading}>
                    <Sparkles className="mr-2 h-4 w-4" />
                    {authLoading
                      ? "Working..."
                      : authMode === "register"
                        ? "Create Account"
                        : "Sign In"}
                  </SmallButton>
                  <SmallButton
                    variant="secondary"
                    onClick={() => {
                      setAuthError("");
                      setAuthMode((mode) =>
                        mode === "register" ? "login" : "register",
                      );
                    }}
                  >
                    {authMode === "register" ? "Have an account?" : "Need an account?"}
                  </SmallButton>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f7f7f8] text-slate-950">
      <div className="flex min-h-screen">
        <aside className="hidden w-[290px] shrink-0 border-r border-slate-200 bg-[#ececec] lg:flex lg:flex-col">
          <div className="border-b border-slate-200 p-4">
            <button
              type="button"
              onClick={handleNewProject}
              className="flex w-full items-center justify-center rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              <MessageSquarePlus className="mr-2 h-4 w-4" />
              New Project
            </button>
          </div>

          <div className="space-y-6 overflow-y-auto p-4">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Projects
              </p>
              <div className="space-y-2">
                {projects.length === 0 ? (
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    No saved projects yet.
                  </div>
                ) : (
                  projects.map((project) => (
                    <div
                      key={project.project_id}
                      className={`flex items-center gap-2 rounded-2xl px-2 py-2 transition ${
                        project.project_id === projectId
                          ? "bg-white shadow-sm ring-1 ring-slate-300"
                          : "hover:bg-white"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => void loadProject(project.project_id)}
                        className="min-w-0 flex-1 px-2 py-1 text-left text-sm text-slate-700"
                      >
                        <p className="truncate font-medium text-slate-950">
                          {project.name || "Untitled Project"}
                        </p>
                        <p className="mt-1 truncate text-xs text-slate-500">
                          {project.has_result ? "Saved result" : "Draft"}
                        </p>
                      </button>
                      <button
                        type="button"
                        onClick={() => void deleteProject(project.project_id)}
                        aria-label={`Delete ${project.name || "Untitled Project"}`}
                        className="rounded-xl border border-slate-200 bg-white p-2 text-slate-500 transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Recent Runs
              </p>
              <div className="space-y-2">
                {workflowRuns.length === 0 ? (
                  <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500">
                    No saved runs yet.
                  </div>
                ) : (
                  workflowRuns.slice(0, 8).map((run) => (
                    <button
                      key={run.run_id}
                      type="button"
                      onClick={() => setSelectedRunId(run.run_id)}
                      className={`block w-full rounded-2xl px-4 py-3 text-left transition ${
                        selectedRun?.run_id === run.run_id
                          ? "bg-white shadow-sm ring-1 ring-slate-300"
                          : "hover:bg-white"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-slate-900">
                          {run.success ? "Completed run" : "Failed run"}
                        </span>
                        <span className="text-xs text-slate-500">
                          {run.success ? "Pass" : "Fail"}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {formatTimestamp(run.created_at)}
                      </p>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:px-6">
            <div className="min-w-0">
              <p className="truncate text-sm text-slate-500">Signed in as {user.email}</p>
              <h1 className="truncate text-lg font-semibold text-slate-950">
                Civora AI
              </h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <a
                href="/upgrades"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Upgrades
              </a>
              <button
                type="button"
                onClick={() => void handleRefreshWorkspace()}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Refresh
              </button>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Sign Out
              </button>
            </div>
          </div>

          <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-6 md:px-6">
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
                  onClick={() => setStrategyMode(option.value as StrategyMode)}
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
                  setSiteName(e.target.value);
                  setSiteNameAuto(false);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void saveProject({
                      nameOverride: siteName.trim(),
                      fileNameOverride: fileName.trim(),
                      autoNamedOverride: false,
                      autoFileNamedOverride: false,
                    });
                  }
                }}
                placeholder="Project name"
              />

              <TextInput
                value={fileName}
                onChange={(e) => {
                  setFileName(e.target.value);
                  setFileNameAuto(false);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void saveProject({
                      nameOverride: siteName.trim(),
                      fileNameOverride: fileName.trim(),
                      autoNamedOverride: false,
                      autoFileNamedOverride: false,
                    });
                  }
                }}
                placeholder="File name"
              />
              </div>

              <div className="flex flex-wrap gap-2">
                {disciplineToggles.map(({ label, checked, setter }) => (
                  <button
                    key={label}
                    type="button"
                    onClick={() => setter(!checked)}
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

            <div className="rounded-[28px] border border-slate-200 bg-white">
              {(() => {
                const sessionLearning = computeLearningScore(chatMessages);
                const reportScore = learningReport?.feedback?.score_percent;
                const reportTotal = learningReport?.feedback?.total;
                const datasetCount = learningReport?.training_examples?.count;
                const lastRun =
                  learningReportUpdatedAt
                    ? new Date(learningReportUpdatedAt).toLocaleString()
                    : null;
                if (!sessionLearning.total && !reportTotal && !datasetCount) return null;
                return (
                  <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-3 text-xs text-slate-500 md:px-6">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold uppercase tracking-[0.14em]">
                        Learning Health
                      </span>
                      <button
                        type="button"
                        onClick={() => void refreshLearningReport()}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-50"
                      >
                        Refresh
                      </button>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {sessionLearning.total ? (
                        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-700">
                          Session helpful: {sessionLearning.score}% ({sessionLearning.total})
                        </span>
                      ) : null}
                      {typeof reportScore === "number" ? (
                        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-700">
                          Global helpful: {reportScore}% ({reportTotal ?? 0})
                        </span>
                      ) : null}
                      {typeof datasetCount === "number" ? (
                        <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold text-slate-700">
                          Training set: {datasetCount}
                        </span>
                      ) : null}
                      {lastRun ? (
                        <span className="text-[11px] text-slate-400">
                          Last refresh: {lastRun}
                        </span>
                      ) : null}
                    </div>
                  </div>
                );
              })()}
              <div
                ref={chatScrollRef}
                className="max-h-[420px] space-y-4 overflow-y-auto p-4 md:p-6"
              >
                {chatMessages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-[28px] px-4 py-3 ${
                        message.role === "user"
                          ? "bg-slate-950 text-white"
                          : message.role === "system"
                            ? "border border-amber-200 bg-amber-50 text-amber-900"
                            : "border border-slate-200 bg-white text-slate-900"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">
                          {message.role === "user"
                            ? "You"
                            : message.role === "system"
                              ? "Action"
                              : "Civora AI"}
                        </span>
                        <span className="text-[11px] opacity-60">
                          {formatChatTimestamp(message.createdAt)}
                        </span>
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6">
                        {message.content}
                      </p>
                      {message.role === "assistant" ? (
                        <div className="mt-3 flex items-center gap-2 text-xs">
                          <span className="text-slate-400">Was this helpful?</span>
                          <button
                            type="button"
                            onClick={() => setMessageFeedback(message.id, "up")}
                            className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                              message.feedback === "up"
                                ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                : "border-slate-200 text-slate-600 hover:bg-slate-50"
                            }`}
                          >
                            Helpful
                          </button>
                          <button
                            type="button"
                            onClick={() => setMessageFeedback(message.id, "down")}
                            className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] transition ${
                              message.feedback === "down"
                                ? "border-rose-500 bg-rose-50 text-rose-700"
                                : "border-slate-200 text-slate-600 hover:bg-slate-50"
                            }`}
                          >
                            Not quite
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>

              <div className="border-t border-slate-200 p-4 md:p-6">
                {(busy || visibleActiveJob) && (
                  <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-950">
                          {thinkingState.label}
                        </p>
                        <p className="mt-1 text-sm text-slate-600">
                          {thinkingState.detail}
                        </p>
                      </div>
                      <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                        {thinkingState.progress}%
                      </span>
                    </div>
                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-slate-950 transition-all duration-500"
                        style={{ width: `${thinkingState.progress}%` }}
                      />
                    </div>
                    {visibleActiveJob && (
                      <div className="mt-3 flex items-center justify-between text-xs text-slate-600">
                        <span className="font-semibold uppercase tracking-[0.12em] text-slate-500">
                          Auto-advance phases
                        </span>
                        <button
                          type="button"
                          onClick={() => setAutoAdvancePhases((prev) => !prev)}
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] transition ${
                            autoAdvancePhases
                              ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          {autoAdvancePhases ? "On" : "Off"}
                        </button>
                      </div>
                    )}
                    {(visibleActiveJob || hasDirectRunInFlight) && (
                      <div className="mt-4 flex justify-end">
                        <button
                          type="button"
                          onClick={handleCancelActiveJob}
                          disabled={String(visibleActiveJob?.status || "").toLowerCase() === "cancelling"}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {String(visibleActiveJob?.status || "").toLowerCase() === "cancelling"
                            ? "Cancelling..."
                            : "Cancel"}
                        </button>
                        {String(visibleActiveJob?.status || "").toLowerCase() === "awaiting_approval" && (
                          <>
                            <div className="ml-2 flex items-center gap-2">
                              <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
                                Revise phase
                              </label>
                              <select
                                value={revisePhaseTarget}
                                onChange={(event) =>
                                  setRevisePhaseTarget(
                                    event.target.value as typeof revisePhaseTarget,
                                  )
                                }
                                className="rounded-xl border border-slate-200 bg-white px-2 py-2 text-xs font-semibold text-slate-700"
                              >
                                <option value="layout">Layout</option>
                                <option value="grading">Grading</option>
                                <option value="drainage_storm">Drainage/Storm</option>
                                <option value="utilities">Utilities</option>
                                <option value="coordination_validation">Coordination</option>
                              </select>
                            </div>
                            <button
                              type="button"
                              onClick={handleReviseActiveJob}
                              className="ml-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                            >
                              Save Changes &amp; Revise
                            </button>
                            <button
                              type="button"
                              onClick={handleContinueActiveJob}
                              className="ml-2 rounded-xl border border-slate-900 bg-slate-950 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
                            >
                              Approve &amp; Continue
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}

                <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50 p-3">
                    <TextArea
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      onKeyDown={(event) => {
                        if (
                          event.key === "Enter" &&
                          !event.shiftKey &&
                          !(event.nativeEvent as KeyboardEvent).isComposing
                        ) {
                          event.preventDefault();
                        if (prompt.trim() || imageName) {
                          handleSendMessage();
                        }
                        }
                      }}
                      placeholder="Message Civora AI with what you want to create or change..."
                      className="h-[150px] min-h-[150px] max-h-[240px] border-0 bg-transparent px-1 py-1 shadow-none focus:ring-0"
                    />
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap gap-2">
                      <label className="inline-flex cursor-pointer items-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
                        <FileImage className="mr-2 h-4 w-4" />
                        Upload
                        <input
                          type="file"
                          accept="image/*"
                          className="hidden"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              await uploadImage(file);
                            }
                          }}
                        />
                      </label>
                      <button
                        type="button"
                        onClick={handleExplainPlan}
                        disabled={!backendResult && !selectedRun}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Explain
                      </button>
                      <button
                        type="button"
                        onClick={() => void runOrchestrator("fix")}
                        disabled={busy || Boolean(visibleActiveJob)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Fix
                      </button>
                      <button
                        type="button"
                        onClick={() => void runOrchestrator("improve")}
                        disabled={busy || Boolean(visibleActiveJob)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Improve
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void saveProject()}
                        disabled={busy || Boolean(visibleActiveJob)}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={handleSendMessage}
                        disabled={busy && !prompt.trim() && !imageName}
                        className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busy && activePlanTool === "run"
                          ? "Working..."
                          : visibleActiveJob
                            ? "Working..."
                            : "Send"}
                      </button>
                    </div>
                  </div>
                </div>

                {!busy && !visibleActiveJob && statusMessage && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    {statusMessage}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-[28px] border border-slate-200 bg-white p-4 md:p-6">
              <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                      Preview Workspace
                    </span>
                    {previewReview && (
                      <span
                        className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                          previewReview.release_status === "ready"
                            ? "bg-emerald-100 text-emerald-800"
                            : previewReview.release_status === "blocked"
                              ? "bg-amber-100 text-amber-800"
                              : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {previewReview.release_status === "ready"
                          ? "Release Ready"
                          : previewReview.release_status === "blocked"
                            ? "Blocked"
                            : "Needs Review"}
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-semibold text-slate-950">Live Preview</p>
                  <p className="mt-1 text-sm text-slate-500">
                    The preview shows the latest engineered plan even when final export is still under review.
                  </p>
                  {previewReview && (
                    <div
                      className={`inline-flex max-w-3xl items-start rounded-2xl border px-4 py-3 text-sm ${
                        previewReview.release_status === "ready"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                          : previewReview.release_status === "blocked"
                            ? "border-amber-200 bg-amber-50 text-amber-900"
                            : "border-slate-200 bg-slate-50 text-slate-700"
                      }`}
                    >
                      <div>
                        <p className="font-semibold">
                          {previewReview.release_status === "ready"
                            ? "Release review is clear."
                            : previewReview.release_status === "blocked"
                              ? "Export is still blocked."
                              : "Preview needs follow-up review."}
                        </p>
                        <p className="mt-1 text-xs">
                          {previewReview.release_note ||
                            "Preview review summary is available for the latest engineering pass."}
                        </p>
                      </div>
                    </div>
                  )}
                  {previewTotalPhaseCount > 0 && previewCompletedPhaseCount < previewTotalPhaseCount ? (
                    <div className="inline-flex max-w-3xl items-start rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                      <div>
                        <p className="font-semibold">Preview shows completed phases only.</p>
                        <p className="mt-1 text-xs">
                          {previewRunningPhase
                            ? `${previewRunningPhase.label} is the current active phase. Systems like drainage, storm, and utilities appear after their phases finish.`
                            : previewNextPendingPhase
                              ? `${previewNextPendingPhase.label} is still pending. Systems like drainage, storm, and utilities appear after their phases finish.`
                              : "Additional systems appear as later phases complete."}
                        </p>
                      </div>
                    </div>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={handlePreviewPlan}
                    disabled={busy}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Refresh Preview
                  </button>
                  {planPreviewUrl ? (
                    <button
                      type="button"
                      onClick={() => setPreviewFullscreenOpen(true)}
                      className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
                    >
                      <Maximize2 className="h-4 w-4" />
                      Fullscreen Preview
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={handleExportDxf}
                    disabled={busy}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Export DXF
                  </button>
                  <button
                    type="button"
                    onClick={handleExportReport}
                    disabled={busy}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Export Report
                  </button>
                </div>
              </div>

              {planPreviewUrl ? (
                <div className="rounded-[28px] border border-slate-200 bg-[radial-gradient(circle_at_top,#f8fafc_0%,#eef2f7_100%)] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)]">
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      <span>Preview Mode</span>
                      <button
                        type="button"
                        onClick={() => setPreviewMode("2d")}
                        className={`rounded-full border px-2.5 py-1 ${
                          previewMode === "2d"
                            ? "border-slate-900 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        2D
                      </button>
                      <button
                        type="button"
                        onClick={() => setPreviewMode("3d")}
                        className={`rounded-full border px-2.5 py-1 ${
                          previewMode === "3d"
                            ? "border-slate-900 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        3D
                      </button>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      <span>Interaction</span>
                      <button
                        type="button"
                        onClick={() => setPreviewInteraction("static")}
                        className={`rounded-full border px-2.5 py-1 ${
                          previewInteraction === "static"
                            ? "border-slate-900 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        Static
                      </button>
                      <button
                        type="button"
                        onClick={() => setPreviewInteraction("interactive")}
                        className={`rounded-full border px-2.5 py-1 ${
                          previewInteraction === "interactive"
                            ? "border-slate-900 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        Interactive
                      </button>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                      <span>Quality</span>
                      <button
                        type="button"
                        onClick={() => setPreviewQuality("standard")}
                        className={`rounded-full border px-2.5 py-1 ${
                          previewQuality === "standard"
                            ? "border-slate-900 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        Standard
                      </button>
                      <button
                        type="button"
                        onClick={() => setPreviewQuality("high")}
                        className={`rounded-full border px-2.5 py-1 ${
                          previewQuality === "high"
                            ? "border-slate-900 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-600"
                        }`}
                      >
                        High
                      </button>
                    </div>
                  </div>
                  {previewMode === "3d" ? (
                    <Preview3DCanvas items={preview3DItems} interactive={previewInteraction === "interactive"} />
                  ) : (
                    <div className="flex min-h-[520px] items-center justify-center overflow-hidden rounded-[20px] bg-white">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={planPreviewUrl}
                        alt="Generated plan preview"
                        className={`max-h-[520px] w-full object-contain shadow-sm ${
                          previewInteraction === "interactive" ? "cursor-zoom-in" : "cursor-default"
                        }`}
                        onClick={() => {
                          if (previewInteraction === "interactive") {
                            setPreviewFullscreenOpen(true);
                          }
                        }}
                      />
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex min-h-[360px] items-center justify-center rounded-[28px] border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">
                  Send a message and Civora AI will generate a plan preview here.
                </div>
              )}

              {previewFullscreenOpen && planPreviewUrl ? (
                <div className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/88 p-4 backdrop-blur-sm">
                  <div className="flex h-full w-full max-w-[96vw] flex-col rounded-[28px] border border-slate-700/60 bg-slate-950 shadow-[0_30px_90px_-40px_rgba(15,23,42,0.95)]">
                    <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-5 py-4 text-white">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
                          Fullscreen Preview
                        </p>
                        <p className="mt-1 text-sm text-slate-200">
                          Inspect the latest engineered plan without the sidebar chrome.
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setPreviewFullscreenOpen(false)}
                        className="inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-100 transition hover:bg-slate-800"
                      >
                        <X className="h-4 w-4" />
                        Close
                      </button>
                    </div>
                    <div className="flex min-h-0 flex-1 items-center justify-center p-4">
                      <div className="relative max-h-full w-full">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={planPreviewUrl}
                          alt="Generated plan preview fullscreen"
                          className="max-h-full w-full rounded-[20px] bg-white object-contain shadow-2xl"
                        />
                        {previewInteraction === "interactive" &&
                        planPreviewAnnotations?.labels?.length ? (
                          <div className="pointer-events-none absolute inset-0">
                            {selectedIssueLabel ? (
                              (() => {
                                const target = planPreviewAnnotations.labels.find(
                                  (item) => item.label === selectedIssueLabel && item.bounds,
                                );
                                if (!target?.bounds) return null;
                                const left = Math.min(Math.max(target.bounds.x1 * 100, 0), 100);
                                const top = Math.min(Math.max(target.bounds.y1 * 100, 0), 100);
                                const right = Math.min(Math.max(target.bounds.x2 * 100, 0), 100);
                                const bottom = Math.min(Math.max(target.bounds.y2 * 100, 0), 100);
                                return (
                                  <div
                                    className="absolute rounded-[12px] border-2 border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_6px_rgba(244,63,94,0.12)]"
                                    style={{
                                      left: `${left}%`,
                                      top: `${top}%`,
                                      width: `${Math.max(right - left, 2)}%`,
                                      height: `${Math.max(bottom - top, 2)}%`,
                                    }}
                                  />
                                );
                              })()
                            ) : null}
                            {planPreviewAnnotations.labels.map((item, idx) => (
                              <div
                                key={`${item.label}-${idx}`}
                                className="group pointer-events-auto absolute"
                                style={{
                                  left: `${Math.min(Math.max(item.x * 100, 0), 100)}%`,
                                  top: `${Math.min(Math.max(item.y * 100, 0), 100)}%`,
                                  transform: "translate(-50%, -50%)",
                                }}
                              >
                                <div
                                  className={`h-2 w-2 rounded-full transition ${
                                    item.label === selectedIssueLabel
                                      ? "bg-rose-500/80 shadow-[0_0_0_6px_rgba(244,63,94,0.15)]"
                                      : "bg-slate-900/30 opacity-0 group-hover:opacity-100"
                                  }`}
                                />
                                <div className="pointer-events-none absolute left-1/2 top-0 z-10 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700 shadow-sm group-hover:block">
                                  {item.label}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {previewInteraction === "interactive" && showMeasurements ? (
                          <div className="pointer-events-none absolute left-6 top-6 w-[240px] rounded-2xl border border-slate-200/70 bg-white/90 p-3 text-xs text-slate-700 shadow-sm backdrop-blur">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                              Measurements
                            </p>
                            <div className="mt-2 space-y-1">
                              {measurementOverlayStats
                                .filter((item) => Number(item.value || 0) > 0)
                                .map((item) => (
                                  <div key={item.label} className="flex items-center justify-between gap-2">
                                    <span>{item.label}</span>
                                    <span className="font-semibold">
                                      {item.unit === "stalls"
                                        ? formatCount(Number(item.value || 0), item.unit)
                                        : formatMetric(Number(item.value || 0), item.unit)}
                                    </span>
                                  </div>
                                ))}
                            </div>
                          </div>
                        ) : null}
                        {previewInteraction === "interactive" && showCalculations ? (
                          <div className="pointer-events-none absolute bottom-6 left-6 w-[240px] rounded-2xl border border-slate-200/70 bg-white/90 p-3 text-xs text-slate-700 shadow-sm backdrop-blur">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                              Calculations
                            </p>
                            <div className="mt-2 space-y-1">
                              {calculationOverlayStats
                                .filter((item) => Number(item.value || 0) > 0)
                                .map((item) => (
                                  <div key={item.label} className="flex items-center justify-between gap-2">
                                    <span>{item.label}</span>
                                    <span className="font-semibold">
                                      {formatMetric(Number(item.value || 0), item.unit)}
                                    </span>
                                  </div>
                                ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {previewReview && (
                <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,1fr)]">
                  <div className="rounded-[24px] border border-slate-200 bg-slate-50/80 p-5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                          Engineering Review
                        </p>
                        <p className="mt-2 text-base font-semibold text-slate-950">
                          Latest run summary
                        </p>
                        {activePreviewPhase ? (
                          <p className="mt-2 text-sm text-slate-600">
                            {activePreviewPhase.label}: {activePreviewPhase.summary}
                          </p>
                        ) : null}
                      </div>
                      <div className="rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-600 shadow-sm ring-1 ring-slate-200">
                        {effectivePreviewUnresolvedCount} unresolved
                      </div>
                    </div>

                    <div className="mt-5 space-y-4">
                      {combinedPreviewPhase ? (
                        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                                Combined View
                              </p>
                              <p className="mt-2 text-sm font-medium text-slate-900">
                                {combinedPreviewPhase.summary}
                              </p>
                            </div>
                            <span
                              className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                                combinedPreviewPhase.status.toLowerCase() === "ready"
                                  ? "bg-emerald-100 text-emerald-700"
                                  : combinedPreviewPhase.status.toLowerCase() === "blocked"
                                    ? "bg-rose-100 text-rose-700"
                                    : combinedPreviewPhase.status.toLowerCase() === "running"
                                      ? "bg-blue-100 text-blue-700"
                                      : "bg-amber-100 text-amber-700"
                              }`}
                            >
                              {toReadableLabel(combinedPreviewPhase.status)}
                            </span>
                          </div>
                          {previewTotalPhaseCount > 0 ? (
                            <div className="mt-4">
                              <div className="flex items-center justify-between gap-3 text-xs font-medium text-slate-500">
                                <span>{previewPhaseHeadline}</span>
                                <span>{previewPhaseProgressPercent}%</span>
                              </div>
                              <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
                                <div
                                  className="h-full rounded-full bg-slate-900 transition-all duration-500"
                                  style={{ width: `${previewPhaseProgressPercent}%` }}
                                />
                              </div>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {previewPhaseEntries.length ? (
                        <div className="rounded-2xl bg-white px-4 py-3 ring-1 ring-slate-200">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                            Phase Progress
                          </p>
                          <div className="mt-3 space-y-2">
                            {previewPhaseEntries
                              .filter((phase) => phase.key !== "combined_view")
                              .map((phase) => (
                              <div
                                key={phase.key}
                                className="flex items-start justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2"
                              >
                                <div className="min-w-0">
                                  <p className="text-sm font-medium text-slate-900">{phase.label}</p>
                                  <p className="mt-1 text-sm text-slate-600">{phase.summary}</p>
                                </div>
                                  <span
                                  className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                                    phase.status.toLowerCase() === "ready" || phase.status.toLowerCase() === "complete"
                                      ? "bg-emerald-100 text-emerald-700"
                                      : phase.status.toLowerCase() === "blocked" || phase.status.toLowerCase() === "failed"
                                        ? "bg-rose-100 text-rose-700"
                                        : phase.status.toLowerCase() === "running"
                                          ? "bg-blue-100 text-blue-700"
                                          : "bg-amber-100 text-amber-700"
                                  }`}
                                >
                                  {toReadableLabel(phase.status)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      <div className="rounded-2xl bg-white px-4 py-3 ring-1 ring-slate-200">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Assumptions
                        </p>
                        <p className="mt-2 text-sm text-slate-700">
                          {previewAssumptionCategories.length
                            ? joinNatural(previewAssumptionCategories, 4)
                            : "No assisted assumptions were recorded on the latest pass."}
                        </p>
                      </div>

                      <div className="rounded-2xl bg-white px-4 py-3 ring-1 ring-slate-200">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Fixes Applied
                        </p>
                        <p className="mt-2 text-sm text-slate-700">
                          {previewFixActions.length
                            ? joinNatural(previewFixActions, 4)
                            : previewFixTargets.length
                              ? joinNatural(previewFixTargets, 4)
                              : "No corrective fix actions were recorded in the latest pass."}
                        </p>
                      </div>

                      <div className="rounded-2xl bg-white px-4 py-3 ring-1 ring-slate-200">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Needs Review
                        </p>
                        <p className="mt-2 text-sm text-slate-700">
                          {previewReviewCategories.length
                            ? joinNatural(previewReviewCategories, 4)
                            : "No major review categories are currently flagged."}
                        </p>
                      </div>

                      <div className="rounded-2xl bg-white px-4 py-3 ring-1 ring-slate-200">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Blockers
                        </p>
                        <p className="mt-2 text-sm text-slate-700">
                          {previewBlockedReasons.length
                            ? joinNatural(previewBlockedReasons, 4)
                            : "No export blockers are currently recorded."}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="rounded-[24px] border border-slate-200 bg-white p-5">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Deliverables
                      </p>
                      <p className="mt-3 text-2xl font-semibold text-slate-950">
                        {(previewReview.ready_deliverables ?? []).length}/
                        {(previewReview.requested_deliverables ?? []).length ||
                          (previewReview.ready_deliverables ?? []).length}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">Requested outputs ready</p>
                      <div className="mt-4 space-y-3 text-sm text-slate-700">
                        <div>
                          <p className="font-medium text-slate-900">Ready now</p>
                          <p className="mt-1 text-slate-600">
                            {previewReadyDeliverables.length
                              ? joinNatural(previewReadyDeliverables, 4)
                              : "No ready deliverables recorded yet."}
                          </p>
                        </div>
                        <div>
                          <p className="font-medium text-slate-900">Still blocked</p>
                          <p className="mt-1 text-slate-600">
                            {previewFailedDeliverables.length
                              ? joinNatural(previewFailedDeliverables, 4)
                              : "No requested deliverables are explicitly failed."}
                          </p>
                        </div>
                        <div>
                          <p className="font-medium text-slate-900">Extra preview outputs</p>
                          <p className="mt-1 text-slate-600">
                            {previewExtraDeliverables.length
                              ? joinNatural(previewExtraDeliverables, 4)
                              : "No extra preview-only outputs were recorded."}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-5">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        What You Need
                      </p>
                      <p className="mt-3 text-sm text-slate-600">{whatYouNeedSummary.note}</p>
                      <div className="mt-4 space-y-3 text-sm text-slate-700">
                        <div>
                          <p className="font-medium text-slate-900">Needed now</p>
                          <p className="mt-1 text-slate-600">
                            {whatYouNeedSummary.neededNow.length
                              ? joinNatural(whatYouNeedSummary.neededNow, 4)
                              : "No critical missing inputs are recorded right now."}
                          </p>
                        </div>
                        <div>
                          <p className="font-medium text-slate-900">Helpful next</p>
                          <p className="mt-1 text-slate-600">
                            {whatYouNeedSummary.supporting.length
                              ? joinNatural(whatYouNeedSummary.supporting, 4)
                              : "No additional supporting files or field references are specifically requested."}
                          </p>
                        </div>
                        <div>
                          <p className="font-medium text-slate-900">Current scope</p>
                          <p className="mt-1 text-slate-600">
                            {whatYouNeedSummary.inScope.length
                              ? joinNatural(whatYouNeedSummary.inScope, 4)
                              : "No active systems are selected yet."}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-5">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Run Stability
                      </p>
                      <p className="mt-3 text-2xl font-semibold text-slate-950">
                        {previewReview.rerun_total ?? 0}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">Reruns across the latest engineering cycle</p>
                      <p className="mt-4 text-sm text-slate-600">
                        {previewRerunSignals.length
                          ? joinNatural(previewRerunSignals, 4)
                          : "No repeated reruns were recorded in the latest pass."}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Issue Navigator
                      </p>
                      <p className="mt-2 text-sm font-medium text-slate-900">
                        Click an issue to highlight the closest system in preview.
                      </p>
                      <div className="mt-3 space-y-2 text-sm text-slate-600">
                        {(issues.length ? issues : defaultIssues).map((issue, idx) => (
                          <button
                            key={`${issue.message}-${idx}`}
                            type="button"
                            onClick={() => {
                              if (previewInteraction !== "interactive") return;
                              setSelectedIssueId(`${issue.message}-${idx}`);
                            }}
                            disabled={previewInteraction !== "interactive"}
                            className={`flex w-full items-start justify-between gap-3 rounded-2xl border px-3 py-2 text-left transition ${
                              selectedIssueId === `${issue.message}-${idx}`
                                ? "border-slate-900 bg-slate-950 text-white"
                                : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                            } ${previewInteraction !== "interactive" ? "cursor-not-allowed opacity-60" : ""}`}
                          >
                            <div className="text-left">
                              <span className="font-medium">{issue.message}</span>
                              {issueTargets[idx]?.label ? (
                                <p className="mt-1 text-[11px] uppercase tracking-[0.12em] opacity-70">
                                  Highlight: {issueTargets[idx]?.label}
                                </p>
                              ) : null}
                            </div>
                            <span className="text-xs uppercase tracking-[0.14em] opacity-60">
                              {issue.severity}
                            </span>
                          </button>
                        ))}
                      </div>
                      <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-500">
                        <span>Allow override</span>
                        <button
                          type="button"
                          className="rounded-full border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-600"
                        >
                          Override
                        </button>
                      </div>
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Engineering Metrics
                      </p>
                      <div className="mt-3 grid gap-2 text-sm text-slate-700">
                        <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                          <span>Total pipe length</span>
                          <span className="font-semibold">
                            {formatMetric(totalPipeLength, "ft")}
                          </span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                          <span>Max slope</span>
                          <span className="font-semibold">
                            {formatMetric(maxSlope, "%")}
                          </span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                          <span>Min slope</span>
                          <span className="font-semibold">
                            {formatMetric(minSlope, "%")}
                          </span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                          <span>Flow (CFS)</span>
                          <span className="font-semibold">
                            {formatMetric(flowCfs, "cfs")}
                          </span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                          <span>Cut / Fill</span>
                          <span className="font-semibold">
                            {formatMetric(cutFillNet, "cf")}
                          </span>
                        </div>
                        <div className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2">
                          <span>Pond size</span>
                          <span className="font-semibold">
                            {formatMetric(basinSize, "sf")}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Design Controls
                      </p>
                      <div className="mt-3 grid gap-3 text-sm text-slate-700">
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Parking count
                          <input
                            type="number"
                            min="0"
                            value={parkingCount}
                            onChange={(event) => setParkingCount(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Building width (ft)
                          <input
                            type="number"
                            min="0"
                            value={buildingWidth}
                            onChange={(event) => setBuildingWidth(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Building count
                          <input
                            type="number"
                            min="0"
                            value={buildingCount}
                            onChange={(event) => setBuildingCount(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Building depth (ft)
                          <input
                            type="number"
                            min="0"
                            value={buildingDepth}
                            onChange={(event) => setBuildingDepth(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Min slope (%)
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={minSlopePct}
                            onChange={(event) => setMinSlopePct(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Max parking slope (%)
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={maxParkingSlopePct}
                            onChange={(event) => setMaxParkingSlopePct(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Max ADA cross slope (%)
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={maxAdaCrossSlopePct}
                            onChange={(event) => setMaxAdaCrossSlopePct(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Max road grade (%)
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={maxRoadGradePct}
                            onChange={(event) => setMaxRoadGradePct(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                        <label className="grid gap-1 text-xs uppercase tracking-[0.14em] text-slate-500">
                          Pipe min slope (%)
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={pipeMinSlopePct}
                            onChange={(event) => setPipeMinSlopePct(event.target.value)}
                            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                          />
                        </label>
                      </div>
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Overlays
                      </p>
                      <div className="mt-3 space-y-2 text-sm text-slate-700">
                        <button
                          type="button"
                          onClick={() => setShowMeasurements((prev) => !prev)}
                          className={`flex w-full items-center justify-between rounded-2xl border px-3 py-2 ${
                            showMeasurements
                              ? "border-slate-900 bg-slate-950 text-white"
                              : "border-slate-200 bg-white text-slate-700"
                          }`}
                        >
                          <span>Measurements overlay</span>
                          <span className="text-xs uppercase tracking-[0.14em]">
                            {showMeasurements ? "On" : "Off"}
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowCalculations((prev) => !prev)}
                          className={`flex w-full items-center justify-between rounded-2xl border px-3 py-2 ${
                            showCalculations
                              ? "border-slate-900 bg-slate-950 text-white"
                              : "border-slate-200 bg-white text-slate-700"
                          }`}
                        >
                          <span>Calculations overlay</span>
                          <span className="text-xs uppercase tracking-[0.14em]">
                            {showCalculations ? "On" : "Off"}
                          </span>
                        </button>
                        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-3 text-xs text-slate-600">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                            Preview Layers
                          </p>
                          <div className="mt-2 grid gap-2">
                            {[
                              { key: "buildings", label: "Buildings" },
                              { key: "roads", label: "Roads + parking" },
                              { key: "grading", label: "Grading contours" },
                              { key: "drainage", label: "Drainage/storm" },
                              { key: "utilities", label: "Utilities" },
                              { key: "structures", label: "Structures + pools" },
                              { key: "lots", label: "Lots + parcels" },
                            ].map((item) => (
                              <button
                                key={item.key}
                                type="button"
                                onClick={() =>
                                  setPreviewLayers((prev) => ({
                                    ...prev,
                                    [item.key]: !prev[item.key as keyof typeof prev],
                                  }))
                                }
                                className={`flex w-full items-center justify-between rounded-2xl border px-3 py-2 text-sm ${
                                  previewLayers[item.key as keyof typeof previewLayers]
                                    ? "border-slate-900 bg-slate-950 text-white"
                                    : "border-slate-200 bg-white text-slate-700"
                                }`}
                              >
                                <span>{item.label}</span>
                                <span className="text-xs uppercase tracking-[0.14em]">
                                  {previewLayers[item.key as keyof typeof previewLayers] ? "On" : "Off"}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Site Inputs
                      </p>
                      <div className="mt-3 space-y-2 text-sm text-slate-700">
                        <button
                          type="button"
                          onClick={() => mapSnapshotInputRef.current?.click()}
                          className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                        >
                          <span>Upload map snapshot</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                            {uploadedImageApiUrl || uploadedImagePreviewUrl ? "Ready" : "Upload"}
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={() => surveyInputRef.current?.click()}
                          className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50"
                        >
                          <span>Import survey file</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                            {surveyFileName ? "Ready" : "Upload"}
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={estimateSurveySlope}
                          disabled={!surveyFileName}
                          className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <span>Estimate slope automatically</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                            {surveySlopeEstimate?.slope_percent ? "Estimated" : "Compute"}
                          </span>
                        </button>
                        <button
                          type="button"
                          onClick={analyzeMapSnapshot}
                          disabled={!mapSnapshotPath}
                          className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <span>Analyze map snapshot</span>
                          <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                            {mapAnalysis?.success ? "Ready" : "Analyze"}
                          </span>
                        </button>
                        {surveyFileName ? (
                          <p className="text-xs text-slate-500">
                            Survey loaded: {surveyFileName}
                          </p>
                        ) : null}
                        {uploadedImageApiUrl || uploadedImagePreviewUrl ? (
                          <p className="text-xs text-slate-500">
                            Map snapshot loaded and ready for interpretation.
                          </p>
                        ) : null}
                        {mapAnalysis?.success ? (
                          <p className="text-xs text-slate-500">
                            Map analysis captured{" "}
                            {(mapAnalysis?.counts as { zones?: number } | undefined)?.zones ?? 0} zones,{" "}
                            {(mapAnalysis?.counts as { objects?: number } | undefined)?.objects ?? 0} objects,{" "}
                            {(mapAnalysis?.counts as { centerlines?: number } | undefined)?.centerlines ?? 0}{" "}
                            centerlines.
                          </p>
                        ) : null}
                        {surveySlopeEstimate?.slope_percent ? (
                          <p className="text-xs text-slate-500">
                            Estimated {surveySlopeEstimate.slope_percent.toFixed(2)}% slope toward{" "}
                            {surveySlopeEstimate.direction || "N/A"} from{" "}
                            {surveySlopeEstimate.point_count ?? 0} points.
                          </p>
                        ) : null}
                      </div>
                      <input
                        ref={mapSnapshotInputRef}
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={async (event) => {
                          const file = event.currentTarget.files?.[0];
                          if (file) {
                            await uploadImage(file);
                          }
                          event.currentTarget.value = "";
                        }}
                      />
                      <input
                        ref={surveyInputRef}
                        type="file"
                        accept=".csv"
                        className="hidden"
                        onChange={async (event) => {
                          const file = event.currentTarget.files?.[0];
                          if (file) {
                            await uploadSurvey(file);
                          }
                          event.currentTarget.value = "";
                        }}
                      />
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Materials &amp; Quantities
                      </p>
                      <p className="mt-2 text-sm text-slate-600">
                        Live takeoffs from the current engineering run.
                      </p>
                      <button
                        type="button"
                        onClick={() => setQuantityRollupsEnabled((prev) => !prev)}
                        className={`mt-3 flex w-full items-center justify-between rounded-2xl border px-3 py-2 text-sm ${
                          quantityRollupsEnabled
                            ? "border-slate-900 bg-slate-950 text-white"
                            : "border-slate-200 bg-white text-slate-700"
                        }`}
                      >
                        <span>Quantity rollups</span>
                        <span className="text-xs uppercase tracking-[0.14em]">
                          {quantityRollupsEnabled ? "On" : "Off"}
                        </span>
                      </button>
                      {quantityRollupsEnabled ? (
                        quantityRows.length ? (
                          <div className="mt-3 grid gap-2 text-sm text-slate-700">
                            {quantityRows.map((row) => (
                              <div
                                key={row.label}
                                className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2"
                              >
                                <span>{row.label}</span>
                                <span className="font-semibold">
                                  {row.unit === "ea" || row.unit === "stalls"
                                    ? formatCount(Number(row.value || 0), row.unit)
                                    : formatMetric(Number(row.value || 0), row.unit)}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="mt-3 text-sm text-slate-500">
                            Quantities will populate once the plan has run through the engine.
                          </p>
                        )
                      ) : null}
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Coverage Scope
                      </p>
                      <div className="mt-3 grid gap-2 text-sm text-slate-700">
                        {[
                          { label: "Roads", status: "Engineering" },
                          { label: "Bridges / structural support", status: "Concept" },
                          { label: "Recreational swimming pools", status: "Concept" },
                          { label: "Subdivisions", status: "Concept" },
                          { label: "Drainage / storm", status: "Engineering" },
                          { label: "Utilities", status: "Engineering" },
                          { label: "Geotechnical support", status: "Concept" },
                          { label: "Environmental / regulatory", status: "Concept" },
                          { label: "Erosion & sediment", status: "Concept" },
                          { label: "Construction workflows", status: "Concept" },
                          { label: "Inspection / operations", status: "Concept" },
                        ].map((item) => (
                          <div
                            key={item.label}
                            className="flex items-center justify-between rounded-2xl border border-slate-200 px-3 py-2"
                          >
                            <span>{item.label}</span>
                            <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                              {item.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-[24px] border border-slate-200 bg-white p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                        Phase Stats
                      </p>
                      <div className="mt-3 grid gap-2 text-sm text-slate-700">
                        {previewPhaseEntries.map((phase) => (
                          <div
                            key={phase.key}
                            className="rounded-2xl border border-slate-200 px-3 py-2"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-medium">{phase.label}</span>
                              <span className="text-xs uppercase tracking-[0.14em] text-slate-400">
                                {phase.status}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-1 text-xs text-slate-500">
                              {(() => {
                                const metrics =
                                  (phaseStats[phase.key as keyof PhaseStats] ?? [])
                                    .filter((item) => Number(item.value || 0) > 0)
                                    .slice(0, 4);
                                if (!metrics.length) {
                                  return (
                                    <p className="text-xs text-slate-500">
                                      Metrics will populate after this phase completes.
                                    </p>
                                  );
                                }
                                return metrics.map((item) => (
                                  <div key={item.label} className="flex items-center justify-between">
                                    <span>{item.label}</span>
                                    <span className="font-semibold text-slate-700">
                                      {item.format === "count"
                                        ? formatCount(Number(item.value || 0), item.unit)
                                        : formatMetric(Number(item.value || 0), item.unit)}
                                    </span>
                                  </div>
                                ));
                              })()}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
