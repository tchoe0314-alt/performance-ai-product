import { useCallback, useEffect, useRef, useState } from "react";

import { markCivoraInteraction, measureCivoraInteractionAfterPaint } from "../utils/performanceProbes";
import type { ProjectStatusSummary } from "../utils/workspaceShell";
import { environmentStorageKey, parseEnvironment, type EnvironmentScope } from "../utils/workspaceEnvironment";

export type DashboardPreviewMode = "2d" | "3d";
export type DashboardPreviewQuality = "standard" | "high";

type UseDashboardPreviewModeStateOptions = {
  updateProjectStatus: (summary: Omit<ProjectStatusSummary, "updatedAt">) => void;
  environmentScope?: EnvironmentScope;
};

export function useDashboardPreviewModeState({
  updateProjectStatus,
  environmentScope,
}: UseDashboardPreviewModeStateOptions) {
  const [previewMode, setPreviewMode] = useState<DashboardPreviewMode>("2d");
  const [previewQuality, setPreviewQuality] = useState<DashboardPreviewQuality>("standard");
  const previewModeProbeRef = useRef<{ value: DashboardPreviewMode; startedAt: number } | null>(null);
  const previewQualityProbeRef = useRef<{ value: DashboardPreviewQuality; startedAt: number } | null>(null);
  const previousEnvironmentScope = useRef<EnvironmentScope | null>(null);
  const account = environmentScope?.account ?? "", project = environmentScope?.project ?? "", generation = environmentScope?.generation ?? 0;
  useEffect(() => {
    if (!account) return;
    const scope = {account, project, generation}, old = previousEnvironmentScope.current;
    previousEnvironmentScope.current = scope;
    let raw: string | null = null;
    try {raw = sessionStorage.getItem(environmentStorageKey(scope));} catch { /* Optional tab memory. */ }
    // A first save or branch acknowledgement inherits the live view. A true
    // project open increments generation and restores that project's choice.
    if (!raw && old?.account === account && old.project !== project && project && old.generation === generation) return;
    const view = parseEnvironment(raw);
    // Parent-owned view hydration cannot be overwritten by an old canvas
    // instance's queued restoration when project loading remounts the canvas.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPreviewMode(view.mode);
    setPreviewQuality(view.quality);
  }, [account, project, generation]);

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
          state: "ready",
          area: "ai realism",
          title: "Plan Sheet view on",
          detail: "High-quality visual styling is on. AI Visualization remains separate and off until selected.",
          nextAction: "Review the plan view or turn on AI Visualization for a visual concept.",
        });
      } else {
        updateProjectStatus({
          state: "ready",
          area: "ai realism",
          title: "Draft view on",
          detail: "Returned to the standard drafting preview.",
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
