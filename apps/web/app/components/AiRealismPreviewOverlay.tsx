import type { CSSProperties, SyntheticEvent } from "react";

import type { AiRealismGenerationStatus } from "./previewPanelTypes";

type AiRealismArtifactView = {
  type: "high_quality_ai_render_v1" | "high_quality_ai_render_v2" | "high_quality_ai_render_v3";
  project_id: string;
  site_frame: {
    width_ft: number;
    height_ft: number;
    map_context_available: boolean;
  };
  source_objects_summary: {
    total: number;
    objects_included: string[];
    counts_by_type: Record<string, number>;
  };
  missing_inputs: string[];
  generated_timestamp: string;
  image_data_url: string;
  renderer?: "local_reference" | "external" | "civora_hybrid";
  provider?: string;
  model?: string;
  mime_type?: string;
  map_context_used?: boolean;
  self_hosted?: boolean;
  reference_manifest?: {
    control_kinds?: string[];
  };
};

type AiRealismPreviewOverlayProps = {
  artifact: AiRealismArtifactView | null;
  blocker: string | null;
  generationStatus: AiRealismGenerationStatus;
  stale: boolean;
  hasTerrainSource: boolean;
  showMap: boolean;
  visualFrameStyle?: CSSProperties;
  watermark: string;
  onRegenerate: () => void;
};

const stopPreviewPointerEvent = (event: SyntheticEvent) => {
  event.stopPropagation();
};

export function AiRealismPreviewOverlay({
  artifact,
  blocker,
  generationStatus,
  stale,
  hasTerrainSource,
  showMap,
  visualFrameStyle,
  watermark,
  onRegenerate,
}: AiRealismPreviewOverlayProps) {
  return (
    <div
      data-testid="ai-realism-preview"
      className={`pointer-events-none absolute inset-0 z-[160] overflow-hidden rounded-[24px] ${
        showMap ? "bg-white/5" : "bg-slate-950/12"
      }`}
      onClick={stopPreviewPointerEvent}
      onDoubleClick={stopPreviewPointerEvent}
      onMouseDown={stopPreviewPointerEvent}
      onMouseMove={stopPreviewPointerEvent}
      onMouseUp={stopPreviewPointerEvent}
    >
      {artifact ? (
        <>
          <div
            data-testid="ai-realism-visual-frame"
            className="pointer-events-none absolute overflow-hidden"
            style={visualFrameStyle ?? { inset: 0 }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              data-testid="ai-realism-image"
              src={artifact.image_data_url}
              alt="AI visualization generated from the current proposed layout"
              className={`pointer-events-none h-full w-full object-fill ${showMap ? "opacity-90" : "opacity-100"}`}
            />
          </div>
          <div
            data-testid="ai-realism-preview-badge"
            className="absolute left-4 top-4 rounded-lg border border-white/55 bg-slate-950/72 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-white shadow-lg backdrop-blur"
          >
            {artifact.renderer === "civora_hybrid"
              ? `Civora private visual · ${showMap && artifact.site_frame.map_context_available ? "over live map" : "proposed site design"}`
              : artifact.renderer === "external"
              ? `Photoreal concept · ${showMap && artifact.site_frame.map_context_available ? "over live map" : "proposed site design"}`
              : `Visual preview · ${showMap && artifact.site_frame.map_context_available ? "Live map + proposed design" : "Proposed site design"}`}
          </div>
          <div
            data-testid="ai-realism-watermark"
            className="absolute bottom-4 left-4 max-w-[min(32rem,calc(100%-2rem))] rounded-md border border-white/25 bg-slate-950/64 px-3 py-1.5 text-[10px] font-semibold text-white shadow-lg backdrop-blur"
          >
            {watermark}
          </div>
          {generationStatus.state === "queued" || generationStatus.state === "generating" ? (
            <div
              data-testid="ai-realism-generation-status"
              className="pointer-events-none absolute bottom-14 left-4 flex max-w-[min(28rem,calc(100%-2rem))] items-center gap-2 rounded-lg border border-white/50 bg-white/92 px-3 py-2 text-xs text-slate-700 shadow-lg backdrop-blur"
            >
              <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
              <span>
                <strong>{generationStatus.stage || "Updating visualization"}</strong>
                {generationStatus.progress ? ` · ${Math.round(generationStatus.progress)}%` : ""}
              </span>
            </div>
          ) : null}
          <details
            data-testid="ai-realism-source-summary"
            className="group pointer-events-auto absolute right-4 top-4 w-[min(20rem,calc(100%-2rem))] text-[11px] text-slate-700"
            onClick={stopPreviewPointerEvent}
            onMouseDown={stopPreviewPointerEvent}
          >
            <summary
              data-testid="ai-realism-details-toggle"
              className="ml-auto flex w-fit cursor-pointer list-none items-center gap-2 rounded-lg border border-white/55 bg-white/88 px-3 py-2 font-semibold text-slate-700 shadow-lg backdrop-blur marker:hidden"
            >
              Preview details
              {stale ? <span className="h-2 w-2 rounded-full bg-amber-500" title="Visualization needs refresh" /> : null}
            </summary>
            <div className="mt-2 max-h-[min(30rem,60vh)] overflow-y-auto rounded-xl border border-white/45 bg-white/92 p-3 shadow-lg backdrop-blur-xl">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold uppercase tracking-[0.14em] text-slate-500">
                    {artifact.type}
                  </p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    Source summary: {artifact.source_objects_summary.total} review object(s)
                    {Object.keys(artifact.source_objects_summary.counts_by_type).length
                      ? ` across ${Object.entries(artifact.source_objects_summary.counts_by_type)
                          .map(([type, count]) => `${type}: ${count}`)
                          .join(", ")}`
                      : ""}
                  </p>
                  <p data-testid="ai-realism-site-frame" className="mt-0.5 text-[10px] text-slate-500">
                    Site frame: {Math.round(artifact.site_frame.width_ft)} ft × {Math.round(artifact.site_frame.height_ft)} ft
                    {showMap && artifact.site_frame.map_context_available
                      ? " · registered over live map context"
                      : " · local site coordinates"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  <a
                    data-testid="ai-realism-view-snapshot"
                    href={artifact.image_data_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                  >
                    View snapshot
                  </a>
                  <a
                    data-testid="ai-realism-save-snapshot"
                    href={artifact.image_data_url}
                    download={`ai-visualization-${artifact.project_id}.${artifact.mime_type === "image/png" ? "png" : artifact.mime_type === "image/jpeg" ? "jpg" : artifact.mime_type === "image/webp" ? "webp" : "svg"}`}
                    className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                  >
                    Save snapshot
                  </a>
                  <button
                    type="button"
                    data-testid="ai-realism-regenerate"
                    onClick={onRegenerate}
                    className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold text-slate-700"
                  >
                    Regenerate
                  </button>
                </div>
              </div>
              {stale ? (
                <p
                  data-testid="ai-realism-stale-warning"
                  className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 font-semibold text-amber-800"
                >
                  AI visualization is stale. Regenerate from current layout.
                </p>
              ) : null}
              <dl className="mt-2 grid gap-1 leading-snug">
                <div>
                  <dt className="font-semibold text-slate-900">Renderer</dt>
                  <dd data-testid="ai-realism-renderer" className="text-slate-600">
                    {artifact.renderer === "civora_hybrid"
                      ? `Civora private hybrid renderer${artifact.model ? ` · ${artifact.model}` : ""}`
                      : artifact.renderer === "external"
                      ? `External photorealistic concept${artifact.model ? ` · ${artifact.model}` : ""}`
                      : "Local plan visualization"}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-900">Map relationship</dt>
                  <dd data-testid="ai-realism-map-context" className="text-slate-600">
                    {showMap && artifact.site_frame.map_context_available
                      ? artifact.map_context_used
                        ? "Map context was included in the visual reference."
                        : artifact.renderer === "civora_hybrid"
                          ? "Live map is shown underneath as a separate layer; its imagery was not sent to the private renderer."
                          : "Live map is shown underneath as a separate layer; its imagery was not sent to the image provider."
                      : "Visualization is registered to local site coordinates."}
                  </dd>
                </div>
                {artifact.renderer === "civora_hybrid" ? (
                  <div>
                    <dt className="font-semibold text-slate-900">Geometry controls</dt>
                    <dd data-testid="ai-realism-control-provenance" className="text-slate-600">
                      {(artifact.reference_manifest?.control_kinds || ["edge", "height_depth"]).join(" + ")} · private worker · no map imagery
                    </dd>
                  </div>
                ) : null}
                <div>
                  <dt className="font-semibold text-slate-900">Objects included</dt>
                  <dd data-testid="ai-realism-objects-included" className="text-slate-600">
                    {artifact.source_objects_summary.objects_included.slice(0, 5).join(", ")}
                    {artifact.source_objects_summary.total > 5 ? "..." : ""}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-900">Missing context</dt>
                  <dd data-testid="ai-realism-missing-context" className="text-slate-600">
                    {artifact.missing_inputs.length
                      ? artifact.missing_inputs.join(", ")
                      : "None reported from current review layout."}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-900">Terrain/source confidence</dt>
                  <dd data-testid="ai-realism-terrain-confidence" className="text-slate-600">
                    {hasTerrainSource
                      ? "Terrain source present in review context; source confidence remains review-only."
                      : "Terrain/source confidence missing or not source-backed."}
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-900">Generated timestamp</dt>
                  <dd data-testid="ai-realism-generated-timestamp" className="text-slate-600">
                    {artifact.generated_timestamp}
                  </dd>
                </div>
              </dl>
            </div>
          </details>
        </>
      ) : generationStatus.state === "queued" || generationStatus.state === "generating" ? (
        <div
          data-testid="ai-realism-generation-status"
          className="pointer-events-auto absolute left-1/2 top-1/2 mx-4 w-[min(26rem,calc(100%-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-xl border border-white/55 bg-white/94 p-4 text-sm text-slate-800 shadow-xl backdrop-blur"
        >
          <div className="flex items-center gap-3">
            <span className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-slate-200 border-t-slate-900" />
            <div className="min-w-0">
              <p className="font-semibold">{generationStatus.stage || "Generating visualization"}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-slate-600">
                {generationStatus.detail || "Creating a photorealistic visual concept from the current layout."}
              </p>
            </div>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200">
            <div
              data-testid="ai-realism-generation-progress"
              className="h-full rounded-full bg-slate-900 transition-[width] duration-300"
              style={{ width: `${Math.max(4, Math.min(100, generationStatus.progress))}%` }}
            />
          </div>
          <p className="mt-2 text-[10px] font-semibold uppercase text-slate-500">
            Visual concept only · technical plan remains authoritative
          </p>
        </div>
      ) : (
        <div
          data-testid="ai-realism-blocker"
          className="pointer-events-auto absolute left-1/2 top-1/2 mx-4 max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-lg"
        >
          <p className="font-semibold">
            {blocker || "AI realism provider is not configured."}
          </p>
          <button
            type="button"
            data-testid="ai-realism-regenerate"
            onClick={onRegenerate}
            className="mt-3 rounded-md border border-amber-300 bg-white px-3 py-2 text-xs font-semibold uppercase tracking-[0.12em] text-amber-900"
          >
            Regenerate
          </button>
        </div>
      )}
    </div>
  );
}
