import type { SiteObjectType } from "../types";
import type { ComponentProps } from "react";
import { SITE_OBJECT_CATALOG } from "../utils/siteObjectCatalog";
import { ObjectManagerBulkToolsPanel } from "./ObjectManagerBulkToolsPanel";
import { ObjectManagerCombineBlocksPanel } from "./ObjectManagerCombineBlocksPanel";
import { ObjectManagerMeasurementsPanel } from "./ObjectManagerMeasurementsPanel";

type MeasurementSummary = ComponentProps<typeof ObjectManagerMeasurementsPanel>["summary"];
type MeasurementRow = ComponentProps<typeof ObjectManagerMeasurementsPanel>["measurements"][number];
type BulkLayoutMode = "align_left" | "align_top" | "distribute_x" | "distribute_y";

type DraftBlockSummary = {
  id: string;
  name: string;
  type: SiteObjectType;
  objectCount: number;
  createdAt: number;
  updatedAt?: number;
  revision?: number;
};

export function ObjectManagerSelectedToolsPanel({
  selectedCount,
  measurementSummary,
  measurements,
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
  blocks,
  onClearSelection,
  onHideSelected,
  onShowSelected,
  onIsolateSelected,
  onLockSelected,
  onUnlockSelected,
  onColorSelected,
  onTypeSelected,
  onDuplicateSelected,
  onLayoutSelected,
  onDeleteSelected,
  onArrayRowsChange,
  onArrayColumnsChange,
  onArraySpacingXChange,
  onArraySpacingYChange,
  onCreateArray,
  onBulkMoveXChange,
  onBulkMoveYChange,
  onMoveSelected,
  onCopyByOffset,
  onBulkMoveToXChange,
  onBulkMoveToYChange,
  onMoveToCoordinate,
  onBulkScaleFactorChange,
  onScaleSelected,
  onBulkRotateAngleChange,
  onRotateSelected,
  onMirrorSelected,
  onCombineObjectNameChange,
  onCombineObjectTypeChange,
  onCombineSelected,
  onDraftBlockNameChange,
  onSaveBlock,
  onRenameBlock,
  onUpdateBlock,
  onInsertBlock,
  onDeleteBlock,
}: {
  selectedCount: number;
  measurementSummary: MeasurementSummary;
  measurements: MeasurementRow[];
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
  blocks: DraftBlockSummary[];
  onClearSelection: () => void;
  onHideSelected: () => void;
  onShowSelected: () => void;
  onIsolateSelected: () => void;
  onLockSelected: () => void;
  onUnlockSelected: () => void;
  onColorSelected: (color: string) => void;
  onTypeSelected: (type: SiteObjectType) => void;
  onDuplicateSelected: () => void;
  onLayoutSelected: (mode: BulkLayoutMode) => void;
  onDeleteSelected: () => void;
  onArrayRowsChange: (value: string) => void;
  onArrayColumnsChange: (value: string) => void;
  onArraySpacingXChange: (value: string) => void;
  onArraySpacingYChange: (value: string) => void;
  onCreateArray: () => void;
  onBulkMoveXChange: (value: string) => void;
  onBulkMoveYChange: (value: string) => void;
  onMoveSelected: () => void;
  onCopyByOffset: () => void;
  onBulkMoveToXChange: (value: string) => void;
  onBulkMoveToYChange: (value: string) => void;
  onMoveToCoordinate: () => void;
  onBulkScaleFactorChange: (value: string) => void;
  onScaleSelected: () => void;
  onBulkRotateAngleChange: (value: string) => void;
  onRotateSelected: () => void;
  onMirrorSelected: (axis: "x" | "y") => void;
  onCombineObjectNameChange: (value: string) => void;
  onCombineObjectTypeChange: (value: SiteObjectType) => void;
  onCombineSelected: () => void;
  onDraftBlockNameChange: (value: string) => void;
  onSaveBlock: () => void;
  onRenameBlock: (blockId: string, value: string) => void;
  onUpdateBlock: (blockId: string) => void;
  onInsertBlock: (blockId: string) => void;
  onDeleteBlock: (blockId: string) => void;
}) {
  const objectTypeOptions = Object.entries(SITE_OBJECT_CATALOG)
    .filter(([type]) => type !== "site")
    .map(([type, catalog]) => ({ type: type as SiteObjectType, label: catalog.label }));

  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3" data-testid="object-manager-multi-select">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold text-slate-700">
          {selectedCount} object{selectedCount === 1 ? "" : "s"} selected
        </p>
        <button
          type="button"
          onClick={onClearSelection}
          className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500 hover:bg-slate-50"
        >
          Clear
        </button>
      </div>
      <ObjectManagerMeasurementsPanel summary={measurementSummary} measurements={measurements} />
      <ObjectManagerBulkToolsPanel
        objectTypeOptions={objectTypeOptions}
        arrayRows={arrayRows}
        arrayColumns={arrayColumns}
        arraySpacingX={arraySpacingX}
        arraySpacingY={arraySpacingY}
        bulkMoveX={bulkMoveX}
        bulkMoveY={bulkMoveY}
        bulkMoveToX={bulkMoveToX}
        bulkMoveToY={bulkMoveToY}
        bulkScaleFactor={bulkScaleFactor}
        bulkRotateAngle={bulkRotateAngle}
        onHideSelected={onHideSelected}
        onShowSelected={onShowSelected}
        onIsolateSelected={onIsolateSelected}
        onLockSelected={onLockSelected}
        onUnlockSelected={onUnlockSelected}
        onColorSelected={onColorSelected}
        onTypeSelected={onTypeSelected}
        onDuplicateSelected={onDuplicateSelected}
        onLayoutSelected={onLayoutSelected}
        onDeleteSelected={onDeleteSelected}
        onArrayRowsChange={onArrayRowsChange}
        onArrayColumnsChange={onArrayColumnsChange}
        onArraySpacingXChange={onArraySpacingXChange}
        onArraySpacingYChange={onArraySpacingYChange}
        onCreateArray={onCreateArray}
        onBulkMoveXChange={onBulkMoveXChange}
        onBulkMoveYChange={onBulkMoveYChange}
        onMoveSelected={onMoveSelected}
        onCopyByOffset={onCopyByOffset}
        onBulkMoveToXChange={onBulkMoveToXChange}
        onBulkMoveToYChange={onBulkMoveToYChange}
        onMoveToCoordinate={onMoveToCoordinate}
        onBulkScaleFactorChange={onBulkScaleFactorChange}
        onScaleSelected={onScaleSelected}
        onBulkRotateAngleChange={onBulkRotateAngleChange}
        onRotateSelected={onRotateSelected}
        onMirrorSelected={onMirrorSelected}
      />
      <ObjectManagerCombineBlocksPanel
        objectTypeOptions={objectTypeOptions}
        combineObjectName={combineObjectName}
        combineObjectType={combineObjectType}
        draftBlockName={draftBlockName}
        blocks={blocks.map((block) => ({
          ...block,
          typeLabel: SITE_OBJECT_CATALOG[block.type]?.label ?? block.type,
        }))}
        onCombineObjectNameChange={onCombineObjectNameChange}
        onCombineObjectTypeChange={onCombineObjectTypeChange}
        onCombineSelected={onCombineSelected}
        onDraftBlockNameChange={onDraftBlockNameChange}
        onSaveBlock={onSaveBlock}
        onRenameBlock={onRenameBlock}
        onUpdateBlock={onUpdateBlock}
        onInsertBlock={onInsertBlock}
        onDeleteBlock={onDeleteBlock}
      />
    </div>
  );
}
