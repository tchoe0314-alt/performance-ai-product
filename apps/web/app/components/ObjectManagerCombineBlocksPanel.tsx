import type { SiteObjectType } from "../types";

type ObjectTypeOption = {
  type: SiteObjectType;
  label: string;
};

type DraftBlockRow = {
  id: string;
  name: string;
  type: SiteObjectType;
  typeLabel: string;
  objectCount: number;
  createdAt: number;
  updatedAt?: number;
  revision?: number;
};

type ObjectManagerCombineBlocksPanelProps = {
  objectTypeOptions: ObjectTypeOption[];
  combineObjectName: string;
  combineObjectType: SiteObjectType;
  draftBlockName: string;
  blocks: DraftBlockRow[];
  onCombineObjectNameChange: (value: string) => void;
  onCombineObjectTypeChange: (type: SiteObjectType) => void;
  onCombineSelected: () => void;
  onDraftBlockNameChange: (value: string) => void;
  onSaveBlock: () => void;
  onRenameBlock: (blockId: string, value: string) => void;
  onUpdateBlock: (blockId: string) => void;
  onInsertBlock: (blockId: string) => void;
  onDeleteBlock: (blockId: string) => void;
};

export function ObjectManagerCombineBlocksPanel({
  objectTypeOptions,
  combineObjectName,
  combineObjectType,
  draftBlockName,
  blocks,
  onCombineObjectNameChange,
  onCombineObjectTypeChange,
  onCombineSelected,
  onDraftBlockNameChange,
  onSaveBlock,
  onRenameBlock,
  onUpdateBlock,
  onInsertBlock,
  onDeleteBlock,
}: ObjectManagerCombineBlocksPanelProps) {
  return (
    <>
      <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3" data-testid="object-manager-combine-selected">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Combine / convert
        </p>
        <p className="mt-1 text-[11px] leading-5 text-slate-500" data-testid="object-manager-semantic-combine-help">
          Select connected linework or one drawn area, then turn it into a named civil object.
        </p>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Name
            <input
              type="text"
              value={combineObjectName}
              onChange={(event) => onCombineObjectNameChange(event.target.value)}
              placeholder="Example: Office Building A"
              aria-label="Combined object name"
              data-testid="object-manager-combine-name"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Type
            <select
              value={combineObjectType}
              onChange={(event) => onCombineObjectTypeChange(event.target.value as SiteObjectType)}
              aria-label="Combined object type"
              data-testid="object-manager-combine-type"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-semibold text-slate-700 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            >
              {objectTypeOptions.map((option) => (
                <option key={`combine-${option.type}`} value={option.type}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button
          type="button"
          onClick={onCombineSelected}
          data-testid="object-manager-combine-action"
          className="mt-2 w-full rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800"
        >
          Combine into Area
        </button>
        <p className="mt-2 text-[11px] leading-5 text-slate-500">
          Source pieces are hidden, not deleted. The result keeps trace, name, type, and affected systems for review.
        </p>
      </div>
      <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3" data-testid="object-manager-block-library">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Reusable blocks
            </p>
            <p className="mt-1 text-[11px] leading-5 text-slate-500">
              Save selected draft objects, then insert traceable review copies.
            </p>
          </div>
          <span className="rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            {blocks.length}
          </span>
        </div>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
          <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
            Block name
            <input
              type="text"
              value={draftBlockName}
              onChange={(event) => onDraftBlockNameChange(event.target.value)}
              placeholder="Example: Utility crossing detail"
              aria-label="Draft block name"
              data-testid="object-manager-block-name"
              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-2 text-sm font-medium text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
            />
          </label>
          <button
            type="button"
            onClick={onSaveBlock}
            data-testid="object-manager-save-block"
            className="self-end rounded-lg bg-slate-950 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-white transition hover:bg-slate-800"
          >
            Save block
          </button>
        </div>
        <div className="mt-3 space-y-2" data-testid="object-manager-block-list">
          {blocks.length ? (
            blocks.map((block) => (
              <div
                key={block.id}
                data-testid="object-manager-block-row"
                className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 sm:grid-cols-[1fr_auto]"
              >
                <div className="min-w-0">
                  <span className="sr-only" data-testid="object-manager-block-display-name">
                    {block.name}
                  </span>
                  <label className="flex flex-col gap-1 text-[11px] font-semibold text-slate-500">
                    Saved block
                    <input
                      key={`block-name-${block.id}-${block.name}`}
                      type="text"
                      defaultValue={block.name}
                      aria-label={`Rename block ${block.name}`}
                      data-testid="object-manager-block-rename"
                      onBlur={(event) => onRenameBlock(block.id, event.currentTarget.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.currentTarget.blur();
                        }
                      }}
                      className="w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-900 outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100"
                    />
                  </label>
                  <p className="mt-1 text-[11px] font-medium text-slate-500">
                    {block.typeLabel} · {block.objectCount} source object{block.objectCount === 1 ? "" : "s"} · rev {block.revision ?? 1}
                  </p>
                  <p className="mt-0.5 text-[10px] font-medium text-slate-400">
                    Updated {new Date(block.updatedAt ?? block.createdAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-1.5 sm:justify-end">
                  <button
                    type="button"
                    onClick={() => onUpdateBlock(block.id)}
                    data-testid="object-manager-update-block"
                    className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
                  >
                    Update
                  </button>
                  <button
                    type="button"
                    onClick={() => onInsertBlock(block.id)}
                    data-testid="object-manager-insert-block"
                    className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-700 hover:bg-slate-50"
                  >
                    Insert
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteBlock(block.id)}
                    data-testid="object-manager-delete-block"
                    className="rounded-md border border-red-100 bg-white px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-red-600 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-3 text-[11px] font-medium text-slate-500">
              No saved blocks yet. Select draft objects, name the block, then save it.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
