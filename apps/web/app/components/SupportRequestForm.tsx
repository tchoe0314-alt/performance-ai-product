"use client";

import { useEffect, useState } from "react";
import { Send } from "lucide-react";

import { apiErrorMessage, postJson } from "../../lib/api";


export type SupportRequestRecord = {
  request_id: string;
  project_id?: string | null;
  category: string;
  severity: string;
  summary: string;
  status: string;
  created_at: number;
  updated_at: number;
};

type SupportRequestFormProps = {
  token: string | null;
  projectId?: string | null;
  initialCategory?: string;
  source?: string;
  onSubmitted?: (request: SupportRequestRecord) => void;
};

const categories = [
  ["workflow", "Workflow"],
  ["account", "Account"],
  ["data", "Project data"],
  ["source", "Source context"],
  ["export", "Export"],
  ["billing", "Billing"],
  ["privacy", "Privacy"],
  ["safety", "Safety"],
  ["other", "Other"],
] as const;

const categoryKeys = new Set(categories.map(([value]) => value));

const fieldClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200";

function normalizeCategory(value?: string) {
  const normalized = String(value || "workflow").trim().toLowerCase();
  if (normalized === "bug") return "workflow";
  return categoryKeys.has(normalized as (typeof categories)[number][0]) ? normalized : "workflow";
}

export function SupportRequestForm({
  token,
  projectId,
  initialCategory,
  source = "support_form",
  onSubmitted,
}: SupportRequestFormProps) {
  const [category, setCategory] = useState(() => normalizeCategory(initialCategory));
  const [severity, setSeverity] = useState("p2");
  const [summary, setSummary] = useState("");
  const [details, setDetails] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setCategory(normalizeCategory(initialCategory));
  }, [initialCategory]);

  const submit = async () => {
    if (!summary.trim()) {
      setStatus("Add a short summary first.");
      return;
    }
    if (!token) {
      setStatus("Sign in to submit an in-product issue.");
      return;
    }
    setBusy(true);
    setStatus("Sending issue...");
    try {
      const response = await postJson<{
        message: string;
        request: SupportRequestRecord;
      }>(
        "/api/support/requests",
        {
          project_id: projectId || "",
          category,
          severity,
          summary: summary.trim(),
          details: details.trim(),
          client_context: {
            source,
            page_url: `${window.location.origin}${window.location.pathname}`,
            user_agent: navigator.userAgent,
            viewport: { width: window.innerWidth, height: window.innerHeight },
          },
        },
        { token },
      );
      setStatus(response.message || `Issue received as ${response.request.request_id}.`);
      setSummary("");
      setDetails("");
      onSubmitted?.(response.request);
    } catch (error) {
      setStatus(apiErrorMessage(error, "Could not submit the issue. Try again after checking your connection."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="support-request-form">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="text-xs font-medium text-slate-600">
          Category
          <select className={`${fieldClass} mt-1`} value={category} onChange={(event) => setCategory(event.target.value)}>
            {categories.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">
          Impact
          <select className={`${fieldClass} mt-1`} value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="p2">Friction</option>
            <option value="p1">Workflow blocked</option>
            <option value="p0">Data or safety risk</option>
            <option value="p3">Suggestion</option>
          </select>
        </label>
      </div>
      <label className="block text-xs font-medium text-slate-600">
        What happened?
        <input
          className={`${fieldClass} mt-1`}
          value={summary}
          maxLength={240}
          autoComplete="off"
          onChange={(event) => setSummary(event.target.value)}
        />
      </label>
      <label className="block text-xs font-medium text-slate-600">
        Details
        <textarea
          className={`${fieldClass} mt-1 min-h-28 resize-y`}
          value={details}
          maxLength={8000}
          onChange={(event) => setDetails(event.target.value)}
        />
      </label>
      <button
        type="button"
        disabled={busy}
        onClick={() => void submit()}
        className="inline-flex h-9 items-center gap-2 rounded-lg bg-slate-950 px-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-wait disabled:opacity-50"
      >
        <Send className="h-4 w-4" />
        {busy ? "Sending..." : "Send issue"}
      </button>
      <p aria-live="polite" data-testid="support-request-status" className="min-h-5 text-xs leading-5 text-slate-600">
        {status}
      </p>
    </div>
  );
}
