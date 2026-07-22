import type { RefObject } from "react";

import { bestSurveySourceLabel, SURVEY_SOURCE_HIERARCHY } from "../utils/surveySourceHierarchy";
import { DisclosurePanel } from "./ui";

type ImageUploadState = "idle" | "uploading" | "detecting" | "ready" | "failed" | string;

type SetupSurveyTerrainSectionProps = {
  hasTerrainSource: boolean;
  surveyFileName: string;
  uploadedImagePreviewUrl: string;
  uploadedImageApiUrl: string;
  surveyPreviewPointCount: number;
  surveyUploadMessage: string;
  imageUploadState: ImageUploadState;
  imageUploadNote: string | null;
  mapSnapshotPath: string | null;
  mapSnapshotInputRef: RefObject<HTMLInputElement | null>;
  surveyInputRef: RefObject<HTMLInputElement | null>;
  onOpenImport: () => void;
  onAnalyzeMapSnapshot: () => void;
  onUploadImage: (file: File) => Promise<void>;
  onUploadExistingConditions: (file: File) => Promise<void>;
};

export function SetupSurveyTerrainSection({
  hasTerrainSource,
  surveyFileName,
  uploadedImagePreviewUrl,
  uploadedImageApiUrl,
  surveyPreviewPointCount,
  surveyUploadMessage,
  imageUploadState,
  imageUploadNote,
  mapSnapshotPath,
  mapSnapshotInputRef,
  surveyInputRef,
  onOpenImport,
  onAnalyzeMapSnapshot,
  onUploadImage,
  onUploadExistingConditions,
}: SetupSurveyTerrainSectionProps) {
  const bestSourceLabel = bestSurveySourceLabel({
    surveyFileName,
    surveyPreviewPointCount,
    hasTerrainSource,
    uploadedImagePreviewUrl,
    uploadedImageApiUrl,
  });

  return (
    <DisclosurePanel
      testId="setup-survey-terrain-card"
      title="Survey / Terrain / Sources"
      subtitle={hasTerrainSource ? "Terrain source available" : surveyFileName || uploadedImagePreviewUrl || uploadedImageApiUrl ? "Sources added for review" : "Optional sources not added"}
      status={hasTerrainSource ? "Ready" : "Optional"}
      statusClassName={hasTerrainSource ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}
    >
      <button
        type="button"
        onClick={onOpenImport}
        className="mb-2 w-full rounded-lg border border-slate-950 bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800"
      >
        Import
      </button>
      <div className="mb-3 rounded-xl border border-slate-200 bg-white/85 p-3" data-testid="survey-source-hierarchy">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Source ladder</p>
        <p className="mt-1 text-xs font-semibold text-slate-800" data-testid="best-survey-source-label">{bestSourceLabel}</p>
        <div className="mt-3 space-y-2">
          {SURVEY_SOURCE_HIERARCHY.map((tier) => (
            <details key={tier.id} className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2" data-testid={`survey-source-tier-${tier.id}`}>
              <summary className="cursor-pointer text-xs font-semibold text-slate-700">
                {tier.rank}. {tier.title}
              </summary>
              <div className="mt-2 space-y-1 text-[11px] leading-5 text-slate-500">
                <p><span className="font-semibold text-slate-600">Examples:</span> {tier.examples}</p>
                <p><span className="font-semibold text-slate-600">Use:</span> {tier.use}</p>
                <p><span className="font-semibold text-slate-600">Confidence:</span> {tier.confidence}</p>
              </div>
            </details>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <button type="button" onClick={() => surveyInputRef.current?.click()} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50">
          {surveyPreviewPointCount ? "Replace Survey" : "Upload Survey"}
        </button>
        <button type="button" onClick={() => mapSnapshotInputRef.current?.click()} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-slate-50">
          {uploadedImagePreviewUrl || uploadedImageApiUrl ? "Replace Map" : "Upload Map"}
        </button>
      </div>
      {surveyUploadMessage ? (
        <p data-testid="survey-upload-status" className={`mt-3 rounded-lg border px-3 py-2 text-xs font-semibold ${
          surveyUploadMessage.toLowerCase().includes("failed")
            ? "border-red-200 bg-red-50 text-red-700"
            : "border-slate-200 bg-slate-50 text-slate-600"
        }`}>
          {surveyUploadMessage}
        </p>
      ) : null}
      {imageUploadState !== "idle" ? (
        <p data-testid="image-upload-status" className={`mt-3 rounded-lg border px-3 py-2 text-xs font-semibold ${
          imageUploadState === "failed" ? "border-red-200 bg-red-50 text-red-700" : "border-slate-200 bg-slate-50 text-slate-600"
        }`}>
          {imageUploadNote || (imageUploadState === "uploading" ? "Uploading image..." : imageUploadState === "detecting" ? "Detecting site features..." : imageUploadState === "failed" ? "Image upload failed." : "Image uploaded.")}
        </p>
      ) : null}
      <button
        type="button"
        onClick={onAnalyzeMapSnapshot}
        disabled={!mapSnapshotPath}
        className="mt-3 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
      >
        {mapSnapshotPath ? "Analyze Map Snapshot" : "Upload Map Before Analysis"}
      </button>
      <input
        ref={mapSnapshotInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={async (event) => {
          const input = event.currentTarget;
          const file = input.files?.[0];
          if (file) {
            await onUploadImage(file);
          }
          input.value = "";
        }}
      />
      <input
        ref={surveyInputRef}
        type="file"
        accept=".csv,.geojson,.json,.dxf,.shp,.zip,.gpkg,.tif,.tiff,.las,.laz,.xml,.landxml"
        className="hidden"
        onChange={async (event) => {
          const input = event.currentTarget;
          const file = input.files?.[0];
          if (file) {
            await onUploadExistingConditions(file);
          }
          input.value = "";
        }}
      />
    </DisclosurePanel>
  );
}
