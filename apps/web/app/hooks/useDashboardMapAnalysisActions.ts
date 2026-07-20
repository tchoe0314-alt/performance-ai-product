import { useCallback } from "react";

import { postJson } from "../../lib/api";
import type { MapAnalysis, ProjectInput, ProjectRecord } from "../types";

type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
}) => Promise<ProjectRecord | null>;

type UseDashboardMapAnalysisActionsOptions = {
  currentProject: ProjectRecord | null;
  mapSnapshotPath: string;
  payloadPreview: ProjectInput;
  saveProject: SaveProject;
  setMapAnalysis: (analysis: MapAnalysis | null) => void;
  setStatusMessage: (message: string) => void;
  token: string | null;
};

export function useDashboardMapAnalysisActions({
  currentProject,
  mapSnapshotPath,
  payloadPreview,
  saveProject,
  setMapAnalysis,
  setStatusMessage,
  token,
}: UseDashboardMapAnalysisActionsOptions) {
  return useCallback(async () => {
    if (!token || !mapSnapshotPath) return;
    try {
      const data = await postJson<MapAnalysis>(
        "/api/image/analyze",
        {
          image_path: mapSnapshotPath,
          source_name: "map_snapshot",
          source_type: "map",
        },
        { token },
      );
      setMapAnalysis(data);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_analysis: data,
      };
      await saveProject({
        silent: true,
        projectInputOverride: {
          ...currentInput,
          input_mode: "user",
          strict_mode: false,
          allow_ai_fill_for_blanks: false,
          meta: {
            ...(currentInput?.meta ?? {}),
            site_inputs: nextSiteInputs,
          },
        },
      });
      setStatusMessage("Map snapshot analyzed.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Map snapshot analysis failed.");
    }
  }, [currentProject, mapSnapshotPath, payloadPreview, saveProject, setMapAnalysis, setStatusMessage, token]);
}
