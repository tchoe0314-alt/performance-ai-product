import { type MutableRefObject, useCallback } from "react";

import type { SurveySlopeResponse } from "../types";
import {
  buildAssumedSlopeEstimate,
  type SystemGenerationTarget,
} from "../utils/workflowConstants";
import { parsePositiveNumber } from "../utils/formatting";

type DetectionChoices = {
  buildings: boolean;
  grading: boolean;
  parking: boolean;
  roads: boolean;
};

type DashboardSelectedDetectionActionsOptions = {
  assumedTerrainSlopePct: string;
  detectionChoices: DetectionChoices;
  handleAnalyzeImageFeatures: () => Promise<void>;
  handleGenerateSystemRef: MutableRefObject<
    | ((
        target: SystemGenerationTarget,
        options?: { slopeEstimateOverride?: SurveySlopeResponse | null },
      ) => Promise<void>)
    | null
  >;
  hasTerrainSource: boolean;
  mapSnapshotPath: string;
  setAssumedTerrainSlopePct: (value: string) => void;
  setStatusMessage: (value: string) => void;
  setSurveySlopeEstimate: (value: SurveySlopeResponse | null) => void;
  setUseSurveyForGrading: (value: boolean) => void;
  siteScaleLocked: boolean;
  surveySlopeEstimate: SurveySlopeResponse | null;
};

export function useDashboardSelectedDetectionActions({
  assumedTerrainSlopePct,
  detectionChoices,
  handleAnalyzeImageFeatures,
  handleGenerateSystemRef,
  hasTerrainSource,
  mapSnapshotPath,
  setAssumedTerrainSlopePct,
  setStatusMessage,
  setSurveySlopeEstimate,
  setUseSurveyForGrading,
  siteScaleLocked,
  surveySlopeEstimate,
}: DashboardSelectedDetectionActionsOptions) {
  return useCallback(async () => {
    if (!siteScaleLocked) {
      setStatusMessage("Lock the site first, then Civora can detect or draft inside that boundary.");
      return;
    }
    const wantsContext = detectionChoices.roads || detectionChoices.buildings || detectionChoices.parking;
    let ranSomething = false;
    if (wantsContext) {
      if (!mapSnapshotPath) {
        setStatusMessage("Map/image detection needs a map snapshot. Grading can still run from survey, terrain, or an explicit assumed slope.");
      } else {
        await handleAnalyzeImageFeatures();
        ranSomething = true;
      }
    }
    if (detectionChoices.grading) {
      let slopeEstimateOverride: SurveySlopeResponse | null = null;
      if (!hasTerrainSource && !surveySlopeEstimate?.slope_percent) {
        const slopePct = parsePositiveNumber(assumedTerrainSlopePct) ?? 8;
        slopeEstimateOverride = buildAssumedSlopeEstimate(slopePct);
        setAssumedTerrainSlopePct(String(slopePct));
        setUseSurveyForGrading(false);
        setSurveySlopeEstimate(slopeEstimateOverride);
        setStatusMessage(`No survey/terrain source is attached, so Civora is using an explicit ${slopePct}% assumed slope for this review draft.`);
      }
      await handleGenerateSystemRef.current?.("grading", { slopeEstimateOverride });
      ranSomething = true;
    }
    if (!ranSomething && !wantsContext && !detectionChoices.grading) {
      setStatusMessage("Select at least one detection option.");
    }
  }, [
    assumedTerrainSlopePct,
    detectionChoices,
    handleAnalyzeImageFeatures,
    handleGenerateSystemRef,
    hasTerrainSource,
    mapSnapshotPath,
    setAssumedTerrainSlopePct,
    setStatusMessage,
    setSurveySlopeEstimate,
    setUseSurveyForGrading,
    siteScaleLocked,
    surveySlopeEstimate?.slope_percent,
  ]);
}
