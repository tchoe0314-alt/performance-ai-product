import type { Dispatch, SetStateAction } from "react";
import { useCallback } from "react";

import { postForm } from "../../lib/api";
import type {
  ChatMessage,
  ProjectInput,
  ProjectRecord,
  SiteInputs,
  UploadExistingConditionsResponse,
  UploadSurveyResponse,
} from "../types";
import { uploadStatusMessage } from "../utils/dashboardStatus";
import {
  mapSurveyPointsToSite,
  summarizeExistingConditionsUpload,
} from "../utils/dashboardExistingConditionsUpload";

type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
}) => Promise<ProjectRecord | null>;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;

type UseDashboardExistingConditionsUploadOptions = {
  appendChatMessage: AppendChatMessage;
  currentProject: ProjectRecord | null;
  lotHeightValue: number | null;
  lotWidthValue: number | null;
  payloadPreview: ProjectInput;
  saveProject: SaveProject;
  setStatusMessage: (message: string) => void;
  setSurveyDiagnostics: Dispatch<SetStateAction<{
    fileType?: string;
    parseSuccess?: boolean;
    pointCount?: number;
    contourCount?: number;
    recognizedColumns?: { x?: string; y?: string; z?: string };
    invalidRows?: number;
    bounds?: { min_x?: number; min_y?: number; max_x?: number; max_y?: number };
    elevationRange?: { min?: number; max?: number };
    warnings?: string[];
  } | null>>;
  setSurveyFileName: Dispatch<SetStateAction<string>>;
  setSurveyPoints: Dispatch<SetStateAction<number[][]>>;
  setSurveyPreviewPoints: Dispatch<SetStateAction<Array<{ x: number; y: number; z?: number }>>>;
  setSurveyUploadMessage: Dispatch<SetStateAction<string>>;
  token: string | null;
  useSurveyForGrading: boolean;
};

export function useDashboardExistingConditionsUpload({
  appendChatMessage,
  currentProject,
  lotHeightValue,
  lotWidthValue,
  payloadPreview,
  saveProject,
  setStatusMessage,
  setSurveyDiagnostics,
  setSurveyFileName,
  setSurveyPoints,
  setSurveyPreviewPoints,
  setSurveyUploadMessage,
  token,
  useSurveyForGrading,
}: UseDashboardExistingConditionsUploadOptions) {
  const uploadExistingConditions = useCallback(async (file: File) => {
    const supportedSurveyPattern = /\.(csv|geojson|json|dxf|shp|zip|gpkg|tif|tiff|las|laz|xml|landxml)$/i;
    if (!supportedSurveyPattern.test(file.name)) {
      const message = "Survey/topo upload failed: Unsupported file. Use CSV, DXF, LAS/LAZ, GeoTIFF, GeoJSON, SHP/ZIP, GPKG, XML, or LandXML.";
      setSurveyFileName(file.name);
      setSurveyUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    if (!token) {
      const message = "Survey/topo upload failed: Sign in/connect backend to upload existing-condition files.";
      setSurveyFileName(file.name);
      setSurveyUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    setSurveyUploadMessage(`Uploading ${file.name} for source review...`);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadExistingConditionsResponse>("/api/upload-existing-conditions", formData, {
        token,
      });
      const storedFilename = data.stored_filename || file.name;
      const canonical = data.canonical_existing_conditions ?? {};
      const survey = canonical.survey && typeof canonical.survey === "object" ? canonical.survey as Record<string, unknown> : {};
      const surveyPoints = Array.isArray(survey.points)
        ? (survey.points as Array<Record<string, unknown>>)
            .map((point) => [Number(point.x), Number(point.y), Number(point.z)])
            .filter((point) => point.every((value) => Number.isFinite(value)))
        : [];
      setSurveyFileName(storedFilename);
      setSurveyPoints(surveyPoints);
      setSurveyPreviewPoints(mapSurveyPointsToSite(surveyPoints, lotWidthValue, lotHeightValue));
      setSurveyDiagnostics({
        fileType: data.file_type,
        parseSuccess: Boolean(data.success && surveyPoints.length),
        pointCount: Number(survey.point_count ?? surveyPoints.length ?? 0),
        contourCount: Number(survey.breakline_count ?? 0),
        recognizedColumns: {},
        invalidRows: 0,
        bounds: survey.bounds as UploadSurveyResponse["bounds"],
        elevationRange: survey.elevation_range as UploadSurveyResponse["elevation_range"],
        warnings: data.warnings,
      });
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        survey_file: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          survey_url: data.file_url || "",
        },
        survey_file_type: data.file_type,
        survey_parse_success: Boolean(data.success && surveyPoints.length),
        survey_point_count: Number(survey.point_count ?? surveyPoints.length ?? 0),
        survey_point_warnings: data.warnings ?? [],
        survey_points: surveyPoints,
        survey_bounds: (survey.bounds as SiteInputs["survey_bounds"]) ?? null,
        survey_elevation_range: (survey.elevation_range as SiteInputs["survey_elevation_range"]) ?? null,
        use_survey_for_grading: useSurveyForGrading,
        existing_conditions_import: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          file_type: data.file_type,
          import_matrix: data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix ?? [],
          canonical_vs_metadata_only: data.canonical_vs_metadata_only ?? data.import_validation?.canonical_vs_metadata_only ?? {},
          blockers: data.blockers ?? data.import_validation?.blockers ?? [],
          package_status: String(data.existing_conditions_package?.status ?? "unknown"),
        },
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
            existing_conditions_package: data.existing_conditions_package,
            existing_conditions_import_validation: data.import_validation,
            existing_conditions_summary: data.existing_conditions_summary,
            canonical_existing_conditions: data.canonical_existing_conditions,
            canonical_existing_conditions_model: data.canonical_existing_conditions?.canonical_existing_conditions_model,
            import_matrix: data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix,
            canonical_vs_metadata_only: data.canonical_vs_metadata_only ?? data.import_validation?.canonical_vs_metadata_only,
          },
        },
      });
      appendChatMessage("assistant", summarizeExistingConditionsUpload(data), "status");
      setSurveyUploadMessage(
        data.existing_conditions_package?.status === "ready"
          ? "Survey/topo imported and ready for review."
          : "Survey/topo imported; exact review needs are recorded.",
      );
      setStatusMessage(
        data.existing_conditions_package?.status === "ready"
          ? "Existing conditions imported and ready."
          : "Existing conditions imported; review needs are recorded.",
      );
    } catch (error) {
      setSurveyFileName(file.name);
      const message = uploadStatusMessage("survey", error);
      setSurveyUploadMessage(message);
      setStatusMessage(message);
    }
  }, [
    appendChatMessage,
    currentProject,
    lotHeightValue,
    lotWidthValue,
    payloadPreview,
    saveProject,
    setStatusMessage,
    setSurveyDiagnostics,
    setSurveyFileName,
    setSurveyPoints,
    setSurveyPreviewPoints,
    setSurveyUploadMessage,
    token,
    useSurveyForGrading,
  ]);

  return { uploadExistingConditions };
}
