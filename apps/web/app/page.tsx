"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  EyeOff,
  FileImage,
  FileText,
  FolderOpen,
  History,
  LogOut,
  Map,
  MessageSquarePlus,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
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
  project_input?: any;
  latest_result?: any;
  metadata?: any;
};

type JobSummary = {
  job_id: string;
  status: string;
  job_type?: string;
  project_id?: string | null;
  updated_at?: number;
  error?: string | null;
  stage?: string;
  stage_detail?: string;
  progress?: number;
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
      produced_deliverables?: string[];
      failed_deliverables?: string[];
      rerun_total?: number;
      rerun_stages?: string[];
      rerun_reasons?: string[];
      release_status?: "ready" | "review" | "blocked" | string;
      release_note?: string;
    };
  };
};

type UploadImageResponse = {
  success: boolean;
  image_path?: string;
  image_url?: string;
  filename?: string;
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
  lotWidth: string;
  lotHeight: string;
  buildingWidth: string;
  buildingDepth: string;
  setback: string;
  parkingCount: string;
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
): ChatMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    createdAt: Date.now(),
    kind,
  };
}

function createWelcomeMessage(): ChatMessage {
  return createChatMessage(
    "assistant",
    "Hi, I’m Civora. I can help you think through a site, answer questions, and turn design requests into a plan when you’re ready. Tell me what you want to change, or just ask me a question first.",
  );
}

function guessProjectTitle(prompt: string): string {
  const cleaned = prompt
    .replace(/\s+/g, " ")
    .replace(/^[^a-zA-Z0-9]+/, "")
    .trim();
  if (!cleaned) return "New Project";

  const normalized = cleaned
    .replace(/^(please|can you|could you|help me|i want to|let's|lets)\s+/i, "")
    .replace(/^(create|design|generate|make|build|update|change|move|add)\s+/i, "")
    .trim();

  const words = normalized.split(" ").filter(Boolean).slice(0, 6);
  const title = words
    .join(" ")
    .replace(/[.?!,:;]+$/g, "")
    .trim();

  if (!title) return "New Project";
  return title.charAt(0).toUpperCase() + title.slice(1);
}

function slugifyFileName(value: string): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "civora-ai-plan";
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
  return value
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

function summarizePlanResponse(
  data: any,
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
      ? assumptionSummary.examples.map((example: any) => ({ field_name: "assumption", reason: String(example || "") }))
      : [];
  const issues = Array.isArray(data?.issues) ? data.issues : [];
  const assumptionExamples = (() => {
    const seen = new Set<string>();
    const formatted = assumptions
      .map((assumption: any) => {
        const field = String(
          assumption?.field_name || assumption?.field || "an input",
        )
          .replace(/_/g, " ")
          .trim();
        const reason = String(assumption?.reason || "").trim();
        const loweredField = field.toLowerCase();
        const loweredReason = reason.toLowerCase();
        if (
          loweredField === "plan" ||
          loweredField === "assumption" ||
          loweredReason === "plan" ||
          loweredReason.includes("planner execution assumption")
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
          .map((example: any) => String(example || "").trim())
          .filter((example: string) => {
            const lowered = example.toLowerCase();
            return Boolean(example) && lowered !== "plan" && !lowered.includes("planner execution assumption");
          })
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
    .map((item: any) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableFixTargets = dominantFixTargets
    .map((item: any) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableReviewCategories = reviewCategories
    .map((item: any) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableBlockedReasons = blockedReasons
    .map((item: any) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableBlockedExports = blockedExports
    .map((item: any) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableProduced = producedDeliverables
    .map((item: any) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const readableFailed = failedDeliverables
    .map((item: any) => toReadableLabel(String(item || "")))
    .filter(Boolean);
  const issueMessages = issues
    .slice(0, 2)
    .map((issue: any) => String(issue?.message || "").trim())
    .filter(Boolean);

  const notes = [
    assumptionExamples.length
      ? `I used assisted assumptions for ${joinNatural(assumptionExamples)}.`
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

function SelectField({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70"
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`relative h-7 w-12 rounded-full transition ${
        checked ? "bg-slate-900" : "bg-slate-300/90"
      }`}
    >
      <span
        className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow-[0_4px_12px_rgba(15,23,42,0.22)] transition ${
          checked ? "left-6" : "left-1"
        }`}
      />
    </button>
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

function buildThinkingState({
  busy,
  activePlanTool,
  activeJobStatus,
  activeJobStage,
  activeJobDetail,
  activeJobProgress,
  statusMessage,
}: {
  busy: boolean;
  activePlanTool: PlanToolMode;
  activeJobStatus?: string;
  activeJobStage?: string;
  activeJobDetail?: string;
  activeJobProgress?: number;
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

  if (normalizedJobStatus && stageLabel) {
    return {
      label: stageLabel,
      detail:
        stageDetail ||
        (normalizedJobStatus === "queued"
          ? "Civora queued the run and is waiting for a worker to pick it up."
          : "Civora is processing the design in the background now."),
      progress: numericProgress ?? (normalizedJobStatus === "queued" ? 12 : 48),
    };
  }

  if (normalizedJobStatus === "queued") {
    return {
      label: "Queued",
      detail: "Civora queued the run and is waiting for a worker to pick it up.",
      progress: 18,
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
  const [imageName, setImageName] = useState("");
  const [siteName, setSiteName] = useState("");
  const [fileName, setFileName] = useState("");
  const [siteNameAuto, setSiteNameAuto] = useState(false);
  const [fileNameAuto, setFileNameAuto] = useState(false);
  const [lotWidth, setLotWidth] = useState("");
  const [lotHeight, setLotHeight] = useState("");
  const [buildingWidth, setBuildingWidth] = useState("");
  const [buildingDepth, setBuildingDepth] = useState("");
  const [setback, setSetback] = useState("");
  const [parkingCount, setParkingCount] = useState("");
  const [roads, setRoads] = useState(true);
  const [grading, setGrading] = useState(true);
  const [drainage, setDrainage] = useState(true);
  const [utilities, setUtilities] = useState(true);

  const [assumptions, setAssumptions] =
    useState<Assumption[]>(defaultAssumptions);
  const [issues, setIssues] = useState<Issue[]>(defaultIssues);
  const [backendResult, setBackendResult] = useState<any>(null);
  const [uploadedImagePreviewUrl, setUploadedImagePreviewUrl] = useState("");
  const [uploadedImageApiUrl, setUploadedImageApiUrl] = useState("");
  const [planPreviewUrl, setPlanPreviewUrl] = useState("");
  const [planPreviewSummary, setPlanPreviewSummary] =
    useState<PreviewResponse["summary"] | null>(null);
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectRecord | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activePlanTool, setActivePlanTool] = useState<PlanToolMode>("run");
  const [selectedPlanToolPanel, setSelectedPlanToolPanel] =
    useState<"explain" | "fix" | "improve">("explain");
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const runSubmissionRef = useRef(false);
  const lastJobStatusRef = useRef<Record<string, string>>({});
  const chatMessagesRef = useRef<ChatMessage[]>([createWelcomeMessage()]);

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

  const payloadPreview = useMemo(
    () => ({
      input_mode: strategyMode,
      strict_mode: strategyMode === "manual",
      prompt_text: prompt || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
      },
      manual_fields: {
        project_name: siteName,
        file_name: fileName,
        units,
        project_type: projectType,
        lot: {
          x: 0,
          y: 0,
          w: Number(lotWidth || 0),
          h: Number(lotHeight || 0),
        },
        setback: Number(setback || 0),
        building_width: Number(buildingWidth || 0),
        building_depth: Number(buildingDepth || 0),
        site_plan: {
          parking_count: Number(parkingCount || 0),
        },
        disciplines: [
          roads ? "corridor" : null,
          grading ? "grading" : null,
          drainage ? "drainage" : null,
          utilities ? "utility" : null,
        ].filter(Boolean),
      },
      allow_ai_fill_for_blanks: strategyMode !== "manual",
    }),
    [
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
      parkingCount,
      roads,
      grading,
      drainage,
      utilities,
      chatMessages,
    ],
  );

  const artifactPayload = useMemo(() => {
    if (
      backendResult &&
      typeof backendResult === "object" &&
      Object.keys(backendResult).length
    ) {
      return {
        result: backendResult,
        filename_stem: fileName || siteName,
      };
    }

    return {
      project_id: projectId || null,
      filename_stem: fileName || siteName,
    };
  }, [backendResult, fileName, projectId, siteName]);

  const workflowRuns = useMemo<WorkflowRunSummary[]>(
    () =>
      Array.isArray(currentProject?.metadata?.workflow?.runs)
        ? currentProject?.metadata?.workflow?.runs
        : [],
    [currentProject],
  );

  const workflowArtifacts = useMemo<WorkflowArtifact[]>(
    () =>
      Array.isArray(currentProject?.metadata?.workflow?.artifacts)
        ? currentProject?.metadata?.workflow?.artifacts
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
          ["queued", "running", "cancelling"].includes(String(job.status || "").toLowerCase()),
      ) ?? null,
    [jobs, projectId],
  );
  const visibleActiveJob = useMemo(
    () => (projectId ? currentProjectActiveJob : activeJob),
    [activeJob, currentProjectActiveJob, projectId],
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
        statusMessage,
      }),
    [busy, visibleActiveJob?.status, visibleActiveJob?.stage, visibleActiveJob?.stage_detail, visibleActiveJob?.progress, activePlanTool, statusMessage],
  );
  const latestRunComparison = useMemo(() => {
    if (workflowRuns.length < 2) return null;
    const current = workflowRuns[0];
    const previous = workflowRuns[1];
    return {
      current,
      previous,
      trustDelta:
        (current.engineering_status?.trust_score ?? 0) -
        (previous.engineering_status?.trust_score ?? 0),
      unresolvedDelta:
        (current.coordination_summary?.unresolved_conflicts ?? 0) -
        (previous.coordination_summary?.unresolved_conflicts ?? 0),
      producedDelta:
        (current.produced_deliverables?.length ?? 0) -
        (previous.produced_deliverables?.length ?? 0),
    };
  }, [workflowRuns]);

  const currentPlanMeta = useMemo(() => backendResult?.final_plan?.meta ?? {}, [backendResult]);
  const currentTruthAudit = useMemo(
    () => currentPlanMeta?.truth_audit ?? {},
    [currentPlanMeta],
  );
  const currentManualFailures = useMemo(
    () =>
      Array.isArray(currentPlanMeta?.manual_validation?.failures)
        ? currentPlanMeta.manual_validation.failures
        : [],
    [currentPlanMeta],
  );
  const currentCoordination = useMemo(
    () => currentPlanMeta?.coordination ?? {},
    [currentPlanMeta],
  );
  const currentExplanation = useMemo(
    () => currentPlanMeta?.explanation ?? {},
    [currentPlanMeta],
  );
  const currentIterations = useMemo(
    () =>
      Array.isArray(backendResult?.metadata?.iterations)
        ? backendResult.metadata.iterations
        : Array.isArray(currentPlanMeta?.iterations)
          ? currentPlanMeta.iterations
          : [],
    [backendResult, currentPlanMeta],
  );
  const suggestedImproveGoal = useMemo(() => {
    const failureBlob = [
      ...currentManualFailures.map((failure: any) =>
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

  const applyBackendResult = (data: any) => {
    setBackendResult(data);
    setPlanPreviewUrl("");
    setPlanPreviewSummary(null);
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
  ) => {
    setChatMessages((current) => {
      const next = [...current, createChatMessage(role, content, kind)];
      chatMessagesRef.current = next;
      return next;
    });
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

  const applyProjectInput = (projectInput: any) => {
    if (!projectInput || typeof projectInput !== "object") {
      return;
    }

    const manualFields = projectInput.manual_fields ?? {};
    const lot = manualFields.lot ?? {};
    const sitePlan = manualFields.site_plan ?? {};
    const disciplines = Array.isArray(manualFields.disciplines)
      ? manualFields.disciplines
      : [];
    const restoredThread = Array.isArray(projectInput.meta?.chat_thread)
      ? projectInput.meta.chat_thread
          .filter((message: any) => message && typeof message.content === "string")
          .map((message: any) => ({
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
    setParkingCount(String(sitePlan.parking_count ?? ""));
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
    if (typeof overrides.lotWidth === "string") setLotWidth(overrides.lotWidth);
    if (typeof overrides.lotHeight === "string") setLotHeight(overrides.lotHeight);
    if (typeof overrides.buildingWidth === "string") setBuildingWidth(overrides.buildingWidth);
    if (typeof overrides.buildingDepth === "string") setBuildingDepth(overrides.buildingDepth);
    if (typeof overrides.setback === "string") setSetback(overrides.setback);
    if (typeof overrides.parkingCount === "string") setParkingCount(overrides.parkingCount);
  };

  const buildChatDecisionContext = (
    overrides: ControlOverrides = {},
    message: string,
  ) => {
    const nextStrategy = overrides.strategyMode ?? strategyMode;
    const liveThread = chatMessagesRef.current;
    const designMemory = extractDesignMemory(liveThread);
    return {
      strategy_mode: nextStrategy,
      site_name: overrides.siteName ?? siteName,
      file_name: overrides.fileName ?? fileName,
      project_type: overrides.projectType ?? projectType,
      units: overrides.units ?? units,
      lot_width: overrides.lotWidth ?? lotWidth,
      lot_height: overrides.lotHeight ?? lotHeight,
      parking_count: overrides.parkingCount ?? parkingCount,
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
        ...designMemory,
        examples: [...designMemory.preferences, ...designMemory.constraints].slice(-8),
      },
      chat_thread: [
        ...liveThread,
        createChatMessage("user", message),
      ].map(({ role, content, kind }) => ({ role, content, kind })),
    };
  };

  const buildPayloadFromOverrides = (
    overrides: ControlOverrides = {},
    promptOverride?: string,
  ) => {
    const nextStrategy = overrides.strategyMode ?? strategyMode;
    const nextSiteName = overrides.siteName ?? siteName;
    const nextFileName = overrides.fileName ?? fileName;
    const nextUnits = overrides.units ?? units;
    const nextProjectType = overrides.projectType ?? projectType;
    const nextRoads = overrides.roads ?? roads;
    const nextGrading = overrides.grading ?? grading;
    const nextDrainage = overrides.drainage ?? drainage;
    const nextUtilities = overrides.utilities ?? utilities;

    return {
      input_mode: nextStrategy,
      strict_mode: nextStrategy === "manual",
      prompt_text: (promptOverride ?? prompt) || null,
      image_path: imageName || null,
      meta: {
        chat_thread: chatMessagesRef.current,
      },
      manual_fields: {
        project_name: nextSiteName,
        file_name: nextFileName,
        units: nextUnits,
        project_type: nextProjectType,
        lot: {
          x: 0,
          y: 0,
          w: Number((overrides.lotWidth ?? lotWidth) || 0),
          h: Number((overrides.lotHeight ?? lotHeight) || 0),
        },
        setback: Number((overrides.setback ?? setback) || 0),
        building_width: Number((overrides.buildingWidth ?? buildingWidth) || 0),
        building_depth: Number((overrides.buildingDepth ?? buildingDepth) || 0),
        site_plan: {
          parking_count: Number((overrides.parkingCount ?? parkingCount) || 0),
        },
        disciplines: [
          nextRoads ? "corridor" : null,
          nextGrading ? "grading" : null,
          nextDrainage ? "drainage" : null,
          nextUtilities ? "utility" : null,
        ].filter(Boolean),
      },
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
    assistantPrefix,
    clearPromptOnSuccess = false,
  }: {
    mode: PlanToolMode;
    requestPayload: any;
    assistantPrefix?: string | null;
    clearPromptOnSuccess?: boolean;
  }) => {
    setBusy(true);
    setActivePlanTool(mode);
    try {
      const data = await postJson<any>("/api/orchestrate", requestPayload, {
        token,
      });
      applyBackendResult(data);
      appendChatMessage(
        "assistant",
        [assistantPrefix, summarizePlanResponse(data, mode)].filter(Boolean).join(" "),
      );
      await requestPreview(
        {
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
      const looksLikeConnectivityFailure = isConnectivityFailureMessage(errorMessage);
      if (looksLikeConnectivityFailure && token) {
        try {
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id: projectId || null,
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
      setBusy(false);
      setActivePlanTool("run");
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
    setProjects(nextProjects);
  };

  const refreshJobs = async (
    authToken = token,
    { suppressError = false }: { suppressError?: boolean } = {},
  ) => {
    if (!authToken) return;
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
      refreshJobs(token, { suppressError: true }),
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
          ["queued", "running", "cancelling"].includes(
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
      await executePlanAction({
        mode,
        requestPayload: {
          ...buildPayloadFromOverrides(),
          full_design_mode: true,
          optimize_goal:
            mode === "fix"
              ? suggestedImproveGoal ?? "reduce_pipe_length"
              : suggestedImproveGoal,
          meta: {
            ...(buildPayloadFromOverrides() as any).meta,
            requested_plan_tool: mode,
          },
        },
      });
      return;
    }

    runSubmissionRef.current = true;
    setBusy(true);
    setActivePlanTool("run");
    setPrompt("");
    appendChatMessage("user", trimmedPrompt);
    setStatusMessage("Civora AI is reviewing your request and starting the design run.");
    try {
      await ensureProjectDraft(trimmedPrompt);
      const decision = await postJson<ChatDecisionResponse>(
        "/api/chat/decide",
        {
          message: trimmedPrompt,
          context: buildChatDecisionContext({}, trimmedPrompt),
        },
        { token },
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
        await executePlanAction({
          mode: resolvedMode,
          requestPayload: {
            ...buildPayloadFromOverrides(overrides),
            full_design_mode: true,
            optimize_goal:
              resolvedMode === "fix"
                ? suggestedImproveGoal ?? "reduce_pipe_length"
                : suggestedImproveGoal,
            meta: {
              ...(buildPayloadFromOverrides(overrides) as any).meta,
              requested_plan_tool: resolvedMode,
              chat_decision_reason: decision.reason,
            },
          },
          assistantPrefix: decision.assistant_message,
          clearPromptOnSuccess: true,
        });
        await saveProject({
          silent: true,
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
          nameOverride: generatedTitle || undefined,
          fileNameOverride: generatedFileName || undefined,
          autoNamedOverride: shouldAutoName,
          autoFileNamedOverride: shouldAutoFileName,
        });
        setBusy(false);
        setActivePlanTool("run");
        return;
      }

      await executePlanAction({
        mode: "run",
        requestPayload: {
          ...buildPayloadFromOverrides(overrides, decision.design_prompt || trimmedPrompt),
          meta: {
            ...(buildPayloadFromOverrides(overrides, decision.design_prompt || trimmedPrompt) as any).meta,
            chat_decision_reason: decision.reason,
            chat_decision_confidence: decision.confidence,
          },
        },
        assistantPrefix: decision.assistant_message,
        clearPromptOnSuccess: true,
      });
      await saveProject({
        silent: true,
        nameOverride: generatedTitle || undefined,
        fileNameOverride: generatedFileName || undefined,
        autoNamedOverride: shouldAutoName,
        autoFileNamedOverride: shouldAutoFileName,
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "";
      if (token && isConnectivityFailureMessage(errorMessage)) {
        try {
          const fallbackPayload = buildPayloadFromOverrides({}, trimmedPrompt);
          const queued = await postJson<{ job: JobSummary }>(
            "/api/jobs/orchestrate",
            {
              project_id: projectId || null,
              request: fallbackPayload,
            },
            { token },
          );
          setActiveJobId(queued.job.job_id);
          appendChatMessage(
            "assistant",
            `The live request could not stay connected long enough to finish the first pass, so I queued it in the background instead. Job ${queued.job.job_id} is now running and I’ll pick it up when it finishes.`,
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
    }
  };

  const queueJob = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const data = await postJson<{ job: JobSummary }>(
        "/api/jobs/orchestrate",
        {
          project_id: projectId || null,
          request: payloadPreview,
        },
        { token },
      );
      setActiveJobId(data.job.job_id);
      setStatusMessage(`Queued job ${data.job.job_id}.`);
      await refreshJobs();
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Job queue failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleSendMessage = () => {
    void runOrchestrator("run");
  };

  const handleCancelActiveJob = async () => {
    if (!token || !visibleActiveJob?.job_id) return;
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
    projectInputOverride?: any;
    latestResultOverride?: any;
    autoNamedOverride?: boolean;
    autoFileNamedOverride?: boolean;
  } = {}) => {
    if (!token) return;
    if (!silent) setBusy(true);
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
    try {
      const data = await postJson<{ project: ProjectRecord }>(
        "/api/projects",
        {
          project_id:
            projectIdOverride !== undefined ? projectIdOverride : projectId || null,
          name: resolvedName,
          project_input: projectInputToSave,
          latest_result: latestResultOverride ?? backendResult ?? {},
          metadata: {
            auto_named: autoNamedOverride ?? siteNameAuto,
            auto_file_named: autoFileNamedOverride ?? fileNameAuto,
          },
        },
        { token },
      );
      setProjectId(data.project.project_id);
      setCurrentProject(data.project);
      await refreshProjects();
      if (!silent) {
        setStatusMessage(
          `Saved project "${data.project.name || resolvedName || "Untitled Project"}".`,
        );
      }
    } catch (error) {
      if (!silent) {
        setStatusMessage(
          error instanceof Error ? error.message : "Project save failed.",
        );
      }
    } finally {
      if (!silent) setBusy(false);
    }
  };

  const loadProject = async (id: string) => {
    if (!token) return;
    try {
      setStatusMessage("Loading project...");
      const data = await getJson<{ project: ProjectRecord }>(
        `/api/projects/${id}`,
        { token },
      );
      const project = data.project;
      setCurrentProject(project);
      setProjectId(project.project_id);
      setSiteName(project.name ?? "");
      applyProjectInput(project.project_input ?? {});
      if (project.latest_result && Object.keys(project.latest_result).length) {
        applyBackendResult(project.latest_result);
        await requestPreview(
          {
            result: project.latest_result,
            filename_stem: fileName || project.name || "civora-ai-plan",
          },
          { silent: true },
        );
      } else {
        setBackendResult(null);
        setPlanPreviewUrl("");
        setPlanPreviewSummary(null);
      }
      setStatusMessage(`Loaded project "${project.name}".`);
      void refreshJobs(token, { suppressError: true });
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Project load failed.",
      );
    }
  };

  const ensureProjectDraft = async (initialPrompt?: string) => {
    if (!token || projectId) return;
    await saveProject({
      silent: true,
      projectIdOverride: null,
      nameOverride: siteName.trim(),
      fileNameOverride: fileName.trim(),
      autoNamedOverride: false,
      autoFileNamedOverride: false,
    });
  };

  const deleteProject = async (id: string) => {
    if (!token) return;
    try {
      await deleteJson(`/api/projects/${id}`, { token });
      if (projectId === id) {
        setProjectId("");
        setCurrentProject(null);
      }
      await refreshProjects();
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
      const data = await getJson<{ job: any }>(`/api/jobs/${id}`, { token });
      const job = data.job;
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
      if (previousStatus !== job.status) {
        lastJobStatusRef.current[job.job_id] = job.status;
        if (job.status === "queued") {
          appendChatMessage(
            "assistant",
            `Job ${job.job_id} is queued and waiting to run in the background.`,
            "status",
          );
        } else if (job.status === "running") {
          appendChatMessage(
            "assistant",
            `Job ${job.job_id} is running in the background now.`,
            "status",
          );
        } else if (job.status === "cancelling") {
          appendChatMessage(
            "assistant",
            `Job ${job.job_id} is cancelling now.`,
            "status",
          );
        }
      }
      if (job.status === "completed" && job.result) {
        applyBackendResult(job.result);
        await requestPreview(
          {
            result: job.result,
            filename_stem: fileName || siteName,
          },
          { silent: true },
        );
        appendChatMessage(
          "assistant",
          summarizePlanResponse(job.result, "run"),
          "message",
        );
        setStatusMessage(`Job ${job.job_id} completed.`);
        setActiveJobId("");
        await refreshProjects();
        if (job.project_id) {
          await loadProject(job.project_id);
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
      setStatusMessage("Image uploaded.");
    } catch (error) {
      setImageName(file.name);
      setStatusMessage(
        error instanceof Error ? error.message : "Image upload failed.",
      );
    }
  };

  const requestPreview = async (
    payload: any,
    options?: { silent?: boolean },
  ) => {
    if (!token) return;
    const data = await postJson<PreviewResponse>("/api/preview", payload, {
      token,
    });
    setPlanPreviewUrl(data.preview_image_data_url);
    setPlanPreviewSummary(data.summary ?? null);
    if (!options?.silent) {
      setStatusMessage("Plan preview generated.");
    }
  };

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
            .map((failure: any) => failure.code || failure.message || "manual validation issue")
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
    setSelectedPlanToolPanel("explain");
    setStatusMessage("Added the latest plan explanation to the conversation.");
  };

  const handleNewProject = async () => {
    setProjectId("");
    setCurrentProject(null);
    setSelectedRunId("");
    setActiveJobId("");
    setPrompt("");
    setImageName("");
    setUploadedImageApiUrl("");
    setUploadedImagePreviewUrl("");
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
    setSetback("");
    setParkingCount("");
    setRoads(true);
    setGrading(true);
    setDrainage(true);
    setUtilities(true);
    setStrategyMode("assisted");
    const nextThread = [createWelcomeMessage()];
    chatMessagesRef.current = nextThread;
    setChatMessages(nextThread);
    setStatusMessage("Started a new project.");
    if (token) {
      await saveProject({
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
      await refreshProjects();
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

  const downloadSavedArtifact = async (artifact: WorkflowArtifact) => {
    if (!token || !artifact.download_path) return;
    try {
      const response = await fetch(toApiUrl(artifact.download_path), {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        throw new Error(`Artifact download failed with status ${response.status}`);
      }
      const blob = await response.blob();
      downloadBlob(blob, artifact.filename || "artifact");
      setStatusMessage(`Downloaded ${artifact.filename || "artifact"}.`);
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Artifact download failed.",
      );
    }
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
      if (projectId) {
        await loadProject(projectId);
      }
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
      if (projectId) {
        await loadProject(projectId);
      }
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
    const interval = window.setInterval(() => {
      void loadJob(activeJobId);
      void refreshJobs();
    }, 3000);
    return () => window.clearInterval(interval);
  }, [token, activeJobId]);

  useEffect(() => {
    if (currentProjectActiveJob && currentProjectActiveJob.job_id !== activeJobId) {
      setActiveJobId(currentProjectActiveJob.job_id);
      return;
    }
    if (
      projectId &&
      activeJob &&
      activeJob.project_id === projectId &&
      !["queued", "running", "cancelling"].includes(String(activeJob.status || "").toLowerCase())
    ) {
      setActiveJobId("");
    }
  }, [activeJob, activeJobId, currentProjectActiveJob, projectId]);

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
                      <div className="mt-4 flex justify-end">
                        <button
                          type="button"
                          onClick={handleCancelActiveJob}
                          disabled={String(visibleActiveJob.status || "").toLowerCase() === "cancelling"}
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {String(visibleActiveJob.status || "").toLowerCase() === "cancelling"
                            ? "Cancelling..."
                            : "Cancel"}
                        </button>
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
                        if (!busy && !visibleActiveJob && (prompt.trim() || imageName)) {
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
                        disabled={busy || Boolean(visibleActiveJob)}
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
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-950">Live Preview</p>
                  <p className="mt-1 text-sm text-slate-500">
                    Preview stays centered and updates alongside the conversation.
                  </p>
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
                <div className="flex min-h-[560px] items-center justify-center overflow-hidden rounded-[28px] border border-slate-200 bg-[radial-gradient(circle_at_top,#f8fafc_0%,#eef2f7_100%)] p-4">
                  <img
                    src={planPreviewUrl}
                    alt="Generated plan preview"
                    className="max-h-[520px] w-full object-contain"
                  />
                </div>
              ) : (
                <div className="flex min-h-[360px] items-center justify-center rounded-[28px] border border-dashed border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-500">
                  Send a message and Civora AI will generate a plan preview here.
                </div>
              )}

              {planPreviewSummary?.review && (
                <div
                  className={`mt-4 rounded-2xl border px-4 py-3 text-sm ${
                    planPreviewSummary.review.release_status === "ready"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                      : planPreviewSummary.review.release_status === "blocked"
                        ? "border-amber-200 bg-amber-50 text-amber-900"
                        : "border-slate-200 bg-slate-50 text-slate-700"
                  }`}
                >
                  <p className="font-semibold">
                    {planPreviewSummary.review.release_status === "ready"
                      ? "Release Review: Ready"
                      : planPreviewSummary.review.release_status === "blocked"
                        ? "Release Review: Blocked"
                        : "Release Review: Needs Review"}
                  </p>
                  <p className="mt-1 text-xs">
                    {planPreviewSummary.review.release_note ||
                      "Preview review summary is available for the latest engineering pass."}
                  </p>
                </div>
              )}

              {planPreviewSummary?.review && (
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Assumptions
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                      {planPreviewSummary.review.assumption_count ?? 0} recorded
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {(planPreviewSummary.review.assumption_categories ?? [])
                        .slice(0, 3)
                        .join(", ") || "No assisted assumptions recorded."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Fixes Applied
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                      {(planPreviewSummary.review.autofix_actions ?? []).length} fix actions
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {(planPreviewSummary.review.autofix_actions ?? [])
                        .slice(0, 2)
                        .join(", ") ||
                        (planPreviewSummary.review.dominant_fix_targets ?? [])
                          .slice(0, 2)
                          .join(", ") ||
                        "No fix actions recorded in the latest pass."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Needs Review
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                      {planPreviewSummary.review.unresolved_conflict_count ?? 0} unresolved
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {(planPreviewSummary.review.review_categories ?? [])
                        .slice(0, 3)
                        .join(", ") || "No outstanding review categories recorded."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Blocked
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                      {(planPreviewSummary.review.blocked_exports ?? []).length} blocked outputs
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {(planPreviewSummary.review.blocked_reasons ?? [])
                        .slice(0, 2)
                        .join(", ") || "No export blockers recorded."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Deliverables
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                      {(planPreviewSummary.review.produced_deliverables ?? []).length}/
                      {(planPreviewSummary.review.requested_deliverables ?? []).length ||
                        (planPreviewSummary.review.produced_deliverables ?? []).length} ready
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {(planPreviewSummary.review.failed_deliverables ?? []).length
                        ? `Failed: ${(planPreviewSummary.review.failed_deliverables ?? [])
                            .slice(0, 2)
                            .join(", ")}`
                        : (planPreviewSummary.review.produced_deliverables ?? [])
                            .slice(0, 2)
                            .join(", ") || "No deliverables recorded yet."}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Stability
                    </p>
                    <p className="mt-2 text-sm font-medium text-slate-900">
                      {planPreviewSummary.review.rerun_total ?? 0} reruns
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {(planPreviewSummary.review.rerun_stages ?? [])
                        .slice(0, 2)
                        .join(", ") ||
                        (planPreviewSummary.review.rerun_reasons ?? [])
                          .slice(0, 2)
                          .join(", ") ||
                        "No repeated reruns recorded."}
                    </p>
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
