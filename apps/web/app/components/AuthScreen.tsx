"use client";

import { motion } from "framer-motion";
import { AlertCircle, Clock3, Eye, EyeOff, FolderOpen, LifeBuoy, Map, Sparkles } from "lucide-react";

import type { AuthStatus } from "../types";
import {
  Card,
  CardContent,
  CardHeader,
  Field,
  Pill,
  SectionTitle,
  SmallButton,
  TextInput,
} from "./ui";

type AuthScreenProps = {
  authMode: "login" | "register";
  authStatus: AuthStatus | null;
  authStatusError: string;
  authName: string;
  authEmail: string;
  authPassword: string;
  showPassword: boolean;
  authError: string;
  authLoading: boolean;
  onAuthModeChange: (mode: "login" | "register") => void;
  onAuthNameChange: (value: string) => void;
  onAuthEmailChange: (value: string) => void;
  onAuthPasswordChange: (value: string) => void;
  onTogglePassword: () => void;
  onClearAuthError: () => void;
  onSubmit: () => void;
};

export default function AuthScreen({
  authMode,
  authStatus,
  authStatusError,
  authName,
  authEmail,
  authPassword,
  showPassword,
  authError,
  authLoading,
  onAuthModeChange,
  onAuthNameChange,
  onAuthEmailChange,
  onAuthPasswordChange,
  onTogglePassword,
  onClearAuthError,
  onSubmit,
}: AuthScreenProps) {
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
              Civora AI — Civil Site Planning Review
            </h1>
            <p className="max-w-2xl text-lg leading-8 text-slate-600">
              Sign in to run civil site concepts, review traceable outcomes,
              and export engineer-review packages from one clean workflow.
            </p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
              <div className="space-y-2 text-sm leading-6 text-slate-600">
                <p>
                  Civora is a private-pilot planning and review workspace for
                  civil site concepts, assumptions, blockers, and review-package
                  materials.
                </p>
                <p className="font-semibold text-slate-800">
                  Every output requires user or licensed engineer review. Civora
                  does not replace professional responsibility or construction
                  release.
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  <a
                    href="/pilot#limitations"
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-slate-50"
                  >
                    Pilot limits
                  </a>
                  <a
                    href="/pilot#responsibility"
                    className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-slate-50"
                  >
                    Responsibility
                  </a>
                  <a
                    href="mailto:support@civora.ai?subject=Civora%20pilot%20support"
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-700 transition hover:bg-slate-50"
                  >
                    <LifeBuoy className="h-3.5 w-3.5" />
                    Support
                  </a>
                </div>
              </div>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card className="rounded-2xl">
              <CardContent className="p-5">
                <FolderOpen className="h-5 w-5 text-slate-900" />
                <p className="mt-3 text-sm font-medium text-slate-900">Projects</p>
                <p className="mt-1 text-sm text-slate-500">
                  Open, rerun, and review approved pilot project history.
                </p>
              </CardContent>
            </Card>
            <Card className="rounded-2xl">
              <CardContent className="p-5">
                <Clock3 className="h-5 w-5 text-slate-900" />
                <p className="mt-3 text-sm font-medium text-slate-900">Runs</p>
                <p className="mt-1 text-sm text-slate-500">
                  See what passed, what failed, and why it matters.
                </p>
              </CardContent>
            </Card>
            <Card className="rounded-2xl">
              <CardContent className="p-5">
                <Map className="h-5 w-5 text-slate-900" />
                <p className="mt-3 text-sm font-medium text-slate-900">Deliverables</p>
                <p className="mt-1 text-sm text-slate-500">
                  Preview, download, and share review-only civil outputs.
                </p>
              </CardContent>
            </Card>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="rounded-[28px]">
            <CardHeader>
              <SectionTitle
                icon={Sparkles}
                title={authMode === "register" ? "Request Pilot Access" : "Sign In"}
                desc="Auth is now user-scoped so projects and jobs are private per beta tester."
              />
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="inline-flex rounded-2xl border border-black/10 bg-slate-100 p-1">
                <button
                  type="button"
                  onClick={() => onAuthModeChange("login")}
                  className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                    authMode === "login"
                      ? "bg-white shadow-sm text-slate-900"
                      : "text-slate-600"
                  }`}
                >
                  Sign In Mode
                </button>
                <button
                  type="button"
                  onClick={() => onAuthModeChange("register")}
                  className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                    authMode === "register"
                      ? "bg-white shadow-sm text-slate-900"
                      : "text-slate-600"
                  }`}
                >
                  Request Access Mode
                </button>
              </div>
              <div className="rounded-2xl border border-black/10 bg-slate-50 p-4 text-sm text-slate-600">
                {authStatus ? (
                  authStatus.user_count > 0 ? (
                    <span>
                      {authStatus.user_count} Civora AI beta account
                      {authStatus.user_count === 1 ? "" : "s"} already exist in this
                      workspace. Use <strong>Sign In</strong> if you made one before,
                      or request approved pilot access.
                    </span>
                  ) : (
                    <span>No Civora AI beta accounts exist yet. Request invite-only pilot access here.</span>
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
                    onChange={(e) => onAuthNameChange(e.target.value)}
                    placeholder="Jane Engineer"
                  />
                </Field>
              ) : null}
              <Field label="Email">
                <TextInput
                  value={authEmail}
                  onChange={(e) => onAuthEmailChange(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                />
              </Field>
              <Field label="Password">
                <div className="relative">
                  <TextInput
                    type={showPassword ? "text" : "password"}
                    value={authPassword}
                    onChange={(e) => onAuthPasswordChange(e.target.value)}
                    placeholder="At least 8 characters"
                    autoComplete={
                      authMode === "register" ? "new-password" : "current-password"
                    }
                    className="pr-12"
                  />
                  <button
                    type="button"
                    onClick={onTogglePassword}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-xl p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </Field>
              {authError ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  {authError}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-3">
                <SmallButton onClick={onSubmit} disabled={authLoading}>
                  <Sparkles className="mr-2 h-4 w-4" />
                  {authLoading
                    ? "Working..."
                    : authMode === "register"
                      ? "Request Pilot Access"
                      : "Sign In"}
                </SmallButton>
                <SmallButton
                  variant="secondary"
                  onClick={() => {
                    onClearAuthError();
                    onAuthModeChange(authMode === "register" ? "login" : "register");
                  }}
                >
                  {authMode === "register" ? "Switch to sign-in" : "Switch to sign-up"}
                </SmallButton>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
