import { useCallback, useMemo } from "react";
import type { MutableRefObject } from "react";

import type { BuildingPlacement, ChatMessage, SiteObjectType } from "../types";
import type {
  DraftBlockDefinition,
  DraftUndoAction,
  RecentChange,
} from "../utils/dashboardTypes";
import type { EngineeringSystemKey } from "../utils/workflowConstants";
import {
  runObjectManagerArraySelected,
  runObjectManagerBulkCopyByOffset,
  runObjectManagerBulkDuplicate,
  runObjectManagerPaste,
} from "../utils/dashboardObjectManagerCopyActions";
import {
  runObjectManagerBulkColor,
  runObjectManagerBulkDelete,
  runObjectManagerBulkLock,
  runObjectManagerBulkType,
  runObjectManagerBulkVisibility,
  runObjectManagerIsolateSelected,
  runObjectManagerLayerIsolate,
  runObjectManagerLayerLock,
  runObjectManagerLayerSelect,
  runObjectManagerLayerVisibility,
} from "../utils/dashboardObjectManagerBulkActions";
import {
  runObjectManagerBulkLayout,
  runObjectManagerBulkMirror,
  runObjectManagerBulkMove,
  runObjectManagerBulkMoveTo,
  runObjectManagerBulkRotate,
  runObjectManagerBulkScale,
  runObjectManagerTransform,
  type ObjectManagerSingleTransform,
} from "../utils/dashboardObjectManagerTransformActions";
import {
  runObjectManagerCombineSelected,
  runObjectManagerDeleteBlock,
  runObjectManagerExplodeCombined,
  runObjectManagerInsertBlock,
  runObjectManagerRenameBlock,
  runObjectManagerSaveBlock,
  runObjectManagerUpdateBlock,
} from "../utils/dashboardObjectManagerBlockActions";
import {
  runObjectVertexAlignToPrevious,
  runObjectVertexCoordinateUpdate,
  runObjectVertexDelete,
  runObjectVertexInsert,
  runObjectVertexSnapToNearestEndpoint,
} from "../utils/dashboardObjectManagerVertexActions";
import {
  runObjectManagerCopy,
  runObjectManagerDelete,
  runObjectManagerInvertSelection,
  runObjectManagerSelect,
  runObjectManagerSelectVisibleDraft,
  runObjectManagerToggleMultiSelect,
} from "../utils/dashboardObjectManagerSelectionActions";
import type { ObjectManagerLayoutAction } from "../utils/dashboardObjectManagerTrace";

type StateSetter<T> = (value: T | ((prev: T) => T)) => void;
type AppendChatMessage = (role: ChatMessage["role"], content: string, kind?: ChatMessage["kind"]) => void;
type RecordRecentChange = (change: Omit<RecentChange, "id" | "createdAt">) => void;
type SystemsImpactedByPlacement = (target?: Partial<BuildingPlacement> | null) => EngineeringSystemKey[];

type UseDashboardObjectManagerActionsOptions = {
  activePlacementId: string | null;
  arrayColumns: string;
  arrayRows: string;
  arraySpacingX: string;
  arraySpacingY: string;
  bulkMoveToX: string;
  bulkMoveToY: string;
  bulkMoveX: string;
  bulkMoveY: string;
  bulkRotateAngle: string;
  bulkScaleFactor: string;
  buildingPlacements: BuildingPlacement[];
  buildingPlacementsRef: MutableRefObject<BuildingPlacement[]>;
  clearGeneratedPreview: () => void;
  combineObjectName: string;
  combineObjectType: SiteObjectType;
  draftBlockLibrary: DraftBlockDefinition[];
  draftBlockName: string;
  handleRemoveBuilding: (id: string) => void;
  handleUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  markSystemsStale: (systems: EngineeringSystemKey[]) => void;
  objectClipboard: BuildingPlacement[];
  persistDraftRefresh: (reason: string) => void;
  recordDraftUndoAction: (action: DraftUndoAction) => void;
  recordRecentChange: RecordRecentChange;
  reportObjectActionBlocker: (message: string) => void;
  selectedObjectIds: string[];
  setActivePlacementId: StateSetter<string | null>;
  setBuildingPlacements: StateSetter<BuildingPlacement[]>;
  setCombineObjectName: StateSetter<string>;
  setCombineObjectType: StateSetter<SiteObjectType>;
  setDraftBlockLibrary: StateSetter<DraftBlockDefinition[]>;
  setDraftBlockName: StateSetter<string>;
  setObjectClipboard: StateSetter<BuildingPlacement[]>;
  setObjectManagerStatusMessage: (message: string) => void;
  setPreviewInteraction: (value: "static" | "edit") => void;
  setSelectedObjectIds: StateSetter<string[]>;
  setStatusMessage: (message: string) => void;
  systemsImpactedByPlacement: SystemsImpactedByPlacement;
  appendChatMessage: AppendChatMessage;
};

export function useDashboardObjectManagerActions({
  activePlacementId,
  arrayColumns,
  arrayRows,
  arraySpacingX,
  arraySpacingY,
  bulkMoveToX,
  bulkMoveToY,
  bulkMoveX,
  bulkMoveY,
  bulkRotateAngle,
  bulkScaleFactor,
  buildingPlacements,
  buildingPlacementsRef,
  clearGeneratedPreview,
  combineObjectName,
  combineObjectType,
  draftBlockLibrary,
  draftBlockName,
  handleRemoveBuilding,
  handleUpdateBuilding,
  markSystemsStale,
  objectClipboard,
  persistDraftRefresh,
  recordDraftUndoAction,
  recordRecentChange,
  reportObjectActionBlocker,
  selectedObjectIds,
  setActivePlacementId,
  setBuildingPlacements,
  setCombineObjectName,
  setCombineObjectType,
  setDraftBlockLibrary,
  setDraftBlockName,
  setObjectClipboard,
  setObjectManagerStatusMessage,
  setPreviewInteraction,
  setSelectedObjectIds,
  setStatusMessage,
  systemsImpactedByPlacement,
  appendChatMessage,
}: UseDashboardObjectManagerActionsOptions) {
  const objectManagerSelectionActions = useMemo(() => ({
    appendStatusMessage: (message: string) => appendChatMessage("assistant", message, "status"),
    handleRemoveBuilding,
    reportObjectActionBlocker,
    setActivePlacementId,
    setObjectClipboard,
    setObjectManagerStatusMessage,
    setPreviewInteraction,
    setSelectedObjectIds,
    setStatusMessage,
  }), [
    appendChatMessage,
    handleRemoveBuilding,
    reportObjectActionBlocker,
    setActivePlacementId,
    setObjectClipboard,
    setObjectManagerStatusMessage,
    setPreviewInteraction,
    setSelectedObjectIds,
    setStatusMessage,
  ]);

  const objectManagerVertexActions = useMemo(() => ({
    handleUpdateBuilding,
    reportObjectActionBlocker,
    setObjectManagerStatusMessage,
    setStatusMessage,
  }), [handleUpdateBuilding, reportObjectActionBlocker, setObjectManagerStatusMessage, setStatusMessage]);

  const handleUpdateObjectVertex = useCallback((
    item: BuildingPlacement,
    vertexIndex: number,
    axis: "x" | "y",
    rawValue: string,
  ) => {
    runObjectVertexCoordinateUpdate({
      item,
      vertexIndex,
      axis,
      rawValue,
      buildingPlacements,
      actions: objectManagerVertexActions,
    });
  }, [buildingPlacements, objectManagerVertexActions]);

  const handleInsertObjectVertex = useCallback((item: BuildingPlacement, vertexIndex: number) => {
    runObjectVertexInsert({
      item,
      vertexIndex,
      actions: objectManagerVertexActions,
    });
  }, [objectManagerVertexActions]);

  const handleDeleteObjectVertex = useCallback((item: BuildingPlacement, vertexIndex: number) => {
    runObjectVertexDelete({
      item,
      vertexIndex,
      actions: objectManagerVertexActions,
    });
  }, [objectManagerVertexActions]);

  const handleSnapObjectVertexToNearestEndpoint = useCallback((item: BuildingPlacement, vertexIndex: number) => {
    runObjectVertexSnapToNearestEndpoint({
      item,
      vertexIndex,
      buildingPlacements,
      actions: objectManagerVertexActions,
    });
  }, [buildingPlacements, objectManagerVertexActions]);

  const handleAlignObjectVertexToPrevious = useCallback((
    item: BuildingPlacement,
    vertexIndex: number,
    axis: "x" | "y",
  ) => {
    runObjectVertexAlignToPrevious({
      item,
      vertexIndex,
      axis,
      actions: objectManagerVertexActions,
    });
  }, [objectManagerVertexActions]);

  const handleObjectManagerSelect = useCallback((id: string) => {
    runObjectManagerSelect({ id, actions: objectManagerSelectionActions });
  }, [objectManagerSelectionActions]);

  const handleObjectManagerToggleMultiSelect = useCallback((id: string, checked: boolean) => {
    runObjectManagerToggleMultiSelect({ id, checked, actions: objectManagerSelectionActions });
  }, [objectManagerSelectionActions]);

  const handleObjectManagerSelectVisibleDraft = useCallback(() => {
    runObjectManagerSelectVisibleDraft({ buildingPlacements, actions: objectManagerSelectionActions });
  }, [buildingPlacements, objectManagerSelectionActions]);

  const handleObjectManagerInvertSelection = useCallback(() => {
    runObjectManagerInvertSelection({
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerSelectionActions,
    });
  }, [buildingPlacements, objectManagerSelectionActions, selectedObjectIds]);

  const handleObjectManagerDelete = useCallback((item: BuildingPlacement) => {
    runObjectManagerDelete({ item, actions: objectManagerSelectionActions });
  }, [objectManagerSelectionActions]);

  const handleObjectManagerCopy = useCallback((item: BuildingPlacement) => {
    runObjectManagerCopy({ item, actions: objectManagerSelectionActions });
  }, [objectManagerSelectionActions]);

  const objectManagerBulkActions = useMemo(() => ({
    setBuildingPlacements,
    setSelectedObjectIds,
    setActivePlacementId,
    setPreviewInteraction,
    setObjectManagerStatusMessage,
    setStatusMessage,
    appendChatMessage,
    recordRecentChange,
    recordDraftUndoAction,
    markSystemsStale,
    systemsImpactedByPlacement,
    reportObjectActionBlocker,
    handleUpdateBuilding,
    clearGeneratedPreview,
    persistDraftRefresh,
  }), [
    appendChatMessage,
    clearGeneratedPreview,
    handleUpdateBuilding,
    markSystemsStale,
    persistDraftRefresh,
    recordDraftUndoAction,
    recordRecentChange,
    reportObjectActionBlocker,
    setActivePlacementId,
    setBuildingPlacements,
    setObjectManagerStatusMessage,
    setPreviewInteraction,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
  ]);

  const objectManagerBlockActions = useMemo(() => ({
    ...objectManagerBulkActions,
    setCombineObjectName,
    setCombineObjectType,
    setDraftBlockLibrary,
    setDraftBlockName,
  }), [
    objectManagerBulkActions,
    setCombineObjectName,
    setCombineObjectType,
    setDraftBlockLibrary,
    setDraftBlockName,
  ]);

  const handleObjectManagerBulkVisibility = useCallback((hidden: boolean) => {
    runObjectManagerBulkVisibility({
      hidden,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerIsolateSelected = useCallback(() => {
    runObjectManagerIsolateSelected({
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkLock = useCallback((locked: boolean) => {
    runObjectManagerBulkLock({
      locked,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkColor = useCallback((color: string) => {
    runObjectManagerBulkColor({
      color,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkType = useCallback((nextType: SiteObjectType) => {
    runObjectManagerBulkType({
      nextType,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkDelete = useCallback(() => {
    runObjectManagerBulkDelete({
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const objectManagerCopyActions = useMemo(() => ({
    setBuildingPlacements,
    setSelectedObjectIds,
    setActivePlacementId,
    setObjectManagerStatusMessage,
    setStatusMessage,
    appendChatMessage,
    recordRecentChange,
    recordDraftUndoAction,
    markSystemsStale,
    systemsImpactedByPlacement,
    reportObjectActionBlocker,
    clearGeneratedPreview,
    persistDraftRefresh,
  }), [
    appendChatMessage,
    clearGeneratedPreview,
    markSystemsStale,
    persistDraftRefresh,
    recordDraftUndoAction,
    recordRecentChange,
    reportObjectActionBlocker,
    setActivePlacementId,
    setBuildingPlacements,
    setObjectManagerStatusMessage,
    setSelectedObjectIds,
    setStatusMessage,
    systemsImpactedByPlacement,
  ]);

  const handleObjectManagerPaste = useCallback(() => {
    runObjectManagerPaste({
      objectClipboard,
      buildingPlacements,
      actions: objectManagerCopyActions,
    });
  }, [buildingPlacements, objectClipboard, objectManagerCopyActions]);

  const handleObjectManagerTransform = useCallback((item: BuildingPlacement, transform: ObjectManagerSingleTransform) => {
    runObjectManagerTransform({
      item,
      transform,
      actions: objectManagerBulkActions,
    });
  }, [objectManagerBulkActions]);

  const handleObjectManagerBulkDuplicate = useCallback(() => {
    runObjectManagerBulkDuplicate({
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerCopyActions,
    });
  }, [buildingPlacements, objectManagerCopyActions, selectedObjectIds]);

  const handleObjectManagerBulkCopyByOffset = useCallback(() => {
    runObjectManagerBulkCopyByOffset({
      buildingPlacements,
      selectedObjectIds,
      bulkMoveX,
      bulkMoveY,
      actions: objectManagerCopyActions,
    });
  }, [buildingPlacements, bulkMoveX, bulkMoveY, objectManagerCopyActions, selectedObjectIds]);

  const handleObjectManagerArraySelected = useCallback(() => {
    runObjectManagerArraySelected({
      buildingPlacements,
      selectedObjectIds,
      arrayRows,
      arrayColumns,
      arraySpacingX,
      arraySpacingY,
      actions: objectManagerCopyActions,
    });
  }, [arrayColumns, arrayRows, arraySpacingX, arraySpacingY, buildingPlacements, objectManagerCopyActions, selectedObjectIds]);

  const handleObjectManagerBulkLayout = useCallback((layout: ObjectManagerLayoutAction) => {
    runObjectManagerBulkLayout({
      layout,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkMove = useCallback(() => {
    runObjectManagerBulkMove({
      bulkMoveX,
      bulkMoveY,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, bulkMoveX, bulkMoveY, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkMoveTo = useCallback(() => {
    runObjectManagerBulkMoveTo({
      bulkMoveToX,
      bulkMoveToY,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, bulkMoveToX, bulkMoveToY, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkScale = useCallback(() => {
    runObjectManagerBulkScale({
      bulkScaleFactor,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, bulkScaleFactor, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkRotate = useCallback(() => {
    runObjectManagerBulkRotate({
      bulkRotateAngle,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, bulkRotateAngle, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerBulkMirror = useCallback((axis: "x" | "y") => {
    runObjectManagerBulkMirror({
      axis,
      buildingPlacements,
      selectedObjectIds,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions, selectedObjectIds]);

  const handleObjectManagerLayerVisibility = useCallback((layerType: SiteObjectType, hidden: boolean) => {
    runObjectManagerLayerVisibility({
      layerType,
      hidden,
      buildingPlacements,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions]);

  const handleObjectManagerLayerLock = useCallback((layerType: SiteObjectType, locked: boolean) => {
    runObjectManagerLayerLock({
      layerType,
      locked,
      buildingPlacements,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions]);

  const handleObjectManagerLayerSelect = useCallback((layerType: SiteObjectType) => {
    runObjectManagerLayerSelect({
      layerType,
      buildingPlacements,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions]);

  const handleObjectManagerLayerIsolate = useCallback((layerType: SiteObjectType) => {
    runObjectManagerLayerIsolate({
      layerType,
      buildingPlacements,
      actions: objectManagerBulkActions,
    });
  }, [buildingPlacements, objectManagerBulkActions]);

  const handleObjectManagerCombineSelected = useCallback(() => {
    runObjectManagerCombineSelected({
      buildingPlacements,
      buildingPlacementsRef,
      selectedObjectIds,
      combineObjectName,
      combineObjectType,
      actions: objectManagerBlockActions,
    });
  }, [buildingPlacements, buildingPlacementsRef, combineObjectName, combineObjectType, objectManagerBlockActions, selectedObjectIds]);

  const handleObjectManagerSaveBlock = useCallback(() => {
    runObjectManagerSaveBlock({
      buildingPlacements,
      selectedObjectIds,
      draftBlockName,
      combineObjectType,
      actions: objectManagerBlockActions,
    });
  }, [buildingPlacements, combineObjectType, draftBlockName, objectManagerBlockActions, selectedObjectIds]);

  const handleObjectManagerInsertBlock = useCallback((definition: DraftBlockDefinition) => {
    runObjectManagerInsertBlock({
      definition,
      buildingPlacements,
      actions: objectManagerBlockActions,
    });
  }, [buildingPlacements, objectManagerBlockActions]);

  const handleObjectManagerUpdateBlock = useCallback((definition: DraftBlockDefinition) => {
    runObjectManagerUpdateBlock({
      definition,
      buildingPlacements,
      selectedObjectIds,
      activePlacementId,
      combineObjectType,
      actions: objectManagerBlockActions,
    });
  }, [activePlacementId, buildingPlacements, combineObjectType, objectManagerBlockActions, selectedObjectIds]);

  const handleObjectManagerRenameBlock = useCallback((definition: DraftBlockDefinition, rawName: string) => {
    runObjectManagerRenameBlock({
      definition,
      rawName,
      draftBlockLibrary,
      actions: objectManagerBlockActions,
    });
  }, [draftBlockLibrary, objectManagerBlockActions]);

  const handleObjectManagerDeleteBlock = useCallback((definition: DraftBlockDefinition) => {
    runObjectManagerDeleteBlock({
      definition,
      draftBlockLibrary,
      actions: objectManagerBlockActions,
    });
  }, [draftBlockLibrary, objectManagerBlockActions]);

  const handleObjectManagerExplodeCombined = useCallback((item: BuildingPlacement) => {
    runObjectManagerExplodeCombined({
      item,
      buildingPlacements,
      actions: objectManagerBlockActions,
    });
  }, [buildingPlacements, objectManagerBlockActions]);

  return {
    handleAlignObjectVertexToPrevious,
    handleDeleteObjectVertex,
    handleInsertObjectVertex,
    handleObjectManagerArraySelected,
    handleObjectManagerBulkColor,
    handleObjectManagerBulkCopyByOffset,
    handleObjectManagerBulkDelete,
    handleObjectManagerBulkDuplicate,
    handleObjectManagerBulkLayout,
    handleObjectManagerBulkLock,
    handleObjectManagerBulkMirror,
    handleObjectManagerBulkMove,
    handleObjectManagerBulkMoveTo,
    handleObjectManagerBulkRotate,
    handleObjectManagerBulkScale,
    handleObjectManagerBulkType,
    handleObjectManagerBulkVisibility,
    handleObjectManagerCombineSelected,
    handleObjectManagerCopy,
    handleObjectManagerDelete,
    handleObjectManagerDeleteBlock,
    handleObjectManagerExplodeCombined,
    handleObjectManagerInsertBlock,
    handleObjectManagerInvertSelection,
    handleObjectManagerIsolateSelected,
    handleObjectManagerLayerIsolate,
    handleObjectManagerLayerLock,
    handleObjectManagerLayerSelect,
    handleObjectManagerLayerVisibility,
    handleObjectManagerPaste,
    handleObjectManagerRenameBlock,
    handleObjectManagerSaveBlock,
    handleObjectManagerSelect,
    handleObjectManagerSelectVisibleDraft,
    handleObjectManagerToggleMultiSelect,
    handleObjectManagerTransform,
    handleObjectManagerUpdateBlock,
    handleSnapObjectVertexToNearestEndpoint,
    handleUpdateObjectVertex,
  };
}
