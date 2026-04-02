"use client";

import React, { useEffect, useMemo, useState } from "react";
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
  };
};

type UploadImageResponse = {
  success: boolean;
  image_path?: string;
  image_url?: string;
  filename?: string;
};

type PlanToolMode = "run" | "fix" | "improve";
type StrategyMode = "manual" | "assisted" | "hybrid";
type ChatIntent = "design" | "conversation";
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
    "I’m ready to help you shape this design. Tell me what you want to create, what should change, or what you want me to explain before we finalize.",
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

function summarizePlanResponse(
  data: any,
  mode: PlanToolMode,
): string {
  const plan = data?.final_plan ?? {};
  const meta = plan?.meta ?? {};
  const explanation = meta?.explanation;
  const truth = meta?.truth_audit?.success;
  const unresolved =
    meta?.coordination?.unresolved_conflicts?.length ??
    meta?.coordination?.unresolved_conflicts ??
    0;
  const producedDeliverables = Array.isArray(meta?.deliverables?.produced)
    ? meta.deliverables.produced
    : Array.isArray(meta?.produced_deliverables)
      ? meta.produced_deliverables
      : [];
  const headline =
    typeof explanation?.summary === "string"
      ? explanation.summary
      : typeof explanation?.overview === "string"
        ? explanation.overview
        : typeof data?.message === "string"
          ? data.message
          : mode === "fix"
            ? "I ran a focused fix pass and updated the active design."
            : mode === "improve"
              ? "I ran an improvement pass and updated the active design."
              : "I updated the active design workspace.";
  const why =
    typeof explanation?.why === "string"
      ? explanation.why
      : typeof explanation?.reasoning === "string"
        ? explanation.reasoning
        : null;

  const notes = [
    truth === true ? "Truth checks passed." : "Truth checks need review.",
    `Unresolved conflicts: ${unresolved}.`,
    producedDeliverables.length
      ? `Produced: ${producedDeliverables.slice(0, 4).join(", ")}.`
      : null,
    why,
  ].filter(Boolean);

  return [headline, ...notes].join(" ");
}

function classifyChatIntent(prompt: string): ChatIntent {
  const text = prompt.trim().toLowerCase();
  if (!text) return "conversation";

  const designSignals = [
    "design",
    "create",
    "generate",
    "make",
    "add",
    "move",
    "change",
    "update",
    "shift",
    "reroute",
    "grade",
    "grading",
    "drainage",
    "utility",
    "utilities",
    "storm",
    "sanitary",
    "road",
    "roads",
    "parking",
    "building",
    "basin",
    "detention",
    "site plan",
    "layout",
    "slope",
    "contour",
  ];

  const conversationSignals = [
    "what",
    "why",
    "how",
    "can you explain",
    "are you",
    "should we",
    "do you think",
    "what happened",
    "what does",
    "can you help me understand",
  ];

  const hasDesignSignal = designSignals.some((signal) => text.includes(signal));
  const hasConversationSignal = conversationSignals.some((signal) =>
    text.includes(signal),
  );

  if (hasConversationSignal && !hasDesignSignal) return "conversation";
  if (text.endsWith("?") && !hasDesignSignal) return "conversation";
  return "design";
}

function buildConversationReply({
  prompt,
  siteName,
  projectType,
  currentExplanation,
  currentTruthAudit,
  currentManualFailures,
  issues,
  currentProject,
}: {
  prompt: string;
  siteName: string;
  projectType: string;
  currentExplanation: any;
  currentTruthAudit: any;
  currentManualFailures: any[];
  issues: Issue[];
  currentProject: ProjectRecord | null;
}) {
  const lower = prompt.toLowerCase();
  const explanationText =
    typeof currentExplanation?.summary === "string"
      ? currentExplanation.summary
      : typeof currentExplanation?.overview === "string"
        ? currentExplanation.overview
        : "";

  if (lower.includes("what did") || lower.includes("explain") || lower.includes("why")) {
    if (explanationText) {
      return explanationText;
    }
    return `We’re currently working on ${siteName || "this project"} as a ${projectType.replaceAll("_", " ")} concept. Ask me to generate or change something and I’ll explain the result as we go.`;
  }

  if (lower.includes("warning") || lower.includes("issue") || lower.includes("problem")) {
    if (currentManualFailures.length) {
      return `The main blockers right now are ${currentManualFailures
        .slice(0, 3)
        .map((failure: any) => failure.code || failure.message || "manual validation issue")
        .join(", ")}.`;
    }
    if (issues.length) {
      return `The current review items are ${issues
        .slice(0, 3)
        .map((issue) => issue.message)
        .join("; ")}.`;
    }
    return "I’m not seeing any major review warnings in the current workspace right now.";
  }

  if (lower.includes("trust") || lower.includes("valid") || lower.includes("truth")) {
    const truthPassed = currentTruthAudit?.success;
    return truthPassed
      ? "The current design state is passing the truth audit checks that are exposed in the workspace."
      : "The current design still needs review on one or more truth checks before I’d call it ready.";
  }

  if (lower.includes("project") || lower.includes("working on")) {
    return currentProject
      ? `We’re working inside the saved project "${currentProject.name}" right now.`
      : `We’re in an unsaved working session for ${siteName || "this project"}.`;
  }

  return "I can answer questions about the current design, explain what changed, or make a new design update when you’re ready.";
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

  const [strategyMode, setStrategyMode] = useState<StrategyMode>("hybrid");
  const [projectType, setProjectType] = useState("commercial_pad");
  const [units, setUnits] = useState("ft");
  const [prompt, setPrompt] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [
    createWelcomeMessage(),
  ]);
  const [imageName, setImageName] = useState("");
  const [siteName, setSiteName] = useState("Civora AI Project");
  const [fileName, setFileName] = useState("civora-ai-plan");
  const [lotWidth, setLotWidth] = useState("220");
  const [lotHeight, setLotHeight] = useState("180");
  const [buildingWidth, setBuildingWidth] = useState("100");
  const [buildingDepth, setBuildingDepth] = useState("80");
  const [setback, setSetback] = useState("10");
  const [parkingCount, setParkingCount] = useState("36");
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
  const [projectToOpen, setProjectToOpen] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [activePlanTool, setActivePlanTool] = useState<PlanToolMode>("run");
  const [selectedPlanToolPanel, setSelectedPlanToolPanel] =
    useState<"explain" | "fix" | "improve">("explain");

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
        chat_thread: chatMessages,
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
    setChatMessages((current) => [...current, createChatMessage(role, content, kind)]);
  };

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

    const nextMode = projectInput.input_mode ?? (projectInput.strict_mode ? "manual" : "hybrid");
    if (nextMode === "manual" || nextMode === "assisted" || nextMode === "hybrid") {
      setStrategyMode(nextMode);
    }
    setPrompt(projectInput.prompt_text ?? "");
    setImageName(projectInput.image_path ?? "");
    setUploadedImageApiUrl(
      projectInput.image_path ? uploadedImageSrc(projectInput.image_path, token) : "",
    );
    setUploadedImagePreviewUrl("");
    setSiteName(manualFields.project_name ?? "Civora AI Project");
    setFileName(manualFields.file_name ?? manualFields.project_name ?? "civora-ai-plan");
    setUnits(manualFields.units ?? "ft");
    setProjectType(manualFields.project_type ?? "commercial_pad");
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
    setChatMessages(restoredThread.length ? restoredThread : [createWelcomeMessage()]);
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
    setProjectToOpen((current) =>
      current && nextProjects.some((project) => project.project_id === current)
        ? current
        : nextProjects[0]?.project_id ?? "",
    );
  };

  const refreshJobs = async (authToken = token) => {
    if (!authToken) return;
    const data = await getJson<{ jobs: JobSummary[] }>("/api/jobs", {
      token: authToken,
    });
    setJobs(Array.isArray(data.jobs) ? data.jobs : []);
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
      await refreshJobs(data.token);
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
    const trimmedPrompt = prompt.trim();
    if (mode === "run" && !trimmedPrompt && !imageName) {
      setStatusMessage("Add a request or image so Civora AI has something to work from.");
      return;
    }
    if (mode === "run" && trimmedPrompt) {
      const intent = classifyChatIntent(trimmedPrompt);
      if (intent === "conversation") {
        appendChatMessage("user", trimmedPrompt);
        appendChatMessage(
          "assistant",
          buildConversationReply({
            prompt: trimmedPrompt,
            siteName,
            projectType,
            currentExplanation,
            currentTruthAudit,
            currentManualFailures,
            issues,
            currentProject,
          }),
        );
        setPrompt("");
        setStatusMessage("Civora AI answered your question without rerunning the design.");
        return;
      }
    }
    setBusy(true);
    setActivePlanTool(mode);
    try {
      if (mode === "run" && trimmedPrompt) {
        appendChatMessage("user", trimmedPrompt);
      } else if (mode === "fix") {
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
      const requestPayload =
        mode === "run"
          ? payloadPreview
          : {
              ...payloadPreview,
              full_design_mode: true,
              optimize_goal:
                mode === "fix"
                  ? suggestedImproveGoal ?? "reduce_pipe_length"
                  : suggestedImproveGoal,
              meta: {
                ...((payloadPreview as any).meta ?? {}),
                requested_plan_tool: mode,
              },
            };
      const data = await postJson<any>("/api/orchestrate", requestPayload, {
        token,
      });
      applyBackendResult(data);
      appendChatMessage("assistant", summarizePlanResponse(data, mode));
      await requestPreview(
        {
          result: data,
          filename_stem: fileName || siteName,
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
      if (mode === "run") {
        setPrompt("");
      }
    } catch (error) {
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

  const saveProject = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const data = await postJson<{ project: ProjectRecord }>(
        "/api/projects",
        {
          project_id: projectId || null,
          name: siteName,
          project_input: payloadPreview,
          latest_result: backendResult ?? {},
        },
        { token },
      );
      setProjectId(data.project.project_id);
      setCurrentProject(data.project);
      await refreshProjects();
      setStatusMessage(`Saved project "${data.project.name}".`);
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Project save failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const loadProject = async (id: string) => {
    if (!token) return;
    try {
      const data = await getJson<{ project: ProjectRecord }>(
        `/api/projects/${id}`,
        { token },
      );
      const project = data.project;
      setCurrentProject(project);
      setProjectId(project.project_id);
      setProjectToOpen(project.project_id);
      setSiteName(project.name ?? "Civora AI Project");
      applyProjectInput(project.project_input ?? {});
      if (project.latest_result && Object.keys(project.latest_result).length) {
        applyBackendResult(project.latest_result);
        await requestPreview(
          {
            result: project.latest_result,
            filename_stem: fileName || project.name,
          },
          { silent: true },
        );
      } else {
        setBackendResult(null);
        setPlanPreviewUrl("");
        setPlanPreviewSummary(null);
      }
      setStatusMessage(`Loaded project "${project.name}".`);
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Project load failed.",
      );
    }
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
      setActiveJobId(job.job_id);
      if (job.status === "completed" && job.result) {
        applyBackendResult(job.result);
        await requestPreview(
          {
            result: job.result,
            filename_stem: fileName || siteName,
          },
          { silent: true },
        );
        setStatusMessage(`Job ${job.job_id} completed.`);
        await refreshProjects();
        if (job.project_id) {
          await loadProject(job.project_id);
        }
      } else if (job.status === "failed") {
        setStatusMessage(job.error ?? "Job failed.");
      } else {
        setStatusMessage(`Job ${job.job_id} is ${job.status}.`);
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

    if (!explanationText) {
      setStatusMessage("Run Civora AI first so there is a plan to explain.");
      return;
    }

    appendChatMessage(
      "assistant",
      [
        explanationText,
        typeof currentExplanation?.why === "string" ? currentExplanation.why : null,
      ]
        .filter(Boolean)
        .join(" "),
      "explanation",
    );
    setSelectedPlanToolPanel("explain");
    setStatusMessage("Added the latest plan explanation to the conversation.");
  };

  const handleNewChat = () => {
    setProjectId("");
    setCurrentProject(null);
    setProjectToOpen(projects[0]?.project_id ?? "");
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
    setSiteName("Civora AI Project");
    setFileName("civora-ai-plan");
    setProjectType("commercial_pad");
    setUnits("ft");
    setLotWidth("220");
    setLotHeight("180");
    setBuildingWidth("100");
    setBuildingDepth("80");
    setSetback("10");
    setParkingCount("36");
    setRoads(true);
    setGrading(true);
    setDrainage(true);
    setUtilities(true);
    setStrategyMode("hybrid");
    setChatMessages([createWelcomeMessage()]);
    setStatusMessage("Started a new Civora AI workspace.");
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
      .then(() => Promise.all([refreshProjects(stored), refreshJobs(stored)]))
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
                Civora AI — AI-Powered Civil Engineering Design Platform
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
              onClick={handleNewChat}
              className="flex w-full items-center justify-center rounded-2xl bg-slate-950 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              <MessageSquarePlus className="mr-2 h-4 w-4" />
              New Chat
            </button>
          </div>

          <div className="space-y-6 overflow-y-auto p-4">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Open Project
              </p>
              <select
                value={projectToOpen}
                onChange={(event) => setProjectToOpen(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70"
              >
                <option value="">Select project</option>
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  if (projectToOpen) {
                    void loadProject(projectToOpen);
                  }
                }}
                disabled={!projectToOpen}
                className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Open Project
              </button>
            </div>

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
                    <button
                      key={project.project_id}
                      type="button"
                      onClick={() => void loadProject(project.project_id)}
                      className={`block w-full rounded-2xl px-4 py-3 text-left text-sm transition ${
                        project.project_id === projectId
                          ? "bg-white text-slate-950 shadow-sm ring-1 ring-slate-300"
                          : "bg-transparent text-slate-700 hover:bg-white hover:shadow-sm"
                      }`}
                    >
                      <p className="truncate font-medium">{project.name}</p>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        {project.has_result ? "Saved result" : "Draft"}
                      </p>
                    </button>
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
                onClick={() => void refreshProjects()}
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
                {
                  value: "hybrid",
                  label: "Hybrid",
                  desc: "Balanced workflow",
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

              <select
                value={projectType}
                onChange={(e) => setProjectType(e.target.value)}
                className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-slate-400 focus:ring-4 focus:ring-slate-200/70"
              >
                <option value="commercial_pad">Commercial pad</option>
                <option value="office_site">Office site</option>
                <option value="multifamily_site">Multifamily site</option>
                <option value="industrial_site">Industrial site</option>
                <option value="corridor_roadway">Corridor roadway</option>
                <option value="drainage_network">Drainage network</option>
              </select>

              <TextInput
                value={siteName}
                onChange={(e) => setSiteName(e.target.value)}
                placeholder="Project name"
              />

              <TextInput
                value={fileName}
                onChange={(e) => setFileName(e.target.value)}
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
              <div className="max-h-[420px] space-y-4 overflow-y-auto p-4 md:p-6">
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
                <div className="mb-4 grid gap-3 md:grid-cols-3">
                  <TextInput
                    value={lotWidth}
                    onChange={(e) => setLotWidth(e.target.value)}
                    placeholder="Lot width"
                  />
                  <TextInput
                    value={lotHeight}
                    onChange={(e) => setLotHeight(e.target.value)}
                    placeholder="Lot height"
                  />
                  <TextInput
                    value={parkingCount}
                    onChange={(e) => setParkingCount(e.target.value)}
                    placeholder="Parking count"
                  />
                </div>

                <div className="mb-4 rounded-3xl border border-slate-200 bg-slate-50 p-3">
                  <TextArea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
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
                        disabled={busy}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Fix
                      </button>
                      <button
                        type="button"
                        onClick={() => void runOrchestrator("improve")}
                        disabled={busy}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Improve
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={saveProject}
                        disabled={busy}
                        className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => void runOrchestrator("run")}
                        disabled={busy}
                        className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {busy && activePlanTool === "run" ? "Working..." : "Send"}
                      </button>
                    </div>
                  </div>
                </div>

                {(statusMessage || busy) && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    {busy
                      ? activePlanTool === "fix"
                        ? "Civora AI is running a focused fix pass..."
                        : activePlanTool === "improve"
                          ? "Civora AI is improving the current plan..."
                          : "Civora AI is updating the design..."
                      : statusMessage}
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

              <div className="mt-4 flex flex-wrap gap-2">
                <Pill>{currentProject?.name || siteName}</Pill>
                <Pill>{planPreviewSummary?.units || units}</Pill>
                <Pill>{planPreviewSummary?.action_count ?? 0} actions</Pill>
                <Pill>
                  Truth{" "}
                  {(backendResult?.final_plan?.meta?.truth_audit?.success ??
                    selectedRun?.truth_success)
                    ? "passed"
                    : "review needed"}
                </Pill>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
