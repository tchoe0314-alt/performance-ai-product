import type { SyntheticEvent } from "react";

type AiRealismArtifactView = {
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
};

type AiRealismPreviewOverlayProps = {
  artifact: AiRealismArtifactView | null;
  blocker: string | null;
  stale: boolean;
  hasTerrainSource: boolean;
  showMap: boolean;
  watermark: string;
  onRegenerate: () => void;
};

const stopPreviewPointerEvent = (event: SyntheticEvent) => {
  event.stopPropagation();
};

export function AiRealismPreviewOverlay({
  artifact,
  blocker,
  stale,
  hasTerrainSource,
  showMap,
  watermark,
  onRegenerate,
}: AiRealismPreviewOverlayProps) {
  return (
    <div
      data-testid="ai-realism-preview"
      className={`pointer-events-none absolute inset-0 z-[160] flex items-center justify-center overflow-hidden rounded-[24px] ${
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
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            data-testid="ai-realism-image"
            src={artifact.image_data_url}
            alt="AI realism visualization generated from the current review layout"
            className={`pointer-events-none h-full w-full object-contain ${showMap ? "opacity-90" : "opacity-100"}`}
          />
          <div
            data-testid="ai-realism-preview-badge"
            className="absolute left-4 top-4 rounded-lg border border-white/55 bg-slate-950/72 px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-white shadow-lg backdrop-blur"
          >
            Preview · {showMap && artifact.site_frame.map_context_available ? "Live map + current layout" : "Current site layout"}
          </div>
          <div
            data-testid="ai-realism-watermark"
            className="absolute inset-x-4 bottom-4 rounded-lg border border-white/30 bg-slate-950/66 px-4 py-2 text-xs font-semibold text-white shadow-lg backdrop-blur"
          >
            {watermark}
          </div>
          <div
            data-testid="ai-realism-source-summary"
            className="pointer-events-auto absolute right-4 top-4 max-w-[min(22rem,calc(100%-2rem))] rounded-xl border border-white/45 bg-white/78 p-3 text-[11px] text-slate-700 shadow-lg backdrop-blur"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold uppercase tracking-[0.14em] text-slate-500">
                  high_quality_ai_render_v1
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
                  {showMap && artifact.site_frame.map_context_available ? " · registered over live map context" : " · local site coordinates"}
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
                  download={`ai-visualization-${artifact.project_id}.svg`}
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
        </>
      ) : (
        <div
          data-testid="ai-realism-blocker"
          className="pointer-events-auto mx-4 max-w-md rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-lg"
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
