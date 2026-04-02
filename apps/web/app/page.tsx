"use client";

import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Download,
  Eye,
  FileImage,
  FolderOpen,
  Layers3,
  LogOut,
  Map,
  RefreshCw,
  Save,
  Settings2,
  Sparkles,
  Upload,
} from "lucide-react";

import {
  deleteJson,
  getJson,
  postBinary,
  postForm,
  postJson,
  toApiUrl,
} from "../lib/api";

type InputMode =
  | "manual"
  | "assisted"
  | "image_assisted"
  | "prompt_assisted"
  | "hybrid";

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

type FeatureCard = {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  desc: string;
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

const authFeatureCards: FeatureCard[] = [
  {
    icon: FolderOpen,
    title: "Projects",
    desc: "Save concept setups and reopen them like a real product.",
  },
  {
    icon: Clock3,
    title: "Jobs",
    desc: "Queue planner runs in the background and track status.",
  },
  {
    icon: Layers3,
    title: "Planner Stack",
    desc: "Orchestrator, planner, core, and engines wired together.",
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
      className={`rounded-3xl border border-black/10 bg-white shadow-sm ${className}`}
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
      <div className="rounded-2xl border border-black/10 bg-white p-2 shadow-sm">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h3 className="text-base font-semibold tracking-tight text-slate-900">
          {title}
        </h3>
        <p className="text-sm text-slate-500">{desc}</p>
      </div>
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
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
      ? "bg-slate-900 text-white hover:bg-slate-800"
      : "border border-black/10 bg-white text-slate-900 hover:bg-slate-50";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center rounded-2xl px-4 py-2 text-sm font-medium shadow-sm transition ${styles} ${
        disabled ? "cursor-not-allowed opacity-60" : ""
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
      <label className="text-sm font-medium text-slate-800">{label}</label>
      {children}
    </div>
  );
}

function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-950 placeholder:text-slate-400 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200 ${
        props.className ?? ""
      }`}
    />
  );
}

function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`min-h-[168px] max-h-[280px] w-full resize-none overflow-y-auto rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm leading-6 text-slate-950 placeholder:text-slate-400 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200 ${
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
      className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
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
        checked ? "bg-slate-900" : "bg-slate-300"
      }`}
    >
      <span
        className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition ${
          checked ? "left-6" : "left-1"
        }`}
      />
    </button>
  );
}

function ModeCard({
  active,
  label,
  desc,
  onClick,
}: {
  active: boolean;
  label: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border p-4 text-left transition ${
        active
          ? "border-slate-900 bg-slate-50 shadow-sm"
          : "border-black/10 hover:bg-slate-50"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="font-medium text-slate-900">{label}</p>
        {active ? <CheckCircle2 className="h-4 w-4 text-slate-900" /> : null}
      </div>
      <p className="mt-1 text-sm text-slate-500">{desc}</p>
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
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authStatusError, setAuthStatusError] = useState("");

  const [inputMode, setInputMode] = useState<InputMode>("assisted");
  const [projectType, setProjectType] = useState("commercial_pad");
  const [units, setUnits] = useState("ft");
  const [strictMode, setStrictMode] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [imageName, setImageName] = useState("");
  const [siteName, setSiteName] = useState("Civora AI Project");
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
  const [activeTab, setActiveTab] = useState<"prompt" | "image">("prompt");
  const [projectId, setProjectId] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [currentProject, setCurrentProject] = useState<ProjectRecord | null>(null);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [activeJobId, setActiveJobId] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [busy, setBusy] = useState(false);

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

  const enablePromptInput = () => {
    setActiveTab("prompt");
    setInputMode((mode) => {
      if (mode === "manual") return "assisted";
      if (mode === "image_assisted") return "hybrid";
      return mode;
    });
  };

  const enableImageInput = () => {
    setActiveTab("image");
    setInputMode((mode) => {
      if (mode === "manual") return "image_assisted";
      if (mode === "assisted" || mode === "prompt_assisted") return "hybrid";
      return mode;
    });
  };

  const payloadPreview = useMemo(
    () => ({
      input_mode: inputMode,
      strict_mode: strictMode,
      prompt_text: prompt || null,
      image_path: imageName || null,
      manual_fields: {
        project_name: siteName,
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
      allow_ai_fill_for_blanks: !strictMode,
    }),
    [
      inputMode,
      strictMode,
      prompt,
      imageName,
      siteName,
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
        filename_stem: siteName,
      };
    }

    return {
      project_id: projectId || null,
      filename_stem: siteName,
    };
  }, [backendResult, projectId, siteName]);

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
  const currentStageStatuses = useMemo(
    () =>
      currentPlanMeta?.stage_completeness?.statuses &&
      typeof currentPlanMeta.stage_completeness.statuses === "object"
        ? currentPlanMeta.stage_completeness.statuses
        : {},
    [currentPlanMeta],
  );
  const currentDeliverables = useMemo(
    () => currentPlanMeta?.deliverables ?? {},
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

    setInputMode((projectInput.input_mode as InputMode) ?? "assisted");
    setStrictMode(Boolean(projectInput.strict_mode));
    setPrompt(projectInput.prompt_text ?? "");
    setImageName(projectInput.image_path ?? "");
    setUploadedImageApiUrl(
      projectInput.image_path ? uploadedImageSrc(projectInput.image_path, token) : "",
    );
    setUploadedImagePreviewUrl("");
    setSiteName(manualFields.project_name ?? "Civora AI Project");
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
    setProjects(Array.isArray(data.projects) ? data.projects : []);
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

  const runOrchestrator = async () => {
    if (!token) return;
    setBusy(true);
    try {
      const data = await postJson<any>("/api/orchestrate", payloadPreview, {
        token,
      });
      applyBackendResult(data);
      setStatusMessage("Direct orchestrator run completed.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Orchestrator failed.",
      );
    } finally {
      setBusy(false);
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
          description: projectDescription,
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
      setSiteName(project.name ?? "Civora AI Project");
      setProjectDescription(project.description ?? "");
      applyProjectInput(project.project_input ?? {});
      if (project.latest_result && Object.keys(project.latest_result).length) {
        applyBackendResult(project.latest_result);
      } else {
        setBackendResult(null);
      }
      setPlanPreviewUrl("");
      setPlanPreviewSummary(null);
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

  const handlePreviewPlan = async () => {
    if (!token) return;
    if (!backendResult && !projectId) {
      setStatusMessage("Run the planner first so there is something to preview.");
      return;
    }
    setBusy(true);
    try {
      const data = await postJson<PreviewResponse>("/api/preview", artifactPayload, {
        token,
      });
      setPlanPreviewUrl(data.preview_image_data_url);
      setPlanPreviewSummary(data.summary ?? null);
      setStatusMessage("Plan preview generated.");
    } catch (error) {
      setStatusMessage(
        error instanceof Error ? error.message : "Preview generation failed.",
      );
    } finally {
      setBusy(false);
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
        <div className="mx-auto grid min-h-[90vh] max-w-6xl items-center gap-8 lg:grid-cols-[1.15fr_0.85fr]">
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
                Sign in to manage projects, queue planning runs, review AI
                assumptions, and turn rough site intent into structured output.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-3">
              {authFeatureCards.map(({ icon: Comp, title, desc }) => {
                return (
                  <Card key={String(title)} className="rounded-2xl">
                    <CardContent className="p-5">
                      <Comp className="h-5 w-5 text-slate-900" />
                      <p className="mt-3 text-sm font-medium text-slate-900">
                        {title}
                      </p>
                      <p className="mt-1 text-sm text-slate-500">{desc}</p>
                    </CardContent>
                  </Card>
                );
              })}
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
                  <TextInput
                    type="password"
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    autoComplete={
                      authMode === "register" ? "new-password" : "current-password"
                    }
                  />
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
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-4 md:p-8">
      <div className="mx-auto mb-6 flex max-w-7xl flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">Signed in as {user.email}</p>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950">
            Civora AI — AI-Powered Civil Engineering Design Platform
          </h1>
        </div>
        <div className="flex flex-wrap gap-3">
          <Pill>Private Beta</Pill>
          <Pill>User Scoped</Pill>
          <SmallButton variant="secondary" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign Out
          </SmallButton>
        </div>
      </div>

      <div className="mx-auto mb-6 max-w-7xl">
        <div className="rounded-3xl border border-black/10 bg-white/90 p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">Latest Outcome</p>
              <p className="mt-1 text-sm text-slate-500">
                {currentProject
                  ? `Active project: ${currentProject.name}`
                  : "Load or save a project to keep runs, artifacts, and workflow history together."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Pill>Truth {(backendResult?.final_plan?.meta?.truth_audit?.success ?? selectedRun?.truth_success) ? "passed" : "pending"}</Pill>
              <Pill>Unresolved {Array.isArray(currentCoordination?.unresolved_conflicts) ? currentCoordination.unresolved_conflicts.length : currentCoordination?.unresolved_conflicts || 0}</Pill>
              <Pill>Produced {(currentDeliverables?.produced || []).length}</Pill>
              <Pill>{Object.keys(currentStageStatuses).length} stages tracked</Pill>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          <Card>
            <CardHeader>
              <SectionTitle
                icon={FolderOpen}
                title="Project Workspace"
                desc="Build requests, save projects, and launch direct or queued engineering runs."
              />
            </CardHeader>
            <CardContent className="grid gap-6">
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Project name">
                  <TextInput value={siteName} onChange={(e) => setSiteName(e.target.value)} />
                </Field>
                <Field label="Project description">
                  <TextInput
                    value={projectDescription}
                    onChange={(e) => setProjectDescription(e.target.value)}
                    placeholder="Retail pad, multifamily concept, drainage study..."
                  />
                </Field>
              </div>

              <div className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
                <Card>
                  <CardHeader>
                    <SectionTitle icon={Sparkles} title="Input Mode" desc="Choose how this run should behave." />
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <ModeCard active={inputMode === "manual"} label="Manual" desc="No AI fill for missing fields" onClick={() => setInputMode("manual")} />
                      <ModeCard active={inputMode === "assisted"} label="Assisted" desc="AI fills only blank fields" onClick={() => setInputMode("assisted")} />
                      <ModeCard active={inputMode === "image_assisted"} label="Image + Assisted" desc="Upload image, then AI helps with blanks" onClick={() => setInputMode("image_assisted")} />
                      <ModeCard active={inputMode === "prompt_assisted"} label="Prompt + Assisted" desc="Prompt-first structured planning" onClick={() => setInputMode("prompt_assisted")} />
                      <ModeCard active={inputMode === "hybrid"} label="Hybrid" desc="Image + prompt + form together" onClick={() => setInputMode("hybrid")} />
                    </div>
                    <div className="flex items-center justify-between rounded-2xl border border-black/10 p-4">
                      <div>
                        <p className="text-sm font-medium text-slate-900">Strict validation</p>
                        <p className="text-xs text-slate-500">Blank required fields become blocking errors.</p>
                      </div>
                      <Toggle checked={strictMode} onChange={setStrictMode} />
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <SectionTitle icon={Layers3} title="Project Setup" desc="Structured inputs that feed the planner stack." />
                  </CardHeader>
                  <CardContent className="grid gap-4 md:grid-cols-2">
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
                    <Field label="Setback">
                      <TextInput value={setback} onChange={(e) => setSetback(e.target.value)} />
                    </Field>
                    <Field label="Parking count">
                      <TextInput value={parkingCount} onChange={(e) => setParkingCount(e.target.value)} />
                    </Field>
                    <Field label="Lot width">
                      <TextInput value={lotWidth} onChange={(e) => setLotWidth(e.target.value)} />
                    </Field>
                    <Field label="Lot height">
                      <TextInput value={lotHeight} onChange={(e) => setLotHeight(e.target.value)} />
                    </Field>
                    <Field label="Building width">
                      <TextInput value={buildingWidth} onChange={(e) => setBuildingWidth(e.target.value)} />
                    </Field>
                    <Field label="Building depth">
                      <TextInput value={buildingDepth} onChange={(e) => setBuildingDepth(e.target.value)} />
                    </Field>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <SectionTitle icon={Upload} title="Prompt or Image Inputs" desc="Use prompt, image, or both." />
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="inline-flex rounded-2xl border border-black/10 bg-slate-100 p-1">
                    <button
                      type="button"
                      onClick={enablePromptInput}
                      className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                        activeTab === "prompt" ? "bg-white shadow-sm" : "text-slate-600"
                      }`}
                    >
                      Prompt
                    </button>
                    <button
                      type="button"
                      onClick={enableImageInput}
                      className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                        activeTab === "image" ? "bg-white shadow-sm" : "text-slate-600"
                      }`}
                    >
                      Image Upload
                    </button>
                  </div>

                  {activeTab === "prompt" ? (
                    <Field label="Prompt">
                      <TextArea
                        value={prompt}
                        onFocus={enablePromptInput}
                        onChange={(e) => {
                          enablePromptInput();
                          setPrompt(e.target.value);
                        }}
                        placeholder="Describe the site, roadway, grading, utility, or drainage concept..."
                        className="whitespace-pre-wrap break-words"
                      />
                      <p className="text-xs text-slate-500">
                        Typing here automatically keeps the run in a prompt-capable mode.
                      </p>
                    </Field>
                  ) : (
                    <Field label="Image file">
                      <div className="rounded-2xl border border-dashed border-black/15 p-6">
                        <div className="flex flex-col items-center justify-center gap-3 text-center">
                          <FileImage className="h-8 w-8 text-slate-700" />
                          <div>
                            <p className="font-medium text-slate-900">Upload sketch, screenshot, or marked-up plan</p>
                            <p className="text-sm text-slate-500">The backend stores the image, and the dashboard keeps a visible photo preview while you work.</p>
                          </div>
                          <div className="flex w-full max-w-md flex-col gap-3">
                            <TextInput
                              value={imageName}
                              onFocus={enableImageInput}
                              onChange={(e) => {
                                enableImageInput();
                                setImageName(e.target.value);
                              }}
                              placeholder="example: retail_site_sketch.png"
                            />
                            <input
                              type="file"
                              accept="image/*"
                              onClick={enableImageInput}
                              onChange={async (e) => {
                                const file = e.target.files?.[0];
                                if (file) {
                                  enableImageInput();
                                  await uploadImage(file);
                                }
                              }}
                              className="block w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-700 file:mr-4 file:rounded-xl file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white"
                            />
                            {uploadedImagePreviewUrl ? (
                              <div className="overflow-hidden rounded-2xl border border-black/10 bg-slate-50">
                                <img
                                  src={uploadedImagePreviewUrl}
                                  alt="Uploaded planning reference"
                                  className="h-48 w-full object-cover"
                                />
                              </div>
                            ) : null}
                            {!uploadedImagePreviewUrl && uploadedImageApiUrl ? (
                              <div className="overflow-hidden rounded-2xl border border-black/10 bg-slate-50">
                                <img
                                  src={uploadedImageApiUrl}
                                  alt="Uploaded planning reference"
                                  className="h-48 w-full object-cover"
                                />
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    </Field>
                  )}

                  <div className="grid gap-4 md:grid-cols-4">
                    {disciplineToggles.map(({ label, checked, setter, desc }) => (
                      <div key={String(label)} className="flex items-center justify-between rounded-2xl border border-black/10 p-4">
                        <div>
                          <p className="text-sm font-medium text-slate-900">{label}</p>
                          <p className="text-xs text-slate-500">{desc}</p>
                        </div>
                        <Toggle checked={checked} onChange={setter} />
                      </div>
                    ))}
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <SmallButton onClick={runOrchestrator} disabled={busy}>
                      <Sparkles className="mr-2 h-4 w-4" />
                      Direct Run
                    </SmallButton>
                    <SmallButton onClick={queueJob} variant="secondary" disabled={busy}>
                      <Clock3 className="mr-2 h-4 w-4" />
                      Queue Job
                    </SmallButton>
                    <SmallButton onClick={saveProject} variant="secondary" disabled={busy}>
                      <Save className="mr-2 h-4 w-4" />
                      Save Project
                    </SmallButton>
                    <SmallButton variant="secondary" onClick={handlePreviewPlan} disabled={busy}>
                      <Eye className="mr-2 h-4 w-4" />
                      Preview Plan
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
                  {statusMessage ? (
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                      <p className="text-sm font-medium text-slate-800">{statusMessage}</p>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          <Card>
            <CardHeader>
              <SectionTitle icon={FolderOpen} title="Saved Projects" desc="User-scoped saved work for this beta account." />
            </CardHeader>
            <CardContent className="space-y-3">
              {currentProject ? (
                <div className="rounded-2xl border border-slate-900 bg-slate-50 p-4 sm:p-5">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-sm font-medium text-slate-900">Active Project</p>
                      <p className="mt-1 text-base font-semibold text-slate-950">{currentProject.name}</p>
                      <p className="mt-1 text-xs text-slate-500">{currentProject.project_id}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Pill>{workflowRuns.length} runs</Pill>
                      <Pill>{workflowArtifacts.length} artifacts</Pill>
                    </div>
                  </div>
                  {workflowArtifacts.length ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {workflowArtifacts.slice(0, 3).map((artifact) => (
                        <SmallButton
                          key={artifact.artifact_id}
                          variant="secondary"
                          onClick={() => void downloadSavedArtifact(artifact)}
                        >
                          {artifact.kind || "artifact"}: {artifact.filename || "download"}
                        </SmallButton>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-3">
                <SmallButton variant="secondary" onClick={() => void refreshProjects()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh
                </SmallButton>
              </div>
              <div className="max-h-[260px] space-y-3 overflow-auto pr-1">
                {projects.length === 0 ? (
                  <p className="text-sm text-slate-500">No saved projects yet.</p>
                ) : (
                  projects.map((project) => (
                    <div key={project.project_id} className={`rounded-2xl border p-4 ${project.project_id === projectId ? "border-slate-900 bg-slate-50" : "border-black/10"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-slate-900">{project.name}</p>
                          <p className="mt-1 text-xs text-slate-500">{project.project_id}</p>
                        </div>
                        {project.has_result ? <Pill>Result</Pill> : <Pill>Draft</Pill>}
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <SmallButton variant="secondary" onClick={() => void loadProject(project.project_id)}>
                          Load
                        </SmallButton>
                        <SmallButton variant="secondary" onClick={() => void deleteProject(project.project_id)}>
                          Delete
                        </SmallButton>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Clock3} title="Queued Jobs" desc="Background planner runs stored in the beta backend." />
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-3">
                <SmallButton variant="secondary" onClick={() => void refreshJobs()}>
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh
                </SmallButton>
              </div>
              <div className="max-h-[260px] space-y-3 overflow-auto pr-1">
                {jobs.length === 0 ? (
                  <p className="text-sm text-slate-500">No jobs yet.</p>
                ) : (
                  jobs.map((job) => (
                    <button
                      key={job.job_id}
                      type="button"
                      onClick={() => void loadJob(job.job_id)}
                      className={`block w-full rounded-2xl border p-4 text-left transition ${
                        job.job_id === activeJobId
                          ? "border-slate-900 bg-slate-50"
                          : "border-black/10 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-slate-900">Job {job.job_id}</p>
                        <Pill>{job.status}</Pill>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">{job.project_id || "No project linked"}</p>
                      {job.error ? <p className="mt-2 text-xs text-red-600">{job.error}</p> : null}
                    </button>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Clock3} title="Project Run History" desc="Recent saved runs for the active project." />
            </CardHeader>
            <CardContent className="space-y-3">
              {!projectId ? (
                <p className="text-sm text-slate-500">Load or save a project to start building workflow history.</p>
              ) : workflowRuns.length === 0 ? (
                <p className="text-sm text-slate-500">No saved run history yet for this project.</p>
              ) : (
                <div className="max-h-[260px] space-y-3 overflow-auto pr-1">
                  {workflowRuns.map((run) => (
                    <button
                      key={run.run_id}
                      type="button"
                      onClick={() => setSelectedRunId(run.run_id)}
                      className={`block w-full rounded-2xl border p-4 text-left transition ${
                        selectedRun?.run_id === run.run_id
                          ? "border-slate-900 bg-slate-50 shadow-sm ring-1 ring-slate-900/10"
                          : "border-black/10 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <p className="text-sm font-medium text-slate-900">{run.source || "run"}</p>
                          <p className="mt-1 text-xs text-slate-500">{formatTimestamp(run.created_at)}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Pill>{run.success ? "Pass" : "Fail"}</Pill>
                          <Pill>{run.input_mode || "unknown"}</Pill>
                          <Pill>{run.coordination_summary?.selected_strategy || "none"}</Pill>
                        </div>
                      </div>
                      <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                        <p>Trust {run.engineering_status?.trust_score ?? 0}</p>
                        <p>Required complete {run.all_required_complete ? "yes" : "no"}</p>
                        <p>Produced {(run.produced_deliverables || []).length}</p>
                        <p>Unresolved {run.coordination_summary?.unresolved_conflicts ?? 0}</p>
                      </div>
                      {run.manual_failures?.length ? (
                        <p className="mt-3 text-xs text-red-600">
                          {run.manual_failures.slice(0, 2).map((item) => item.code || item.message).join(" | ")}
                        </p>
                      ) : null}
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Settings2} title="Run Detail" desc="Selected saved run detail from project history." />
            </CardHeader>
            <CardContent className="space-y-4">
              {!selectedRun ? (
                <p className="text-sm text-slate-500">Select a saved run to inspect its detail.</p>
              ) : (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Pill>{selectedRun.success ? "Pass" : "Fail"}</Pill>
                    <Pill>{selectedRun.input_mode || "unknown"}</Pill>
                    <Pill>{selectedRun.strict_mode ? "strict" : "non-strict"}</Pill>
                    <Pill>{selectedRun.coordination_summary?.selected_strategy || "none"}</Pill>
                  </div>
                  <div className="grid gap-3 text-sm text-slate-700 xl:grid-cols-2">
                    <div className="rounded-2xl border border-black/10 bg-slate-50/70 p-4">
                      <p className="font-medium text-slate-900">Run summary</p>
                      <p className="mt-2 text-xs text-slate-500">{formatTimestamp(selectedRun.created_at)}</p>
                      <p className="mt-2">Trust {selectedRun.engineering_status?.trust_score ?? 0}</p>
                      <p>Truth {selectedRun.truth_success ? "passed" : "failed"}</p>
                      <p>Required complete {selectedRun.all_required_complete ? "yes" : "no"}</p>
                      <p>Unresolved {selectedRun.coordination_summary?.unresolved_conflicts ?? 0}</p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-slate-50/70 p-4">
                      <p className="font-medium text-slate-900">Deliverables</p>
                      <p className="mt-2 text-xs text-slate-500">
                        Requested {(selectedRun.requested_deliverables || []).length} • Produced {(selectedRun.produced_deliverables || []).length} • Failed {(selectedRun.failed_deliverables || []).length}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(selectedRun.produced_deliverables || []).slice(0, 6).map((item) => (
                          <Pill key={item}>{item}</Pill>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="rounded-2xl border border-black/10 p-4">
                    <p className="text-sm font-medium text-slate-900">Stage status</p>
                    <div className="mt-3 grid gap-2 lg:grid-cols-2">
                      {Object.entries(selectedRun.stage_summary?.statuses || {}).map(([name, status]) => (
                        <div key={name} className="rounded-xl border border-black/10 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                          <span className="font-medium text-slate-900">{name.replaceAll("_", " ")}</span>: {String(status)}
                        </div>
                      ))}
                    </div>
                  </div>
                  {selectedRun.manual_failures?.length ? (
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
                      <p className="text-sm font-medium text-red-800">Manual failures</p>
                      <div className="mt-3 space-y-2">
                        {selectedRun.manual_failures.slice(0, 4).map((failure, idx) => (
                          <div key={`${failure.code || "detail"}-${idx}`} className="text-xs text-red-700">
                            <span className="font-medium">{failure.code || failure.message || "failure"}</span>
                            {failure.system || failure.rule || failure.location
                              ? ` • ${[failure.system, failure.rule, failure.location].filter(Boolean).join(" | ")}`
                              : ""}
                          </div>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={RefreshCw} title="Latest Run Comparison" desc="Quick comparison between the two latest saved runs." />
            </CardHeader>
            <CardContent className="space-y-3">
              {!latestRunComparison ? (
                <p className="text-sm text-slate-500">Two saved runs are needed before comparison appears here.</p>
              ) : (
                <>
                  <div className="grid gap-3 xl:grid-cols-2">
                    <div className="rounded-2xl border border-black/10 bg-slate-50/70 p-4">
                      <p className="text-sm font-medium text-slate-900">Latest</p>
                      <p className="mt-1 text-xs text-slate-500">{formatTimestamp(latestRunComparison.current.created_at)}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Pill>{latestRunComparison.current.success ? "Pass" : "Fail"}</Pill>
                        <Pill>{latestRunComparison.current.engineering_status?.trust_score ?? 0} trust</Pill>
                      </div>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-slate-50/70 p-4">
                      <p className="text-sm font-medium text-slate-900">Previous</p>
                      <p className="mt-1 text-xs text-slate-500">{formatTimestamp(latestRunComparison.previous.created_at)}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Pill>{latestRunComparison.previous.success ? "Pass" : "Fail"}</Pill>
                        <Pill>{latestRunComparison.previous.engineering_status?.trust_score ?? 0} trust</Pill>
                      </div>
                    </div>
                  </div>
                  <div className="grid gap-3 text-sm text-slate-700 sm:grid-cols-3">
                    <div className="rounded-2xl border border-black/10 bg-slate-50/70 p-4">
                      <p className="font-medium text-slate-900">Trust delta</p>
                      <p className="mt-2">{latestRunComparison.trustDelta >= 0 ? "+" : ""}{latestRunComparison.trustDelta.toFixed(1)}</p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-slate-50/70 p-4">
                      <p className="font-medium text-slate-900">Unresolved delta</p>
                      <p className="mt-2">{latestRunComparison.unresolvedDelta >= 0 ? "+" : ""}{latestRunComparison.unresolvedDelta}</p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-slate-50/70 p-4">
                      <p className="font-medium text-slate-900">Produced delta</p>
                      <p className="mt-2">{latestRunComparison.producedDelta >= 0 ? "+" : ""}{latestRunComparison.producedDelta}</p>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Layers3} title="Stage Status" desc="Current run completeness from canonical stage metadata." />
            </CardHeader>
            <CardContent className="space-y-3">
              {Object.keys(currentStageStatuses).length === 0 ? (
                <p className="text-sm text-slate-500">Run or load a planner result to inspect stage-level status.</p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.entries(currentStageStatuses).map(([stageName, stageStatus]) => (
                    <div key={stageName} className="rounded-2xl border border-black/10 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-slate-900">{stageName.replaceAll("_", " ")}</p>
                        <Pill>{String(stageStatus)}</Pill>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Download} title="Deliverable Manager" desc="Requested, produced, and failed deliverables from the current result." />
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              {[
                { label: "Requested", items: currentDeliverables?.requested || [] },
                { label: "Produced", items: currentDeliverables?.produced || [] },
                { label: "Failed", items: currentDeliverables?.failed || [] },
              ].map((group) => (
                <div key={group.label} className="rounded-2xl border border-black/10 p-4">
                  <p className="text-sm font-medium text-slate-900">{group.label}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {group.items.length ? group.items.map((item: string) => <Pill key={item}>{item}</Pill>) : <span className="text-xs text-slate-500">None</span>}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={AlertTriangle} title="Conflict + Failure Review" desc="Manual-mode failures and coordination state tied to canonical metadata." />
            </CardHeader>
            <CardContent className="space-y-3">
              {currentManualFailures.length === 0 && !currentCoordination ? (
                <p className="text-sm text-slate-500">Run or load a planner result to inspect failures and conflicts.</p>
              ) : (
                <>
                  <div className="rounded-2xl border border-black/10 p-4 text-sm text-slate-700">
                    <div className="flex flex-wrap gap-2">
                      <Pill>Strategy {currentCoordination?.selected_group_strategy || "none"}</Pill>
                      <Pill>Unresolved {Array.isArray(currentCoordination?.unresolved_conflicts) ? currentCoordination.unresolved_conflicts.length : currentCoordination?.unresolved_conflicts || 0}</Pill>
                    </div>
                  </div>
                  <div className="max-h-[260px] space-y-3 overflow-auto pr-1">
                    {currentManualFailures.length === 0 ? (
                      <p className="text-sm text-slate-500">No manual failures in the current result.</p>
                    ) : (
                      currentManualFailures.map((failure: any, idx: number) => (
                        <div key={`${failure.code || "failure"}-${idx}`} className="rounded-2xl border border-red-200 bg-red-50 p-4">
                          <p className="text-sm font-medium text-red-800">{failure.code || failure.message || "Manual failure"}</p>
                          <p className="mt-2 text-xs text-red-700">
                            {[failure.system, failure.rule, failure.location].filter(Boolean).join(" | ") || "No location metadata"}
                          </p>
                          {failure.reason || failure.message ? (
                            <p className="mt-2 text-xs text-red-700">{failure.reason || failure.message}</p>
                          ) : null}
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Download} title="Saved Deliverables" desc="Artifacts saved for the active project run history." />
            </CardHeader>
            <CardContent className="space-y-3">
              {!projectId ? (
                <p className="text-sm text-slate-500">Load or save a project to keep downloadable artifacts here.</p>
              ) : workflowArtifacts.length === 0 ? (
                <p className="text-sm text-slate-500">No saved artifacts yet. Export a DXF or report while a project is loaded.</p>
              ) : (
                <div className="max-h-[240px] space-y-3 overflow-auto pr-1">
                  {workflowArtifacts.map((artifact) => (
                    <div key={artifact.artifact_id} className="rounded-2xl border border-black/10 p-4">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-900">{artifact.filename || artifact.kind || "artifact"}</p>
                          <p className="mt-1 text-xs text-slate-500">{artifact.kind || "artifact"} • {formatTimestamp(artifact.created_at)}</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Pill>{artifact.kind || "artifact"}</Pill>
                          <SmallButton variant="secondary" onClick={() => void downloadSavedArtifact(artifact)}>
                            Download
                          </SmallButton>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Eye} title="Plan Preview" desc="Rendered preview generated from the current planner actions." />
            </CardHeader>
            <CardContent className="space-y-4">
              {planPreviewUrl ? (
                <>
                  <div className="flex max-h-[420px] min-h-[220px] items-center justify-center overflow-hidden rounded-2xl border border-black/10 bg-slate-50 p-4 sm:min-h-[280px]">
                    <img
                      src={planPreviewUrl}
                      alt="Generated plan preview"
                      className="h-full max-h-[380px] w-full object-contain"
                    />
                  </div>
                  {planPreviewSummary ? (
                    <div className="flex flex-wrap gap-2">
                      <Pill>{planPreviewSummary.project_name || siteName}</Pill>
                      <Pill>{planPreviewSummary.action_count ?? 0} actions</Pill>
                      <Pill>{planPreviewSummary.units || units}</Pill>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="text-sm text-slate-500">
                  Run the planner, then click <strong>Preview Plan</strong> to see a rendered view here.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={CheckCircle2} title="AI Assumptions" desc="Anything AI fills should stay visible and reviewable." />
            </CardHeader>
            <CardContent>
              <div className="max-h-[220px] space-y-3 overflow-auto pr-1">
                {assumptions.map((item, idx) => (
                  <div key={idx} className="rounded-2xl border border-black/10 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium text-slate-900">{item.field}</p>
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
              <SectionTitle icon={AlertTriangle} title="Validation + Review" desc="Warnings and errors from the planner stack." />
            </CardHeader>
            <CardContent className="space-y-3">
              {issues.map((issue, idx) => (
                <div key={idx} className="rounded-2xl border border-black/10 p-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className={`h-4 w-4 ${issue.severity === "error" ? "text-red-600" : "text-amber-500"}`} />
                    <p className="text-sm font-medium capitalize text-slate-900">{issue.severity}</p>
                  </div>
                  <p className="mt-2 text-sm text-slate-500">{issue.message}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Map} title="Request Payload" desc="The normalized request sent to the backend." />
            </CardHeader>
            <CardContent>
              <pre className="max-h-[260px] overflow-auto rounded-2xl border border-black/10 bg-white p-4 text-xs leading-6 text-slate-950 shadow-sm">
                {JSON.stringify(payloadPreview, null, 2)}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <SectionTitle icon={Settings2} title="Backend Result" desc="Live result from direct or queued planner execution." />
            </CardHeader>
            <CardContent>
              <pre className="max-h-[320px] overflow-auto rounded-2xl border border-black/10 bg-white p-4 text-xs leading-6 text-slate-950 shadow-sm">
                {backendResult
                  ? JSON.stringify(backendResult, null, 2)
                  : "Run the planner to see backend output here."}
              </pre>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
