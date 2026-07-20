import { useCallback, useEffect, useRef, useState } from "react";

import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import type { ProjectStatusSummary } from "../utils/workspaceShell";

export type DashboardPreviewMode = "2d" | "3d";
export type DashboardPreviewQuality = "standard" | "high";

type UseDashboardPreviewModeStateOptions = {
  updateProjectStatus: (summary: Omit<ProjectStatusSummary, "updatedAt">) => void;
};

export function useDashboardPreviewModeState({
  updateProjectStatus,
}: UseDashboardPreviewModeStateOptions) {
  const [previewMode, setPreviewMode] = useState<DashboardPreviewMode>("2d");
  const [previewQuality, setPreviewQuality] = useState<DashboardPreviewQuality>("standard");
  const previewModeProbeRef = useRef<{ value: DashboardPreviewMode; startedAt: number } | null>(null);
  const previewQualityProbeRef = useRef<{ value: DashboardPreviewQuality; startedAt: number } | null>(null);

  const handleSetPreviewMode = useCallback(
    (value: DashboardPreviewMode) => {
      if (value !== previewMode) {
        previewModeProbeRef.current = { value, startedAt: markCivoraInteraction() };
      }
      setPreviewMode(value);
    },
    [previewMode],
  );

  const handleSetPreviewQuality = useCallback(
    (value: DashboardPreviewQuality) => {
      if (value !== previewQuality) {
        previewQualityProbeRef.current = { value, startedAt: markCivoraInteraction() };
      }
      if (value === "high") {
        updateProjectStatus({
          state: "working",
          area: "ai realism",
          title: "Creating AI realism",
          detail: "Civora is switching to high-quality visual preview mode.",
          nextAction: "Review the preview panel for provider, object, or layout blockers.",
        });
      } else {
        updateProjectStatus({
          state: "ready",
          area: "ai realism",
          title: "AI realism off",
          detail: "Returned to Standard preview quality.",
          nextAction: "Continue drafting or open Generate when ready.",
        });
      }
      setPreviewQuality(value);
    },
    [previewQuality, updateProjectStatus],
  );

  useEffect(() => {
    const probe = previewModeProbeRef.current;
    if (!probe || probe.value !== previewMode) return;
    measureCivoraInteractionAfterPaint(`preview.mode.${previewMode}`, probe.startedAt, { mode: previewMode });
    previewModeProbeRef.current = null;
  }, [previewMode]);

  useEffect(() => {
    const probe = previewQualityProbeRef.current;
    if (!probe || probe.value !== previewQuality) return;
    measureCivoraInteractionAfterPaint(`preview.quality.${previewQuality}`, probe.startedAt, {
      quality: previewQuality,
    });
    previewQualityProbeRef.current = null;
  }, [previewQuality]);

  return {
    previewMode,
    setPreviewMode,
    previewQuality,
    setPreviewQuality,
    handleSetPreviewMode,
    handleSetPreviewQuality,
  };
}
