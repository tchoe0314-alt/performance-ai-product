# Phase 1.3 — Unified edit transactions

Purpose: make workspace edits atomic, recoverable and persistent rather than dependent on a browser session.

## Ownership and behavior

The dashboard uses one transaction graph for committed editable project inputs. Canvas, inspector, chat, grouping, imports and bulk edits enter the same snapshot observer. A transaction stores its parent, detached before/after inputs, affected object IDs, reason, actor, calculation invalidations, warnings, timestamp and replay instruction. Optional descriptions preserve familiar recovery wording; they never supply replacement geometry.

Undo and Redo restore whole transactions, including multi-object requests. Saving and reopening retains the cursor and redo path. Editing after Undo creates another branch without deleting abandoned transactions. Only the current branch head is directly undoable; old entries remain visible without unsafe selective snapshot replacement.

History lives in `meta.edit_history_v1`, including the canonical document's input metadata. Existing project persistence stores it without a separate service. The backend validates graph integrity, seals authenticated actors, prevents rewriting stored transactions, and merges approved concurrent branches by ID. Existing revision guards still authorize replacements. Legacy writers are journaled at the save boundary using reconciled authoritative geometry.

## Safety

Batch planning detaches inputs and validates groups before publishing. Invalid saved graphs fail closed before resetting the working workspace. Failed saves retain the live edit and history for retry. Replay preserves chat and result history while invalidating affected calculation systems; previous results do not become active merely because an edit was restored.

Prompt typing, project identity and result freshness are not geometry edits. Restore-time defaults are semantically equivalent without changing saved snapshots. Generation/review/visualization notices are read-only history entries, not fake Undo operations.

## Boundaries

Undo does not delete uploaded files, generated external artifacts, account-wide definitions or immutable calculation history. Read-only notices retain the latest 100 entries. Transactions are not silently pruned; incoming graphs have a 10,000-transaction safety limit. Unbounded history performance and hosted database operation are not certified by this milestone. Geometry validity is not engineering approval.

Verification: see the companion [completion report](../release/phase-1-unified-edit-transactions-completion-2026-10-04.md).
