import type { MutableRefObject } from "react";

import type {
  BuildingPlacement,
  ChatMessage,
  ProjectInput,
  SiteInputs,
  SurveySlopeResponse,
} from "../types";
import { uploadedImageSrc } from "./auth";
import { buildDashboardProjectInputView } from "./dashboardProjectInputView";
import type { SystemStatus } from "./workflowConstants";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;

export function runDashboardApplyProjectInput({
  chatMessagesRef,
  projectInput,
  setActivePlacementId,
  setAssumedTerrainSlopePct,
  setBuildingCount,
  setBuildingDepth,
  setBuildingPlacements,
  setBuildingWidth,
  setChatMessages,
  setDrainage,
  setDrainageAllowSlopeAdjust,
  setDrainageConnectOrphans,
  setDrainageForcedInlets,
  setDrainageMaxSlopeAdjust,
  setFileName,
  setFileNameAuto,
  setGrading,
  setImageName,
  setLotHeight,
  setLotWidth,
  setMaxAdaCrossSlopePct,
  setMaxParkingSlopePct,
  setMaxRoadGradePct,
  setMinSlopePct,
  setParkingCount,
  setPipeMinSlopePct,
  setPlacementModeEnabled,
  setProjectType,
  setPrompt,
  setRoads,
  setSetback,
  setSiteName,
  setSiteNameAuto,
  setSurveySlopeEstimate,
  setSystemStatuses,
  setUnits,
  setUploadedImageApiUrl,
  setUploadedImagePreviewUrl,
  setUseSurveyForGrading,
  setUtilities,
  siteInputs,
  token,
}: {
  chatMessagesRef: MutableRefObject<ChatMessage[]>;
  projectInput: ProjectInput;
  setActivePlacementId: StateSetter<string | null>;
  setAssumedTerrainSlopePct: StateSetter<string>;
  setBuildingCount: StateSetter<string>;
  setBuildingDepth: StateSetter<string>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setBuildingWidth: StateSetter<string>;
  setChatMessages: StateSetter<ChatMessage[]>;
  setDrainage: StateSetter<boolean>;
  setDrainageAllowSlopeAdjust: StateSetter<boolean>;
  setDrainageConnectOrphans: StateSetter<boolean>;
  setDrainageForcedInlets: StateSetter<Array<{ x: number; y: number; name?: string }>>;
  setDrainageMaxSlopeAdjust: StateSetter<number>;
  setFileName: StateSetter<string>;
  setFileNameAuto: StateSetter<boolean>;
  setGrading: StateSetter<boolean>;
  setImageName: StateSetter<string>;
  setLotHeight: StateSetter<string>;
  setLotWidth: StateSetter<string>;
  setMaxAdaCrossSlopePct: StateSetter<string>;
  setMaxParkingSlopePct: StateSetter<string>;
  setMaxRoadGradePct: StateSetter<string>;
  setMinSlopePct: StateSetter<string>;
  setParkingCount: StateSetter<string>;
  setPipeMinSlopePct: StateSetter<string>;
  setPlacementModeEnabled: StateSetter<boolean>;
  setProjectType: StateSetter<string>;
  setPrompt: StateSetter<string>;
  setRoads: StateSetter<boolean>;
  setSetback: StateSetter<string>;
  setSiteName: StateSetter<string>;
  setSiteNameAuto: StateSetter<boolean>;
  setSurveySlopeEstimate: StateSetter<SurveySlopeResponse | null>;
  setSystemStatuses: StateSetter<Record<string, SystemStatus>>;
  setUnits: StateSetter<string>;
  setUploadedImageApiUrl: StateSetter<string>;
  setUploadedImagePreviewUrl: StateSetter<string>;
  setUseSurveyForGrading: StateSetter<boolean>;
  setUtilities: StateSetter<boolean>;
  siteInputs: SiteInputs | null | undefined;
  token: string | null;
}) {
  if (!projectInput || typeof projectInput !== "object") {
    return;
  }

  const restoredProjectInput = buildDashboardProjectInputView(projectInput, siteInputs);

  setPrompt(restoredProjectInput.promptText);
  setImageName(restoredProjectInput.imagePath);
  setUploadedImageApiUrl(
    restoredProjectInput.imagePath ? uploadedImageSrc(restoredProjectInput.imagePath, token ?? "") : "",
  );
  setUploadedImagePreviewUrl("");
  setSiteName(restoredProjectInput.siteName);
  setFileName(restoredProjectInput.fileName);
  setSiteNameAuto(restoredProjectInput.siteNameAuto);
  setFileNameAuto(restoredProjectInput.fileNameAuto);
  setUnits(restoredProjectInput.units);
  setProjectType(restoredProjectInput.projectType);
  setLotWidth(restoredProjectInput.lotWidth);
  setLotHeight(restoredProjectInput.lotHeight);
  setSetback(restoredProjectInput.setback);
  setBuildingWidth(restoredProjectInput.buildingWidth);
  setBuildingDepth(restoredProjectInput.buildingDepth);
  setBuildingCount(restoredProjectInput.buildingCount);
  setBuildingPlacements(restoredProjectInput.mergedPlacements);
  setPlacementModeEnabled(false);
  setActivePlacementId(null);
  setParkingCount(restoredProjectInput.parkingCount);
  if (restoredProjectInput.officeProgramDims) {
    setBuildingWidth(restoredProjectInput.officeProgramDims.width);
    setBuildingDepth(restoredProjectInput.officeProgramDims.depth);
  }
  setMinSlopePct(restoredProjectInput.minSlopePct);
  if (typeof restoredProjectInput.assumedTerrainSlopePct === "number") {
    setAssumedTerrainSlopePct(String(restoredProjectInput.assumedTerrainSlopePct));
    setSurveySlopeEstimate(restoredProjectInput.assumedSlopeEstimate);
    setUseSurveyForGrading(false);
  }
  setPipeMinSlopePct(restoredProjectInput.pipeMinSlopePct);
  setDrainageForcedInlets(restoredProjectInput.drainageForcedInlets);
  setDrainageConnectOrphans(restoredProjectInput.drainageConnectOrphans);
  setDrainageAllowSlopeAdjust(restoredProjectInput.drainageAllowSlopeAdjust);
  setDrainageMaxSlopeAdjust(restoredProjectInput.drainageMaxSlopeAdjust);
  setMaxParkingSlopePct(restoredProjectInput.maxParkingSlopePct);
  setMaxRoadGradePct(restoredProjectInput.maxRoadGradePct);
  setMaxAdaCrossSlopePct(restoredProjectInput.maxAdaCrossSlopePct);
  setRoads(restoredProjectInput.roads);
  setGrading(restoredProjectInput.grading);
  setDrainage(restoredProjectInput.drainage);
  setUtilities(restoredProjectInput.utilities);
  if (restoredProjectInput.systemStatuses) {
    setSystemStatuses(restoredProjectInput.systemStatuses);
  }
  const nextThread = restoredProjectInput.chatThread;
  chatMessagesRef.current = nextThread;
  setChatMessages(nextThread);
}
