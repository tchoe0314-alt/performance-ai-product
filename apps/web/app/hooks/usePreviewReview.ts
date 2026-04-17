"use client";

import { useMemo } from "react";

import type { PlanMeta, PreviewResponse, PreviewReview } from "../types";
import { joinNatural, toArray, toReadableLabel } from "../utils/formatting";

type UsePreviewReviewOptions = {
  currentPlanMeta: PlanMeta;
  planPreviewSummary: PreviewResponse["summary"] | null;
};

type PreviewPhaseEntry = {
  key: string;
  label: string;
  status: string;
  ready: boolean;
  summary: string;
  currentStage: string;
  currentStatus: string;
};

export default function usePreviewReview({
  currentPlanMeta,
  planPreviewSummary,
}: UsePreviewReviewOptions) {
  const previewReview: PreviewReview | null = useMemo(() => {
    const resultReleaseReview =
      currentPlanMeta?.release_review && typeof currentPlanMeta.release_review === "object"
        ? currentPlanMeta.release_review
        : null;
    const resultPhaseCheckpoints =
      currentPlanMeta?.phase_checkpoints && typeof currentPlanMeta.phase_checkpoints === "object"
        ? currentPlanMeta.phase_checkpoints
        : null;
    const summaryReview =
      planPreviewSummary?.review && typeof planPreviewSummary.review === "object"
        ? planPreviewSummary.review
        : null;

    const hasResultReviewSignal = Boolean(
      resultReleaseReview &&
        (Object.keys(resultReleaseReview).length ||
          Object.keys(resultPhaseCheckpoints || {}).length ||
          currentPlanMeta?.release_status),
    );

    if (!hasResultReviewSignal) {
      return summaryReview;
    }

    return {
      ...(summaryReview || {}),
      ...(resultReleaseReview || {}),
      phase_checkpoints:
        resultReleaseReview?.phase_checkpoints && typeof resultReleaseReview.phase_checkpoints === "object"
          ? resultReleaseReview.phase_checkpoints
          : resultPhaseCheckpoints || summaryReview?.phase_checkpoints || {},
      release_status:
        String(resultReleaseReview?.release_status || currentPlanMeta?.release_status || "").trim() ||
        summaryReview?.release_status ||
        "review",
      release_note:
        String(resultReleaseReview?.release_note || "").trim() ||
        String(currentPlanMeta?.release_note || "").trim() ||
        summaryReview?.release_note ||
        "",
    };
  }, [currentPlanMeta, planPreviewSummary]);

  const previewAssumptionCategories = useMemo(
    () =>
      toArray(previewReview?.assumption_categories)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean),
    [previewReview],
  );
  const previewFixActions = useMemo(
    () =>
      toArray(previewReview?.autofix_actions)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean),
    [previewReview],
  );
  const previewFixTargets = useMemo(
    () =>
      toArray(previewReview?.dominant_fix_targets)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean),
    [previewReview],
  );
  const previewReviewCategories = useMemo(
    () =>
      toArray(previewReview?.review_categories)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter((item: string | null | undefined) => {
          const normalized = String(item || "").toLowerCase();
          return Boolean(item) && normalized !== "uncategorized" && normalized !== "general";
        }),
    [previewReview],
  );
  const previewBlockedReasons = useMemo(
    () =>
      toArray(previewReview?.blocked_reasons)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean),
    [previewReview],
  );
  const previewFailedDeliverables = useMemo(
    () =>
      toArray(previewReview?.failed_deliverables)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean),
    [previewReview],
  );
  const previewExtraDeliverables = useMemo(
    () =>
      toArray(previewReview?.extra_deliverables)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean),
    [previewReview],
  );
  const previewReadyDeliverables = useMemo(
    () =>
      toArray(previewReview?.ready_deliverables)
        .map((item: unknown) => toReadableLabel(String(item || "")))
        .filter(Boolean),
    [previewReview],
  );

  const previewPhaseEntries = useMemo<PreviewPhaseEntry[]>(
    () =>
      (
        [
          "layout",
          "grading",
          "drainage_storm",
          "utilities",
          "coordination_validation",
          "combined_view",
        ] as const
      )
        .map((key) => {
          const phase = previewReview?.phase_checkpoints?.[key];
          if (!phase) {
            return null;
          }
          const label = toReadableLabel(String(phase.label || key || "")) || "Phase";
          const status = String(phase.status || (phase.ready ? "ready" : "review") || "review");
          const deliverables = toArray(phase.deliverables)
            .map((item: unknown) => toReadableLabel(String(item || "")))
            .filter(Boolean);
          const blockers = [
            ...toArray(phase.blockers),
            ...toArray(phase.blocked_reasons),
          ]
            .map((item: unknown) => toReadableLabel(String(item || "")))
            .filter(Boolean);
          const messages = toArray(phase.messages)
            .map((item: unknown) => String(item || "").trim())
            .filter(Boolean);
          const note = String(phase.note || "").trim();
          const currentStage = toReadableLabel(String(phase.current_stage || ""));
          const currentStatus = String(phase.current_status || "").trim();
          const phaseSummary =
            key === "combined_view" && (phase.total_phase_count || phase.completed_phase_count)
              ? (() => {
                  const countSummary = `${phase.completed_phase_count ?? 0}/${phase.total_phase_count ?? 0} phases complete`;
                  if (currentStage && currentStatus && currentStatus.toLowerCase() !== "complete") {
                    return `${countSummary} • ${currentStage} ${toReadableLabel(currentStatus)}`.trim();
                  }
                  return countSummary;
                })()
              : messages[0] ||
                note ||
                (deliverables.length
                  ? `Ready: ${joinNatural(deliverables, 3)}`
                  : blockers.length
                    ? `Watch: ${joinNatural(blockers, 3)}`
                    : phase.ready
                      ? "Phase outputs are saved."
                      : "Phase is still under review.");
          return {
            key,
            label,
            status,
            ready: Boolean(phase.ready),
            summary: phaseSummary,
            currentStage,
            currentStatus,
          };
        })
        .filter(Boolean) as PreviewPhaseEntry[],
    [previewReview],
  );

  const combinedPreviewPhase =
    previewPhaseEntries.find((phase) => phase.key === "combined_view") ?? null;
  const phaseOnlyEntries = previewPhaseEntries.filter(
    (phase) => phase.key !== "combined_view",
  );

  const previewRunningPhase =
    phaseOnlyEntries.find((phase) =>
      ["running"].includes(phase.status.toLowerCase()) ||
      phase.currentStatus.toLowerCase() === "running",
    ) ?? null;

  const previewCompletedPhaseCount = useMemo(() => {
    const explicitCount = Number(
      previewReview?.phase_checkpoints?.combined_view?.completed_phase_count ?? NaN,
    );
    if (Number.isFinite(explicitCount) && explicitCount >= 0) {
      return explicitCount;
    }
    return phaseOnlyEntries.filter((phase) =>
      ["ready", "complete"].includes(phase.status.toLowerCase()),
    ).length;
  }, [previewReview, phaseOnlyEntries]);

  const previewTotalPhaseCount = useMemo(() => {
    const explicitTotal = Number(
      previewReview?.phase_checkpoints?.combined_view?.total_phase_count ?? NaN,
    );
    if (Number.isFinite(explicitTotal) && explicitTotal > 0) {
      return explicitTotal;
    }
    return phaseOnlyEntries.length;
  }, [previewReview, phaseOnlyEntries]);

  const previewNextPendingPhase =
    phaseOnlyEntries.find((phase) =>
      ["pending", "partial", "review"].includes(phase.status.toLowerCase()),
    ) ?? null;

  const previewPhaseProgressPercent = useMemo(() => {
    if (!previewTotalPhaseCount) return 0;
    const explicitJobProgress = Number(
      previewReview?.phase_checkpoints?.combined_view?.job_progress ?? NaN,
    );
    const base = Math.max(
      0,
      Math.min(1, previewCompletedPhaseCount / previewTotalPhaseCount),
    );
    if (Number.isFinite(explicitJobProgress) && previewRunningPhase) {
      const perPhase = 1 / previewTotalPhaseCount;
      const runningFraction = Math.max(0, Math.min(1, explicitJobProgress / 100));
      return Math.round(
        Math.max(base, Math.min(1, base + perPhase * runningFraction)) * 100,
      );
    }
    if (previewRunningPhase) {
      return Math.round(
        Math.min(1, base + 0.5 / previewTotalPhaseCount) * 100,
      );
    }
    return Math.round(base * 100);
  }, [
    previewReview,
    previewTotalPhaseCount,
    previewCompletedPhaseCount,
    previewRunningPhase,
  ]);

  const previewPhaseHeadline = previewRunningPhase
    ? `Continuing with ${previewRunningPhase.label}`
    : previewNextPendingPhase
      ? `Waiting to continue with ${previewNextPendingPhase.label}`
      : previewTotalPhaseCount > 0
        ? `${previewCompletedPhaseCount}/${previewTotalPhaseCount} phases complete`
        : "";

  const previewRerunSignals = useMemo(
    () =>
      [
        ...toArray(previewReview?.rerun_stages).map((item: unknown) =>
          toReadableLabel(String(item || "")),
        ),
        ...toArray(previewReview?.rerun_reasons).map((item: unknown) =>
          toReadableLabel(String(item || "")),
        ),
      ].filter(Boolean),
    [previewReview],
  );

  return {
    previewReview,
    previewAssumptionCategories,
    previewFixActions,
    previewFixTargets,
    previewReviewCategories,
    previewBlockedReasons,
    previewFailedDeliverables,
    previewExtraDeliverables,
    previewReadyDeliverables,
    previewPhaseEntries,
    combinedPreviewPhase,
    phaseOnlyEntries,
    previewCompletedPhaseCount,
    previewTotalPhaseCount,
    previewRunningPhase,
    previewNextPendingPhase,
    previewPhaseProgressPercent,
    previewPhaseHeadline,
    previewRerunSignals,
  };
}
