import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiErrorMessage, classifyApiError, getJson, postJson } from "../../lib/api";
import type { BuildingPlacement } from "../types";
import type { AiRealismProviderMode } from "../utils/previewViewModel";
import {
  aiRealismMissingInputs as buildAiRealismMissingInputs,
  buildAiRealismLayoutHash,
  buildAiRealismSourceObjects,
  createAiRealismArtifact,
  summarizeAiRealismSourceObjects,
} from "../utils/previewAiRealism";
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import {
  AI_REALISM_WATERMARK,
  type AiRealismArtifact,
  type AiRealismGenerationStatus,
} from "./previewPanelTypes";

type AiRealismPreviewOptions = {
  authToken?: string | null;
  buildingPlacements: BuildingPlacement[];
  cadEntityPreviewObjects: BuildingPlacement[];
  suggestedPlacements: BuildingPlacement[];
  lotWidth: number;
  lotHeight: number;
  siteRotationDeg: number;
  hasTerrainSource: boolean;
  geocode: { lat?: number; lng?: number } | null | undefined;
  currentProjectId?: string | null;
  planPreviewProjectId?: string | null;
  providerMode: AiRealismProviderMode;
  onAiRealismChange?: (event: { type: "generated" | "stale" | "blocked"; detail: string }) => void;
};

type VisualizationJob = {
  job_id?: string;
  status?: string;
  stage?: string;
  stage_detail?: string;
  progress?: number;
  error?: string | null;
  result?: { artifact?: AiRealismArtifact; error_details?: { message?: string } };
};

const INITIAL_GENERATION_STATUS: AiRealismGenerationStatus = {
  state: "idle",
  stage: "",
  detail: "",
  progress: 0,
  jobId: "",
};

const POLL_INTERVAL_MS = 1000;
const MAX_POLL_ATTEMPTS = 180;
const MAX_CONSECUTIVE_POLL_FAILURES = 5;

function sleep(milliseconds: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));
}

export function useAiRealismPreview({
  authToken,
  buildingPlacements,
  cadEntityPreviewObjects,
  suggestedPlacements,
  lotWidth,
  lotHeight,
  siteRotationDeg,
  hasTerrainSource,
  geocode,
  currentProjectId,
  planPreviewProjectId,
  providerMode,
  onAiRealismChange,
}: AiRealismPreviewOptions) {
  const [aiRealismEnabled, setAiRealismEnabled] = useState(false);
  const [aiRealismArtifact, setAiRealismArtifact] = useState<AiRealismArtifact | null>(null);
  const [aiRealismBlocker, setAiRealismBlocker] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] = useState<AiRealismGenerationStatus>(INITIAL_GENERATION_STATUS);
  const aiRealismGenerationFrameRef = useRef<number | null>(null);
  const activeRequestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const requestSequenceRef = useRef(0);
  const mountedRef = useRef(true);

  const aiRealismSourceObjects = useMemo(
    () => buildAiRealismSourceObjects([...buildingPlacements, ...cadEntityPreviewObjects, ...suggestedPlacements]),
    [buildingPlacements, cadEntityPreviewObjects, suggestedPlacements],
  );
  const aiRealismLayoutHash = useMemo(
    () =>
      buildAiRealismLayoutHash({
        lotWidth,
        lotHeight,
        siteRotationDeg,
        hasTerrainSource,
        sourceObjects: aiRealismSourceObjects,
      }),
    [aiRealismSourceObjects, hasTerrainSource, lotHeight, lotWidth, siteRotationDeg],
  );
  const currentLayoutHashRef = useRef(aiRealismLayoutHash);
  currentLayoutHashRef.current = aiRealismLayoutHash;
  const aiRealismSourceSummary = useMemo(
    () => summarizeAiRealismSourceObjects(aiRealismSourceObjects),
    [aiRealismSourceObjects],
  );
  const aiRealismMissingInputs = useMemo(
    () => buildAiRealismMissingInputs({ sourceObjects: aiRealismSourceObjects, geocode, hasTerrainSource }),
    [aiRealismSourceObjects, geocode, hasTerrainSource],
  );
  const aiRealismStale = Boolean(
    aiRealismArtifact && aiRealismArtifact.source_layout_hash !== aiRealismLayoutHash,
  );
  const aiRealismStaleNoticeRef = useRef("");

  useEffect(() => {
    if (!aiRealismStale) {
      aiRealismStaleNoticeRef.current = "";
      return;
    }
    const key = `${aiRealismArtifact?.generated_timestamp || "artifact"}:${aiRealismLayoutHash}`;
    if (aiRealismStaleNoticeRef.current === key) return;
    aiRealismStaleNoticeRef.current = key;
    onAiRealismChange?.({
      type: "stale",
      detail: "AI visualization is stale after the review layout changed.",
    });
  }, [aiRealismArtifact?.generated_timestamp, aiRealismLayoutHash, aiRealismStale, onAiRealismChange]);

  const stopActiveRequest = useCallback(() => {
    activeRequestRef.current?.controller.abort();
    activeRequestRef.current = null;
  }, []);

  const setBlocked = useCallback((detail: string, state: "failed" | "unavailable" = "failed") => {
    setAiRealismBlocker(detail);
    setGenerationStatus((previous) => ({
      ...previous,
      state,
      stage: state === "unavailable" ? "Visualization unavailable" : "Could not complete",
      detail,
    }));
    onAiRealismChange?.({ type: "blocked", detail });
  }, [onAiRealismChange]);

  const pollVisualizationJob = useCallback(async ({
    jobId,
    requestId,
    requestedLayoutHash,
    controller,
  }: {
    jobId: string;
    requestId: number;
    requestedLayoutHash: string;
    controller: AbortController;
  }) => {
    let consecutivePollFailures = 0;
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
      if (controller.signal.aborted || activeRequestRef.current?.id !== requestId) return;
      let response: { success: boolean; job: VisualizationJob };
      try {
        response = await getJson<{ success: boolean; job: VisualizationJob }>(`/api/jobs/${jobId}`, {
          token: authToken,
          signal: controller.signal,
        });
        consecutivePollFailures = 0;
      } catch (error) {
        if (controller.signal.aborted || activeRequestRef.current?.id !== requestId) return;
        const kind = classifyApiError(error);
        const status = Number((error as { status?: number })?.status || 0);
        const retryable =
          kind === "backend_unreachable" ||
          kind === "rate_limited" ||
          (kind === "request_failed" && status >= 500);
        consecutivePollFailures += 1;
        if (!retryable || consecutivePollFailures > MAX_CONSECUTIVE_POLL_FAILURES) throw error;
        setGenerationStatus((previous) => ({
          ...previous,
          state: previous.state === "queued" ? "queued" : "generating",
          stage: "Reconnecting to visualization job",
          detail: "The renderer is still working. Civora is retrying a temporary status connection.",
          jobId,
        }));
        await sleep(
          kind === "rate_limited"
            ? 5_000
            : POLL_INTERVAL_MS * Math.min(3, consecutivePollFailures),
        );
        continue;
      }
      const job = response.job || {};
      const status = String(job.status || "queued").toLowerCase();
      const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
      setGenerationStatus({
        state: status === "queued" || status === "pending" ? "queued" : "generating",
        stage: String(job.stage || (status === "queued" ? "Queued" : "Generating visualization")),
        detail: String(job.stage_detail || "Creating a visual concept from the current layout."),
        progress,
        jobId,
      });
      if (status === "completed") {
        const artifact = job.result?.artifact;
        if (!artifact?.image_data_url) {
          throw new Error("The visualization job completed without an image. Retry the visualization.");
        }
        if (
          artifact.source_layout_hash !== requestedLayoutHash ||
          requestedLayoutHash !== currentLayoutHashRef.current
        ) {
          setBlocked("The layout changed while the visualization was generating. Regenerate from the current layout.");
          return;
        }
        setAiRealismArtifact(artifact);
        setAiRealismBlocker(null);
        setGenerationStatus({
          state: "ready",
          stage: "Visualization ready",
          detail: artifact.renderer === "civora_hybrid"
            ? "Civora's private hybrid renderer generated a visual concept from the current layout controls."
            : "External photorealistic visual concept generated from the current layout.",
          progress: 100,
          jobId,
        });
        onAiRealismChange?.({
          type: "generated",
          detail: artifact.renderer === "civora_hybrid"
            ? "Private hybrid visualization generated from the current review layout."
            : "External photorealistic visualization generated from the current review layout.",
        });
        return;
      }
      if (["failed", "cancelled"].includes(status)) {
        throw new Error(
          String(job.result?.error_details?.message || job.error || "The visualization could not complete. Retry in a moment."),
        );
      }
      await sleep(POLL_INTERVAL_MS);
    }
    throw new Error("The visualization is taking longer than expected. Retry, or continue using the technical plan view.");
  }, [authToken, onAiRealismChange, setBlocked]);

  const generateAiRealismArtifact = useCallback(async () => {
    if (!aiRealismSourceObjects.length) {
      setBlocked("Add or generate proposed design objects before creating AI visualization.");
      return;
    }
    if (providerMode === "disabled") {
      setBlocked("AI visualization provider is not configured.", "unavailable");
      return;
    }
    stopActiveRequest();
    if (providerMode === "mock") {
      setAiRealismArtifact(createAiRealismArtifact({
        currentProjectId,
        planPreviewProjectId,
        sourceLayoutHash: aiRealismLayoutHash,
        sourceObjects: aiRealismSourceObjects,
        sourceSummary: aiRealismSourceSummary,
        missingInputs: aiRealismMissingInputs,
        hasTerrainSource,
        lotWidth,
        lotHeight,
        mapContextAvailable:
          typeof geocode?.lat === "number" && Number.isFinite(geocode.lat) &&
          typeof geocode?.lng === "number" && Number.isFinite(geocode.lng),
        watermark: AI_REALISM_WATERMARK,
      }));
      setAiRealismBlocker(null);
      setGenerationStatus({
        state: "ready",
        stage: "Plan visualization ready",
        detail: "Deterministic local reference visualization generated.",
        progress: 100,
        jobId: "",
      });
      onAiRealismChange?.({
        type: "generated",
        detail: "AI visualization regenerated from the current review layout.",
      });
      return;
    }
    if (!authToken) {
      setBlocked("Sign in to create a photorealistic visualization.", "unavailable");
      return;
    }

    const requestId = ++requestSequenceRef.current;
    const controller = new AbortController();
    activeRequestRef.current = { id: requestId, controller };
    setAiRealismBlocker(null);
    setGenerationStatus({
      state: "queued",
      stage: "Queueing visualization",
      detail: "Sending bounded geometry controls to the visualization queue.",
      progress: 8,
      jobId: "",
    });
    try {
      const response = await postJson<{ success: boolean; job: VisualizationJob }>(
        "/api/jobs/ai-visualization",
        {
          project_id: currentProjectId || planPreviewProjectId || null,
          source_layout_hash: aiRealismLayoutHash,
          source_objects: aiRealismSourceObjects,
          source_objects_summary: aiRealismSourceSummary,
          missing_inputs: aiRealismMissingInputs,
          site_frame: {
            width_ft: lotWidth,
            height_ft: lotHeight,
            rotation_deg: siteRotationDeg,
            map_context_available:
              typeof geocode?.lat === "number" && Number.isFinite(geocode.lat) &&
              typeof geocode?.lng === "number" && Number.isFinite(geocode.lng),
          },
          geocode: geocode || {},
          visual_style: "orthographic aerial site concept",
        },
        { token: authToken, signal: controller.signal },
      );
      const jobId = String(response.job?.job_id || "");
      if (!jobId) throw new Error("The backend did not return a visualization job ID.");
      setGenerationStatus((previous) => ({ ...previous, jobId }));
      await pollVisualizationJob({
        jobId,
        requestId,
        requestedLayoutHash: aiRealismLayoutHash,
        controller,
      });
    } catch (error) {
      if (controller.signal.aborted || !mountedRef.current) return;
      setBlocked(apiErrorMessage(error, "The visualization could not complete. Retry in a moment."));
    } finally {
      if (activeRequestRef.current?.id === requestId) activeRequestRef.current = null;
    }
  }, [
    aiRealismLayoutHash,
    aiRealismMissingInputs,
    aiRealismSourceObjects,
    aiRealismSourceSummary,
    authToken,
    currentProjectId,
    geocode,
    hasTerrainSource,
    lotHeight,
    lotWidth,
    onAiRealismChange,
    planPreviewProjectId,
    pollVisualizationJob,
    providerMode,
    setBlocked,
    siteRotationDeg,
    stopActiveRequest,
  ]);

  const setAiVisualizationOff = useCallback(() => {
    const startedAt = markCivoraInteraction();
    if (aiRealismGenerationFrameRef.current !== null) {
      window.cancelAnimationFrame(aiRealismGenerationFrameRef.current);
      aiRealismGenerationFrameRef.current = null;
    }
    stopActiveRequest();
    setAiRealismEnabled(false);
    setAiRealismBlocker(null);
    measureCivoraInteractionAfterPaint("preview.aiVisualization.off", startedAt, {
      hasArtifact: Boolean(aiRealismArtifact),
    });
  }, [aiRealismArtifact, stopActiveRequest]);

  const setAiVisualizationOn = useCallback(() => {
    const startedAt = markCivoraInteraction();
    setAiRealismEnabled(true);
    measureCivoraInteractionAfterPaint("preview.aiVisualization.on", startedAt, {
      hasArtifact: Boolean(aiRealismArtifact),
      providerConfigured: providerMode !== "disabled",
    });
    if (aiRealismArtifact || aiRealismGenerationFrameRef.current !== null) return;
    aiRealismGenerationFrameRef.current = window.requestAnimationFrame(() => {
      aiRealismGenerationFrameRef.current = null;
      void generateAiRealismArtifact();
    });
  }, [aiRealismArtifact, generateAiRealismArtifact, providerMode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleVisualizationCommand = (event: Event) => {
      const enabled = (event as CustomEvent<{ enabled?: boolean }>).detail?.enabled !== false;
      if (enabled) {
        setAiVisualizationOn();
      } else {
        setAiVisualizationOff();
      }
    };
    window.addEventListener("civora:set-ai-visualization", handleVisualizationCommand);
    return () => window.removeEventListener("civora:set-ai-visualization", handleVisualizationCommand);
  }, [setAiVisualizationOff, setAiVisualizationOn]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (aiRealismGenerationFrameRef.current !== null) {
        window.cancelAnimationFrame(aiRealismGenerationFrameRef.current);
      }
      stopActiveRequest();
    };
  }, [stopActiveRequest]);

  const aiRealismDisplayArtifact = useMemo(
    () => (aiRealismArtifact ? { ...aiRealismArtifact, stale: aiRealismStale } : null),
    [aiRealismArtifact, aiRealismStale],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const debugWindow = window as unknown as Record<string, unknown>;
    debugWindow.__civoraAiRealismArtifact = aiRealismDisplayArtifact;
    debugWindow.__civoraAiRealismEnabled = aiRealismEnabled;
    debugWindow.__civoraAiRealismLayoutHash = aiRealismLayoutHash;
    debugWindow.__civoraAiRealismGenerationStatus = generationStatus;
  }, [aiRealismDisplayArtifact, aiRealismEnabled, aiRealismLayoutHash, generationStatus]);

  return {
    aiRealismEnabled,
    aiRealismBlocker,
    aiRealismSourceSummary,
    aiRealismMissingInputs,
    aiRealismDisplayArtifact,
    generationStatus,
    generateAiRealismArtifact,
    setAiVisualizationOff,
    setAiVisualizationOn,
  };
}
