import type { DraftUndoAction } from "./dashboardTypes";

/** Legacy standalone compatibility helper. The dashboard uses editTransactions' durable graph. */
export function createDraftHistory(limit = 100) {
  let undo: DraftUndoAction[] = [];
  let redo: DraftUndoAction[] = [];
  const clone = (action: DraftUndoAction) => JSON.parse(JSON.stringify(action)) as DraftUndoAction;
  return {
    get last() { return undo.at(-1) ?? null; },
    get next() { return redo.at(-1) ?? null; },
    record(action: DraftUndoAction) {
      if (action === redo.at(-1)) {
        undo.push(redo.pop()!);
      } else {
        undo.push(clone(action));
        redo = [];
      }
      undo = undo.slice(-limit);
    },
    prepareUndo(action: DraftUndoAction) {
      // Selective undo invalidates the linear branch rather than replaying
      // unrelated snapshots over the changed drawing.
      if (JSON.stringify(action) !== JSON.stringify(undo.at(-1))) { undo = []; redo = []; }
      redo.push(clone(action));
      redo = redo.slice(-limit);
    },
    consumeUndo() { undo.pop(); },
    reset() { undo = []; redo = []; },
  };
}
