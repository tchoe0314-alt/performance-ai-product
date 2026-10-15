import { classifyApiError } from "../../lib/api";

/** A deadline also settles callers whose transport ignores cancellation. */
export async function withLoginDeadline<T>(
  attempt: (signal: AbortSignal) => Promise<T>,
  timeoutMs = 15_000,
): Promise<T> {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new RangeError("Invalid sign-in deadline.");
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      const error = Object.assign(new Error("Sign-in took too long. Try again shortly."), { name: "LoginTimeoutError" });
      reject(error);
      controller.abort();
    }, timeoutMs);
  });
  try {
    return await Promise.race([deadline, attempt(controller.signal)]);
  } finally {
    clearTimeout(timer);
  }
}

export function isTransientLoginError(error: unknown): boolean {
  if (error instanceof Error && error.name === "AbortError") return false;
  const status = error && typeof error === "object" && "status" in error ? error.status : undefined;
  if (typeof status === "number") return [502, 503, 504].includes(status);
  return classifyApiError(error) === "backend_unreachable";
}

/** Login only: never reuse this policy for signup, billing or design writes. */
export async function retryTransientLogin<T>(
  attempt: () => Promise<T>,
  pause: () => Promise<void> = () => new Promise(resolve => setTimeout(resolve, 350)),
): Promise<T> {
  try {
    return await attempt();
  } catch (error) {
    if (!isTransientLoginError(error)) throw error;
    await pause();
    // Exactly one retry; the second error remains visible to the caller.
    return attempt();
  }
}
