import { expect, test } from "@playwright/test";
import type { postJson } from "../../lib/api";
import type { PlanRequestPayload, PlanResponse } from "../../app/types";
import { createDashboardPlanExecutor } from "../../app/utils/dashboardPlanExecution";
import { resolveCanonicalCanvasInput } from "../../app/utils/canonicalCanvasProject";

const payload = { project_id: "project-a" } as PlanRequestPayload;
const result = { final_plan: { actions: [], meta: {} }, explanation: { summary: "Fixture review draft" } } as PlanResponse;

test("direct and queued execution seal current geometry into the canonical document", async () => {
  for (const forceQueue of [false, true]) {
    let captured: PlanRequestPayload | undefined;
    const state = fixture(async (path, body) => {
      captured = (path === "/api/orchestrate" ? body : (body as { request: unknown }).request) as PlanRequestPayload;
      return path === "/api/orchestrate" ? result : { job: { job_id: "canonical-job" } };
    });
    const request = { manual_fields: { units: "ft", site_objects: [{ id: "road", type: "road", x: 140.25, y: 50, w: 30, d: 100 }] } } as PlanRequestPayload;
    expect(await state.execute({ mode: "run", requestPayload: request, forceQueue })).toBe(forceQueue ? "queued" : "completed");
    expect(captured?.canonical_project_v1).toBeTruthy();
    expect(resolveCanonicalCanvasInput(captured!).manual_fields?.site_objects?.[0].x).toBe(140.25);
  }
});

test("fallback keeps the sealed geometry even if the caller changes its original input", async () => {
  const request = { manual_fields: { site_objects: [{ id: "road", type: "road", x: 140.25, y: 50, w: 30, d: 100 }] } } as PlanRequestPayload;
  const state = fixture(async (path, body) => {
    if (path === "/api/orchestrate") {
      request.manual_fields!.site_objects![0].x = 999;
      throw new Error("Failed to fetch");
    }
    const queued = (body as { request: PlanRequestPayload }).request;
    expect(queued.manual_fields!.site_objects![0].x).toBe(140.25);
    expect(resolveCanonicalCanvasInput(queued).manual_fields!.site_objects![0].x).toBe(140.25);
    return { job: { job_id: "sealed-fallback" } };
  });
  expect(await state.execute({ mode: "run", requestPayload: request })).toBe("queued");
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(yes => { resolve = yes; });
  return { promise, resolve };
}
function fixture(transport: (path: string, body: unknown, options?: { signal?: AbortSignal; token?: string | null }) => Promise<unknown>) {
  let generation = 1;
  const writes: Array<[string, unknown]> = [];
  const controller = new AbortController();
  const directRunAbortRef = { current: controller as AbortController | null };
  const options = {
    token: "fixture", projectId: "project-a", fileName: "plan", siteName: "Office",
    getWorkspaceGeneration: () => generation, directRunAbortRef,
    setBusy: (value: boolean) => { writes.push(["busy", value]); },
    setActivePlanTool: (value: string) => { writes.push(["tool", value]); },
    setActiveJobId: (value: string) => { writes.push(["job", value]); },
    setPrompt: (value: string) => { writes.push(["prompt", value]); },
    setStatusMessage: (value: string) => { writes.push(["message", value]); },
    updateProjectStatus: (value: unknown) => { writes.push(["status", value]); },
    appendChatMessage: (_role: string, value: string) => { writes.push(["chat", value]); },
    applyBackendResult: (value: PlanResponse) => { writes.push(["result", value]); },
    requestPreview: async () => { writes.push(["preview", true]); },
    post: transport as typeof postJson,
  };
  return { options, writes, controller, execute: createDashboardPlanExecutor(options), switchProject: () => { generation++; } };
}

test("direct success publishes result, preview and review status and clears run ownership", async () => {
  const state = fixture(async () => result);
  expect(await state.execute({ mode: "fix", requestPayload: payload, clearPromptOnSuccess: true })).toBe("completed");
  expect(state.writes.filter(([key]) => key === "result")).toEqual([["result", result]]);
  expect(state.writes).toContainEqual(["preview", true]);
  expect(state.writes).toContainEqual(["prompt", ""]);
  expect(state.writes.at(-2)).toEqual(["busy", false]);
  expect(state.options.directRunAbortRef.current).toBeNull();
});

test("failed calculation cannot publish, preview, clear the prompt or return completed", async () => {
  const failure = { success: false, message: "Parking input is missing", missing_requirements: { missing_fields: ["parking_count"] }, final_plan: { actions: [], meta: {} } } as PlanResponse;
  const state = fixture(async () => failure);
  expect(await state.execute({ mode: "run", requestPayload: payload, clearPromptOnSuccess: true })).toBe("blocked");
  expect(state.writes.some(([key]) => ["result", "preview", "prompt"].includes(key))).toBe(false);
  expect(state.writes).toContainEqual(["message", "Parking input is missing"]);
  expect(state.writes.filter(([key]) => key === "status").at(-1)?.[1]).toMatchObject({ state: "blocked" });
  expect(state.writes.at(-2)).toEqual(["busy", false]);
});

test("server-archived calculation cannot become the active browser result", async () => {
  const state = fixture(async () => ({ ...result, success: true, metadata: { calculation_save_v1: { disposition: "archived", calculation_id: "older", reason: "project_inputs_changed" } } }));
  expect(await state.execute({ mode: "run", requestPayload: payload })).toBe("stale");
  expect(state.writes.some(([key]) => key === "result" || key === "preview")).toBe(false);
});

test("an unsaved edit during a direct run archives rather than publishing its result", async () => {
  const response = deferred<PlanResponse>();
  const state = fixture(async () => response.promise);
  let revision = "before";
  let retained = 0;
  const execute = createDashboardPlanExecutor({ ...state.options,
    getLiveInputFingerprint: () => revision,
    retainStaleResult: async () => { retained++; },
  });
  const running = execute({ mode: "run", requestPayload: payload });
  revision = "after edit";
  response.resolve(result);
  expect(await running).toBe("stale");
  expect(retained).toBe(1);
  expect(state.writes.some(([key]) => key === "result" || key === "preview")).toBe(false);
});

test("late direct result after project switch cannot publish or clear a new run", async () => {
  const response = deferred<PlanResponse>();
  const state = fixture(async () => response.promise);
  const run = state.execute({ mode: "run", requestPayload: payload });
  const initialWrites = state.writes.length;
  state.switchProject();
  const newer = new AbortController();
  state.options.directRunAbortRef.current = newer;
  response.resolve(result);
  expect(await run).toBe("stale");
  expect(state.writes).toHaveLength(initialWrites);
  expect(state.options.directRunAbortRef.current).toBe(newer);
});

test("late queued result after project switch cannot attach an old job", async () => {
  const response = deferred<{ job: { job_id: string } }>();
  const state = fixture(async () => response.promise);
  const run = state.execute({ mode: "run", requestPayload: payload, forceQueue: true });
  const initialWrites = state.writes.length;
  state.switchProject();
  response.resolve({ job: { job_id: "old-job" } });
  expect(await run).toBe("stale");
  expect(state.writes).toHaveLength(initialWrites);
});

test("switching during preview prevents late review status and prompt cleanup", async () => {
  const state = fixture(async () => result);
  state.options.requestPreview = async () => { state.switchProject(); };
  expect(await createDashboardPlanExecutor(state.options)({ mode: "run", requestPayload: payload, clearPromptOnSuccess: true })).toBe("stale");
  expect(state.writes.some(([key]) => key === "prompt")).toBe(false);
  expect(state.writes.some(([key, value]) => key === "status" && (value as { state: string }).state === "needs review")).toBe(false);
});

test("connectivity fallback queues exactly once and reports connection rather than timeout", async () => {
  const paths: string[] = [];
  const state = fixture(async (path, body) => {
    paths.push(path);
    if (path === "/api/orchestrate") throw new Error("Failed to fetch");
    expect(body).toEqual({ project_id: null, request: payload });
    return { job: { job_id: "queued" } };
  });
  expect(await state.execute({ mode: "run", requestPayload: payload, resolvedProjectId: null })).toBe("queued");
  expect(paths).toEqual(["/api/orchestrate", "/api/jobs/orchestrate"]);
  expect(state.writes).toContainEqual(["job", "queued"]);
  expect(state.writes.some(([key, value]) => key === "chat" && String(value).includes("direct connection was interrupted"))).toBe(true);
});

test("timeout queues once but explicit cancellation never starts a fallback job", async () => {
  for (const cancel of [false, true]) {
    const paths: string[] = [];
    const state = fixture(async (path, _body, options) => {
      paths.push(path);
      if (path === "/api/jobs/orchestrate") return { job: { job_id: "timeout-job" } };
      return new Promise((_resolve, reject) => {
        options?.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true });
      });
    });
    const run = state.execute({ mode: "run", requestPayload: payload, signal: state.controller.signal, timeoutMs: 5 });
    if (cancel) state.controller.abort();
    expect(await run).toBe(cancel ? "cancelled" : "queued");
    expect(paths).toEqual(cancel ? ["/api/orchestrate"] : ["/api/orchestrate", "/api/jobs/orchestrate"]);
  }
});

test("already cancelled requests do not change UI or start any network request", async () => {
  const state = fixture(async () => { throw new Error("Unexpected network request"); });
  state.controller.abort();
  expect(await state.execute({ mode: "run", requestPayload: payload, signal: state.controller.signal, forceQueue: true })).toBe("cancelled");
  expect(state.writes).toEqual([]);
});

test("disabled fallback and failed staged queue stay blocked and release busy state", async () => {
  for (const forceQueue of [false, true]) {
    const paths: string[] = [];
    const state = fixture(async path => { paths.push(path); throw new Error("Backend unreachable"); });
    expect(await state.execute({ mode: "run", requestPayload: payload, allowQueueFallback: false, forceQueue })).toBe("blocked");
    expect(paths).toEqual([forceQueue ? "/api/jobs/orchestrate" : "/api/orchestrate"]);
    expect(state.writes.some(([key, value]) => key === "status" && (value as { state: string }).state === "blocked")).toBe(true);
    expect(state.writes.at(-2)).toEqual(["busy", false]);
  }
});
