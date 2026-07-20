import { useEffect, useMemo } from "react";

import { toApiUrl } from "../../lib/api";
import type { PlanMeta, PlanPdfElement } from "../types";

type DashboardPlanPdfDerivedStateOptions = {
  currentPlanMeta: PlanMeta;
  selectedPlanPdfElementId: string;
  setPlanPdfElementDraftText: (value: string) => void;
  setPlanPdfMoveX: (value: string) => void;
  setPlanPdfMoveY: (value: string) => void;
  setSelectedPlanPdfElementId: (value: string) => void;
  token: string;
};

export function useDashboardPlanPdfDerivedState({
  currentPlanMeta,
  selectedPlanPdfElementId,
  setPlanPdfElementDraftText,
  setPlanPdfMoveX,
  setPlanPdfMoveY,
  setSelectedPlanPdfElementId,
  token,
}: DashboardPlanPdfDerivedStateOptions) {
  const planPdfAnalysis = currentPlanMeta.plan_pdf_analysis_v1;
  const planPdfEditableSheet = currentPlanMeta.plan_pdf_editable_sheet_v1 ?? planPdfAnalysis?.editable_sheet;
  const planPdfElements = useMemo<PlanPdfElement[]>(
    () => (planPdfEditableSheet?.elements ?? []).filter((item): item is PlanPdfElement => Boolean(item?.element_id)),
    [planPdfEditableSheet?.elements],
  );
  const selectedPlanPdfElement = useMemo(
    () => planPdfElements.find((item) => item.element_id === selectedPlanPdfElementId) ?? planPdfElements[0] ?? null,
    [planPdfElements, selectedPlanPdfElementId],
  );
  const planPdfFirstPage = planPdfAnalysis?.pages?.[0] ?? null;
  const planPdfSourceUrl = planPdfAnalysis?.source_pdf?.file_url
    ? toApiUrl(`${planPdfAnalysis.source_pdf.file_url}?access_token=${encodeURIComponent(token || "")}`)
    : "";
  const planPdfSummary = planPdfAnalysis?.summary ?? {};
  const planPdfBlockers = planPdfAnalysis?.blockers ?? [];
  const planPdfChangedReport = currentPlanMeta.plan_pdf_changed_elements_v1 ?? planPdfEditableSheet?.changed_elements ?? null;
  const planPdfChangedElements = planPdfChangedReport?.elements ?? [];
  const planPdfUnreadableItems = planPdfBlockers.filter((item) => /ocr|raster|vector|unread|parser|renderer/i.test(String(item)));
  const planPdfExtractionSummaryRows = [
    ["Text", Number(planPdfSummary.text_evidence_count ?? 0)],
    ["Labels", Number(planPdfSummary.label_count ?? 0)],
    ["Dimensions", Number(planPdfSummary.dimension_count ?? 0)],
    ["Title block", Number(planPdfSummary.title_block_count ?? 0)],
    ["Scale", Number(planPdfSummary.scale_candidate_count ?? 0)],
    ["Elevations", Number(planPdfSummary.elevation_callout_count ?? 0)],
    ["Matchlines", Number(planPdfSummary.matchline_count ?? 0)],
    ["Details", Number(planPdfSummary.detail_block_count ?? 0)],
  ] satisfies Array<[string, number]>;
  const planPdfClassificationPreviewRows = [
    ["Labels", "labels"],
    ["Dimensions", "dimensions"],
    ["Title block fields", "title_blocks"],
    ["Scale candidates", "scale_candidates"],
    ["Elevation callouts", "elevation_callouts"],
    ["Matchlines", "matchlines"],
    ["Detail blocks", "detail_blocks"],
  ].map(([label, bucket]) => {
    const items = planPdfAnalysis?.classifications?.[bucket] ?? [];
    return {
      label,
      value: items
        .slice(0, 3)
        .map((item) => String(item.text ?? "").trim())
        .filter(Boolean)
        .join(" | "),
    };
  });

  useEffect(() => {
    if (selectedPlanPdfElement?.element_id && selectedPlanPdfElement.element_id !== selectedPlanPdfElementId) {
      setSelectedPlanPdfElementId(selectedPlanPdfElement.element_id);
    }
    setPlanPdfElementDraftText(selectedPlanPdfElement?.text ?? "");
    const bbox = selectedPlanPdfElement?.bbox;
    setPlanPdfMoveX(bbox?.x0 !== undefined ? String(bbox.x0) : "");
    setPlanPdfMoveY(bbox?.y0 !== undefined ? String(bbox.y0) : "");
  }, [
    selectedPlanPdfElement?.bbox,
    selectedPlanPdfElement?.element_id,
    selectedPlanPdfElement?.text,
    selectedPlanPdfElementId,
    setPlanPdfElementDraftText,
    setPlanPdfMoveX,
    setPlanPdfMoveY,
    setSelectedPlanPdfElementId,
  ]);

  return {
    planPdfAnalysis,
    planPdfBlockers,
    planPdfChangedElements,
    planPdfChangedReport,
    planPdfClassificationPreviewRows,
    planPdfEditableSheet,
    planPdfElements,
    planPdfExtractionSummaryRows,
    planPdfFirstPage,
    planPdfSourceUrl,
    planPdfSummary,
    planPdfUnreadableItems,
    selectedPlanPdfElement,
  };
}
