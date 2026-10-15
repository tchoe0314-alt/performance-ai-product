# Quantity and export version checkpoint — October 4, 2026

## Implemented scope

New canvas-bound calculation results include `quantity_binding_v1`: input signature,
portable live-input key, workflow run reference, and paths to the quantities and
cost estimate in that exact result. Existing calculation history retains that
whole result. No quantities, units, prices, or engineering evidence are invented.

Quantity reports include this reference and optional saved calculation ID.
Artifact history summaries also retain the calculation reference. The quantities
panel identifies its calculation when available; stale totals remain visible as
previous results with “Out of date” and a disabled report download. Legacy results
without a reference are labelled “Calculation version unverified.”

Website DXF, review PDF, JSON and quantity-report actions check live unsaved inputs
before creating a new export. Preliminary review scope no longer bypasses stale
system/output checks. Backend DXF, JSON and PDF entry points independently check
saved project inputs at execution time and reject stale/archived results with 409.
Already-created artifact download paths are unchanged; they are not new current
plan exports. No production deployment, purchase or bulk migration occurred.

## Verification

- Affected backend selection: 234 tests and 5 subtests passed. Includes artifact
  workflows, calculation bindings/history, project/job workflows, persistence,
  migration, lifecycle and access isolation. 22 existing dependency warnings.
- Targeted web selection: 14 checks passed in the Chromium project. Includes
  browser quantities-panel reachability, real disposable local authentication,
  canonical edit/save/reopen and multi-step undo/redo, plus contract tests for
  stale export actions and quantity component labels/disabled state. Not all 14
  are browser interactions: pure contract/component-tree checks run in Node.
- Production web build and TypeScript checks passed. Final whitespace check is
  recorded by the completing turn.

## Remaining boundaries

1. Results/quantities still use compatibility ownership and references; canonical
   collection migration is not complete. Legacy unbound results remain compatible
   and unverified rather than being falsely treated as proven-current.
2. Input signatures cover canvas/manual/site inputs, not every prompt, external
   source governance record, pricing policy or complete engineering dependency.
3. Export freshness is checked at execution entry, not through a transactional
   lock covering file generation. A simultaneous edit during file generation is
   not yet fully fenced. Artifact metadata currently uses the existing full-save
   workflow; general revision checks and metadata-only atomic updates remain
   necessary to prevent concurrent sessions from overwriting newer work.
4. Undo stacks are session-only. Production/Postgres migration, live backup gates,
   hosted browser tests and engineering validation remain outside this checkpoint.

Phase 1.1 is not complete. Next high-value work: revision/conflict protection for
project and artifact saves, followed by explicit canonical quantity ownership.
