import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { apiErrorMessage, classifyApiError, getJson, postJson } from "../../lib/api";

import type { AuthStatus, UserRecord } from "../types";
import { isTransientLoginError, retryTransientLogin, withLoginDeadline } from "../utils/loginRetry";

import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
  shouldRestoreStoredToken,
} from "../utils/auth";

type RefreshJobsOptions = { suppressError?: boolean; force?: boolean };

type UseAuthStateOptions = {
  onRefreshProjects: (token: string) => Promise<void>;
  onRefreshJobs: (token: string, options?: RefreshJobsOptions) => Promise<void>;
  onStatusMessage?: (message: string) => void;
  onLogoutCleanup?: () => void;
  skipInitialAuthStatus?: boolean;
  skipStoredAuthRestore?: boolean;
  shouldSkipStoredAuthRestore?: () => boolean;
};

const noop = () => {};

export default function useAuthState({
  onRefreshProjects,
  onRefreshJobs,
  onStatusMessage = noop,
  onLogoutCleanup = noop,
  skipInitialAuthStatus = false,
  skipStoredAuthRestore = false,
  shouldSkipStoredAuthRestore,
}: UseAuthStateOptions) {
  const [token, setToken] = useState(() => {
    if (
      typeof window === "undefined" ||
      skipStoredAuthRestore ||
      !shouldRestoreStoredToken() ||
      shouldSkipStoredAuthRestore?.()
    ) {
      return "";
    }
    return getStoredToken();
  });
  const [user, setUser] = useState<UserRecord | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("register");
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authInvitationToken, setAuthInvitationToken] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authStatusError, setAuthStatusError] = useState("");
  const authGenerationRef = useRef(0);

  const refreshProjectsRef = useRef(onRefreshProjects);
  const refreshJobsRef = useRef(onRefreshJobs);
  const statusMessageRef = useRef(onStatusMessage);
  const shouldSkipStoredAuthRestoreRef = useRef(shouldSkipStoredAuthRestore);

  useEffect(() => {
    refreshProjectsRef.current = onRefreshProjects;
  }, [onRefreshProjects]);

  useEffect(() => {
    refreshJobsRef.current = onRefreshJobs;
  }, [onRefreshJobs]);

  useEffect(() => {
    statusMessageRef.current = onStatusMessage;
  }, [onStatusMessage]);

  useEffect(() => {
    shouldSkipStoredAuthRestoreRef.current = shouldSkipStoredAuthRestore;
  }, [shouldSkipStoredAuthRestore]);

  const loadMe = useCallback(async (authToken: string) => {
    try {
      const data = await getJson<{ user: UserRecord }>("/api/auth/me", {
        token: authToken,
      });
      return data.user;
    } catch (error) {
      if (classifyApiError(error) === "auth_expired") {
        throw new Error("Session expired. Sign in again.");
      }
      throw error;
    }
  }, []);

  const loadAuthStatus = useCallback(async (isCurrent: () => boolean = () => true) => {
    try {
      const data = await getJson<AuthStatus>("/api/auth/status");
      if (!isCurrent()) return;
      setAuthStatus(data);
      if (data.public_registration_enabled === false) setAuthMode("login");
      setAuthStatusError("");
    } catch (error) {
      if (!isCurrent()) return;
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
    const generation = ++authGenerationRef.current;
    setAuthLoading(true);
    setAuthError("");
    setAuthStatusError("");
    try {
      if (authMode === "register" && authStatus?.public_registration_enabled === false && !authInvitationToken.trim()) {
        throw new Error("Access is invitation-only. Sign in or contact support.");
      }
      const path =
        authMode === "register" ? "/api/auth/register" : "/api/auth/login";
      const body =
        authMode === "register"
          ? {
              name: authName,
              email: authEmail,
              password: authPassword,
              ...(authInvitationToken.trim() ? { invitation_token: authInvitationToken.trim() } : {}),
            }
          : {
              email: authEmail,
              password: authPassword,
            };
      const submit = () => postJson<{ token: string; user: UserRecord }>(path, body);
      const data = authMode === "login"
        ? await retryTransientLogin(() => withLoginDeadline(signal => postJson<{ token: string; user: UserRecord }>(path, body, { signal })))
        : await submit();
      if (generation !== authGenerationRef.current) return;
      setToken(data.token);
      setStoredToken(data.token);
      setUser(data.user);
      setAuthPassword(""); setAuthInvitationToken("");
      const refreshResults = await Promise.allSettled([
        refreshProjectsRef.current(data.token),
        refreshJobsRef.current(data.token, { suppressError: true }),
      ]);
      if (generation !== authGenerationRef.current) return;
      const refreshNeedsRetry = refreshResults.some((result) => result.status === "rejected");
      onStatusMessage(
        refreshNeedsRetry
          ? `Signed in to Civora AI as ${data.user.name}. Project or job lists need a refresh.`
          : `Signed in to Civora AI as ${data.user.name}.`,
      );
    } catch (error) {
      if (generation !== authGenerationRef.current) return;
      const kind = classifyApiError(error);
      setAuthError(
        authMode === "login" && isTransientLoginError(error)
          ? "Sign-in is temporarily unavailable. Try again shortly."
          : kind === "backend_unreachable"
          ? "Backend connection needs attention. Check the backend URL, then try signing in again."
          : kind === "api_blocked"
            ? "Backend access needs attention. Check the app/backend access settings, then retry sign-in."
            : apiErrorMessage(error, "Authentication failed."),
      );
    } finally {
      if (generation === authGenerationRef.current) setAuthLoading(false);
    }
  }, [authMode, authName, authEmail, authPassword, authInvitationToken, authStatus, onStatusMessage]);

  const handleLogout = useCallback(async () => {
    // Invalidate pending restore/sign-in before awaiting server revocation.
    // Nothing from this old logout may clear a subsequent sign-in either.
    ++authGenerationRef.current;
    clearStoredToken();
    setToken("");
    setUser(null);
    setAuthLoading(false);
    setAuthMode("login");
    setAuthPassword(""); setAuthInvitationToken(""); setAuthError("");
    onLogoutCleanup();
    onStatusMessage("Signed out.");
    try {
      if (token) {
        await postJson("/api/auth/logout", {}, { token });
      }
    } catch {
      // Ignore logout API errors and clear local state anyway.
    }
  }, [onLogoutCleanup, onStatusMessage, token]);

  useLayoutEffect(() => {
    if (
      token ||
      skipStoredAuthRestore ||
      !shouldRestoreStoredToken() ||
      shouldSkipStoredAuthRestoreRef.current?.()
    ) {
      return;
    }
    const stored = getStoredToken();
    if (stored) setToken(stored);
  }, [skipStoredAuthRestore, token]);

  useEffect(() => {
    const generation = ++authGenerationRef.current;
    let cancelled = false;
    const isCurrent = () => !cancelled && generation === authGenerationRef.current;
    const cleanup = () => {
      cancelled = true;
      ++authGenerationRef.current;
    };
    if (!skipInitialAuthStatus) {
      void loadAuthStatus(isCurrent);
    }
    const shouldSkipStoredRestore =
      skipStoredAuthRestore ||
      !shouldRestoreStoredToken() ||
      Boolean(shouldSkipStoredAuthRestoreRef.current?.());
    const stored = shouldSkipStoredRestore ? "" : getStoredToken();
    if (!stored) return cleanup;
    setToken(stored);
    void loadMe(stored)
      .then((restoredUser) => {
        if (!isCurrent()) return;
        setUser(restoredUser);
        setAuthStatusError("");
        void Promise.allSettled([
          refreshProjectsRef.current(stored),
          refreshJobsRef.current(stored, { suppressError: true }),
        ]);
      })
      .catch((error) => {
        if (!isCurrent()) return;
        // A rate limit/outage is not evidence that the credential expired.
        // Keep tab-scoped credentials for recovery; the server still authorizes
        // every operation. Only a genuine authentication rejection clears them.
        const expired = classifyApiError(error) === "auth_expired";
        if (expired) {
          clearStoredToken();
          setToken("");
        } else {
          statusMessageRef.current(apiErrorMessage(error, "Session check unavailable. Retry shortly."));
        }
        setAuthStatusError(
          error instanceof Error && error.message === "Session expired. Sign in again."
            ? "Session expired. Sign in again."
            : apiErrorMessage(error, "Backend connection needs attention. Sign in after the backend is available."),
        );
      });
    return cleanup;
  }, [
    loadAuthStatus,
    loadMe,
    skipInitialAuthStatus,
    skipStoredAuthRestore,
  ]);

  return {
    token,
    user,
    authMode,
    authStatus,
    authName,
    authEmail,
    authPassword,
    authInvitationToken,
    showPassword,
    authError,
    authLoading,
    authStatusError,
    setAuthMode,
    setAuthName,
    setAuthEmail,
    setAuthPassword,
    setAuthInvitationToken,
    setAuthError,
    setShowPassword,
    handleAuth,
    handleLogout,
  };
}
