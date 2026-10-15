# Phase 3.2 — local verification, October 12, 2026

## Changes and purpose

Added explicit Required / Preferred / Assumed / Unknown selection and trust display inside the existing brief rows. Added explicit value confirmation, exact pre-rounding/source bindings, persisted records, calculation invalidation, named activity entries and existing transactional undo/redo support. Viewer editing is withheld and malformed records are rejected on both sides of the save boundary.

Reproduced and repaired a legacy program loss on autosave: the old building-area target was visible before classification but omitted by the existing save payload builder. The shared preservation helper now carries only explicit building-area/use program fields, without overwriting live values or restoring obsolete geometry/parking.

## Evidence register

- Backend affected collection: **86 passed, 16 passing subtests**, 4.28 seconds. Includes classification validation, canonical adapters, edit history, revision conflicts, project-store fast paths and account lifecycle/backup.
- Final production frontend compilation, type checking and page generation passed. After adding a stale-project identity guard and clarifying recorded/source trust labels, the rebuilt candidate passed **67 checks**, zero failures/skips, 24.7 seconds: 44 repeated pure contracts (11 unique cases repeated across four targets), 20 rendered cases across Chromium/WebKit and their mobile targets, and three real-local account/project checks. Earlier 67-check evidence (25.1 seconds) is superseded by this final run, not added to it as distinct tests.
- Neighboring 39-check pack: **38 passed, one failed at disposable signup with HTTP 429**, 37.2 seconds. That one case passed its isolated final-candidate rerun in 4.0 seconds. All selected neighboring cases have passing evidence across batches; this is not a single 39-green aggregate claim. No normal security limit was weakened; only the owned local API was restarted between fixture batches.
- Focused lint and whitespace validation passed. A newly introduced memoization dependency warning was repaired by depending on the actual saved input used by the payload builder.
- The real-local classification test separately passed three consecutive runs after fixing test navigation to await the mounted workspace after reload. Its subsequent extended version also passed save/reload, undo/redo, malformed-write rejection, failed-save retention/retry, preservation of the legacy target, and shared viewer permission checks.

## Earlier failed attempts

The first saved-project run exposed the real program-loss bug and was not counted as passing. A later timeout was an incorrect Redo accessible-name selector; corrected to the existing label without changing the product. Another run navigated before the workspace stage mounted after reload; added explicit readiness assertions, rather than a sleep or removing reload checks.

An affected 39-check browser pack initially produced 34 passes, three disposable-account signup failures with HTTP 429, and two cases not run after its failure threshold. All three setup failures and both omitted cases subsequently passed in isolated checks without relaxing production limits. Final packs use isolated local API batches to avoid accumulating signup traffic across separate collections.

## Release boundary and next milestone

No deployment, new subscription, customer account mutation or paid generation was performed. Python 3.11.15, isolated disposable local accounts and disabled providers were used. These are affected-milestone tests, not a new cumulative Phase 0–current audit or hosted candidate certificate. That broader audit remains due at the completion of the whole phase.

The last two application changes affect classification actions/display only: refuse an action from an old rendered project context, keep source descriptions separate from the current trust status, and label sourced/external statuses as recorded provenance. The neighboring 39-case evidence predates those narrow changes; the entire affected 67-case feature pack was repeated on the final rebuilt application afterward. No assertion was removed to conceal a feature failure.

Legacy hard constraints remain active regardless of a classification label; this milestone does not claim complete preference-aware optimization or external verification of an uploaded source. Hosted verification and the previous Firefox/security-tooling limits remain open. No database migration is needed.

Next is 3.3: a dedicated Edit Brief drawer for direct values, units, source references/attachments, confirmation, explicit relaxation, reset to source values and dependent-calculation visibility.
