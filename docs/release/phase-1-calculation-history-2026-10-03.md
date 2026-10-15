# Retained calculations without overwriting edited layouts

Local, uncommitted Phase 1 checkpoint. No production deployment or purchases.

## Behavior

For background orchestration/checkpoints and drainage runs with an adopted
canonical canvas, calculation saves now use a separate result-only boundary:

- Save the complete result and exact submitted input snapshot in project-scoped
  `project_calculation_history`, including failed/partial results.
- Lock the project row / SQLite write transaction before comparing current saved
  inputs with the calculation's input binding.
- Matching inputs: update the current result, without rewriting project inputs,
  labels, session state, or project metadata.
- Changed inputs: retain the result as archived; leave the entire current project
  unchanged, including a newer active result if one exists.
- History listing reports `is_active` from the current result reference and input
  association. The stored `disposition` describes activation at save time, not
  permanent currentness; editing afterward makes that entry inactive.

Authenticated history list/detail routes live under
`/api/projects/{project_id}/calculations`. History includes source inputs and
results in account exports, and project/account deletion cascades its removal.
No second copy of history is embedded in project-shell responses/autosaves.

The job-detail endpoint rechecks freshness against current saved inputs, including
edits made after result activation but before job polling. Website job publication
does not apply stale/archived results, refresh their preview, or mark systems
fresh. Completed archived jobs clear busy ownership and explicitly report that
the calculation was saved in history. Job details also label archived results.

## Verification

- 221 backend tests plus 5 subtests passed: calculation history, actual job runner
  with an edit during execution, locking race, canonical canvas/results, design,
  project/job/artifact workflows, fast paths, permissions, collaboration, legacy
  migration, account export/deletion, backup/lifecycle. 22 existing third-party
  deprecation warnings; no failures in the final selection.
- 27 Chromium checks passed: late-job publication suppression, ordinary approval
  continuation/export/polling, result-loader suppression, real local editing,
  persistence/reopening, legacy compatibility, save queue and execution contracts.
- 9 additional Safari/WebKit and mobile Chromium/WebKit checks passed for local
  persistence, canonical editing/save/reopen, and stale saved-result suppression.
- Production website build/type checking, scoped lint, and whitespace checks passed.
- Final local website build: `4Jq-_eo0nFR2dXTA8auHs`, port 3050. API port 18886 uses
  disposable storage `/tmp/civora-phase1-canonical.oAOyri`, AI/image providers off.
- The late-job browser test uses intercepted responses; actual storage locking,
  runner integration, and API freshness are independently exercised in backend
  tests. These are not hosted-provider or real-site engineering proofs.

## Remaining limits

- SQLite behavior is tested. PostgreSQL schema and locking paths are implemented
  but not verified against a running PostgreSQL service in this checkpoint.
- Legacy callers without an adopted canvas retain the old save path. Direct-run
  saves, arbitrary project saves, and simultaneous editing sessions do not yet
  have a general optimistic-revision policy.
- Freshness uses the previously documented canvas/manual-fields/site-input scope;
  independent source records, prompts, and all strategy settings are not yet
  represented by a complete calculation dependency model.
- The comparison is with saved inputs. Unsaved local edits need a stronger
  live-canvas revision guard on every publication/export boundary.
- Existing result/export compatibility paths remain; history capture is not full
  canonical result/quantity ownership, a history restoration UI, or a complete
  stale-export policy. A separate browsable quantity/result-history model remains.
- Phase 1.1 and deferred production storage/backup gates remain incomplete.
