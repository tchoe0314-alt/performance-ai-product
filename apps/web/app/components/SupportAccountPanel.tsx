"use client";

import { useState } from "react";
import { AlertTriangle, Download, LifeBuoy, Trash2 } from "lucide-react";

import { apiErrorMessage, getJson, toApiUrl } from "../../lib/api";
import { SupportRequestForm } from "./SupportRequestForm";


type SupportAccountPanelProps = {
  token: string | null;
  projectId?: string | null;
  userEmail: string;
  onAccountDeleted: () => void;
};

type DeletionReadiness = {
  success: boolean;
  ready: boolean;
  confirmation_phrase: string;
  blockers: Array<{ code: string; message: string }>;
};

const fieldClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200";

async function downloadAccountArchive(token: string): Promise<void> {
  const response = await fetch(toApiUrl("/api/account/export"), {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(String(payload?.detail || `Export failed with status ${response.status}.`));
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] || "civora-account-export.zip";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

export function SupportAccountPanel({ token, projectId, userEmail, onAccountDeleted }: SupportAccountPanelProps) {
  const [exportBusy, setExportBusy] = useState(false);
  const [accountStatus, setAccountStatus] = useState("");
  const [readiness, setReadiness] = useState<DeletionReadiness | null>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);

  const exportData = async () => {
    if (!token) {
      setAccountStatus("Sign in before downloading account data.");
      return;
    }
    setExportBusy(true);
    setAccountStatus("Preparing account archive...");
    try {
      await downloadAccountArchive(token);
      setAccountStatus("Account archive downloaded.");
    } catch (error) {
      setAccountStatus(apiErrorMessage(error, "Could not prepare the account archive."));
    } finally {
      setExportBusy(false);
    }
  };

  const checkDeletion = async () => {
    if (!token) {
      setAccountStatus("Sign in before managing account deletion.");
      return;
    }
    setAccountStatus("Checking account ownership...");
    try {
      const response = await getJson<DeletionReadiness>("/api/account/deletion-readiness", { token });
      setReadiness(response);
      setAccountStatus(
        response.ready
          ? "Deletion is available after password and exact confirmation. Download an archive first."
          : response.blockers.map((item) => item.message).join(" "),
      );
    } catch (error) {
      setAccountStatus(apiErrorMessage(error, "Could not check account deletion readiness."));
    }
  };

  const deleteAccount = async () => {
    if (!token || !readiness?.ready) return;
    setDeleteBusy(true);
    setAccountStatus("Deleting account data...");
    try {
      const response = await fetch(toApiUrl("/api/account"), {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ current_password: password, confirmation }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(String(payload?.detail || "Account deletion could not complete."));
      if (!payload?.account_deleted) throw new Error(String(payload?.message || "Account deletion could not complete."));
      setAccountStatus(String(payload?.message || "Account deleted."));
      if (payload?.storage_cleanup_complete === false) {
        window.alert(String(payload?.message || "Account access was removed, but file cleanup needs support follow-up."));
      }
      onAccountDeleted();
    } catch (error) {
      setAccountStatus(apiErrorMessage(error, "Account deletion could not complete."));
    } finally {
      setDeleteBusy(false);
    }
  };

  return (
    <div className="space-y-3" data-testid="support-account-panel">
      <details data-testid="support-disclosure" className="group rounded-xl border border-slate-200 bg-white">
        <summary data-testid="support-summary" className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm font-semibold text-slate-900">
          <LifeBuoy className="h-4 w-4 text-slate-500" />
          Support
          <span className="ml-auto text-xs font-normal text-slate-500 group-open:hidden">Report a problem</span>
        </summary>
        <div className="space-y-3 border-t border-slate-100 p-4">
          <SupportRequestForm token={token} projectId={projectId} source="workspace_help" />
          <p className="text-xs leading-5 text-slate-500">
            Login trouble? <a className="font-semibold text-slate-700 underline" href="mailto:support@civora.ai?subject=Civora%20support">Email support@civora.ai</a>.
          </p>
        </div>
      </details>

      <details data-testid="account-data-disclosure" className="group rounded-xl border border-slate-200 bg-white">
        <summary data-testid="account-data-summary" className="flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm font-semibold text-slate-900">
          <Download className="h-4 w-4 text-slate-500" />
          Account data
          <span className="ml-auto max-w-44 truncate text-xs font-normal text-slate-500 group-open:hidden">{userEmail}</span>
        </summary>
        <div className="space-y-3 border-t border-slate-100 p-4">
          <p className="text-xs leading-5 text-slate-600">Download owned project records, account history, uploaded files, and generated artifacts in one ZIP archive.</p>
          <button type="button" disabled={exportBusy} onClick={() => void exportData()} className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 disabled:opacity-50">
            <Download className="h-4 w-4" />
            {exportBusy ? "Preparing..." : "Download my data"}
          </button>

          <details data-testid="delete-account-disclosure" className="rounded-lg border border-red-200 bg-red-50/50">
            <summary data-testid="delete-account-summary" className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-xs font-semibold text-red-800">
              <AlertTriangle className="h-4 w-4" /> Delete account
            </summary>
            <div className="space-y-3 border-t border-red-100 p-3">
              <p className="text-xs leading-5 text-red-800">Deletion is permanent. Shared ownership must be transferred first. Download your archive before continuing.</p>
              <button type="button" onClick={() => void checkDeletion()} className="h-9 rounded-lg border border-red-200 bg-white px-3 text-sm font-semibold text-red-800">Check deletion</button>
              {readiness?.ready ? (
                <div className="space-y-2">
                  <label className="block text-xs font-medium text-red-800">
                    Current password
                    <input type="password" autoComplete="current-password" className={`${fieldClass} mt-1`} value={password} onChange={(event) => setPassword(event.target.value)} />
                  </label>
                  <label className="block text-xs font-medium text-red-800">
                    Type {readiness.confirmation_phrase}
                    <input className={`${fieldClass} mt-1`} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
                  </label>
                  <button type="button" disabled={deleteBusy || !password || confirmation !== readiness.confirmation_phrase} onClick={() => void deleteAccount()} className="inline-flex h-9 items-center gap-2 rounded-lg bg-red-700 px-3 text-sm font-semibold text-white disabled:opacity-40">
                    <Trash2 className="h-4 w-4" />
                    {deleteBusy ? "Deleting..." : "Permanently delete account"}
                  </button>
                </div>
              ) : null}
            </div>
          </details>
          <p aria-live="polite" className="text-xs leading-5 text-slate-600">{accountStatus}</p>
        </div>
      </details>
    </div>
  );
}
