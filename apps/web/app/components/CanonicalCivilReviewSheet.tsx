"use client";

import { useState } from "react";
import type { CivilReviewSheetProps } from "./CivilReviewSheet";
import { reviewSheetGeometry } from "../utils/reviewSheetGeometry";

export default function CanonicalCivilReviewSheet(props: CivilReviewSheetProps) {
  const [expanded, setExpanded] = useState(false);
  const geometry = reviewSheetGeometry(props.placements, props.lotWidth, props.lotHeight);
  const scale = Math.min(800 / geometry.bounds.width, 540 / geometry.bounds.height);
  const xy = ([x, y]: [number, number]) => [85 + (x - geometry.bounds.minX) * scale, 110 + (y - geometry.bounds.minY) * scale];
  const points = (values: [number, number][]) => values.map(point => xy(point).join(",")).join(" ");
  const objects = geometry.objects.filter(object => object.item.type !== "site");
  const types = [...new Set(objects.map(object => String(object.item.type ?? "object").replaceAll("_", " ")))];
  return <section data-testid="civil-review-sheet-preview" className={`overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm ${expanded ? "fixed inset-4 z-[90] flex flex-col" : ""}`}>
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
      <div><p className="text-xs font-semibold uppercase tracking-widest text-slate-500">Civil Review Sheet</p>
        <p className="mt-1 text-sm font-semibold text-slate-950">Current project geometry · review only</p>
        <p className="mt-1 text-xs text-slate-500">No sample buildings, utility routes, contours or elevations are substituted for missing project data.</p></div>
      <button type="button" data-testid="civil-review-sheet-expand" onClick={() => setExpanded(value => !value)} className="rounded-full border border-slate-200 px-3 py-1 text-xs">
        {expanded ? "Close full sheet" : "View full sheet"}</button>
    </div>
    {geometry.invalidIds.length > 0 ? <p role="alert" className="p-3 text-sm text-red-700">Invalid geometry omitted: {geometry.invalidIds.join(", ")}. Repair before relying on this sheet.</p> : null}
    <div className={`${expanded ? "min-h-0 flex-1" : ""} overflow-auto bg-slate-100 p-3`}>
      <svg data-testid="civil-review-sheet-svg" role="img" aria-label="Current project civil review sheet" viewBox="0 0 1200 760" className="min-w-[940px] bg-white">
        <rect x="20" y="20" width="1160" height="720" fill="white" stroke="#111" strokeWidth="3" />
        <rect x="65" y="65" width="845" height="610" fill="white" stroke="#111" />
        <g data-testid="civil-review-sheet-plan">
          <text x="80" y="88" fontSize="13" fontWeight="700">CURRENT PROJECT · REVIEW ONLY · NOT FOR CONSTRUCTION</text>
          {geometry.objects.map(({ item, points: shape, island, isPolyline, isPoint }) => {
            const center = xy([(item.x ?? 0) + item.w / 2, (item.y ?? 0) + item.d / 2]);
            return <g key={item.id} data-testid={item.type === "site" ? "civil-review-sheet-boundary" : "civil-review-sheet-plan-object"} data-object-id={item.id} data-world-points={JSON.stringify(shape)}>
              {isPoint ? <circle cx={xy(shape[0])[0]} cy={xy(shape[0])[1]} r="3" fill="#111" /> : isPolyline ? <polyline points={points(shape)} fill="none" stroke="#111" strokeWidth="1.4" /> : <polygon points={points(shape)} fill={item.type === "site" ? "none" : "#f8fafc"} stroke="#111" strokeWidth={item.type === "site" ? 2 : 1.2} strokeDasharray={item.type === "site" ? "6 3" : undefined} />}
              {island ? <polygon points={points(island)} fill="white" stroke="#111" /> : null}
              {item.type !== "site" ? <text x={center[0]} y={center[1]} textAnchor="middle" fontSize="8">{item.label || item.id}</text> : null}
              <title>{item.label || item.id}{isPolyline ? " · stored route centerline" : " · stored footprint"}</title>
            </g>;
          })}
          {objects.length === 0 ? <text x="120" y="160" fontSize="13">No placed project objects. No sample layout substituted.</text> : null}
        </g>
        <g data-testid="civil-review-sheet-title-block">
          <rect x="930" y="65" width="220" height="610" fill="white" stroke="#111" />
          <text x="945" y="100" fontSize="24" fontWeight="800">CIVORA</text>
          <foreignObject x="945" y="120" width="190" height="155"><div className="text-xs leading-6 text-slate-950"><strong>{props.projectName || "Untitled Project"}</strong><br />{props.addressLabel || "No address applied"}<br />Local project-coordinate view. Units, orientation, datum and survey/control require confirmation.</div></foreignObject>
          <text x="945" y="310" fontSize="11" fontWeight="700">REVIEW NOTES</text>
          <foreignObject x="945" y="325" width="190" height="250"><div className="text-[11px] leading-5 text-slate-950">Actual placed, visible objects only. Scale is uniform; objects outside the boundary are not moved into it.<br /><br />No invented contours, grade values, utility connections, north orientation or professional approvals.<br /><br />Parking footprints do not imply verified stall capacity or access. Engineering calculations and evidence need separate review.</div></foreignObject>
          <text x="945" y="620" fontSize="11">CONCEPT REVIEW EXHIBIT</text>
        </g>
        <g data-testid="civil-review-sheet-legend"><foreignObject x="80" y="652" width="820" height="25"><div className="text-[10px] text-slate-950">Objects: {types.join(" · ") || "none"}</div></foreignObject></g>
        <g data-testid="civil-review-sheet-profile"><text x="80" y="704" fontSize="10">REVIEW ONLY · Profiles and elevations are not supplied by this preview.</text></g>
        <g data-testid="civil-review-sheet-source-summary"><foreignObject x="80" y="710" width="1050" height="25"><div className="text-[10px] text-slate-950">Source candidates: {props.sourceCandidateCount} · Missing: {props.missingSources.join(", ") || "none reported (not independently verified)"}</div></foreignObject></g>
      </svg>
    </div>
  </section>;
}
