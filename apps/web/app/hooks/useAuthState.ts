import { useCallback, useEffect, useRef, useState } from "react";

import { apiErrorMessage, classifyApiError, getJson, postJson } from "../../lib/api";

import type { AuthStatus, UserRecord } from "../types";

import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from "../utils/auth";

type RefreshJobsOptions = { suppressError?: boolean; force?: boolean };

type UseAuthStateOptions = {
  onRefreshProjects: (token: string) => Promise<void>;
  onRefreshJobs: (token: string, options?: RefreshJobsOptions) => Promise<void>;
  onStatusMessage?: (message: string) => void;
  onLogoutCleanup?: () => void;
  skipInitialAuthStatus?: boolean;
  skipStoredAuthRestore?: boolean;
};

const noop = () => {};

export default function useAuthState({
  onRefreshProjects,
  onRefreshJobs,
  onStatusMessage = noop,
  onLogoutCleanup = noop,
  skipInitialAuthStatus = false,
  skipStoredAuthRestore = false,
}: UseAuthStateOptions) {
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

  const refreshProjectsRef = useRef(onRefreshProjects);
  const refreshJobsRef = useRef(onRefreshJobs);

  useEffect(() => {
    refreshProjectsRef.current = onRefreshProjects;
  }, [onRefreshProjects]);

  useEffect(() => {
    refreshJobsRef.current = onRefreshJobs;
  }, [onRefreshJobs]);

  const loadMe = useCallback(async (authToken: string) => {
    try {
      const data = await getJson<{ user: UserRecord }>("/api/auth/me", {
        token: authToken,
      });
      setUser(data.user);
      setAuthStatusError("");
    } catch (error) {
      if (classifyApiError(error) === "auth_expired") {
        throw new Error("Session expired. Sign in again.");
      }
      throw error;
    }
  }, []);

  const loadAuthStatus = useCallback(async () => {
    try {
      const data = await getJson<AuthStatus>("/api/auth/status");
      setAuthStatus(data);
      setAuthStatusError("");
    } catch (error) {
      setAuthStatus(null);
      const kind = classifyApiError(error);
      setAuthStatusError(
        kind === "backend_unreachable"
          ? "Backend connection needs attention. Sign-in will be available once the backend responds."
          : kind === "api_blocked"
            ? "Backend access needs attention. Check the app/backend access settings, then retry sign-in."
            : apiErrorMessage(error, "Civora AI could not load backend status."),
      );
    }
  }, []);

  const handleAuth = useCallback(async () => {
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
      await refreshProjectsRef.current(data.token);
      await refreshJobsRef.current(data.token, { suppressError: true });
      onStatusMessage(`Signed in to Civora AI as ${data.user.name}.`);
    } catch (error) {
      const kind = classifyApiError(error);
      setAuthError(
        kind === "backend_unreachable"
          ? "Backend connection needs attention. Check the backend URL, then try signing in again."
          : kind === "api_blocked"
            ? "Backend access needs attention. Check the app/backend access settings, then retry sign-in."
            : apiErrorMessage(error, "Authentication failed."),
      );
    } finally {
      setAuthLoading(false);
    }
  }, [authMode, authName, authEmail, authPassword, onStatusMessage]);

  const handleLogout = useCallback(async () => {
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
    onLogoutCleanup();
    onStatusMessage("Signed out.");
  }, [onLogoutCleanup, onStatusMessage, token]);

  useEffect(() => {
    if (!skipInitialAuthStatus) {
      void loadAuthStatus();
    }
    const stored = skipStoredAuthRestore ? "" : getStoredToken();
    if (!stored) return;
    setToken(stored);
    void loadMe(stored)
      .then(async () => {
        await refreshProjectsRef.current(stored);
        await refreshJobsRef.current(stored, { suppressError: true });
      })
      .catch((error) => {
        clearStoredToken();
        setToken("");
        setAuthStatusError(
          error instanceof Error && error.message === "Session expired. Sign in again."
            ? "Session expired. Sign in again."
            : apiErrorMessage(error, "Backend connection needs attention. Sign in after the backend is available."),
        );
      });
  }, [loadAuthStatus, loadMe, skipInitialAuthStatus, skipStoredAuthRestore]);

  return {
    token,
    user,
    authMode,
    authStatus,
    authName,
    authEmail,
    authPassword,
    showPassword,
    authError,
    authLoading,
    authStatusError,
    setAuthMode,
    setAuthName,
    setAuthEmail,
    setAuthPassword,
    setAuthError,
    setShowPassword,
    handleAuth,
    handleLogout,
  };
}
