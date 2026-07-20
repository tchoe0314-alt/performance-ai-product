import { X } from "lucide-react";

import type { PreviewResponse } from "../types";
import { buildPreviewBoundsStyle } from "../utils/previewLayoutHelpers";
import { PreviewAnnotationLabelMarkers } from "./PreviewAnnotationLabelMarkers";

type PreviewImageBounds = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type PreviewHighlightBounds = Parameters<typeof buildPreviewBoundsStyle>[0];
type PreviewAnnotationLabels = NonNullable<NonNullable<PreviewResponse["preview_annotations"]>["labels"]>;

export function PreviewFullscreenHeader({
  description,
  onClose,
}: {
  description: string;
  onClose: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-5 py-4 text-white">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
          Fullscreen Preview
        </p>
        <p className="mt-1 text-sm text-slate-200">{description}</p>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-100 transition hover:bg-slate-800"
      >
        <X className="h-4 w-4" />
        Close
      </button>
    </div>
  );
}

export function PreviewPlanAnnotationOverlay({
  imageBounds,
  labels,
  selectedIssueLabel,
  showHover,
  activeHighlightBounds,
  issueHighlightBounds,
  showUnlockedSiteFrame = false,
}: {
  imageBounds: PreviewImageBounds;
  labels: PreviewAnnotationLabels;
  selectedIssueLabel: string;
  showHover: boolean;
  activeHighlightBounds: PreviewHighlightBounds | null;
  issueHighlightBounds: PreviewHighlightBounds | null;
  showUnlockedSiteFrame?: boolean;
}) {
  return (
    <div
      className="pointer-events-none absolute"
      style={{
        left: imageBounds.left,
        top: imageBounds.top,
        width: imageBounds.width,
        height: imageBounds.height,
      }}
    >
      {showUnlockedSiteFrame ? (
        <div className="absolute inset-0 rounded-[16px] border border-dashed border-slate-300/70" />
      ) : null}
      {activeHighlightBounds ? (
        <div
          className="absolute rounded-[14px] border border-sky-400/90 bg-sky-400/10 shadow-[0_0_0_4px_rgba(56,189,248,0.14)]"
          style={buildPreviewBoundsStyle(activeHighlightBounds)}
        />
      ) : null}
      {issueHighlightBounds ? (
        <div
          className="absolute rounded-[12px] border border-rose-400/80 bg-rose-400/10 shadow-[0_0_0_4px_rgba(244,63,94,0.1)]"
          style={buildPreviewBoundsStyle(issueHighlightBounds)}
        />
      ) : null}
      <PreviewAnnotationLabelMarkers
        labels={labels}
        selectedIssueLabel={selectedIssueLabel}
        showHover={showHover}
      />
    </div>
  );
}
