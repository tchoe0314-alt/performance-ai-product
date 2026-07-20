import type { Dispatch, SetStateAction } from "react";
import { useCallback } from "react";

import { postForm, postJson } from "../../lib/api";
import type {
  BuildingPlacement,
  ImageDetectResponse,
  ProjectInput,
  ProjectRecord,
  SiteObjectType,
  UploadImageResponse,
} from "../types";
import { uploadedImageSrc } from "../utils/auth";
import { uploadStatusMessage } from "../utils/dashboardStatus";
import { clampValue } from "../utils/objectGeometry";
import type { ProjectStatusSummary } from "../utils/workspaceShell";

type SaveProject = (options?: {
  silent?: boolean;
  projectInputOverride?: ProjectInput;
}) => Promise<ProjectRecord | null>;
type AutoFitSite = (
  width: number,
  height: number,
  label?: string,
  siteIdOverride?: string | null,
  fitMap?: boolean,
  lockSite?: boolean,
  preserveExistingObjects?: boolean,
) => void;
type UpdateProjectStatus = (updates: Omit<ProjectStatusSummary, "updatedAt">) => void;
type AskClarification = (question: string, action: string, payload?: Record<string, unknown>) => void;

type UseDashboardImageDetectionActionsOptions = {
  askClarification: AskClarification;
  autoFitSite: AutoFitSite;
  buildingPlacements: BuildingPlacement[];
  clearGeneratedPreview: () => void;
  currentProject: ProjectRecord | null;
  detectionScaleFtPerPx: number | null;
  lotHeightValue: number | null;
  lotWidthValue: number | null;
  mapSnapshotPath: string;
  payloadPreview: ProjectInput;
  saveProject: SaveProject;
  setDetectedPlacements: Dispatch<SetStateAction<BuildingPlacement[]>>;
  setImageName: Dispatch<SetStateAction<string>>;
  setImageUploadNote: Dispatch<SetStateAction<string | null>>;
  setImageUploadState: Dispatch<SetStateAction<"idle" | "uploading" | "uploaded" | "detecting" | "failed">>;
  setMapSnapshotPath: Dispatch<SetStateAction<string>>;
  setShowSiteBounds: Dispatch<SetStateAction<boolean>>;
  setSiteScaleLocked: Dispatch<SetStateAction<boolean>>;
  setSiteSelectionMode: Dispatch<SetStateAction<boolean>>;
  setStatusMessage: (message: string) => void;
  setUploadedImageApiUrl: Dispatch<SetStateAction<string>>;
  setUploadedImagePreviewUrl: Dispatch<SetStateAction<string>>;
  token: string | null;
  updateProjectStatus: UpdateProjectStatus;
};

const detectedObjectLabels: Record<SiteObjectType, string> = {
  site: "Site",
  setback_zone: "Setback Zone",
  no_build_zone: "No-Build Zone",
  building: "Detected Building",
  retail_building: "Detected Retail",
  multifamily_building: "Detected Multifamily",
  industrial_building: "Detected Industrial",
  office_building: "Detected Office",
  pad: "Detected Pad",
  pool: "Detected Pool",
  amenity: "Detected Amenity",
  open_space: "Detected Open Space",
  entrance: "Detected Entrance",
  driveway: "Detected Driveway",
  road: "Detected Road",
  parking: "Detected Parking",
  sidewalk: "Detected Path",
  basin: "Detected Basin",
  outfall: "Detected Outfall",
  inlet: "Detected Inlet",
  manhole: "Detected Manhole",
  hydrant: "Detected Hydrant",
  utility_corridor: "Detected Utility Corridor",
  lot_block: "Detected Lot Block",
  bridge: "Detected Bridge",
  custom: "Detected Custom Geometry",
};

export function useDashboardImageDetectionActions({
  askClarification,
  autoFitSite,
  buildingPlacements,
  clearGeneratedPreview,
  currentProject,
  detectionScaleFtPerPx,
  lotHeightValue,
  lotWidthValue,
  mapSnapshotPath,
  payloadPreview,
  saveProject,
  setDetectedPlacements,
  setImageName,
  setImageUploadNote,
  setImageUploadState,
  setMapSnapshotPath,
  setShowSiteBounds,
  setSiteScaleLocked,
  setSiteSelectionMode,
  setStatusMessage,
  setUploadedImageApiUrl,
  setUploadedImagePreviewUrl,
  token,
  updateProjectStatus,
}: UseDashboardImageDetectionActionsOptions) {
  const mapDetectionToPlacement = useCallback(
    (
      detection: {
        kind: string;
        bbox: [number, number, number, number];
        confidence?: number;
        geometry_type?: "polygon" | "polyline" | "rect";
        geometry?: Array<[number, number]>;
      },
      imageWidth: number,
      imageHeight: number,
    ): BuildingPlacement | null => {
      if (!imageWidth || !imageHeight) return null;
      const [x, y, w, h] = detection.bbox;
      const width = lotWidthValue;
      const height = lotHeightValue;
      if (!width || !height) return null;
      const scaleFtPerPx = detectionScaleFtPerPx && detectionScaleFtPerPx > 0 ? detectionScaleFtPerPx : null;
      const mapPoint = (pt: [number, number]) => {
        const [px, py] = pt;
        const mappedX = scaleFtPerPx ? px * scaleFtPerPx : (px / imageWidth) * width;
        const mappedY = scaleFtPerPx ? py * scaleFtPerPx : (py / imageHeight) * height;
        return [mappedX, mappedY] as [number, number];
      };
      const mappedGeometry = Array.isArray(detection.geometry)
        ? detection.geometry.map((pt) => mapPoint(pt))
        : null;
      const geometryBounds = mappedGeometry?.length
        ? mappedGeometry.reduce(
            (acc, pt) => ({
              minX: Math.min(acc.minX, pt[0]),
              minY: Math.min(acc.minY, pt[1]),
              maxX: Math.max(acc.maxX, pt[0]),
              maxY: Math.max(acc.maxY, pt[1]),
            }),
            {
              minX: Number.POSITIVE_INFINITY,
              minY: Number.POSITIVE_INFINITY,
              maxX: Number.NEGATIVE_INFINITY,
              maxY: Number.NEGATIVE_INFINITY,
            },
          )
        : null;
      const mappedX = geometryBounds ? geometryBounds.minX : scaleFtPerPx ? x * scaleFtPerPx : (x / imageWidth) * width;
      const mappedY = geometryBounds ? geometryBounds.minY : scaleFtPerPx ? y * scaleFtPerPx : (y / imageHeight) * height;
      const mappedW = geometryBounds ? geometryBounds.maxX - geometryBounds.minX : scaleFtPerPx ? w * scaleFtPerPx : (w / imageWidth) * width;
      const mappedD = geometryBounds ? geometryBounds.maxY - geometryBounds.minY : scaleFtPerPx ? h * scaleFtPerPx : (h / imageHeight) * height;
      const typeMap: Record<string, SiteObjectType> = {
        building: "building",
        road: "road",
        parking: "parking",
        sidewalk: "sidewalk",
        driveway: "driveway",
        basin: "basin",
        pool: "pool",
        open_space: "open_space",
      };
      const type = typeMap[detection.kind] ?? "building";
      return {
        id: `detected_${Math.random().toString(36).slice(2, 9)}`,
        label: detectedObjectLabels[type] ?? "Detected Object",
        x: clampValue(mappedX, 0, width - mappedW),
        y: clampValue(mappedY, 0, height - mappedD),
        w: Math.max(12, mappedW),
        d: Math.max(12, mappedD),
        rotation: 0,
        type,
        source: "detected_from_image",
        generated: false,
        confidence: detection.confidence ?? 0.2,
        confirmed: false,
        geometryType: detection.geometry_type,
        geometry: mappedGeometry ?? undefined,
        capabilities: { movable: true, resizable: true, rotatable: false, deletable: true },
        placed: true,
        meta: {
          detection_kind: detection.kind,
          confidence: detection.confidence ?? 0.2,
          detected: true,
          scale_source: scaleFtPerPx ? "calibrated" : "approximate",
          scale_ft_per_px: scaleFtPerPx ?? null,
        },
      };
    },
    [detectionScaleFtPerPx, lotHeightValue, lotWidthValue],
  );

  const handleAnalyzeImageFeatures = useCallback(async (overridePath?: string) => {
    if (!token) {
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs connection",
        detail: "Sign in/connect backend to detect site context.",
        nextAction: "Sign in or reconnect backend, then run map/image detection again.",
      });
      return;
    }
    const sourcePath = overridePath || mapSnapshotPath;
    if (!sourcePath) {
      askClarification(
        "Upload a site image or map snapshot before running detection. Want me to open the Site Inputs panel?",
        "upload_image_then_detect",
      );
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs image",
        detail: "A site image or map snapshot is required before detection.",
        nextAction: "Upload a site image or map snapshot, then run detection.",
      });
      return;
    }
    clearGeneratedPreview();
    setImageUploadState("detecting");
    setImageUploadNote("Detecting site features…");
    updateProjectStatus({
      state: "working",
      area: "setup",
      title: "Detecting site context",
      detail: "Civora is detecting site features from the uploaded map/image.",
      nextAction: "Wait for detections, then review suggested objects before generating.",
    });
    const width = lotWidthValue;
    const height = lotHeightValue;
    if (!width || !height) {
      askClarification(
        "I need the site boundary dimensions before detection. What size should the site be?",
        "set_site_then_detect",
      );
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Set site dimensions to run detection.");
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs site size",
        detail: "Site boundary dimensions are required before detection.",
        nextAction: "Set site width/depth or draw a boundary, then run detection again.",
      });
      return;
    }
    try {
      const result = await postJson<ImageDetectResponse>(
        "/api/image/detect-features",
        { image_path: sourcePath, source_type: "map" },
        { token },
      );
      const detections = Array.isArray(result.detections) ? result.detections : [];
      const mapped = detections
        .map((det) => mapDetectionToPlacement(det, result.image_width ?? 0, result.image_height ?? 0))
        .filter((item): item is BuildingPlacement => Boolean(item));
      setDetectedPlacements(mapped);
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        detected_objects: mapped,
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
      setImageUploadState("uploaded");
      setImageUploadNote(mapped.length ? "Detection complete. Review suggested objects." : "No detections found.");
      updateProjectStatus({
        state: result.success ? "needs review" : "blocked",
        area: "setup",
        title: result.success ? "Site context needs review" : "Site context needs attention",
        detail: result.success
          ? (mapped.length ? "Detection complete. Review suggested objects." : "Detection complete. No detections were found.")
          : result.message || "Detection failed.",
        nextAction: result.success
          ? "Review suggested objects in Object Manager before generating."
          : "Check the map/image source and retry detection.",
      });
    } catch (error) {
      setImageUploadState("failed");
      setImageUploadNote("Detection failed.");
      updateProjectStatus({
        state: "blocked",
        area: "setup",
        title: "Site context needs attention",
        detail: error instanceof Error ? error.message : "Detection failed.",
        nextAction: "Check the uploaded map/image and backend connection, then retry detection.",
      });
    }
  }, [
    askClarification,
    clearGeneratedPreview,
    currentProject,
    lotHeightValue,
    lotWidthValue,
    mapDetectionToPlacement,
    mapSnapshotPath,
    payloadPreview,
    saveProject,
    setDetectedPlacements,
    setImageUploadNote,
    setImageUploadState,
    token,
    updateProjectStatus,
  ]);

  const uploadImage = useCallback(async (file: File) => {
    if (!token) {
      const message = "Image upload failed: Sign in/connect backend to upload images.";
      setImageUploadState("failed");
      setImageUploadNote(message);
      setStatusMessage(message);
      return;
    }
    const localPreviewUrl = URL.createObjectURL(file);
    setUploadedImagePreviewUrl(localPreviewUrl);
    setImageUploadState("uploading");
    setImageUploadNote("Uploading image…");
    clearGeneratedPreview();
    try {
      const imageElement = new Image();
      const imageSize = await new Promise<{ width: number; height: number } | null>((resolve) => {
        imageElement.onload = () => resolve({ width: imageElement.width, height: imageElement.height });
        imageElement.onerror = () => resolve(null);
        imageElement.src = localPreviewUrl;
      });
      const formData = new FormData();
      formData.append("file", file);
      const data = await postForm<UploadImageResponse>("/api/upload-image", formData, {
        token,
      });
      setImageName(data.image_path || file.name);
      setUploadedImageApiUrl(
        data.image_url ? uploadedImageSrc(data.image_url, token) : "",
      );
      setMapSnapshotPath(data.image_path || "");
      const currentInput = currentProject?.project_input ?? payloadPreview;
      const nextSiteInputs = {
        ...(currentInput?.meta?.site_inputs ?? {}),
        map_snapshot: {
          filename: data.filename || file.name,
          stored_filename: data.image_path || file.name,
          image_path: data.image_path || "",
          image_url: data.image_url || "",
        },
        site_alignment_locked: true,
      };
      const hasSite = buildingPlacements.some((item) => item.type === "site");
      let width = lotWidthValue;
      let height = lotHeightValue;
      if (!hasSite) {
        const acres = 10;
        const baseSide = Math.sqrt(acres * 43560);
        const aspect =
          imageSize && imageSize.width > 0 && imageSize.height > 0
            ? imageSize.width / imageSize.height
            : 1;
        const fallbackWidth = baseSide * Math.sqrt(aspect);
        const fallbackHeight = baseSide / Math.sqrt(aspect);
        const scaledWidth =
          imageSize && detectionScaleFtPerPx
            ? imageSize.width * detectionScaleFtPerPx
            : null;
        const scaledHeight =
          imageSize && detectionScaleFtPerPx
            ? imageSize.height * detectionScaleFtPerPx
            : null;
        width = scaledWidth ?? fallbackWidth;
        height = scaledHeight ?? fallbackHeight;
        autoFitSite(width, height, "Site Boundary");
        setShowSiteBounds(false);
        setSiteScaleLocked(true);
        setSiteSelectionMode(false);
      }
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
          manual_fields: {
            ...(currentInput?.manual_fields ?? {}),
            lot: {
              x: 0,
              y: 0,
              w: width || 0,
              h: height || 0,
            },
          },
        },
      });
      setImageUploadState("uploaded");
      setImageUploadNote("Image uploaded. Ready for detection.");
      setStatusMessage("Image uploaded.");
      if (width && height) {
        setImageUploadState("detecting");
        setImageUploadNote("Detecting site features…");
        void handleAnalyzeImageFeatures(data.image_path || "");
      } else {
        setStatusMessage("Image uploaded. Set site dimensions to run detection.");
      }
    } catch (error) {
      setImageName(file.name);
      setImageUploadState("failed");
      const message = uploadStatusMessage("image", error);
      setImageUploadNote(message);
      setStatusMessage(message);
    }
  }, [
    autoFitSite,
    buildingPlacements,
    clearGeneratedPreview,
    currentProject,
    detectionScaleFtPerPx,
    handleAnalyzeImageFeatures,
    lotHeightValue,
    lotWidthValue,
    payloadPreview,
    saveProject,
    setImageName,
    setImageUploadNote,
    setImageUploadState,
    setMapSnapshotPath,
    setShowSiteBounds,
    setSiteScaleLocked,
    setSiteSelectionMode,
    setStatusMessage,
    setUploadedImageApiUrl,
    setUploadedImagePreviewUrl,
    token,
  ]);

  return { handleAnalyzeImageFeatures, uploadImage };
}
