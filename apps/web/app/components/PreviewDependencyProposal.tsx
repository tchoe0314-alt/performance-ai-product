import { createPortal } from "react-dom";
import { useCompactViewport } from "../hooks/useCompactViewport";
import type { BuildingPlacement } from "../types";
import type { CanonicalDependencyProposal } from "../utils/canonicalDependencyPolicies";

type ProposalGeometryProps = {
  proposal: CanonicalDependencyProposal | null;
  mapAnchoredRectPercent: (item: BuildingPlacement) => { left: number; top: number; width: number; height: number };
  sitePointToSvgPercent: (point: [number, number]) => string;
};

export function PreviewDependencyProposalGeometry({
  proposal,
  mapAnchoredRectPercent,
  sitePointToSvgPercent,
}: ProposalGeometryProps) {
  if (!proposal) return null;
  return (
    <g data-testid="dependency-proposal-geometry" aria-label="Proposed linked parking positions">
      {proposal.after.map((item) => {
        if (item.geometryType && item.geometry?.length) {
          const points = item.geometry.map(sitePointToSvgPercent).join(" ");
          return item.geometryType === "polyline" ? (
            <polyline key={item.id} points={points} fill="none" stroke="#0ea5e9" strokeWidth="0.75" strokeDasharray="2 1.5" />
          ) : (
            <polygon key={item.id} points={points} fill="rgba(14,165,233,0.16)" stroke="#0ea5e9" strokeWidth="0.75" strokeDasharray="2 1.5" />
          );
        }
        const rect = mapAnchoredRectPercent(item);
        return (
          <g key={item.id}>
            <rect
              x={rect.left}
              y={rect.top}
              width={rect.width}
              height={rect.height}
              fill="rgba(14,165,233,0.16)"
              stroke="#0284c7"
              strokeWidth="0.75"
              strokeDasharray="2 1.5"
              vectorEffect="non-scaling-stroke"
            />
            <text x={rect.left + rect.width / 2} y={Math.max(2, rect.top - 1)} textAnchor="middle" fontSize="2.2" fill="#0369a1">
              PROPOSED · {item.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}

type ProposalCardProps = {
  proposal: CanonicalDependencyProposal;
  onAccept: () => void;
  onAdjust: () => void;
  onReject: () => void;
};

export function PreviewDependencyProposalCard({ proposal, onAccept, onAdjust, onReject }: ProposalCardProps) {
  const compactViewport = useCompactViewport();
  const reviewCount = proposal.reflowReports.filter((report) => report.status === "review").length;
  const card = (
    <section
      data-testid="dependency-proposal-card"
      data-presentation={compactViewport ? "viewport" : "canvas"}
      className={`${compactViewport
        ? "fixed left-1/2 top-[calc(env(safe-area-inset-top)+5rem)] z-[850] max-h-[calc(100svh-12rem)] overflow-y-auto"
        : "absolute left-1/2 top-4 z-[70]"} w-[min(92%,34rem)] -translate-x-1/2 rounded-2xl border border-sky-200 bg-white/95 p-3 shadow-xl backdrop-blur`}
      aria-label="Linked parking proposal"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-sky-700">Civora suggestion · not applied</p>
          <p className="mt-1 text-sm font-semibold text-slate-900">
            Apply the complete {proposal.after.length}-object change to {proposal.buildingLabel} and its linked objects?
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            The dashed blue geometry previews the whole transaction. Nothing has been applied; the working plan is unchanged.
          </p>
          <p className={`mt-1 text-[11px] font-semibold ${reviewCount ? "text-amber-700" : "text-emerald-700"}`} data-testid="dependency-proposal-validation">
            {reviewCount
              ? `${reviewCount} parking field${reviewCount === 1 ? "" : "s"} still needs boundary or collision review.`
              : "Site boundary and basic collision checks are clear."}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button type="button" data-testid="dependency-proposal-reject" onClick={onReject} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50">
            Reject
          </button>
          <button type="button" data-testid="dependency-proposal-adjust" onClick={onAdjust} className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs font-semibold text-sky-800 hover:bg-sky-100">
            Adjust
          </button>
          <button type="button" data-testid="dependency-proposal-accept" onClick={onAccept} className="rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">
            Accept
          </button>
        </div>
      </div>
    </section>
  );
  // The mobile drawer is a separate stacking layer over the canvas. Portal
  // review controls out of that layer without moving or applying geometry.
  return compactViewport ? createPortal(card, document.body) : card;
}
