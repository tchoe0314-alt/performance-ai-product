# Phase 0 through 2.5 regression audit — 2026-10-06

## Scope

Audit of the current inherited working tree, not a clean commit or a claim of production parity. Preserve all existing work. Run the backend suite, milestone browser packs, broader legacy/regression browser packs, production compilation, lint/types, and a non-authenticated live public-site smoke. No deployment, customer-account mutation, provider purchase or paid generation is authorized or performed by this audit.

## Repairs

Generate published its own review geometry and stored flow summary after the direct-run snapshot was captured. The existing focused rerun browser test reproduced a missing checkpoint. Publish those Generate-owned updates synchronously, read the latest payload builder, and seal the published site metadata into the request before execution. Keep the existing freshness guard unchanged: genuinely later user edits still archive the result; project switches still reject late publication.

Strengthen the rerun test to require the first outbound payload to contain generated review geometry and its grading flow summary. Existing checkpoint assertions remain intact.

Update the old Apple-clean UI test to navigate the current five-stage workspace and use icon controls' accessible names, rather than requiring removed text labels or old top-level Generate navigation. This preserves the product's approved compact UI rather than changing it to satisfy obsolete selectors.

Add an account lifecycle regression proving saved workspace preferences are exported with the owner's data and removed when the disposable account is deleted.

Pin `source-map-js` to patched version 1.2.2. The dependency install changed one package; production dependency audit now reports zero vulnerabilities. Full development-tool audit still reports five high-severity findings through the unpatched braces/micromatch/fast-glob/Next lint chain. Do not apply the proposed forced Next lint downgrade; that is a breaking toolchain change, not a safe remediation.

Additional legacy test repairs use the stage-navigation helper in Generate/Deliver and accept the approved lowercase `ft` dimension label without weakening dimension values or geometry assertions.

Restore a user-visible entry to Workspace settings through the existing project-actions menu. Stage redesign had left run-default settings without a normal navigation entry. Project settings continues to open identity details separately. Standards checks now use the actual Brief tool selector; the support fixture selects the exact Details textbox, and the slow-save fixture mocks the new authenticated layout endpoint instead of making a request with its synthetic token.

The restored Settings panel received a new serious/critical accessibility assertion. It reproduced label contrast of 2.54:1 against the required 4.5:1. Darken the six shared setting labels from slate-400 to slate-600; retain the accessibility assertion and include this panel in opt-in cross-browser coverage.

## Completed evidence

- Full backend collection: **2,029 passed, 128 passing subtests, 44 warnings**, 436 seconds. The newly added account-layout lifecycle test was collected separately afterward.
- Account lifecycle and layout focused pack including that new test: **24 passed**.
- Phase 0 candidate/protected-object/batch/placement/review-sheet/transaction-save pack: **28 passed**.
- Phase 0–2.5 milestone Chromium pack: **54 passed initially; 13 failed during disposable-account setup after hitting normal authentication throttling**. Isolated reruns confirmed all failed cases pass: object/tab pack 6 passed (two previously passing checks included), transaction pack 5 passed, account actions/header/environment pack 4 passed. No production rate limits were relaxed.
- Generate execution/freshness and corrected Apple-clean UI pack: **16 passed**, including the reproduced checkpoint test after repair and first-request snapshot assertions.
- Supporting-panel/stage/header/environment/design-system pack across WebKit, mobile Chromium and mobile WebKit: **123 passed, 3 explicitly skipped map-engine checks**. Actual pointer snapping, storage denial, responsive bounds and serious accessibility checks are included; pure contract cases in these packs are not rendered-browser evidence.
- Actual public https://civoraai.com workspace smoke and security-header checks: **2 passed**. No sign-in or customer edits. This is the currently deployed version, not proof that local changes are deployed.
- Production frontend compilation, TypeScript, focused lint, embedded concept-core parity and whitespace validation passed. Full lint has zero errors and two inherited warnings: unused legacy workflow-menu computation and save callback dependencies.

## Outstanding verification boundaries

Firefox's installed automation browser stalled in graphics/content startup again; its attempt was interrupted, not passed. Hosted authenticated persistence, migrations/Postgres runtime, worker/rollback behavior, real imagery/detection providers, source accuracy and independent engineering validity are not certified by these local tests. Existing Phase 0 founder-approved exclusions remain exclusions, not silently converted to passing evidence.

Development-only dependency advisories remain open as described above; production dependency scanning is clean after the narrow patch. The local disk also has less than 1 GB free, so existing build directories were reused rather than creating more build copies or deleting unrelated user files.

The Generate checkpoint defect is repaired and verified in the focused browser workflow. A controlled-response rerun pass is not an assertion that every real provider/calculation workflow is verified.

Full-canvas focus and selected mobile supporting region remain transient, as documented in 2.5; saved account settings cover mode, panel visibility and preferred sizes. Concurrent devices do not receive live layout broadcasts. Phase 7.2's full quantitative delta engine is not implied by the existing summary bar.

## Broader browser sweep

The first wide 440-check Chromium run reached its failure threshold: 289 passed, 10 failed, 1 skipped, 140 did not run, and an unhandled test-helper promise error. Nine failures were obsolete navigation/text selectors, independently repaired and rerun; the drainage matrix likewise needed current Review navigation. It then passed a separate 4.2-minute real-local backend job run across six scenarios, including actual Apply requests and repeated-action deduplication. This proves supported workflow and truthful warnings, not successful engineering repair of every unsafe scenario: the uphill scenario still reported SLOPE_ADJUSTMENT_FAILED and review warnings.

The drainage test's legacy `phase5-autofix` filename is not the master roadmap's Phase 5 completion status. No new roadmap phase was implemented during this audit.

The tail collection completed with 129 passed, 4 failed, 3 skipped. Support and slow-save mock repairs and actual standards navigation passed in a three-check rerun; Workspace settings required the restored menu entry, subsequently verified in the final build below. The tail includes real-local two-user isolation, sustained two-window editing, physical map pointer conversion, project lifecycle and native geometry integrations. These results are recorded as separate packs rather than pretending the first broad run was all green.

Phase 1's additional object-definition/dependency/transaction contracts: 50 passed. Corrected legacy focused packs: Apple-clean UI and Generate freshness/execution 16 passed; centered-site flow 3 passed; Generate/Deliver 1 passed; loading/status 5 passed; naming/trust 3 passed; responsiveness 2 passed; support/Chat/standards 3 passed. Counts overlap the broad collections and must not be summed as distinct tests.

## Final closeout

The final wide Chromium collection completed all **439 selected checks: 432 passed, 3 failed, 4 skipped**, in 6.6 minutes. Its selection excludes the separately tested milestone, hosted and long drainage-job packs; this is not a claim that every repository test ran in one collection. The failed cases were project drawer lifecycle, two-user concurrent project isolation and Settings contrast. Both project/account cases passed an unchanged, isolated two-check rerun against the final build. Their broad-run failures remain recorded; isolated success does not establish that the aggregate run is free of timing or shared test-environment interference.

Settings contrast was tested before the updated label colors were rebuilt. After rebuilding the production candidate, its complete functional and serious/critical accessibility check passed on **all four supported test targets: Chromium, WebKit, mobile Chromium and mobile WebKit**. No failing assertion was removed. Final build compilation, type checking and page generation passed; final whitespace checks passed.

An additional affected-workflow pack on the functional candidate passed **28 checks** covering Generate freshness/execution, project actions, stages and remembered layouts. The only application change after that pack was the Settings label color, verified by the four-target rerun above. No open reproducible functional regression was left from the exercised collections; this does not prove universal bug freedom, production capacity or hosted parity.

Coverage includes canonical object edits, grouping/uncombining, custom types, collision and dependency rules, undo/redo transactions, stale calculation handling, first-edit tab branching, project save/reload/delete, owner isolation, view-only shared actions, identity/error handling, exports, workspace stages, responsive controls and per-user layout lifecycle. Source/context and engineering assertions retain their review gates rather than treating mock provider responses as validated real-world designs.

The disk reached roughly 116 MB free during verification. Only this task's validated `.next-phase22/cache/webpack` compiler cache was removed (about 574 MB); it is regenerable, not source or user project data. The final rebuild regenerated its cache. No unrelated build directory, project file or test evidence was deleted.

**Release boundary:** changes are local and have not been deployed. The next release blocker is authenticated hosted verification of this exact candidate, including persistence and calculation/provider workflows. Firefox startup, development-tool security advisories and inherited lint warnings remain explicit limitations. No new master-roadmap milestone beyond 2.5 was started.
