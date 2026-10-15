# Phase 3.1 — local verification, October 12, 2026

## Changes

Added a read-only Active Brief Summary in the existing Setup panel and optional professional dock. It covers all roadmap categories, updates from current inputs, distinguishes program targets from drawn results, discloses unknowns and unverified values, and keeps lengthy requirements behind a disclosure.

No new database schema, project write, generation gate or provider was introduced. Existing identity/Edit brief/chat controls are preserved. Explicit saved program fields remain readable in legacy projects without overriding live edits or restoring stale geometry.

## Repairs during verification

The first browser/accessibility pack caught invalid nested definition-list markup in the new component. Fixed the markup; retained the serious/critical assertions. Neighboring professional-layout accessibility also reproduced that defect and is rerun against the repair.

A strengthened numeric acreage assertion exposed an incorrect test assumption: `/demo/workspace` intentionally starts empty unless explicitly seeded. Corrected the fixture with the existing `seedDemo=1` option; did not change product behavior. Live dimension tests confirm both brief views update together.

## Evidence

Final production compilation, type checking and static page generation passed. Focused lint and whitespace validation passed.

- Final new-feature pack: **45 passed**, zero failures/skips, 26.8 seconds. This includes seven pure projection contracts repeated across four test projects (28 checks), 16 rendered browser checks across Chromium, WebKit, mobile Chromium and mobile WebKit, and one real-local authenticated saved-project check. Repeated pure contracts are not 28 different browser workflows.
- Rendered checks cover exact acreage, 320-pixel portrait, short landscape and desktop containment, serious/critical accessibility, read-only/no-project-write behavior, reload, and synchronized live updates in both summary locations. Screenshots from desktop and mobile were retained; desktop appearance was visually inspected.
- The saved-project check reopens two canonical projects with different acreage, building targets and use, switches between them, reloads, and proves both project inputs and revision tokens remain unchanged. No customer accounts were used.
- Affected-workflow pack: **31 passed**, zero failures/skips, 33.1 seconds, on the final candidate. It covers direct/queued Generate freshness, centered-site entry/chat, remembered layout and account preferences, independent project/tab stage memory, and Settings accessibility/functionality.

These packs are scoped regression evidence, not a new complete backend suite or whole-phase/cumulative audit. Earlier failed attempts are retained as evidence of repairs; the final runs use the rebuilt candidate, not an older serving process.

## Limits and next milestone

This is local candidate evidence, not deployment proof. No deployment, spending, customer-account changes or paid provider requests were performed. Provider execution was disabled in a fresh disposable local backend using Python 3.11.15 and repository-pinned requirements.

New classifications, complete editable brief fields, source attachments and acceptance of assumptions remain milestones 3.2/3.3. Existing hosted/Firefox/security-tooling limitations from the cumulative audit are not waived. A broad whole-phase audit is due when Phase 3 is finished, not claimed by this milestone's affected checks.

Next: 3.2 records Required / Preferred / Assumed / Unknown and the trust status for every value. Decide whether new entered values default to a category or require an explicit choice; missing values remain Unknown and sourced/extracted values must not be auto-confirmed.

## Subsequent 3.2 compatibility repair

Milestone 3.2's real save test found that the existing control payload could omit a legacy stored building-area/use program during autosave. Milestone 3.1 proved read/reopen projection, not this subsequent classification-write path. The shared payload builders now preserve those two explicit fields without restoring old geometry/parking, and the saved-project regression verifies their survival through classification, reload and undo/redo. See `phase-3-brief-classification-completion-2026-10-12.md` for the newer evidence.
