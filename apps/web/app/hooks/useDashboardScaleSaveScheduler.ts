import { useCallback, type MutableRefObject } from "react";

import type { PlanRequestPayload, PlanResponse, ProjectInput, ProjectRecord } from "../types";
import { parsePositiveNumber } from "../utils/formatting";

type SaveProjectRef = MutableRefObject<
  (options?: {
    silent?: boolean;
    projectIdOverride?: string | null;
    nameOverride?: string;
    fileNameOverride?: string;
    projectInputOverride?: ProjectInput;
    latestResultOverride?: PlanResponse;
    autoNamedOverride?: boolean;
    autoFileNamedOverride?: boolean;
  }) => Promise<ProjectRecord | null>
>;

type UseDashboardScaleSaveSchedulerInput = {
  currentProject: ProjectRecord | null;
  detectionScaleFeet: string;
  detectionScalePixels: string;
  payloadPreview: PlanRequestPayload;
  projectLoadRequestRef: MutableRefObject<number>;
  resolvedProjectIdRef: MutableRefObject<string>;
  saveProjectRef: SaveProjectRef;
  scaleSaveTimeoutRef: MutableRefObject<number | null>;
  siteScaleLocked: boolean;
};

export function useDashboardScaleSaveScheduler({
  currentProject,
  detectionScaleFeet,
  detectionScalePixels,
  payloadPreview,
  projectLoadRequestRef,
  resolvedProjectIdRef,
  saveProjectRef,
  scaleSaveTimeoutRef,
  siteScaleLocked,
}: UseDashboardScaleSaveSchedulerInput) {
  return useCallback(
    (ftPerPx: number, source: "mapbox" | "manual" | "approximate") => {
      if (scaleSaveTimeoutRef.current !== null) {
        window.clearTimeout(scaleSaveTimeoutRef.current);
        scaleSaveTimeoutRef.current = null;
      }
      const activeProjectId = resolvedProjectIdRef.current || currentProject?.project_id || "";
      if (!activeProjectId) return;
      const workspaceGeneration = projectLoadRequestRef.current;
      const currentInput = currentProject?.project_input ?? payloadPreview;
      scaleSaveTimeoutRef.current = window.setTimeout(() => {
        scaleSaveTimeoutRef.current = null;
        if (projectLoadRequestRef.current !== workspaceGeneration) return;
        if (resolvedProjectIdRef.current !== activeProjectId) return;
        if (!saveProjectRef.current) return;
        void saveProjectRef.current({
          silent: true,
          projectIdOverride: activeProjectId,
          projectInputOverride: {
            ...currentInput,
            input_mode: "user",
            strict_mode: false,
            allow_ai_fill_for_blanks: false,
            meta: {
              ...(currentInput?.meta ?? {}),
              site_inputs: {
                ...(currentInput?.meta?.site_inputs ?? {}),
                detection_scale: {
                  distance_ft: detectionScaleFeet ? parsePositiveNumber(detectionScaleFeet) ?? undefined : undefined,
                  pixel_distance: detectionScalePixels ? parsePositiveNumber(detectionScalePixels) ?? undefined : undefined,
                  scale_ft_per_px: ftPerPx,
                  scale_source: source,
                },
                site_alignment_locked: siteScaleLocked,
              },
            },
          },
        });
      }, 600);
    },
    [
      currentProject,
      detectionScaleFeet,
      detectionScalePixels,
      payloadPreview,
      projectLoadRequestRef,
      resolvedProjectIdRef,
      saveProjectRef,
      scaleSaveTimeoutRef,
      siteScaleLocked,
    ],
  );
}
