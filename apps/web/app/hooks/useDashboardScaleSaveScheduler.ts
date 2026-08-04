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
  currentProjectRef: MutableRefObject<ProjectRecord | null>;
  detectionScaleFeet: string;
  detectionScalePixels: string;
  payloadPreviewRef: MutableRefObject<PlanRequestPayload>;
  projectLoadRequestRef: MutableRefObject<number>;
  resolvedProjectIdRef: MutableRefObject<string>;
  saveProjectRef: SaveProjectRef;
  scaleSaveTimeoutRef: MutableRefObject<number | null>;
  siteScaleLockedRef: MutableRefObject<boolean>;
};

export function useDashboardScaleSaveScheduler({
  currentProjectRef,
  detectionScaleFeet,
  detectionScalePixels,
  payloadPreviewRef,
  projectLoadRequestRef,
  resolvedProjectIdRef,
  saveProjectRef,
  scaleSaveTimeoutRef,
  siteScaleLockedRef,
}: UseDashboardScaleSaveSchedulerInput) {
  return useCallback(
    (ftPerPx: number, source: "mapbox" | "manual" | "approximate") => {
      if (scaleSaveTimeoutRef.current !== null) {
        window.clearTimeout(scaleSaveTimeoutRef.current);
        scaleSaveTimeoutRef.current = null;
      }
      const activeProjectId = resolvedProjectIdRef.current || currentProjectRef.current?.project_id || "";
      if (!activeProjectId) return;
      const workspaceGeneration = projectLoadRequestRef.current;
      scaleSaveTimeoutRef.current = window.setTimeout(() => {
        scaleSaveTimeoutRef.current = null;
        if (projectLoadRequestRef.current !== workspaceGeneration) return;
        if (resolvedProjectIdRef.current !== activeProjectId) return;
        if (!saveProjectRef.current) return;
        const liveProject = currentProjectRef.current;
        const currentInput = liveProject?.project_input ?? payloadPreviewRef.current;
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
                site_alignment_locked: siteScaleLockedRef.current,
              },
            },
          },
        });
      }, 600);
    },
    [
      currentProjectRef,
      detectionScaleFeet,
      detectionScalePixels,
      payloadPreviewRef,
      projectLoadRequestRef,
      resolvedProjectIdRef,
      saveProjectRef,
      scaleSaveTimeoutRef,
      siteScaleLockedRef,
    ],
  );
}
