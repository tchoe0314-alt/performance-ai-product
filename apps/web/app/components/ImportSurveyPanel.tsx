import type { RefObject } from "react";

import { bestSurveySourceLabel, SURVEY_SOURCE_HIERARCHY } from "../utils/surveySourceHierarchy";

type ImageUploadState = "idle" | "uploading" | "detecting" | "failed" | "ready";

type ImportSurveyPanelProps = {
  mapSnapshotReady: boolean;
  surveyPointCount: number;
  imageUploadState: ImageUploadState | string;
  imageUploadNote?: string | null;
  surveyUploadMessage?: string | null;
  planPdfReady: boolean;
  mapAnalysisReady: boolean;
  mapSnapshotPath?: string | null;
  hasTerrainSource: boolean;
  detectionScaleFtPerPx: number | null;
  siteRotationDeg: number;
  siteScaleLocked: boolean;
  mapSnapshotInputRef: RefObject<HTMLInputElement | null>;
  surveyInputRef: RefObject<HTMLInputElement | null>;
  onUploadImage: (file: File) => Promise<void>;
  onUploadExistingConditions: (file: File) => Promise<void>;
  onOpenPlanPdf: () => void;
  onAnalyzeMapSnapshot: () => void;
  onFitToSite: () => void;
  onMapCenter: () => void;
  onAlignRoad: () => void;
  onResetRotation: () => void;
  onRotationChange: (value: number) => void;
};

export function ImportSurveyPanel({
  mapSnapshotReady,
  surveyPointCount,
  imageUploadState,
  imageUploadNote,
  surveyUploadMessage,
  planPdfReady,
  mapAnalysisReady,
  mapSnapshotPath,
  hasTerrainSource,
  detectionScaleFtPerPx,
  siteRotationDeg,
  siteScaleLocked,
  mapSnapshotInputRef,
  surveyInputRef,
  onUploadImage,
  onUploadExistingConditions,
  onOpenPlanPdf,
  onAnalyzeMapSnapshot,
  onFitToSite,
  onMapCenter,
  onAlignRoad,
  onResetRotation,
  onRotationChange,
}: ImportSurveyPanelProps) {
  const bestSourceLabel = bestSurveySourceLabel({
    surveyPreviewPointCount: surveyPointCount,
    hasTerrainSource,
    uploadedImagePreviewUrl: mapSnapshotReady ? "uploaded" : "",
  });

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Import inputs</p>
        <div className="mt-3 space-y-2">
          <button type="button" onClick={() => mapSnapshotInputRef.current?.click()} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            <span>Map snapshot / image</span>
            <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{mapSnapshotReady ? "Ready" : "Upload"}</span>
          </button>
          {imageUploadState !== "idle" ? (
            <p data-testid="image-upload-status" className={`rounded-xl border px-3 py-2 text-xs font-semibold ${
              imageUploadState === "failed"
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-slate-200 bg-slate-50 text-slate-600"
            }`}>
              {imageUploadNote ||
                (imageUploadState === "uploading"
                  ? "Uploading image..."
                  : imageUploadState === "detecting"
                    ? "Detecting site features..."
                    : imageUploadState === "failed"
                      ? "Image upload failed."
                      : "Image uploaded.")}
            </p>
          ) : null}
          <button type="button" onClick={() => surveyInputRef.current?.click()} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            <span>Survey / topo file</span>
            <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{surveyPointCount ? "Ready" : "Upload"}</span>
          </button>
          {surveyUploadMessage ? (
            <p data-testid="survey-upload-status" className={`rounded-xl border px-3 py-2 text-xs font-semibold ${
              surveyUploadMessage.toLowerCase().includes("failed")
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-slate-200 bg-slate-50 text-slate-600"
            }`}>
              {surveyUploadMessage}
            </p>
          ) : null}
          <button type="button" onClick={onOpenPlanPdf} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            <span>Plan PDF visual editor</span>
            <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{planPdfReady ? "Review" : "Open"}</span>
          </button>
          <button type="button" onClick={onAnalyzeMapSnapshot} disabled={!mapSnapshotPath} className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60">
            <span>Analyze map snapshot</span>
            <span className="text-xs uppercase tracking-[0.14em] text-slate-400">{mapAnalysisReady ? "Ready" : "Analyze"}</span>
          </button>
        </div>
        <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3" data-testid="import-source-hierarchy">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Best source order</p>
          <p className="mt-1 text-xs font-semibold text-slate-800">{bestSourceLabel}</p>
          <ol className="mt-3 space-y-1 text-xs font-semibold text-slate-600">
            {SURVEY_SOURCE_HIERARCHY.map((tier) => (
              <li key={tier.id}>
                {tier.rank}. {tier.title}
              </li>
            ))}
          </ol>
          <p className="mt-3 text-[11px] leading-5 text-slate-500">
            Supported review inputs include CSV/TXT point files, DXF, LandXML, GeoJSON/JSON, SHP/ZIP, GPKG,
            GeoTIFF, LAS/LAZ, PDFs, and map images. Civora stores source confidence separately from drawing
            and generated design output.
          </p>
        </div>
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
      </div>
      <div className="grid grid-cols-2 gap-2">
        {[
          ["Survey pts", surveyPointCount],
          ["Terrain", hasTerrainSource ? "Ready" : "Missing"],
          ["Image", mapSnapshotReady ? "Ready" : "Missing"],
          ["Scale", detectionScaleFtPerPx ? `${detectionScaleFtPerPx.toFixed(2)} ft/px` : "Unset"],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">{label}</p>
            <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Map calibration</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {[
            ["Fit to site", onFitToSite],
            ["Map center", onMapCenter],
            ["Align road", onAlignRoad],
            ["Reset rotation", onResetRotation],
          ].map(([label, onClick]) => (
            <button
              key={String(label)}
              type="button"
              onClick={onClick as () => void}
              className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold uppercase tracking-[0.14em] text-slate-700 hover:bg-slate-50"
            >
              {String(label)}
            </button>
          ))}
        </div>
        <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
          Rotation
          <input
            type="range"
            min={-180}
            max={180}
            value={siteRotationDeg}
            disabled={siteScaleLocked}
            onChange={(event) => onRotationChange(Number(event.target.value))}
            className="mt-2 h-2 w-full accent-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
          />
        </label>
      </div>
    </div>
  );
}
