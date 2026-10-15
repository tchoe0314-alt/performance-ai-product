"use client";

import { useRef, useState } from "react";
import { apiErrorMessage, postJson } from "../../lib/api";

const inputClass = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900";
const buttonClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 disabled:opacity-50";

export function PasswordRecoveryForm({ email, onEmailChange, onComplete }: {
  email: string; onEmailChange: (value: string) => void; onComplete: () => void;
}) {
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const pending = useRef(false);

  async function submit(confirm: boolean) {
    if (pending.current) return;
    pending.current = true; setBusy(true); setStatus("");
    try {
      if (confirm) {
        await postJson("/api/auth/password-reset/confirm", { email, token: code.trim(), new_password: password });
        setCode(""); setPassword(""); onComplete();
        setStatus("Password changed. Sign in again.");
      } else {
        await postJson("/api/auth/password-reset/request", { email });
        setStatus("If that account exists, a code was sent.");
      }
    } catch (error) { setStatus(apiErrorMessage(error, "Could not reset password.")); }
    finally { pending.current = false; setBusy(false); }
  }

  return <details className="mt-4 rounded-xl border border-slate-200 p-3" data-testid="password-recovery">
    <summary className="cursor-pointer text-sm font-medium text-slate-800">Forgot password?</summary>
    <form className="mt-3 space-y-3" onSubmit={event => { event.preventDefault(); void submit(true); }}>
      <label className="block text-sm text-slate-700">Recovery email
        <input type="email" autoComplete="email" value={email} onChange={event => onEmailChange(event.target.value)} required maxLength={254} disabled={busy} className={inputClass} />
      </label>
      <button type="button" disabled={busy || !email.trim()} onClick={() => void submit(false)} className={buttonClass}>Send reset code</button>
      <label className="block text-sm text-slate-700">Reset code
        <input type="password" autoComplete="one-time-code" value={code} onChange={event => setCode(event.target.value)} required maxLength={256} disabled={busy} className={inputClass} />
      </label>
      <label className="block text-sm text-slate-700">New password
        <input type="password" autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} required minLength={8} maxLength={1024} disabled={busy} className={inputClass} />
      </label>
      <button type="submit" disabled={busy || !code.trim() || password.length < 8} className={buttonClass}>{busy ? "Working…" : "Reset password"}</button>
      <p role="status" className="text-sm text-slate-700">{status}</p>
    </form>
  </details>;
}
