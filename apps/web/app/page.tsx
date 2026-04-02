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
    setBusy(true);
    setActivePlanTool(mode);
    try {
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
    } catch (error) {
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
    <div className="min-h-screen bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] p-4 md:p-6">
      <div className="mx-auto mb-6 flex max-w-[1600px] flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-sm text-slate-500">Signed in as {user.email}</p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">
            Civora AI — AI-Powered Civil Engineering Design Platform
          </h1>
          <p className="max-w-3xl text-sm leading-6 text-slate-600">
            Enter a request, generate a coordinated civil concept, and review the
            plan with a stable preview-first workspace.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <SmallButton variant="secondary" onClick={handleNewChat}>
            <MessageSquarePlus className="mr-2 h-4 w-4" />
            New Chat
          </SmallButton>
          <SmallButton variant="secondary" onClick={() => void refreshProjects()}>
            <History className="mr-2 h-4 w-4" />
            Refresh History
          </SmallButton>
          <SmallButton variant="secondary" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign Out
          </SmallButton>
        </div>
      </div>

      <div className="mx-auto grid max-w-[1600px] items-start gap-6 xl:grid-cols-[280px_minmax(0,1.2fr)_360px]">
        <motion.aside
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-3rem)] xl:overflow-y-auto xl:pr-1"
        >
          <Card>
            <CardHeader>
              <SectionTitle
                icon={FolderOpen}
                title="Project Access"
                desc="Open saved work, start fresh, and keep files organized."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              <Field label="Open project">
                <div className="space-y-2">
                  <select
                    value={projectToOpen}
                    onChange={(event) => setProjectToOpen(event.target.value)}
                    className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                  >
                    <option value="">Select project</option>
                    {projects.map((project) => (
                      <option key={project.project_id} value={project.project_id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                  <SmallButton
                    variant="secondary"
                    onClick={() => {
                      if (projectToOpen) {
                        void loadProject(projectToOpen);
                      }
                    }}
                    disabled={!projectToOpen}
                  >
                    <FolderOpen className="mr-2 h-4 w-4" />
                    Open Project
                  </SmallButton>
                </div>
              </Field>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Saved Projects
                </p>
                <div className="max-h-[260px] space-y-2 overflow-y-auto pr-1">
                  {projects.length === 0 ? (
                    <p className="text-sm text-slate-500">No saved projects yet.</p>
                  ) : (
                    projects.map((project) => (
                      <button
                        key={project.project_id}
                        type="button"
                        onClick={() => void loadProject(project.project_id)}
                        className={`block w-full rounded-2xl border px-4 py-3 text-left transition ${
                          project.project_id === projectId
                            ? "border-slate-900 bg-slate-50 shadow-sm"
                            : "border-black/10 bg-white hover:bg-slate-50"
                        }`}
                      >
                        <p className="truncate text-sm font-medium text-slate-900">
                          {project.name}
                        </p>
                        <p className="mt-1 truncate text-xs text-slate-500">
                          {project.has_result ? "Saved result available" : "Draft only"}
                        </p>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle
                icon={MessageSquarePlus}
                title="Session"
                desc="Keep the current workspace context clear and easy to reset."
              />
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-2xl border border-black/10 bg-slate-50 px-4 py-3">
                <p className="text-sm font-medium text-slate-900">
                  {currentProject?.name || siteName}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {projectId ? "Active saved project" : "Unsaved working session"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Pill>Mode {strategyMode}</Pill>
                <Pill>{projectType.replaceAll("_", " ")}</Pill>
                <Pill>{units}</Pill>
              </div>
              <SmallButton variant="secondary" onClick={handleNewChat}>
                <MessageSquarePlus className="mr-2 h-4 w-4" />
                New Chat
              </SmallButton>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle
                icon={History}
                title="History"
                desc="Recent runs for the active project."
              />
            </CardHeader>
            <CardContent className="space-y-3">
              {!projectId ? (
                <p className="text-sm text-slate-500">
                  Open a project to browse its saved run history.
                </p>
              ) : workflowRuns.length === 0 ? (
                <p className="text-sm text-slate-500">No runs saved yet for this project.</p>
              ) : (
                <div className="max-h-[420px] space-y-3 overflow-y-auto pr-1">
                  {workflowRuns.map((run) => (
                    <button
                      key={run.run_id}
                      type="button"
                      onClick={() => setSelectedRunId(run.run_id)}
                      className={`block w-full rounded-2xl border px-4 py-3 text-left transition ${
                        selectedRun?.run_id === run.run_id
                          ? "border-slate-900 bg-slate-50 shadow-sm"
                          : "border-black/10 bg-white hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium text-slate-900">
                          {run.success ? "Completed run" : "Failed run"}
                        </p>
                        <Pill>{run.success ? "Pass" : "Fail"}</Pill>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        {formatTimestamp(run.created_at)}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Pill>
                          Trust {run.engineering_status?.trust_score ?? 0}
                        </Pill>
                        <Pill>
                          Unresolved {run.coordination_summary?.unresolved_conflicts ?? 0}
                        </Pill>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.aside>

        <motion.main
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="min-w-0 space-y-6"
        >
          <Card>
            <CardHeader>
              <SectionTitle
                icon={Sparkles}
                title="Design Workspace"
                desc="One clear workflow: choose a strategy, describe the design, generate, then review the preview."
              />
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(320px,0.95fr)]">
                <div className="space-y-4 rounded-3xl border border-black/10 bg-slate-50/80 p-4">
                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Workflow Strategy
                    </p>
                    <div className="grid gap-3 sm:grid-cols-3">
                      {[
                        {
                          value: "manual",
                          label: "Manual",
                          desc: "Strict, explicit engineering input.",
                        },
                        {
                          value: "assisted",
                          label: "Assisted",
                          desc: "AI fills gaps and keeps momentum.",
                        },
                        {
                          value: "hybrid",
                          label: "Hybrid",
                          desc: "Balanced workflow for most projects.",
                        },
                      ].map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setStrategyMode(option.value as StrategyMode)}
                          className={`rounded-2xl border px-4 py-4 text-left transition ${
                            strategyMode === option.value
                              ? "border-slate-900 bg-white shadow-sm"
                              : "border-black/10 bg-white/80 hover:bg-white"
                          }`}
                        >
                          <p className="text-sm font-medium text-slate-900">
                            {option.label}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {option.desc}
                          </p>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Project name">
                      <TextInput
                        value={siteName}
                        onChange={(e) => setSiteName(e.target.value)}
                      />
                    </Field>
                    <Field label="File name">
                      <TextInput
                        value={fileName}
                        onChange={(e) => setFileName(e.target.value)}
                        placeholder="civora-ai-plan"
                      />
                    </Field>
                    <Field label="Project type">
                      <SelectField
                        value={projectType}
                        onChange={setProjectType}
                        options={[
                          { value: "commercial_pad", label: "Commercial pad" },
                          { value: "office_site", label: "Office site" },
                          { value: "multifamily_site", label: "Multifamily site" },
                          { value: "industrial_site", label: "Industrial site" },
                          { value: "corridor_roadway", label: "Corridor roadway" },
                          { value: "drainage_network", label: "Drainage network" },
                        ]}
                      />
                    </Field>
                    <Field label="Units">
                      <SelectField
                        value={units}
                        onChange={setUnits}
                        options={[
                          { value: "ft", label: "Feet" },
                          { value: "m", label: "Meters" },
                          { value: "mm", label: "Millimeters" },
                        ]}
                      />
                    </Field>
                  </div>

                  <div className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Include in design
                    </p>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      {disciplineToggles.map(({ label, checked, setter, desc }) => (
                        <div
                          key={label}
                          className="flex items-center justify-between rounded-2xl border border-black/10 bg-white px-4 py-3"
                        >
                          <div>
                            <p className="text-sm font-medium text-slate-900">
                              {label}
                            </p>
                            <p className="text-xs text-slate-500">{desc}</p>
                          </div>
                          <Toggle checked={checked} onChange={setter} />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-dashed border-black/15 bg-white p-4">
                    <div className="flex items-start gap-3">
                      <FileImage className="mt-0.5 h-5 w-5 text-slate-700" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-900">
                          Upload reference image
                        </p>
                        <p className="mt-1 text-sm text-slate-500">
                          Add a sketch, markup, or screenshot to guide the design.
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 space-y-3">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (file) {
                            await uploadImage(file);
                          }
                        }}
                        className="block w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-700 file:mr-4 file:rounded-xl file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white"
                      />
                      <TextInput
                        value={imageName}
                        onChange={(e) => setImageName(e.target.value)}
                        placeholder="Reference image path or filename"
                      />
                      {uploadedImagePreviewUrl || uploadedImageApiUrl ? (
                        <div className="overflow-hidden rounded-2xl border border-black/10 bg-slate-50">
                          <img
                            src={uploadedImagePreviewUrl || uploadedImageApiUrl}
                            alt="Uploaded planning reference"
                            className="h-44 w-full object-cover"
                          />
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>

                <div className="space-y-4 rounded-3xl border border-black/10 bg-white p-4">
                  <div className="space-y-2">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Project Brief
                    </p>
                    <p className="text-sm text-slate-500">
                      Describe the civil site request once. Civora AI will use the selected strategy and design scope automatically.
                    </p>
                  </div>
                  <TextArea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Describe the site, access, grading goals, drainage intent, utilities, constraints, and any required outcomes..."
                    className="h-[260px] min-h-[260px] max-h-[320px] whitespace-pre-wrap break-words"
                  />
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <Field label="Lot width">
                      <TextInput
                        value={lotWidth}
                        onChange={(e) => setLotWidth(e.target.value)}
                      />
                    </Field>
                    <Field label="Lot height">
                      <TextInput
                        value={lotHeight}
                        onChange={(e) => setLotHeight(e.target.value)}
                      />
                    </Field>
                    <Field label="Building width">
                      <TextInput
                        value={buildingWidth}
                        onChange={(e) => setBuildingWidth(e.target.value)}
                      />
                    </Field>
                    <Field label="Building depth">
                      <TextInput
                        value={buildingDepth}
                        onChange={(e) => setBuildingDepth(e.target.value)}
                      />
                    </Field>
                    <Field label="Setback">
                      <TextInput
                        value={setback}
                        onChange={(e) => setSetback(e.target.value)}
                      />
                    </Field>
                    <Field label="Parking count">
                      <TextInput
                        value={parkingCount}
                        onChange={(e) => setParkingCount(e.target.value)}
                      />
                    </Field>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <SmallButton
                      onClick={() => void runOrchestrator("run")}
                      disabled={busy}
                    >
                      <Sparkles
                        className={`mr-2 h-4 w-4 ${busy ? "animate-spin" : ""}`}
                      />
                      {busy && activePlanTool === "run" ? "Generating..." : "Generate Plan"}
                    </SmallButton>
                    <SmallButton
                      variant="secondary"
                      onClick={() => {
                        setSelectedPlanToolPanel("fix");
                        void runOrchestrator("fix");
                      }}
                      disabled={busy}
                    >
                      <AlertTriangle className="mr-2 h-4 w-4" />
                      {busy && activePlanTool === "fix" ? "Fixing..." : "Fix Issues"}
                    </SmallButton>
                    <SmallButton
                      variant="secondary"
                      onClick={() => {
                        setSelectedPlanToolPanel("improve");
                        void runOrchestrator("improve");
                      }}
                      disabled={busy}
                    >
                      <Sparkles className="mr-2 h-4 w-4" />
                      {busy && activePlanTool === "improve" ? "Improving..." : "Improve Plan"}
                    </SmallButton>
                    <SmallButton
                      variant="secondary"
                      onClick={() => setSelectedPlanToolPanel("explain")}
                      disabled={!backendResult && !selectedRun}
                    >
                      <Eye className="mr-2 h-4 w-4" />
                      Explain Plan
                    </SmallButton>
                    <SmallButton
                      variant="secondary"
                      onClick={saveProject}
                      disabled={busy}
                    >
                      <Save className="mr-2 h-4 w-4" />
                      Save Project
                    </SmallButton>
                    <SmallButton
                      variant="secondary"
                      onClick={queueJob}
                      disabled={busy}
                    >
                      <Clock3 className="mr-2 h-4 w-4" />
                      Queue Job
                    </SmallButton>
                  </div>
                  {(statusMessage || busy) ? (
                    <div
                      className={`rounded-2xl border px-4 py-3 ${
                        busy
                          ? "border-slate-300 bg-slate-100"
                          : "border-slate-200 bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        {busy ? (
                          <RefreshCw className="h-4 w-4 animate-spin text-slate-700" />
                        ) : (
                          <CheckCircle2 className="h-4 w-4 text-slate-700" />
                        )}
                        <p className="text-sm font-medium text-slate-800">
                          {busy
                            ? activePlanTool === "fix"
                              ? "Civora AI is running a focused fix pass..."
                              : activePlanTool === "improve"
                                ? "Civora AI is improving the current plan..."
                                : "Civora AI is generating your plan..."
                            : statusMessage}
                        </p>
                      </div>
                    </div>
                  ) : null}
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle
                icon={Map}
                title="Plan Preview"
                desc="Preview stays centered, readable, and dominant while you review results."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              {planPreviewUrl ? (
                <>
                  <div className="flex min-h-[620px] items-center justify-center overflow-hidden rounded-3xl border border-black/10 bg-[radial-gradient(circle_at_top,#f8fafc_0%,#eef2f7_100%)] p-4">
                    <img
                      src={planPreviewUrl}
                      alt="Generated plan preview"
                      className="max-h-[580px] w-full object-contain"
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Pill>{planPreviewSummary?.project_name || siteName}</Pill>
                    <Pill>{planPreviewSummary?.action_count ?? 0} actions</Pill>
                    <Pill>{planPreviewSummary?.units || units}</Pill>
                    <Pill>
                      Truth {(backendResult?.final_plan?.meta?.truth_audit?.success ?? selectedRun?.truth_success) ? "passed" : "review needed"}
                    </Pill>
                  </div>
                </>
              ) : (
                <div className="flex min-h-[420px] items-center justify-center rounded-3xl border border-dashed border-black/10 bg-slate-50 p-8 text-center text-sm text-slate-500">
                  Generate a plan and Civora AI will place the preview here automatically.
                </div>
              )}

              <div className="flex flex-wrap gap-3">
                <SmallButton variant="secondary" onClick={handlePreviewPlan} disabled={busy}>
                  <Eye className="mr-2 h-4 w-4" />
                  Refresh Preview
                </SmallButton>
                <SmallButton variant="secondary" onClick={handleExportDxf} disabled={busy}>
                  <Download className="mr-2 h-4 w-4" />
                  Export DXF
                </SmallButton>
                <SmallButton variant="secondary" onClick={handleExportReport} disabled={busy}>
                  <Download className="mr-2 h-4 w-4" />
                  Export Report
                </SmallButton>
              </div>
            </CardContent>
          </Card>
        </motion.main>

        <motion.aside
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="min-w-0 space-y-6 xl:max-h-[calc(100vh-3rem)] xl:overflow-y-auto xl:pr-2"
        >
          <Card>
            <CardHeader>
              <SectionTitle
                icon={FileText}
                title="Plan Tools"
                desc="Explain the result, focus on fixes, or ask for a stronger iteration."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                {[
                  { key: "explain", label: "Explain" },
                  { key: "fix", label: "Fix" },
                  { key: "improve", label: "Improve" },
                ].map((tab) => (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() =>
                      setSelectedPlanToolPanel(
                        tab.key as "explain" | "fix" | "improve",
                      )
                    }
                    className={`rounded-full px-3 py-2 text-xs font-medium transition ${
                      selectedPlanToolPanel === tab.key
                        ? "bg-slate-900 text-white"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="rounded-2xl border border-black/10 bg-slate-50/80 p-4">
                {selectedPlanToolPanel === "explain" ? (
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-900">
                      What Civora AI did
                    </p>
                    <p className="text-sm leading-6 text-slate-700">
                      {currentExplanation?.summary ||
                        selectedRun?.message ||
                        "Generate a plan to see the explanation here."}
                    </p>
                    {Array.isArray(currentExplanation?.bullets) &&
                    currentExplanation.bullets.length ? (
                      <div className="space-y-2">
                        {currentExplanation.bullets.slice(0, 6).map((bullet: string, index: number) => (
                          <div
                            key={`${bullet}-${index}`}
                            className="flex gap-2 text-sm text-slate-700"
                          >
                            <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-slate-400" />
                            <span>{bullet}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : selectedPlanToolPanel === "fix" ? (
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-900">
                      Focused fix pass
                    </p>
                    <p className="text-sm leading-6 text-slate-700">
                      Civora AI reruns the current project with an issue-aware optimization goal to reduce the most obvious blockers before you review again.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Pill>Goal {suggestedImproveGoal ?? "reduce_pipe_length"}</Pill>
                      <Pill>
                        Failures {currentManualFailures.length || selectedRun?.manual_failures?.length || 0}
                      </Pill>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-900">
                      Improvement loop
                    </p>
                    <p className="text-sm leading-6 text-slate-700">
                      Improve Plan uses the orchestrator’s iterative workflow to search for a cleaner coordinated outcome while preserving the same project intent.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Pill>Goal {suggestedImproveGoal ?? "balanced"}</Pill>
                      <Pill>
                        Strategy {currentCoordination?.selected_group_strategy || selectedRun?.coordination_summary?.selected_strategy || "none"}
                      </Pill>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle
                icon={AlertTriangle}
                title="AI Review"
                desc="Warnings, assumptions, and manual failures in one place."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-2">
                <Pill>
                  Unresolved {Array.isArray(currentCoordination?.unresolved_conflicts) ? currentCoordination.unresolved_conflicts.length : currentCoordination?.unresolved_conflicts || selectedRun?.coordination_summary?.unresolved_conflicts || 0}
                </Pill>
                <Pill>
                  Truth {(backendResult?.final_plan?.meta?.truth_audit?.success ?? selectedRun?.truth_success) ? "passed" : "review needed"}
                </Pill>
              </div>

              <div className="space-y-3">
                {(currentManualFailures.length ? currentManualFailures : selectedRun?.manual_failures || []).slice(0, 4).map((failure: any, idx: number) => (
                  <div
                    key={`${failure.code || "failure"}-${idx}`}
                    className="rounded-2xl border border-red-200 bg-red-50 p-4"
                  >
                    <p className="text-sm font-medium text-red-800">
                      {failure.code || failure.message || "Manual failure"}
                    </p>
                    <p className="mt-2 text-xs text-red-700">
                      {[failure.system, failure.rule, failure.location]
                        .filter(Boolean)
                        .join(" | ") || "No location metadata"}
                    </p>
                    {failure.reason || failure.message ? (
                      <p className="mt-2 text-xs text-red-700">
                        {failure.reason || failure.message}
                      </p>
                    ) : null}
                  </div>
                ))}

                {issues.slice(0, 4).map((issue, idx) => (
                  <div
                    key={`${issue.message}-${idx}`}
                    className="rounded-2xl border border-black/10 bg-white p-4"
                  >
                    <div className="flex items-center gap-2">
                      <AlertTriangle
                        className={`h-4 w-4 ${
                          issue.severity === "error"
                            ? "text-red-600"
                            : "text-amber-500"
                        }`}
                      />
                      <p className="text-sm font-medium capitalize text-slate-900">
                        {issue.severity}
                      </p>
                    </div>
                    <p className="mt-2 text-sm text-slate-600">{issue.message}</p>
                  </div>
                ))}
              </div>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  AI-filled inputs
                </p>
                {assumptions.slice(0, 4).map((item, idx) => (
                  <div key={idx} className="rounded-2xl border border-black/10 bg-white p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-slate-900">
                        {item.field}
                      </p>
                      <Pill>AI filled</Pill>
                    </div>
                    <p className="mt-1 text-sm text-slate-800">{item.value}</p>
                    <p className="mt-2 text-xs text-slate-500">{item.reason}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle
                icon={Sparkles}
                title="Engineering Insights"
                desc="A compact view into solver quality, truth checks, and iteration depth."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-black/10 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Trust
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-slate-950">
                    {backendResult?.final_plan?.meta?.engineering_status?.trust_score ??
                      selectedRun?.engineering_status?.trust_score ??
                      0}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Engineering trust score
                  </p>
                </div>
                <div className="rounded-2xl border border-black/10 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Iterations
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-slate-950">
                    {currentIterations.length}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Improvement loop passes recorded
                  </p>
                </div>
              </div>

              <div className="rounded-2xl border border-black/10 bg-white p-4">
                <p className="text-sm font-medium text-slate-900">Truth audit</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Pill>
                    Canonical {currentTruthAudit?.summary?.canonical_validity ? "valid" : "review"}
                  </Pill>
                  <Pill>
                    Hydraulics {currentTruthAudit?.summary?.hydraulic_completeness ? "complete" : "review"}
                  </Pill>
                  <Pill>
                    Graphs {currentTruthAudit?.summary?.graph_validity ? "valid" : "review"}
                  </Pill>
                  <Pill>
                    Quantities {currentTruthAudit?.summary?.quantity_alignment ? "aligned" : "review"}
                  </Pill>
                  <Pill>
                    Conflicts {currentTruthAudit?.summary?.conflict_integrity ? "clean" : "review"}
                  </Pill>
                </div>
              </div>

              {currentIterations.length ? (
                <div className="rounded-2xl border border-black/10 bg-white p-4">
                  <p className="text-sm font-medium text-slate-900">
                    Latest improvement notes
                  </p>
                  <div className="mt-3 space-y-2">
                    {currentIterations
                      .slice(-2)
                      .reverse()
                      .map((iteration: any, index: number) => (
                        <div key={`${iteration.iteration_index || index}`} className="rounded-2xl bg-slate-50 px-3 py-2">
                          <p className="text-xs font-medium text-slate-700">
                            Iteration {iteration.iteration_index ?? index + 1}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {Array.isArray(iteration.notes) && iteration.notes.length
                              ? iteration.notes.join(" ")
                              : iteration.message || "No extra notes recorded."}
                          </p>
                        </div>
                      ))}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle
                icon={History}
                title="Run Comparison"
                desc="Compare the newest result against the previous saved run."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              {!latestRunComparison ? (
                <p className="text-sm text-slate-500">
                  Save at least two runs to compare changes here.
                </p>
              ) : (
                <>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl border border-black/10 bg-slate-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Trust Delta
                      </p>
                      <p className="mt-2 text-lg font-semibold text-slate-950">
                        {latestRunComparison.trustDelta >= 0 ? "+" : ""}
                        {latestRunComparison.trustDelta}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-slate-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Unresolved Delta
                      </p>
                      <p className="mt-2 text-lg font-semibold text-slate-950">
                        {latestRunComparison.unresolvedDelta >= 0 ? "+" : ""}
                        {latestRunComparison.unresolvedDelta}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-slate-50 p-4">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Deliverables Delta
                      </p>
                      <p className="mt-2 text-lg font-semibold text-slate-950">
                        {latestRunComparison.producedDelta >= 0 ? "+" : ""}
                        {latestRunComparison.producedDelta}
                      </p>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-black/10 bg-white p-4 text-sm text-slate-600">
                    Current run from {formatTimestamp(latestRunComparison.current.created_at)} compared to the previous saved run from {formatTimestamp(latestRunComparison.previous.created_at)}.
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle
                icon={Download}
                title="Artifacts"
                desc="Saved exports for the active project."
              />
            </CardHeader>
            <CardContent className="space-y-3">
              {!projectId ? (
                <p className="text-sm text-slate-500">
                  Open or save a project to keep downloadable artifacts here.
                </p>
              ) : workflowArtifacts.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No saved artifacts yet. Export a DXF or report while a project is loaded.
                </p>
              ) : (
                <div className="max-h-[260px] space-y-3 overflow-y-auto pr-1">
                  {workflowArtifacts.map((artifact) => (
                    <div
                      key={artifact.artifact_id}
                      className="rounded-2xl border border-black/10 bg-white p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">
                            {artifact.filename || artifact.kind || "artifact"}
                          </p>
                          <p className="mt-1 text-xs text-slate-500">
                            {artifact.kind || "artifact"} •{" "}
                            {formatTimestamp(artifact.created_at)}
                          </p>
                        </div>
                        <SmallButton
                          variant="secondary"
                          onClick={() => void downloadSavedArtifact(artifact)}
                        >
                          Download
                        </SmallButton>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.aside>
      </div>
    </div>
  );
}
