# Pilot execution: P1 verified progress

Local candidate only; not deployed. This does not close P2–P6 or certify engineering/capacity.

October 13 follow-up: see [integration progress](pilot-integration-progress-2026-10-13.md). The original open save-hook, zero-valid field and drawing-only export work below has since been implemented and tested; the development advisory and hosted/external gates remain open. The following original evidence is retained as a dated checkpoint, not the final candidate status.

## Changes and reason

- Updated the Sharp override to 0.35.5 and regenerated the lockfile. The production dependency audit now reports zero known advisories.
- Added a nonnegative parser for setback and parking requirements. Explicit zero is preserved; blank/invalid/negative values remain absent. Strictly positive dimensions still use the existing positive parser.
- The live drawing builder now emits an explicit empty object list. Previously omission meant the canonical snapshot retained older state. Empty projects can now reconcile accepted saves, and deleting the final object clears the canonical drawing rather than retaining its prior geometry. Legacy callers that omit object ownership are not automatically treated as deleting everything.
- Added parser, empty-canvas serialization and final-object deletion regression coverage, including a real website deletion/save/reload test.

## Evidence

- Production build `.next-pilot-p1`: passed, including TypeScript checking.
- Production dependency audit: passed, zero known advisories.
- Focused input/canonical contract tests: 9 passed. The separate unimplemented preliminary-export probe was explicitly excluded, not waived.
- Actual production-built local website/browser checks: 21 distinct tests passed covering explicit-zero and positive controls, canonical reopen, stale-result protection, history/undo/redo, failed-save recovery, copy/replace/cancel, project details, accessibility, four viewport sizes, and final-object deletion/reload.
- Initial browser run: 16 passed; 4 could not create their fixtures because signup returned HTTP 429. Those four passed unchanged after restarting the owned local API. Signup protections were not weakened. An earlier run without local fixture environment variables skipped 14 checks and is not counted as authenticated evidence.
- Changed utilities and new regression tests: lint passed. The existing save hook still has one dependency warning for `exportDraftHistory`/`tabBranch`; no lint errors. Do not silently suppress it or add an unstable object dependency without investigating autosave effects.
- Local API was restarted using the clean pinned backend runtime from the independent audit, with the existing disposable local storage and paid providers disabled.

## Open work

P1 still needs the remaining zero-valid field review and save-hook dependency investigation before its full exit is declared. Development-only lint dependencies retain an unpatched braces advisory: [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). No incompatible Next lint downgrade or blanket audit waiver was applied.

P2 needs the founder's sourced-requirement override decision before source protection is implemented. Recommended: require explicit Override, preserve the original for Reset, and record the edit in history.

P4's safe preliminary geometry export remains unfinished. Hosted release/rollback checks, Firefox verification, performance profiling and external engineering/CAD validation remain open. No new production release, paid call or external contact occurred.
