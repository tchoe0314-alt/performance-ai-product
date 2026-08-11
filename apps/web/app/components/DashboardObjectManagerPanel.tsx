import type { Dispatch, SetStateAction } from "react";
import type { BuildingPlacement, SiteObjectType } from "../types";
import { getObjectDimensionsLabel, getObjectDisplayType, getObjectEditBlocker } from "../utils/objectGeometry";
import type { ObjectManagerLayoutAction } from "../utils/dashboardObjectManagerTrace";
import type { CadToolRequestForPreview, DraftBlockDefinition, RecentChange } from "../utils/dashboardTypes";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import { ObjectManagerPanel, type ObjectManagerPanelProps } from "./ObjectManagerPanel";

type ObjectManagerTransform = "rotate" | "flip_horizontal" | "flip_vertical";

type DashboardObjectManagerPanelProps = {
  cadToolGroups: ObjectManagerPanelProps["cadTools"]["groups"];
  triggerCadTool: (tool: CadToolRequestForPreview["tool"], label: string) => void;
  pendingPlacementObjects: BuildingPlacement[];
  handleSelectPlacementTarget: (id: string) => void;
  selectedBuilding: BuildingPlacement | null;
  handleObjectManagerSelect: (id: string) => void;
  handleObjectManagerClearSelection: () => void;
  setFocusObjectId: Dispatch<SetStateAction<string | null>>;
  onCloseSidePanel: () => void;
  handleObjectManagerCopy: (item: BuildingPlacement) => void;
  handleObjectManagerTransform: (item: BuildingPlacement, transform: ObjectManagerTransform) => void;
  handleObjectManagerDelete: (item: BuildingPlacement) => void;
  buildingPlacements: BuildingPlacement[];
  placedObjects: BuildingPlacement[];
  pendingPlacementCount: number;
  selectedObjectIds: string[];
  hiddenObjectCount: number;
  objectManagerTypes: SiteObjectType[];
  objectClipboard: BuildingPlacement[];
  handleObjectManagerSelectVisibleDraft: () => void;
  handleObjectManagerInvertSelection: () => void;
  handleObjectManagerPaste: () => void;
  handleUpdateBuilding: (id: string, updates: Partial<BuildingPlacement>) => void;
  recordRecentChange: (change: Omit<RecentChange, "id" | "createdAt">) => void;
  pushRecoveryMessage: (message: string) => void;
  objectManagerLayerRows: ObjectManagerPanelProps["layerControls"]["rows"];
  handleObjectManagerLayerSelect: (layerType: SiteObjectType) => void;
  handleObjectManagerLayerIsolate: (layerType: SiteObjectType) => void;
  handleObjectManagerLayerVisibility: (layerType: SiteObjectType, hidden: boolean) => void;
  handleObjectManagerLayerLock: (layerType: SiteObjectType, locked: boolean) => void;
  objectManagerStatusMessage: string;
  recentChanges: RecentChange[];
  handleUndoRecentChange: (change: RecentChange) => void;
  recentChangesOpen: boolean;
  lastDraftAction: unknown;
  redoDraftAction: unknown;
  setRecentChangesOpen: Dispatch<SetStateAction<boolean>>;
  handleUndoDraftAction: () => void;
  handleRedoDraftAction: () => void;
  selectedObjectRows: unknown[];
  selectedObjectMeasurementSummary: NonNullable<ObjectManagerPanelProps["selectedTools"]>["measurementSummary"];
  selectedObjectMeasurements: NonNullable<ObjectManagerPanelProps["selectedTools"]>["measurements"];
  arrayRows: string;
  arrayColumns: string;
  arraySpacingX: string;
  arraySpacingY: string;
  bulkMoveX: string;
  bulkMoveY: string;
  bulkMoveToX: string;
  bulkMoveToY: string;
  bulkScaleFactor: string;
  bulkRotateAngle: string;
  combineObjectName: string;
  combineObjectType: SiteObjectType;
  draftBlockName: string;
  draftBlockLibrary: DraftBlockDefinition[];
  handleObjectManagerBulkVisibility: (hidden: boolean) => void;
  handleObjectManagerIsolateSelected: () => void;
  handleObjectManagerBulkLock: (locked: boolean) => void;
  handleObjectManagerBulkColor: (color: string) => void;
  handleObjectManagerBulkType: (nextType: SiteObjectType) => void;
  handleObjectManagerBulkDuplicate: () => void;
  handleObjectManagerBulkLayout: (layout: ObjectManagerLayoutAction) => void;
  handleObjectManagerBulkDelete: () => void;
  setArrayRows: Dispatch<SetStateAction<string>>;
  setArrayColumns: Dispatch<SetStateAction<string>>;
  setArraySpacingX: Dispatch<SetStateAction<string>>;
  setArraySpacingY: Dispatch<SetStateAction<string>>;
  handleObjectManagerArraySelected: () => void;
  setBulkMoveX: Dispatch<SetStateAction<string>>;
  setBulkMoveY: Dispatch<SetStateAction<string>>;
  handleObjectManagerBulkMove: () => void;
  handleObjectManagerBulkCopyByOffset: () => void;
  setBulkMoveToX: Dispatch<SetStateAction<string>>;
  setBulkMoveToY: Dispatch<SetStateAction<string>>;
  handleObjectManagerBulkMoveTo: () => void;
  setBulkScaleFactor: Dispatch<SetStateAction<string>>;
  handleObjectManagerBulkScale: () => void;
  setBulkRotateAngle: Dispatch<SetStateAction<string>>;
  handleObjectManagerBulkRotate: () => void;
  handleObjectManagerBulkMirror: (axis: "x" | "y") => void;
  setCombineObjectName: Dispatch<SetStateAction<string>>;
  setCombineObjectType: Dispatch<SetStateAction<SiteObjectType>>;
  handleObjectManagerCombineSelected: () => void;
  setDraftBlockName: Dispatch<SetStateAction<string>>;
  handleObjectManagerSaveBlock: () => void;
  handleObjectManagerRenameBlock: (definition: DraftBlockDefinition, rawName: string) => void;
  handleObjectManagerUpdateBlock: (definition: DraftBlockDefinition) => void;
  handleObjectManagerInsertBlock: (definition: DraftBlockDefinition) => void;
  handleObjectManagerDeleteBlock: (definition: DraftBlockDefinition) => void;
  units: string;
  activePlacementId: string | null;
  selectedObjectSet: Set<string>;
  sourceConfidenceByObjectId: ObjectManagerPanelProps["objectList"]["sourceConfidenceByObjectId"];
  objectOutlineColor: string;
  handleObjectManagerToggleMultiSelect: (id: string, checked: boolean) => void;
  reportObjectActionBlocker: (message: string) => void;
  handleToggleBuildingLock: (id: string) => void;
  handleOpenDetailsPanel: () => void;
  handleObjectManagerExplodeCombined: (item: BuildingPlacement) => void;
};

export function DashboardObjectManagerPanel({
  cadToolGroups,
  triggerCadTool,
  pendingPlacementObjects,
  handleSelectPlacementTarget,
  selectedBuilding,
  handleObjectManagerSelect,
  handleObjectManagerClearSelection,
  setFocusObjectId,
  onCloseSidePanel,
  handleObjectManagerCopy,
  handleObjectManagerTransform,
  handleObjectManagerDelete,
  buildingPlacements,
  placedObjects,
  pendingPlacementCount,
  selectedObjectIds,
  hiddenObjectCount,
  objectManagerTypes,
  objectClipboard,
  handleObjectManagerSelectVisibleDraft,
  handleObjectManagerInvertSelection,
  handleObjectManagerPaste,
  handleUpdateBuilding,
  recordRecentChange,
  pushRecoveryMessage,
  objectManagerLayerRows,
  handleObjectManagerLayerSelect,
  handleObjectManagerLayerIsolate,
  handleObjectManagerLayerVisibility,
  handleObjectManagerLayerLock,
  objectManagerStatusMessage,
  recentChanges,
  handleUndoRecentChange,
  recentChangesOpen,
  lastDraftAction,
  redoDraftAction,
  setRecentChangesOpen,
  handleUndoDraftAction,
  handleRedoDraftAction,
  selectedObjectRows,
  selectedObjectMeasurementSummary,
  selectedObjectMeasurements,
  arrayRows,
  arrayColumns,
  arraySpacingX,
  arraySpacingY,
  bulkMoveX,
  bulkMoveY,
  bulkMoveToX,
  bulkMoveToY,
  bulkScaleFactor,
  bulkRotateAngle,
  combineObjectName,
  combineObjectType,
  draftBlockName,
  draftBlockLibrary,
  handleObjectManagerBulkVisibility,
  handleObjectManagerIsolateSelected,
  handleObjectManagerBulkLock,
  handleObjectManagerBulkColor,
  handleObjectManagerBulkType,
  handleObjectManagerBulkDuplicate,
  handleObjectManagerBulkLayout,
  handleObjectManagerBulkDelete,
  setArrayRows,
  setArrayColumns,
  setArraySpacingX,
  setArraySpacingY,
  handleObjectManagerArraySelected,
  setBulkMoveX,
  setBulkMoveY,
  handleObjectManagerBulkMove,
  handleObjectManagerBulkCopyByOffset,
  setBulkMoveToX,
  setBulkMoveToY,
  handleObjectManagerBulkMoveTo,
  setBulkScaleFactor,
  handleObjectManagerBulkScale,
  setBulkRotateAngle,
  handleObjectManagerBulkRotate,
  handleObjectManagerBulkMirror,
  setCombineObjectName,
  setCombineObjectType,
  handleObjectManagerCombineSelected,
  setDraftBlockName,
  handleObjectManagerSaveBlock,
  handleObjectManagerRenameBlock,
  handleObjectManagerUpdateBlock,
  handleObjectManagerInsertBlock,
  handleObjectManagerDeleteBlock,
  units,
  activePlacementId,
  selectedObjectSet,
  sourceConfidenceByObjectId,
  objectOutlineColor,
  handleObjectManagerToggleMultiSelect,
  reportObjectActionBlocker,
  handleToggleBuildingLock,
  handleOpenDetailsPanel,
  handleObjectManagerExplodeCombined,
}: DashboardObjectManagerPanelProps) {
  const objectTypeOptions = Object.entries(SITE_OBJECT_CATALOG)
    .filter(([type]) => type !== "site")
    .map(([type, catalog]) => ({ type: type as SiteObjectType, label: catalog.label }));

  return (
    <ObjectManagerPanel
      cadTools={{ groups: cadToolGroups, onSelectTool: triggerCadTool }}
      needsPlacement={{
        items: pendingPlacementObjects.map((item) => ({
          id: item.id,
          label: item.label,
          typeLabel: SITE_OBJECT_CATALOG[item.type ?? "custom"]?.label ?? "Object",
          widthFt: item.w,
          depthFt: item.d,
        })),
        onPlace: handleSelectPlacementTarget,
      }}
      selectedObject={{
        selectedObject: selectedBuilding,
        displayType: selectedBuilding ? getObjectDisplayType(selectedBuilding) : "",
        dimensionsLabel: selectedBuilding ? getObjectDimensionsLabel(selectedBuilding) : "",
        objectTypeOptions,
        objectOutlineColor,
        onClearSelection: handleObjectManagerClearSelection,
        onRename: (item, value) => {
          const blocker = getObjectEditBlocker(item, "rename");
          if (blocker) {
            reportObjectActionBlocker(blocker);
            return;
          }
          handleUpdateBuilding(item.id, { label: value });
        },
        onColor: (item, value) => {
          const blocker = getObjectEditBlocker(item, "style");
          if (blocker) {
            reportObjectActionBlocker(blocker);
            return;
          }
          handleUpdateBuilding(item.id, {
            meta: {
              ...(item.meta ?? {}),
              ui_color: value,
            },
          });
        },
        onType: (item, nextType) => {
          const blocker = getObjectEditBlocker(item, "type");
          if (blocker) {
            reportObjectActionBlocker(blocker);
            return;
          }
          handleUpdateBuilding(item.id, {
            type: nextType,
            use: SITE_OBJECT_CATALOG[nextType]?.use ?? item.use,
            meta: {
              ...(item.meta ?? {}),
              category: SITE_OBJECT_CATALOG[nextType]?.category ?? "advanced",
            },
          });
        },
        onHeight: (item, heightFt) => {
          const blocker = getObjectEditBlocker(item, "resize");
          if (blocker) {
            reportObjectActionBlocker(blocker);
            return;
          }
          handleUpdateBuilding(item.id, { h: Math.max(1, Math.min(heightFt, 500)) });
        },
        onRoofProfile: (item, profile) => {
          const blocker = getObjectEditBlocker(item, "style");
          if (blocker) {
            reportObjectActionBlocker(blocker);
            return;
          }
          handleUpdateBuilding(item.id, {
            meta: {
              ...(item.meta ?? {}),
              roof_profile: profile,
            },
          });
        },
        onToggleVisibility: (item) => {
          const blocker = getObjectEditBlocker(item, "hide");
          if (blocker) {
            reportObjectActionBlocker(blocker);
            return;
          }
          handleUpdateBuilding(item.id, {
            meta: {
              ...(item.meta ?? {}),
              ui_hidden: !Boolean(item.meta?.ui_hidden),
            },
          });
        },
        onMove: (item) => handleSelectPlacementTarget(item.id),
        onFocus: (item) => {
          setFocusObjectId(item.id);
          onCloseSidePanel();
        },
        onCopy: handleObjectManagerCopy,
        onRotate: (item) => handleObjectManagerTransform(item, "rotate"),
        onFlipHorizontal: (item) => handleObjectManagerTransform(item, "flip_horizontal"),
        onDelete: handleObjectManagerDelete,
      }}
      overview={{
        totalCount: buildingPlacements.length,
        placedCount: placedObjects.length,
        pendingCount: pendingPlacementCount,
        selectedCount: selectedObjectIds.length,
        hiddenCount: hiddenObjectCount,
        typeLabels: objectManagerTypes,
        clipboardLabels: objectClipboard.map((item) => item.label),
        onSelectVisibleDraft: handleObjectManagerSelectVisibleDraft,
        onInvertSelection: handleObjectManagerInvertSelection,
        onPaste: handleObjectManagerPaste,
      }}
      hiddenState={{
        hiddenCount: hiddenObjectCount,
        onShowAll: () => {
          const hiddenObjects = buildingPlacements.filter((item) => Boolean(item.meta?.ui_hidden));
          const restorableHiddenObjects = hiddenObjects.filter((item) => !item.meta?.combined_into_object_id);
          const preservedTraceCount = hiddenObjects.length - restorableHiddenObjects.length;
          restorableHiddenObjects.forEach((item) => {
            handleUpdateBuilding(item.id, {
              meta: {
                ...(item.meta ?? {}),
                ui_hidden: false,
              },
            });
          });
          recordRecentChange({
            type: "object_visibility_changed",
            label: "Objects shown",
            detail: preservedTraceCount
              ? `${restorableHiddenObjects.length} hidden object${restorableHiddenObjects.length === 1 ? "" : "s"} shown; ${preservedTraceCount} combined source trace piece${preservedTraceCount === 1 ? "" : "s"} stayed hidden.`
              : "All hidden objects are visible again.",
            undoBlockedReason: "Hide specific objects again from Object Manager if needed.",
          });
          pushRecoveryMessage(preservedTraceCount
            ? `${restorableHiddenObjects.length} hidden object${restorableHiddenObjects.length === 1 ? "" : "s"} shown. ${preservedTraceCount} combined source trace piece${preservedTraceCount === 1 ? "" : "s"} stayed hidden until you explode the combined object.`
            : "All hidden objects are visible again.");
        },
      }}
      layerControls={{
        rows: objectManagerLayerRows,
        onSelectLayer: handleObjectManagerLayerSelect,
        onIsolateLayer: handleObjectManagerLayerIsolate,
        onSetLayerHidden: handleObjectManagerLayerVisibility,
        onSetLayerLocked: handleObjectManagerLayerLock,
      }}
      statusMessage={objectManagerStatusMessage}
      recentChanges={{
        changes: recentChanges.map((change) => ({
          id: change.id,
          label: change.label,
          detail: change.detail,
          createdAt: change.createdAt,
          canUndo: Boolean(change.undo),
          onAction: () => handleUndoRecentChange(change),
        })),
        open: recentChangesOpen,
        canUndoDraft: Boolean(lastDraftAction),
        canRedoDraft: Boolean(redoDraftAction),
        onToggleOpen: () => setRecentChangesOpen((value) => !value),
        onUndoDraft: handleUndoDraftAction,
        onRedoDraft: handleRedoDraftAction,
      }}
      selectedTools={selectedObjectIds.length > 0 ? {
        selectedCount: selectedObjectRows.length,
        measurementSummary: selectedObjectMeasurementSummary,
        measurements: selectedObjectMeasurements,
        arrayRows,
        arrayColumns,
        arraySpacingX,
        arraySpacingY,
        bulkMoveX,
        bulkMoveY,
        bulkMoveToX,
        bulkMoveToY,
        bulkScaleFactor,
        bulkRotateAngle,
        combineObjectName,
        combineObjectType,
        draftBlockName,
        blocks: draftBlockLibrary.map((block) => ({
          id: block.id,
          name: block.name,
          type: block.type,
          objectCount: block.objects.length,
          createdAt: block.createdAt,
          updatedAt: block.updatedAt,
          revision: block.revision,
        })),
        onClearSelection: handleObjectManagerClearSelection,
        onHideSelected: () => handleObjectManagerBulkVisibility(true),
        onShowSelected: () => handleObjectManagerBulkVisibility(false),
        onIsolateSelected: handleObjectManagerIsolateSelected,
        onLockSelected: () => handleObjectManagerBulkLock(true),
        onUnlockSelected: () => handleObjectManagerBulkLock(false),
        onColorSelected: handleObjectManagerBulkColor,
        onTypeSelected: handleObjectManagerBulkType,
        onDuplicateSelected: handleObjectManagerBulkDuplicate,
        onLayoutSelected: handleObjectManagerBulkLayout,
        onDeleteSelected: handleObjectManagerBulkDelete,
        onArrayRowsChange: setArrayRows,
        onArrayColumnsChange: setArrayColumns,
        onArraySpacingXChange: setArraySpacingX,
        onArraySpacingYChange: setArraySpacingY,
        onCreateArray: handleObjectManagerArraySelected,
        onBulkMoveXChange: setBulkMoveX,
        onBulkMoveYChange: setBulkMoveY,
        onMoveSelected: handleObjectManagerBulkMove,
        onCopyByOffset: handleObjectManagerBulkCopyByOffset,
        onBulkMoveToXChange: setBulkMoveToX,
        onBulkMoveToYChange: setBulkMoveToY,
        onMoveToCoordinate: handleObjectManagerBulkMoveTo,
        onBulkScaleFactorChange: setBulkScaleFactor,
        onScaleSelected: handleObjectManagerBulkScale,
        onBulkRotateAngleChange: setBulkRotateAngle,
        onRotateSelected: handleObjectManagerBulkRotate,
        onMirrorSelected: handleObjectManagerBulkMirror,
        onCombineObjectNameChange: setCombineObjectName,
        onCombineObjectTypeChange: setCombineObjectType,
        onCombineSelected: handleObjectManagerCombineSelected,
        onDraftBlockNameChange: setDraftBlockName,
        onSaveBlock: handleObjectManagerSaveBlock,
        onRenameBlock: (blockId, value) => {
          const block = draftBlockLibrary.find((item) => item.id === blockId);
          if (block) handleObjectManagerRenameBlock(block, value);
        },
        onUpdateBlock: (blockId) => {
          const block = draftBlockLibrary.find((item) => item.id === blockId);
          if (block) handleObjectManagerUpdateBlock(block);
        },
        onInsertBlock: (blockId) => {
          const block = draftBlockLibrary.find((item) => item.id === blockId);
          if (block) handleObjectManagerInsertBlock(block);
        },
        onDeleteBlock: (blockId) => {
          const block = draftBlockLibrary.find((item) => item.id === blockId);
          if (block) handleObjectManagerDeleteBlock(block);
        },
      } : null}
      objectList={{
        objects: buildingPlacements,
        units,
        activeObjectId: activePlacementId,
        selectedObjectSet,
        sourceConfidenceByObjectId,
        objectOutlineColor: objectOutlineColor || "#64748b",
        onMove: handleSelectPlacementTarget,
        onSelect: handleObjectManagerSelect,
        onToggleMultiSelect: handleObjectManagerToggleMultiSelect,
        onDelete: handleObjectManagerDelete,
        onUpdate: handleUpdateBuilding,
        onReportBlocker: reportObjectActionBlocker,
        onToggleLock: handleToggleBuildingLock,
        onFocus: (objectId) => {
          setFocusObjectId(objectId);
          onCloseSidePanel();
        },
        onInspect: handleOpenDetailsPanel,
        onCopy: handleObjectManagerCopy,
        onTransform: handleObjectManagerTransform,
        onExplodeCombined: handleObjectManagerExplodeCombined,
      }}
    />
  );
}
