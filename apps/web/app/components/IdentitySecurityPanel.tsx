"use client";

import { useEffect, useId, useRef, useState } from "react";
import { apiErrorMessage, getJson, postJson } from "../../lib/api";

const inputClass = "mt-1 w-full min-w-0 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900";
const buttonClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 disabled:opacity-50";

export function IdentitySecurityPanel({ token, email, onProjectJoined, onSignedOut }: {
  token: string; email: string; onProjectJoined?: () => void | Promise<void>; onSignedOut: () => void;
}) {
  const id = useId();
  const [verified, setVerified] = useState<boolean | null>(null);
  const [emailCode, setEmailCode] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);

  async function run(action: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true; setBusy(true); setStatus("");
    try { await action(); }
    catch (error) { if (active.current) setStatus(apiErrorMessage(error, "Could not complete this action.")); }
    finally { pending.current = false; if (active.current) setBusy(false); }
  }

  return <details className="rounded-xl border border-slate-200 bg-white p-4" data-testid="identity-security"
    onToggle={event => { if (event.currentTarget.open && verified === null) void run(async () => {
      const response = await getJson<{ verified: boolean }>("/api/auth/email-verification/status", { token });
      if (active.current) setVerified(response.verified);
    }); }}>
    <summary className="cursor-pointer text-sm font-semibold text-slate-900">Account security</summary>
    <div className="mt-3 space-y-4">
      <p className="break-all text-xs text-slate-600">{email}</p>
      {verified === true ? <p className="text-sm text-slate-700">Email verified</p> : <form className="space-y-2" onSubmit={event => {
        event.preventDefault(); void run(async () => {
          await postJson("/api/auth/email-verification/confirm", { token: emailCode.trim() }, { token });
          if (!active.current) return;
          setVerified(true); setEmailCode(""); setStatus("Email verified.");
        });
      }}>
        <button type="button" disabled={busy} className={buttonClass} onClick={() => void run(async () => {
          await postJson("/api/auth/email-verification/request", {}, { token }); if (active.current) setStatus("Verification code sent.");
        })}>Send verification code</button>
        <label htmlFor={`${id}-email`} className="block text-xs font-medium text-slate-700">Email verification code</label>
        <input id={`${id}-email`} type="password" autoComplete="one-time-code" maxLength={256} value={emailCode} onChange={event => setEmailCode(event.target.value)} disabled={busy} className={inputClass} />
        <button disabled={busy || !emailCode.trim()} type="submit" className={buttonClass}>Verify email</button>
      </form>}
      <form className="space-y-2 border-t border-slate-100 pt-3" onSubmit={event => {
        event.preventDefault(); void run(async () => {
          await postJson("/api/invitations/accept", { token: inviteCode.trim() }, { token });
          if (!active.current) return;
          setInviteCode(""); setStatus("Invitation accepted. Open it from Projects.");
          try { await onProjectJoined?.(); } catch { if (active.current) setStatus("Invitation accepted. Refresh Projects to open it."); }
        });
      }}>
        <label htmlFor={`${id}-invite`} className="block text-xs font-medium text-slate-700">Invitation code</label>
        <input id={`${id}-invite`} type="password" autoComplete="one-time-code" maxLength={256} value={inviteCode} onChange={event => setInviteCode(event.target.value)} disabled={busy} className={inputClass} />
        <button disabled={busy || !inviteCode.trim()} type="submit" className={buttonClass}>Accept invitation</button>
      </form>
      <form className="space-y-2 border-t border-slate-100 pt-3" onSubmit={event => {
        event.preventDefault(); void run(async () => {
          await postJson("/api/auth/logout-all", { current_password: password }, { token });
          if (active.current) { setPassword(""); onSignedOut(); }
        });
      }}>
        <label htmlFor={`${id}-password`} className="block text-xs font-medium text-slate-700">Current password</label>
        <input id={`${id}-password`} type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} disabled={busy} className={inputClass} />
        <button disabled={busy || !password} type="submit" className={buttonClass}>Sign out all devices</button>
      </form>
      <p role="status" className="text-sm text-slate-700">{status}</p>
    </div>
  </details>;
}
