"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, CheckCircle2, LifeBuoy, LogIn } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { SupportRequestForm, type SupportRequestRecord } from "../components/SupportRequestForm";
import { apiErrorMessage, classifyApiError, getJson } from "../../lib/api";
import { clearStoredToken, getStoredToken } from "../utils/auth";


type SupportListResponse = {
  requests: SupportRequestRecord[];
};

type AuthState = "checking" | "ready" | "signed_out" | "unavailable";

export function SupportPageClient() {
  const searchParams = useSearchParams();
  const requestedCategory = searchParams.get("category") || "workflow";
  const projectId = searchParams.get("project") || "";
  const [token, setToken] = useState("");
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [status, setStatus] = useState("Checking your Civora session...");
  const [requests, setRequests] = useState<SupportRequestRecord[]>([]);

  const loadRequests = useCallback(async (authToken: string) => {
    const response = await getJson<SupportListResponse>("/api/support/requests", { token: authToken });
    setRequests(response.requests.slice(0, 5));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const restoreSession = async () => {
      await Promise.resolve();
      const stored = getStoredToken();
      if (cancelled) return;
      if (!stored) {
        setAuthState("signed_out");
        setStatus("Sign in to Civora before sending an issue.");
        return;
      }
      setToken(stored);
      try {
        await getJson<{ user: { user_id: string } }>("/api/auth/me", { token: stored });
        if (cancelled) return;
        setAuthState("ready");
        setStatus("Your signed-in session is ready.");
        try {
          await loadRequests(stored);
        } catch (error) {
          if (!cancelled) {
            setStatus(apiErrorMessage(error, "Your session is ready. Recent reports could not load, but you can still send a new issue."));
          }
        }
      } catch (error) {
        if (cancelled) return;
        if (classifyApiError(error) === "auth_expired") {
          clearStoredToken();
          setToken("");
          setAuthState("signed_out");
          setStatus("Your session expired. Sign in again before sending an issue.");
          return;
        }
        setAuthState("unavailable");
        setStatus(apiErrorMessage(error, "Support is temporarily unavailable. Try again after checking your connection."));
      }
    };
    void restoreSession();
    return () => {
      cancelled = true;
    };
  }, [loadRequests]);

  const recordSubmission = (request: SupportRequestRecord) => {
    setRequests((current) => [request, ...current.filter((item) => item.request_id !== request.request_id)].slice(0, 5));
  };

  const reportTitle = requestedCategory.toLowerCase() === "bug" ? "Report a Civora problem" : "Civora support";

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-8 text-slate-900" data-testid="support-page">
      <div className="mx-auto max-w-3xl">
        <Link href="/demo/workspace" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-950">
          <ArrowLeft className="h-4 w-4" />
          Back to workspace
        </Link>

        <header className="mt-8 border-b border-slate-200 pb-7">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-200 bg-white">
            <LifeBuoy className="h-5 w-5 text-slate-700" />
          </div>
          <h1 className="mt-4 text-3xl font-semibold">{reportTitle}</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
            Tell us what happened, where it happened, and what you expected. Civora stores the report with a reference ID and removes authentication secrets from diagnostic context.
          </p>
        </header>

        <section className="mt-6 rounded-lg border border-slate-200 bg-white p-5">
          <div className="mb-5 flex items-start gap-3 border-b border-slate-100 pb-4">
            <CheckCircle2 className={`mt-0.5 h-5 w-5 ${authState === "ready" ? "text-emerald-600" : "text-slate-400"}`} />
            <div>
              <h2 className="text-sm font-semibold">Session</h2>
              <p aria-live="polite" className="mt-1 text-xs leading-5 text-slate-600">{status}</p>
            </div>
          </div>
          {authState === "ready" && token ? (
            <SupportRequestForm
              token={token}
              projectId={projectId}
              initialCategory={requestedCategory}
              source="standalone_support_page"
              onSubmitted={recordSubmission}
            />
          ) : authState === "signed_out" ? (
            <Link href="/demo/workspace" className="inline-flex h-9 items-center gap-2 rounded-lg bg-slate-950 px-3 text-sm font-semibold text-white">
              <LogIn className="h-4 w-4" />
              Open Civora to sign in
            </Link>
          ) : null}
        </section>

        {authState === "ready" ? (
          <section className="mt-5 rounded-lg border border-slate-200 bg-white p-5" data-testid="recent-support-requests">
            <h2 className="text-sm font-semibold">Recent reports</h2>
            {requests.length ? (
              <div className="mt-3 divide-y divide-slate-100">
                {requests.map((request) => (
                  <div key={request.request_id} className="grid gap-1 py-3 text-xs sm:grid-cols-[1fr_auto] sm:items-center">
                    <div>
                      <p className="font-semibold text-slate-800">{request.summary}</p>
                      <p className="mt-1 font-mono text-slate-500">{request.request_id}</p>
                    </div>
                    <span className="w-fit rounded-full bg-slate-100 px-2 py-1 font-medium capitalize text-slate-600">{request.status.replaceAll("_", " ")}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-xs leading-5 text-slate-500">No reports from this account yet.</p>
            )}
          </section>
        ) : null}

        <p className="mt-5 text-xs leading-5 text-slate-500">
          Do not include passwords, access tokens, private keys, or other credentials. For sign-in trouble, email{" "}
          <a className="font-semibold text-slate-700 underline" href="mailto:support@civora.ai?subject=Civora%20support">support@civora.ai</a>.
        </p>
      </div>
    </main>
  );
}
