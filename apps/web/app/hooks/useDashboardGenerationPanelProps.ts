import { useMemo } from "react";
import type { ComponentProps, Dispatch, SetStateAction } from "react";

import { DrainageWorkbenchPanel } from "../components/DrainageWorkbenchPanel";
import { GeneratePanel } from "../components/GeneratePanel";
import { GradingWorkbenchPanel } from "../components/GradingWorkbenchPanel";
import { LandscapeWorkbenchPanel } from "../components/LandscapeWorkbenchPanel";
import { RoadwayWorkbenchPanel } from "../components/RoadwayWorkbenchPanel";
import { SanitaryWorkbenchPanel } from "../components/SanitaryWorkbenchPanel";
import { SystemReadinessPanel } from "../components/SystemReadinessPanel";
import { UtilitiesWorkbenchPanel } from "../components/UtilitiesWorkbenchPanel";
import { WaterFireFlowWorkbenchPanel } from "../components/WaterFireFlowWorkbenchPanel";
import type { BuildingPlacement, Issue } from "../types";
import type { SidePanelKey } from "../utils/workspaceShell";
import type { SystemGenerationTarget } from "../utils/workflowConstants";

type GeneratePanelProps = ComponentProps<typeof GeneratePanel>;
type GradingWorkbenchPanelProps = ComponentProps<typeof GradingWorkbenchPanel>;
type DrainageWorkbenchPanelProps = ComponentProps<typeof DrainageWorkbenchPanel>;
type UtilitiesWorkbenchPanelProps = ComponentProps<typeof UtilitiesWorkbenchPanel>;
type SanitaryWorkbenchPanelProps = ComponentProps<typeof SanitaryWorkbenchPanel>;
type WaterFireFlowWorkbenchPanelProps = ComponentProps<typeof WaterFireFlowWorkbenchPanel>;
type SystemReadinessPanelProps = ComponentProps<typeof SystemReadinessPanel>;
type RoadwayWorkbenchPanelProps = ComponentProps<typeof RoadwayWorkbenchPanel>;
type LandscapeWorkbenchPanelProps = ComponentProps<typeof LandscapeWorkbenchPanel>;

type UseDashboardGenerationPanelPropsInput = {
  missingSite: boolean;
  busy: boolean;
  activeJobStatus: string;
  approvalState: GeneratePanelProps["approvalState"];
  approvalCheckpointLabel: string | null;
  approvalError: string | null;
  statusMessage: string;
  assistedEnabled: boolean;
  pendingPlacementCount: number;
  pendingPlacementLabels: string[];
  currentUserLayoutContext: GeneratePanelProps["currentUserLayoutContext"];
  autoSiteContextFlowSummary: GeneratePanelProps["autoSiteContextFlowSummary"];
  systemReadinessRows: GeneratePanelProps["systemReadinessRows"];
  issues: Issue[];
  generateFlowSummary: GeneratePanelProps["generateFlowSummary"];
  reactiveValidation: GeneratePanelProps["reactiveValidation"];
  reactiveAffectedRunTarget: GeneratePanelProps["reactiveAffectedRunTarget"];
  onAssistedEnabledChange: Dispatch<SetStateAction<boolean>>;
  onStatusMessageChange: Dispatch<SetStateAction<string>>;
  onGenerateFlowSummaryChange: Dispatch<SetStateAction<GeneratePanelProps["generateFlowSummary"]>>;
  onGenerateSystem: (target: SystemGenerationTarget) => Promise<void>;
  onContinueActiveJob: () => Promise<void>;
  drainageIssueApplyLabel: GeneratePanelProps["drainageIssueApplyLabel"];
  canApplyDrainageIssue: GeneratePanelProps["canApplyDrainageIssue"];
  getIssueGuidance: GeneratePanelProps["getIssueGuidance"];
  onApplyDrainageIssue: GeneratePanelProps["onApplyDrainageIssue"];
  formatStageLabel: GeneratePanelProps["formatStageLabel"];
  hasTerrainSource: boolean;
  hasGradingSurface: boolean;
  siteTooLargeForGrading: boolean;
  systemStatuses: SystemReadinessPanelProps["systemStatuses"];
  useSurveyForGrading: boolean;
  onUseSurveyForGradingChange: Dispatch<SetStateAction<boolean>>;
  minSlopePct: GradingWorkbenchPanelProps["minSlopePct"];
  maxParkingSlopePct: GradingWorkbenchPanelProps["maxParkingSlopePct"];
  maxRoadGradePct: GradingWorkbenchPanelProps["maxRoadGradePct"];
  maxAdaCrossSlopePct: GradingWorkbenchPanelProps["maxAdaCrossSlopePct"];
  onMinSlopePctChange: GradingWorkbenchPanelProps["onMinSlopePctChange"];
  onMaxParkingSlopePctChange: GradingWorkbenchPanelProps["onMaxParkingSlopePctChange"];
  onMaxRoadGradePctChange: GradingWorkbenchPanelProps["onMaxRoadGradePctChange"];
  onMaxAdaCrossSlopePctChange: GradingWorkbenchPanelProps["onMaxAdaCrossSlopePctChange"];
  drainageAllowSlopeAdjust: boolean;
  onDrainageAllowSlopeAdjustChange: Dispatch<SetStateAction<boolean>>;
  gradingEarthworkUx: GradingWorkbenchPanelProps["gradingEarthworkUx"];
  onOpenPanel: (panel: SidePanelKey) => void;
  hasBasinPlaced: boolean;
  hasHardSystemBlock: boolean;
  drainageSourceOverride: DrainageWorkbenchPanelProps["drainageSourceOverride"];
  onDrainageSourceOverrideChange: Dispatch<SetStateAction<"civora" | "user">>;
  drainageConnectOrphans: boolean;
  onDrainageConnectOrphansChange: Dispatch<SetStateAction<boolean>>;
  drainageMaxSlopeAdjust: DrainageWorkbenchPanelProps["drainageMaxSlopeAdjust"];
  onDrainageMaxSlopeAdjustChange: DrainageWorkbenchPanelProps["onDrainageMaxSlopeAdjustChange"];
  onAddObject: DrainageWorkbenchPanelProps["onAddObject"];
  drainage: boolean;
  utilities: boolean;
  pipeMinSlopePct: UtilitiesWorkbenchPanelProps["pipeMinSlopePct"];
  onUtilitiesChange: Dispatch<SetStateAction<boolean>>;
  onPipeMinSlopePctChange: UtilitiesWorkbenchPanelProps["onPipeMinSlopePctChange"];
  buildingPlacements: BuildingPlacement[];
  confirmedBuildingCount: number;
  waterFireFlowReview: WaterFireFlowWorkbenchPanelProps["waterFireFlowReview"];
  roads: boolean;
  stormHydrologyReview: SystemReadinessPanelProps["stormHydrologyReview"];
  systemReadinessPanelKey: SystemReadinessPanelProps["sidePanelForRender"];
  siteScaleLocked: boolean;
  activeCivil3DWorkflowTab: RoadwayWorkbenchPanelProps["activeCivil3DWorkflowTab"];
  onCivil3DWorkflowTabChange: RoadwayWorkbenchPanelProps["onCivil3DWorkflowTabChange"];
  roadwayWorkbenchData: RoadwayWorkbenchPanelProps["roadwayWorkbenchData"];
  sourceConfidenceRows: RoadwayWorkbenchPanelProps["sourceConfidenceRows"];
  civil3DWorkflowBlockers: RoadwayWorkbenchPanelProps["civil3DWorkflowBlockers"];
  gradingSourceSummary: RoadwayWorkbenchPanelProps["gradingSourceSummary"];
  hasVerifiedSurveyControl: boolean;
  onShowProfileControls: () => void;
  parkingAngle: RoadwayWorkbenchPanelProps["parkingAngle"];
  onParkingAngleChange: RoadwayWorkbenchPanelProps["onParkingAngleChange"];
  onRoadsChange: Dispatch<SetStateAction<boolean>>;
  parkingLoading: RoadwayWorkbenchPanelProps["parkingLoading"];
  onParkingLoadingChange: RoadwayWorkbenchPanelProps["onParkingLoadingChange"];
  parkingStallWidth: RoadwayWorkbenchPanelProps["parkingStallWidth"];
  onParkingStallWidthChange: RoadwayWorkbenchPanelProps["onParkingStallWidthChange"];
  parkingAisleWidth: RoadwayWorkbenchPanelProps["parkingAisleWidth"];
  onParkingAisleWidthChange: RoadwayWorkbenchPanelProps["onParkingAisleWidthChange"];
  parkingStallDepth: RoadwayWorkbenchPanelProps["parkingStallDepth"];
  onParkingStallDepthChange: RoadwayWorkbenchPanelProps["onParkingStallDepthChange"];
  parkingAdaCount: RoadwayWorkbenchPanelProps["parkingAdaCount"];
  onParkingAdaCountChange: RoadwayWorkbenchPanelProps["onParkingAdaCountChange"];
  parkingCompactCount: RoadwayWorkbenchPanelProps["parkingCompactCount"];
  onParkingCompactCountChange: RoadwayWorkbenchPanelProps["onParkingCompactCountChange"];
  parkingAdaAisleWidth: RoadwayWorkbenchPanelProps["parkingAdaAisleWidth"];
  onParkingAdaAisleWidthChange: RoadwayWorkbenchPanelProps["onParkingAdaAisleWidthChange"];
  parkingCompactWidth: RoadwayWorkbenchPanelProps["parkingCompactWidth"];
  onParkingCompactWidthChange: RoadwayWorkbenchPanelProps["onParkingCompactWidthChange"];
  activeRoadwayWorkbenchTab: RoadwayWorkbenchPanelProps["activeRoadwayWorkbenchTab"];
  onRoadwayWorkbenchTabChange: RoadwayWorkbenchPanelProps["onRoadwayWorkbenchTabChange"];
  hasBackendResult: boolean;
};

export function useDashboardGenerationPanelProps({
  missingSite,
  busy,
  activeJobStatus,
  approvalState,
  approvalCheckpointLabel,
  approvalError,
  statusMessage,
  assistedEnabled,
  pendingPlacementCount,
  pendingPlacementLabels,
  currentUserLayoutContext,
  autoSiteContextFlowSummary,
  systemReadinessRows,
  issues,
  generateFlowSummary,
  reactiveValidation,
  reactiveAffectedRunTarget,
  onAssistedEnabledChange,
  onStatusMessageChange,
  onGenerateFlowSummaryChange,
  onGenerateSystem,
  onContinueActiveJob,
  drainageIssueApplyLabel,
  canApplyDrainageIssue,
  getIssueGuidance,
  onApplyDrainageIssue,
  formatStageLabel,
  hasTerrainSource,
  hasGradingSurface,
  siteTooLargeForGrading,
  systemStatuses,
  useSurveyForGrading,
  onUseSurveyForGradingChange,
  minSlopePct,
  maxParkingSlopePct,
  maxRoadGradePct,
  maxAdaCrossSlopePct,
  onMinSlopePctChange,
  onMaxParkingSlopePctChange,
  onMaxRoadGradePctChange,
  onMaxAdaCrossSlopePctChange,
  drainageAllowSlopeAdjust,
  onDrainageAllowSlopeAdjustChange,
  gradingEarthworkUx,
  onOpenPanel,
  hasBasinPlaced,
  hasHardSystemBlock,
  drainageSourceOverride,
  onDrainageSourceOverrideChange,
  drainageConnectOrphans,
  onDrainageConnectOrphansChange,
  drainageMaxSlopeAdjust,
  onDrainageMaxSlopeAdjustChange,
  onAddObject,
  drainage,
  utilities,
  pipeMinSlopePct,
  onUtilitiesChange,
  onPipeMinSlopePctChange,
  buildingPlacements,
  confirmedBuildingCount,
  waterFireFlowReview,
  roads,
  stormHydrologyReview,
  systemReadinessPanelKey,
  siteScaleLocked,
  activeCivil3DWorkflowTab,
  onCivil3DWorkflowTabChange,
  roadwayWorkbenchData,
  sourceConfidenceRows,
  civil3DWorkflowBlockers,
  gradingSourceSummary,
  hasVerifiedSurveyControl,
  onShowProfileControls,
  parkingAngle,
  onParkingAngleChange,
  onRoadsChange,
  parkingLoading,
  onParkingLoadingChange,
  parkingStallWidth,
  onParkingStallWidthChange,
  parkingAisleWidth,
  onParkingAisleWidthChange,
  parkingStallDepth,
  onParkingStallDepthChange,
  parkingAdaCount,
  onParkingAdaCountChange,
  parkingCompactCount,
  onParkingCompactCountChange,
  parkingAdaAisleWidth,
  onParkingAdaAisleWidthChange,
  parkingCompactWidth,
  onParkingCompactWidthChange,
  activeRoadwayWorkbenchTab,
  onRoadwayWorkbenchTabChange,
  hasBackendResult,
}: UseDashboardGenerationPanelPropsInput) {
  const generatePanelProps = useMemo<GeneratePanelProps>(() => ({
    missingSite,
    busy,
    activeJobStatus,
    approvalState,
    approvalCheckpointLabel,
    approvalError,
    statusMessage,
    assistedEnabled,
    pendingPlacementCount,
    pendingPlacementLabels,
    currentUserLayoutContext,
    autoSiteContextFlowSummary,
    systemReadinessRows,
    issues,
    generateFlowSummary,
    reactiveValidation,
    reactiveAffectedRunTarget,
    onAssistedEnabledChange,
    onStatusMessageChange,
    onGenerateFlowSummaryChange: (summary) => onGenerateFlowSummaryChange(summary),
    onGenerateSystem: (target) => void onGenerateSystem(target),
    onContinueActiveJob: () => void onContinueActiveJob(),
    drainageIssueApplyLabel,
    canApplyDrainageIssue,
    getIssueGuidance,
    onApplyDrainageIssue,
    formatStageLabel,
  }), [
    assistedEnabled,
    autoSiteContextFlowSummary,
    busy,
    canApplyDrainageIssue,
    currentUserLayoutContext,
    drainageIssueApplyLabel,
    formatStageLabel,
    generateFlowSummary,
    getIssueGuidance,
    activeJobStatus,
    approvalCheckpointLabel,
    approvalError,
    approvalState,
    issues,
    missingSite,
    onApplyDrainageIssue,
    onAssistedEnabledChange,
    onGenerateFlowSummaryChange,
    onGenerateSystem,
    onContinueActiveJob,
    onStatusMessageChange,
    pendingPlacementCount,
    pendingPlacementLabels,
    reactiveAffectedRunTarget,
    reactiveValidation,
    statusMessage,
    systemReadinessRows,
  ]);

  const gradingWorkbenchPanelProps = useMemo<GradingWorkbenchPanelProps>(() => ({
    hasTerrainSource,
    hasGradingSurface,
    siteTooLargeForGrading,
    gradingStatus: systemStatuses.grading,
    useSurveyForGrading,
    onUseSurveyForGradingChange,
    minSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    maxAdaCrossSlopePct,
    onMinSlopePctChange,
    onMaxParkingSlopePctChange,
    onMaxRoadGradePctChange,
    onMaxAdaCrossSlopePctChange,
    drainageAllowSlopeAdjust,
    onDrainageAllowSlopeAdjustChange,
    gradingEarthworkUx,
    missingSite,
    onOpenAnalysis: () => onOpenPanel("analysis"),
    onGenerateGrading: () => void onGenerateSystem("grading"),
  }), [
    drainageAllowSlopeAdjust,
    gradingEarthworkUx,
    hasGradingSurface,
    hasTerrainSource,
    maxAdaCrossSlopePct,
    maxParkingSlopePct,
    maxRoadGradePct,
    minSlopePct,
    missingSite,
    onDrainageAllowSlopeAdjustChange,
    onGenerateSystem,
    onMaxAdaCrossSlopePctChange,
    onMaxParkingSlopePctChange,
    onMaxRoadGradePctChange,
    onMinSlopePctChange,
    onOpenPanel,
    onUseSurveyForGradingChange,
    siteTooLargeForGrading,
    systemStatuses.grading,
    useSurveyForGrading,
  ]);

  const drainageWorkbenchPanelProps = useMemo<DrainageWorkbenchPanelProps>(() => ({
    hasBasinPlaced,
    hasTerrainSource,
    hasHardSystemBlock,
    drainageStatus: systemStatuses.drainage,
    drainageSourceOverride,
    onDrainageSourceOverrideChange,
    drainageConnectOrphans,
    onDrainageConnectOrphansChange,
    drainageAllowSlopeAdjust,
    onDrainageAllowSlopeAdjustChange,
    drainageMaxSlopeAdjust,
    onDrainageMaxSlopeAdjustChange,
    missingSite,
    onAddObject,
    onGenerateDrainage: () => void onGenerateSystem("drainage"),
  }), [
    drainageAllowSlopeAdjust,
    drainageConnectOrphans,
    drainageMaxSlopeAdjust,
    drainageSourceOverride,
    hasBasinPlaced,
    hasHardSystemBlock,
    hasTerrainSource,
    missingSite,
    onAddObject,
    onDrainageAllowSlopeAdjustChange,
    onDrainageConnectOrphansChange,
    onDrainageMaxSlopeAdjustChange,
    onDrainageSourceOverrideChange,
    onGenerateSystem,
    systemStatuses.drainage,
  ]);

  const utilitiesWorkbenchPanelProps = useMemo<UtilitiesWorkbenchPanelProps>(() => ({
    hasHardSystemBlock,
    utilitiesStatus: systemStatuses.utilities,
    drainageEnabled: drainage,
    utilitiesEnabled: utilities,
    pipeMinSlopePct,
    onUtilitiesChange,
    onPipeMinSlopePctChange,
    onOpenSanitary: () => onOpenPanel("sanitary"),
    onOpenWater: () => onOpenPanel("water"),
    onAddObject,
    onGenerateUtilities: () => void onGenerateSystem("utilities"),
  }), [
    drainage,
    hasHardSystemBlock,
    onAddObject,
    onGenerateSystem,
    onOpenPanel,
    onPipeMinSlopePctChange,
    onUtilitiesChange,
    pipeMinSlopePct,
    systemStatuses.utilities,
    utilities,
  ]);

  const sanitaryWorkbenchPanelProps = useMemo<SanitaryWorkbenchPanelProps>(() => ({
    hasHardSystemBlock,
    utilitiesStatus: systemStatuses.utilities,
    utilitiesEnabled: utilities,
    pipeMinSlopePct,
    buildingCoverageLabel: buildingPlacements.length ? `${confirmedBuildingCount} buildings` : "No buildings",
    onUtilitiesChange,
    onPipeMinSlopePctChange,
    onAddObject,
    onGenerateUtilities: () => void onGenerateSystem("utilities"),
  }), [
    buildingPlacements.length,
    confirmedBuildingCount,
    hasHardSystemBlock,
    onAddObject,
    onGenerateSystem,
    onPipeMinSlopePctChange,
    onUtilitiesChange,
    pipeMinSlopePct,
    systemStatuses.utilities,
    utilities,
  ]);

  const waterFireFlowWorkbenchPanelProps = useMemo<WaterFireFlowWorkbenchPanelProps>(() => ({
    hasHardSystemBlock,
    systemUtilitiesStatus: systemStatuses.utilities,
    waterFireFlowReview,
    buildingPlacements,
    utilities,
    onUtilitiesChange,
    onAddObject,
    onGenerateUtilities: () => void onGenerateSystem("utilities"),
  }), [
    buildingPlacements,
    hasHardSystemBlock,
    onAddObject,
    onGenerateSystem,
    onUtilitiesChange,
    systemStatuses.utilities,
    utilities,
    waterFireFlowReview,
  ]);

  const systemReadinessPanelProps = useMemo<SystemReadinessPanelProps>(() => ({
    sidePanelForRender: systemReadinessPanelKey,
    siteTooLargeForGrading,
    systemStatuses,
    siteScaleLocked,
    hasTerrainSource,
    hasBasinPlaced,
    hasHardSystemBlock,
    buildingPlacements,
    utilities,
    pipeMinSlopePct,
    roads,
    maxRoadGradePct,
    stormHydrologyReview,
    onOpenPanel,
  }), [
    buildingPlacements,
    hasBasinPlaced,
    hasHardSystemBlock,
    hasTerrainSource,
    maxRoadGradePct,
    onOpenPanel,
    pipeMinSlopePct,
    roads,
    siteScaleLocked,
    siteTooLargeForGrading,
    stormHydrologyReview,
    systemReadinessPanelKey,
    systemStatuses,
    utilities,
  ]);

  const roadwayWorkbenchPanelProps = useMemo<RoadwayWorkbenchPanelProps>(() => ({
    activeCivil3DWorkflowTab,
    onCivil3DWorkflowTabChange,
    roadwayWorkbenchData,
    gradingEarthworkUx,
    sourceConfidenceRows,
    civil3DWorkflowBlockers,
    gradingSourceSummary,
    hasTerrainSource,
    hasVerifiedSurveyControl,
    onShowProfileControls,
    roadsStatus: systemStatuses.roads,
    parkingStatus: systemStatuses.parking,
    maxRoadGradePct,
    onMaxRoadGradePctChange,
    parkingAngle,
    onParkingAngleChange,
    roads,
    onRoadsChange,
    parkingLoading,
    onParkingLoadingChange,
    parkingStallWidth,
    onParkingStallWidthChange,
    parkingAisleWidth,
    onParkingAisleWidthChange,
    parkingStallDepth,
    onParkingStallDepthChange,
    parkingAdaCount,
    onParkingAdaCountChange,
    parkingCompactCount,
    onParkingCompactCountChange,
    parkingAdaAisleWidth,
    onParkingAdaAisleWidthChange,
    parkingCompactWidth,
    onParkingCompactWidthChange,
    activeRoadwayWorkbenchTab,
    onRoadwayWorkbenchTabChange,
    maxAdaCrossSlopePct,
    onMaxAdaCrossSlopePctChange,
    onAddObject,
    onGenerateSystem,
  }), [
    activeCivil3DWorkflowTab,
    activeRoadwayWorkbenchTab,
    civil3DWorkflowBlockers,
    gradingEarthworkUx,
    gradingSourceSummary,
    hasTerrainSource,
    hasVerifiedSurveyControl,
    maxAdaCrossSlopePct,
    maxRoadGradePct,
    onAddObject,
    onCivil3DWorkflowTabChange,
    onGenerateSystem,
    onMaxAdaCrossSlopePctChange,
    onMaxRoadGradePctChange,
    onParkingAdaAisleWidthChange,
    onParkingAdaCountChange,
    onParkingAisleWidthChange,
    onParkingAngleChange,
    onParkingCompactCountChange,
    onParkingCompactWidthChange,
    onParkingLoadingChange,
    onParkingStallDepthChange,
    onParkingStallWidthChange,
    onRoadsChange,
    onRoadwayWorkbenchTabChange,
    onShowProfileControls,
    parkingAdaAisleWidth,
    parkingAdaCount,
    parkingAisleWidth,
    parkingAngle,
    parkingCompactCount,
    parkingCompactWidth,
    parkingLoading,
    parkingStallDepth,
    parkingStallWidth,
    roadwayWorkbenchData,
    roads,
    sourceConfidenceRows,
    systemStatuses.parking,
    systemStatuses.roads,
  ]);

  const landscapeWorkbenchPanelProps = useMemo<LandscapeWorkbenchPanelProps>(() => ({
    buildingPlacements,
    hasBackendResult,
    onAddObject,
  }), [buildingPlacements, hasBackendResult, onAddObject]);

  return {
    drainageWorkbenchPanelProps,
    generatePanelProps,
    gradingWorkbenchPanelProps,
    landscapeWorkbenchPanelProps,
    roadwayWorkbenchPanelProps,
    sanitaryWorkbenchPanelProps,
    systemReadinessPanelProps,
    utilitiesWorkbenchPanelProps,
    waterFireFlowWorkbenchPanelProps,
  };
}
