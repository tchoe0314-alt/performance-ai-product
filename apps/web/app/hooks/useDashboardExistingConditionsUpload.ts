import type { Dispatch, SetStateAction } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { postForm, postJson } from "../../lib/api";
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
  buildExistingConditionsSourceEffects,
  buildImportedSurveyProvenance,
  mapSurveyPointsToSite,
  summarizeExistingConditionsUpload,
} from "../utils/dashboardExistingConditionsUpload";
import {
  canReviewSurveyControl,
  latestMatchingSurveyControlReview,
  sameSurveyControlReviewTarget,
  surveyControlReviewMessage,
  surveyControlReviewTarget,
  type SurveyControlReviewRecord,
} from "../utils/surveyControlReview";

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
  setSourceEffectRows: Dispatch<SetStateAction<string[]>>;
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
  setSourceEffectRows,
  setSurveyUploadMessage,
  token,
  useSurveyForGrading,
}: UseDashboardExistingConditionsUploadOptions) {
  const [latestImportedBoundaryInput, setLatestImportedBoundaryInput] = useState<ProjectInput | null>(null);
  const [surveyReviewPending, setSurveyReviewPending] = useState(false);
  const [surveyReviewError, setSurveyReviewError] = useState("");
  const [surveyReviewResult, setSurveyReviewResult] = useState<SurveyControlReviewRecord | null>(null);
  const currentProjectRef = useRef(currentProject);
  const surveyReviewRequestRef = useRef(0);
  const reviewTarget = surveyControlReviewTarget(currentProject);
  const reviewTargetKey = reviewTarget ? `${reviewTarget.projectId}:${reviewTarget.sourceId}:${reviewTarget.sourceDigest}` : "";
  currentProjectRef.current = currentProject;
  useEffect(() => {
    surveyReviewRequestRef.current += 1;
    setLatestImportedBoundaryInput(null);
    setSurveyReviewPending(false);
    setSurveyReviewError("");
    setSurveyReviewResult(null);
  }, [currentProject?.project_id]);
  useEffect(() => {
    surveyReviewRequestRef.current += 1;
    setSurveyReviewPending(false);
    setSurveyReviewError("");
    setSurveyReviewResult(null);
  }, [reviewTargetKey]);

  const recordSurveyControlReview = useCallback(async (decision: "accepted_for_review" | "rejected") => {
    const target = surveyControlReviewTarget(currentProjectRef.current);
    if (!token || !target) {
      setSurveyReviewError("The current saved survey source is unavailable. Reopen the project and try again.");
      return;
    }
    if (!canReviewSurveyControl(currentProjectRef.current)) {
      setSurveyReviewError("Reviewer access is required to record a survey-control decision.");
      return;
    }
    if (decision === "accepted_for_review" && !target.completeForReview) {
      setSurveyReviewError("The current source has missing or mismatched control evidence and cannot be accepted for review.");
      return;
    }
    const requestId = ++surveyReviewRequestRef.current;
    setSurveyReviewPending(true);
    setSurveyReviewError("");
    try {
      const response = await postJson<{ success: boolean; survey_control_review?: SurveyControlReviewRecord }>(
        `/api/projects/${encodeURIComponent(target.projectId)}/survey-control-review`,
        { source_id: target.sourceId, source_digest: target.sourceDigest, decision },
        { token },
      );
      const review = response.survey_control_review ?? null;
      if (requestId !== surveyReviewRequestRef.current || !sameSurveyControlReviewTarget(currentProjectRef.current, target)) return;
      if (!response.success || !review
          || review.project_id !== target.projectId
          || review.source_id !== target.sourceId
          || String(review.source_digest ?? "").toLowerCase() !== target.sourceDigest) {
        setSurveyReviewError("The server did not bind the decision to the current survey source. No review state was applied.");
        return;
      }
      setSurveyReviewResult(review);
      setStatusMessage(surveyControlReviewMessage(review));
    } catch (error) {
      if (requestId !== surveyReviewRequestRef.current || !sameSurveyControlReviewTarget(currentProjectRef.current, target)) return;
      const detail = error instanceof Error ? error.message : "Survey-control review failed.";
      setSurveyReviewError(`${detail} The current source remains unreviewed.`);
    } finally {
      if (requestId === surveyReviewRequestRef.current && sameSurveyControlReviewTarget(currentProjectRef.current, target)) {
        setSurveyReviewPending(false);
      }
    }
  }, [setStatusMessage, token]);

  const uploadExistingConditions = useCallback(async (file: File) => {
    const supportedSurveyPattern = /\.(csv|txt|geojson|json|dxf|shp|zip|gpkg|tif|tiff|las|laz|xml|landxml)$/i;
    if (!supportedSurveyPattern.test(file.name)) {
      const message = "Survey/topo upload failed: Unsupported file. Use CSV/TXT, DXF, LAS/LAZ, GeoTIFF, GeoJSON, SHP/ZIP, GPKG, XML, or LandXML.";
      setSurveyUploadMessage(message);
      setStatusMessage(message);
      return;
    }
    if (!token) {
      const message = "Survey/topo upload failed: Sign in/connect backend to upload existing-condition files.";
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
      const sourceEffectRows = buildExistingConditionsSourceEffects(data);
      const canonical = data.canonical_existing_conditions ?? {};
      const survey = canonical.survey && typeof canonical.survey === "object" ? canonical.survey as Record<string, unknown> : {};
      const surveyPoints = Array.isArray(survey.points)
        ? (survey.points as Array<Record<string, unknown>>)
            .filter((point) => [point.x, point.y, point.z].every((value) => typeof value === "number" && Number.isFinite(value)))
            .map((point) => [Number(point.x), Number(point.y), Number(point.z)])
            .filter((point) => point.every((value) => Number.isFinite(value)))
        : [];
      const surveyProvenance = buildImportedSurveyProvenance(data);
      // A stored file is not an accepted replacement. Preserve the active source
      // (including its warnings and points) when parsing fails.
      if (data.success !== true || ((data.file_type === "csv" || /\.csv$/i.test(file.name)) && surveyPoints.length < 3)) {
        const detail = data.message || "No usable survey/source data was recognized.";
        const message = `Survey/topo upload failed: ${detail} Active source unchanged.`;
        setSurveyUploadMessage(message);
        setStatusMessage(message);
        return;
      }
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const activeImport = currentInput?.meta?.site_inputs?.existing_conditions_import;
      const activeDigest = String(activeImport?.source_sha256 ?? currentInput?.meta?.site_inputs?.survey_file?.source_sha256 ?? "").trim().toLowerCase();
      const uploadedDigest = String(data.source_sha256 ?? "").trim().toLowerCase();
      if (activeDigest && uploadedDigest && activeDigest === uploadedDigest) {
        const message = `Duplicate source unchanged: ${file.name} matches the active source. Project data and review state were not changed.`;
        setSurveyUploadMessage(message);
        setStatusMessage(message);
        return;
      }
      surveyReviewRequestRef.current += 1;
      setSurveyReviewPending(false);
      setSurveyReviewError("");
      setSurveyReviewResult(null);
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        survey_file: {
          filename: data.filename || file.name,
          stored_filename: storedFilename,
          survey_url: data.file_url || "",
          source_sha256: data.source_sha256 || "",
          source_reference: data.uploaded_source_reference ?? {},
        },
        survey_file_type: data.file_type,
        survey_parse_success: Boolean(data.success && surveyPoints.length),
        survey_point_count: Number(survey.point_count ?? surveyPoints.length ?? 0),
        survey_point_warnings: data.warnings ?? [],
        survey_points: surveyPoints,
        survey_bounds: (survey.bounds as SiteInputs["survey_bounds"]) ?? null,
        survey_elevation_range: (survey.elevation_range as SiteInputs["survey_elevation_range"]) ?? null,
        ...surveyProvenance,
        survey_control_evidence_review: data.survey_control_evidence_review ?? {},
        use_survey_for_grading: useSurveyForGrading,
            existing_conditions_import: {
              filename: data.filename || file.name,
              stored_filename: storedFilename,
              source_sha256: data.source_sha256 || "",
              uploaded_source_reference: data.uploaded_source_reference ?? {},
              survey_control_evidence_review: data.survey_control_evidence_review ?? {},
              file_type: data.file_type,
              source_effect_rows: sourceEffectRows,
              import_matrix: data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix ?? [],
          canonical_vs_metadata_only: data.canonical_vs_metadata_only ?? data.import_validation?.canonical_vs_metadata_only ?? {},
          blockers: data.blockers ?? data.import_validation?.blockers ?? [],
          package_status: String(data.existing_conditions_package?.status ?? "unknown"),
        },
      };
      const nextProjectInput: ProjectInput = {
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
          survey_control_evidence_review: data.survey_control_evidence_review,
          import_matrix: data.import_matrix ?? data.import_validation?.import_matrix ?? data.import_validation?.importer_production_matrix,
          canonical_vs_metadata_only: data.canonical_vs_metadata_only ?? data.import_validation?.canonical_vs_metadata_only,
        },
      };
      const saved = await saveProject({
        silent: true,
        projectInputOverride: nextProjectInput,
      });
      if (!saved) {
        const message = "Survey/topo upload not applied: project save failed. Active source unchanged.";
        setSurveyUploadMessage(message);
        setStatusMessage(message);
        return;
      }
      setLatestImportedBoundaryInput(nextProjectInput);
      setSurveyFileName(storedFilename);
      setSourceEffectRows(sourceEffectRows);
      setSurveyPoints(surveyPoints);
      setSurveyPreviewPoints(mapSurveyPointsToSite(surveyPoints, lotWidthValue, lotHeightValue));
      setSurveyDiagnostics({
        fileType: data.file_type,
        parseSuccess: Boolean(surveyPoints.length),
        pointCount: surveyPoints.length,
        contourCount: Number(survey.breakline_count ?? 0),
        recognizedColumns: {},
        invalidRows: 0,
        bounds: survey.bounds as UploadSurveyResponse["bounds"],
        elevationRange: survey.elevation_range as UploadSurveyResponse["elevation_range"],
        warnings: data.warnings,
      });
      appendChatMessage("assistant", summarizeExistingConditionsUpload(data), "status");
      setSurveyUploadMessage(
        data.survey_control_evidence_review?.status === "complete_for_review"
          ? "Survey/topo source and control metadata match for review only; this does not authorize grading."
          : "Survey/topo imported for review only; exact control gaps or mismatches are recorded.",
      );
      setStatusMessage(
        data.existing_conditions_package?.status === "ready"
          ? "Existing conditions imported and ready."
          : "Existing conditions imported; review needs are recorded.",
      );
    } catch (error) {
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
    setSourceEffectRows,
    setSurveyUploadMessage,
    token,
    useSurveyForGrading,
  ]);

  const savedSurveyReview = latestMatchingSurveyControlReview(currentProject);
  const visibleSurveyReview = surveyReviewResult ?? savedSurveyReview;
  const surveyControlReview = reviewTarget ? {
    canReview: canReviewSurveyControl(currentProject),
    completeForReview: reviewTarget.completeForReview,
    pending: surveyReviewPending,
    message: surveyReviewError
      || (surveyReviewPending ? "Recording this exact source and digest with the server…" : surveyControlReviewMessage(visibleSurveyReview)),
    tone: surveyReviewError
      ? "error" as const
      : visibleSurveyReview?.decision === "accepted_for_review"
        ? "success" as const
        : visibleSurveyReview?.decision === "rejected" || !reviewTarget.completeForReview
          ? "warning" as const
          : "neutral" as const,
    onAccept: () => { void recordSurveyControlReview("accepted_for_review"); },
    onReject: () => { void recordSurveyControlReview("rejected"); },
  } : undefined;

  return { uploadExistingConditions, latestImportedBoundaryInput, surveyControlReview };
}
