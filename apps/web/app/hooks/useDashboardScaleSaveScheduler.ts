import { useCallback, type MutableRefObject } from "react";

import type { PlanRequestPayload, PlanResponse, ProjectInput, ProjectRecord } from "../types";
import { parsePositiveNumber } from "../utils/formatting";
import { resolveCanonicalCanvasInput } from "../utils/canonicalCanvasProject";

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
      if (!Number.isFinite(ftPerPx) || ftPerPx <= 0) return;
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
        const savedInput = liveProject?.project_input
          ? resolveCanonicalCanvasInput(liveProject.project_input) : undefined;
        const liveInput = payloadPreviewRef.current;
        const currentInput = {
          ...savedInput,
          ...liveInput,
          manual_fields: { ...savedInput?.manual_fields, ...liveInput.manual_fields },
          meta: { ...savedInput?.meta, ...liveInput.meta,
            site_inputs: { ...savedInput?.meta?.site_inputs, ...liveInput.meta?.site_inputs } },
        };
        const detectionScale = {
          distance_ft: detectionScaleFeet ? parsePositiveNumber(detectionScaleFeet) ?? undefined : undefined,
          pixel_distance: detectionScalePixels ? parsePositiveNumber(detectionScalePixels) ?? undefined : undefined,
          scale_ft_per_px: ftPerPx,
          scale_source: source,
        };
        const savedSiteInputs = savedInput?.meta?.site_inputs;
        const savedScale = savedSiteInputs?.detection_scale;
        // Map callbacks can fire on each render, including save acknowledgements.
        // Only an already-persisted equal value is a no-op; failed saves remain
        // retryable, and unsaved live geometry must never be replaced by its
        // older saved snapshot just to update map scale.
        if (savedScale?.scale_ft_per_px === detectionScale.scale_ft_per_px &&
            savedScale.scale_source === detectionScale.scale_source &&
            savedScale.distance_ft === detectionScale.distance_ft &&
            savedScale.pixel_distance === detectionScale.pixel_distance &&
            savedSiteInputs?.site_alignment_locked === siteScaleLockedRef.current) return;
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
                detection_scale: detectionScale,
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
