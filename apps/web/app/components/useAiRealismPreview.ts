import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { BuildingPlacement } from "../types";
import {
  aiRealismMissingInputs as buildAiRealismMissingInputs,
  buildAiRealismLayoutHash,
  buildAiRealismSourceObjects,
  createAiRealismArtifact,
  summarizeAiRealismSourceObjects,
} from "../utils/previewAiRealism";
import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import { AI_REALISM_WATERMARK, type AiRealismArtifact } from "./previewPanelTypes";

type AiRealismPreviewOptions = {
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
  aiRealismProviderConfigured: boolean;
  onAiRealismChange?: (event: { type: "generated" | "stale" | "blocked"; detail: string }) => void;
};

export function useAiRealismPreview({
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
  aiRealismProviderConfigured,
  onAiRealismChange,
}: AiRealismPreviewOptions) {
  const [aiRealismEnabled, setAiRealismEnabled] = useState(false);
  const [aiRealismArtifact, setAiRealismArtifact] = useState<AiRealismArtifact | null>(null);
  const [aiRealismBlocker, setAiRealismBlocker] = useState<string | null>(null);
  const aiRealismGenerationFrameRef = useRef<number | null>(null);

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
  const aiRealismSourceSummary = useMemo(
    () => summarizeAiRealismSourceObjects(aiRealismSourceObjects),
    [aiRealismSourceObjects],
  );
  const aiRealismMissingInputs = useMemo(
    () => buildAiRealismMissingInputs({
      sourceObjects: aiRealismSourceObjects,
      geocode,
      hasTerrainSource,
    }),
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
      detail: "AI realism visualization is stale after the review layout changed.",
    });
  }, [aiRealismArtifact?.generated_timestamp, aiRealismLayoutHash, aiRealismStale, onAiRealismChange]);

  const generateAiRealismArtifact = useCallback(() => {
    if (!aiRealismSourceObjects.length) {
      setAiRealismBlocker("Add or generate site objects before creating AI realism.");
      onAiRealismChange?.({
        type: "blocked",
        detail: "Add or generate site objects before creating AI realism.",
      });
      return;
    }
    if (!aiRealismProviderConfigured) {
      setAiRealismBlocker("AI realism provider is not configured.");
      onAiRealismChange?.({
        type: "blocked",
        detail: "AI realism provider is not configured.",
      });
      return;
    }
    setAiRealismArtifact(createAiRealismArtifact({
      currentProjectId,
      planPreviewProjectId,
      sourceLayoutHash: aiRealismLayoutHash,
      sourceObjects: aiRealismSourceObjects,
      sourceSummary: aiRealismSourceSummary,
      missingInputs: aiRealismMissingInputs,
      hasTerrainSource,
      watermark: AI_REALISM_WATERMARK,
    }));
    setAiRealismBlocker(null);
    onAiRealismChange?.({
      type: "generated",
      detail: "AI realism visualization regenerated from the current review layout.",
    });
  }, [
    aiRealismLayoutHash,
    aiRealismMissingInputs,
    aiRealismProviderConfigured,
    aiRealismSourceObjects,
    aiRealismSourceSummary,
    currentProjectId,
    hasTerrainSource,
    onAiRealismChange,
    planPreviewProjectId,
  ]);

  const setAiVisualizationOff = useCallback(() => {
    const startedAt = markCivoraInteraction();
    if (aiRealismGenerationFrameRef.current !== null) {
      window.cancelAnimationFrame(aiRealismGenerationFrameRef.current);
      aiRealismGenerationFrameRef.current = null;
    }
    setAiRealismEnabled(false);
    setAiRealismBlocker(null);
    measureCivoraInteractionAfterPaint("preview.aiVisualization.off", startedAt, {
      hasArtifact: Boolean(aiRealismArtifact),
    });
  }, [aiRealismArtifact]);

  const setAiVisualizationOn = useCallback(() => {
    const startedAt = markCivoraInteraction();
    setAiRealismEnabled(true);
    measureCivoraInteractionAfterPaint("preview.aiVisualization.on", startedAt, {
      hasArtifact: Boolean(aiRealismArtifact),
      providerConfigured: aiRealismProviderConfigured,
    });
    if (aiRealismArtifact || aiRealismGenerationFrameRef.current !== null) return;
    aiRealismGenerationFrameRef.current = window.requestAnimationFrame(() => {
      aiRealismGenerationFrameRef.current = null;
      generateAiRealismArtifact();
    });
  }, [aiRealismArtifact, aiRealismProviderConfigured, generateAiRealismArtifact]);

  useEffect(() => {
    return () => {
      if (aiRealismGenerationFrameRef.current !== null) {
        window.cancelAnimationFrame(aiRealismGenerationFrameRef.current);
      }
    };
  }, []);

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
  }, [aiRealismDisplayArtifact, aiRealismEnabled, aiRealismLayoutHash]);

  return {
    aiRealismEnabled,
    aiRealismBlocker,
    aiRealismSourceSummary,
    aiRealismMissingInputs,
    aiRealismDisplayArtifact,
    generateAiRealismArtifact,
    setAiVisualizationOff,
    setAiVisualizationOn,
  };
}
