# Pilot integration — October 13, 2026

Local candidate only. This is evidence and remaining work, not a declaration that the full pilot plan or master roadmap is complete.

Subsequent findings and fixes are in the [layout follow-up](pilot-layout-followup-2026-10-13.md). In particular, its geometry-search findings supersede the P3 assumption below; this report retains the earlier checkpoint evidence rather than relabeling it as the latest run.

## Implemented

- P1: patched Sharp to 0.35.5; production dependency audit reports zero known advisories. Explicit zero requirements survive controls, canonical save/reload and layout generation. Empty object ownership clears the last deleted object. Whole-number building/parking limits reject invalid calculation requests while allowing drafts to be saved. Grading thresholds no longer silently substitute larger values for explicit zero or tighter limits.
- P1/state: stabilized save-hook dependencies; included raw draft controls in edit detection. Replaced edit-history ledgers atomically rather than merging abandoned redo branches. A queued copy save now adopts the accepted copy name without replacing newer geometry.
- P2: sixteen editable requirement fields, unit conversion without changing drawing units, explicit sourced-value Override, Reset, classifications, undo/history and autosave through the existing canonical state. Added a fifteen-category source register with acceptance, versions, verification references, rights references, supersession and dependencies. Missing requirements explain why they matter and who must verify them.
- P2 scope: additional height, coverage, access, stormwater and similar requirements are recorded, **not automatically checked**. Calculation and export metadata disclose this; recorded requirements cannot make the readiness report claim full-system approval. No jurisdictional rules or verified survey data have been fabricated.
- P3 correction: the existing alternatives panel contains written strategies, not separately solved layouts. Its default now offers five distinct strategies and explicitly discloses the absence of alternative geometry/feasibility checks. Current input-bound quantities are required for heuristic comparisons; stale/unbound quantities remain saved but are not republished as current strategy deltas. This does **not** complete calculated layout alternatives.
- P4: separate acknowledged drawing-only PDF/DXF export from saved current geometry, with server revision checks, editor permissions and worker revalidation. It does not reuse stale calculations. Added cul-de-sac island/paired markings, CAD layers and correct declared DXF unit headers without rescaling coordinates. PDF review removed implied verified north and default reviewer sign-off, and made footprint outlines readable.
- P5 profiling: the assisted regression generated 1.53 billion function calls under cProfile. Candidate evaluation and repeated copying dominate. Removed discarded deep-copy return snapshots at three internal candidate refresh sites, retaining recomputation, conflict detection, validation and rollback. Default explicit snapshot calls remain isolated. A comparable unprofiled check was 62.39 seconds with copies restored and 61.59 seconds with copies skipped: **no meaningful latency improvement demonstrated**. Do not compare the instrumented 264-second run against an uninstrumented run as a speedup.

## Evidence and limits

Targeted backend suites, browser contract tests and actual local website tests have been run throughout implementation. Latest combined evidence is below; intermediate passes do not establish a final candidate pass. Paid providers are disabled for these tests and disposable local accounts are used.

### Latest candidate evidence

- Full backend regression after the source changes: **2,149 passed; 128 subtests passed; 56 warnings**, 352.46 seconds. An additional canonical-edit/stale-strategy regression was added after collection and passed in the separate 7-case alternatives suite. Do not describe that extra case as part of the 2,149-case run.
- Production web build `.next-pilot-final4`: passed, including TypeScript. Subsequent type check, targeted lint and `git diff --check`: passed. Isolated pilot build output directories are ignored, not committed.
- On that production build: **26 distinct focused Chromium tests passed** across brief/source editing, current/stock drawing exports, strategy comparison/selection, canonical persistence, viewer permissions, zero/empty input handling and contracts. Some are pure contracts/demo checks, not authenticated website runs. These are affected-flow tests, not a new exhaustive whole-browser-suite run.
- Earlier wider affected-flow run: 17 passed, four stopped at signup HTTP 429. Those four passed unchanged in a separate local run. Signup protections were not weakened. Broader object/dependency/group/chat/history tests passed; their earlier build identity is retained in test artifacts and is not substituted for final-build evidence.
- Real browser tests exposed and led to code fixes for floating-point unit display noise and copy-name save races. The new strategy test's navigation, endpoint and button-name mistakes were corrected in the test. One source-save poll threw before the asynchronous record existed; it now waits for persistence while retaining strict validation. Initial failures/interruption artifacts remain available.
- Production dependency audit: **zero known advisories**. Full development audit: **five high-severity affected dependency nodes** in the unpatched braces/lint chain. No unsafe framework downgrade or blanket waiver was applied.
- Public `https://civoraai.com/api/release-identity` read-only check reports `ee2055de42b3561eab8822257f911c2dfb693e26`. These local changes have not been deployed.

Local build/runtime test outputs are under `apps/web/test-results/`; local recovery evidence is below. A source inventory is recorded separately before handoff. Neither a fingerprint nor a passing test suite is deployment, professional acceptance or capacity certification.

PDF visual QA has inspected both pages of the drawing-only example after fixing faint outlines and misleading north/reviewer labels. Native DXF parsing has checked coordinates, layers, the central island and paired markings in both feet and metres. This is not AutoCAD/Civil 3D acceptance by an external CAD user.

An isolated SQLite backup/restore of the disposable local test database passed in 3.084 seconds, with matching schema/content evidence and integrity checks. Report: `/tmp/civora-pilot-recovery.hqFB2d/report.json`. This does not prove hosted PostgreSQL recovery.

Safari/WebKit: 9 focused checks passed, including real brief/source saves and accessibility. Mobile Chromium: 4 real website/accessibility checks passed. Firefox launch again reported sandbox-extension and SWGL framebuffer errors before application assertions; the runaway owned test process was stopped. One test was interrupted and one did not run. Firefox is unverified, not passed.

## Remaining plan gates

- P1: development lint dependency advisory remains unpatched upstream; no incompatible framework downgrade or blanket waiver.
- P2: actual pilot survey/parcel/document inputs and professional confirmation still required. Source references are user records, not independent certification. Protection across older entry points needs coverage beyond the new brief editor.
- P3: integrate actual separately calculated geometry alternatives with acceptance/history and canonical state, not just written strategies. Retain a documented complete commercial design run including supported chat edits, conflict review and sourced pricing. Existing smoke tests are not proof of real site suitability or a calibrated cost estimate.
- P4: new drawing-only export provides footprints/linework, not independently generated parking stalls/aisles or calculated profiles. Verify the existing calculated export's detailed geometry and external editable-CAD reuse before claiming no redrawing.
- P5: isolate an exact release checkpoint from the large inherited working tree; finish performance profiling, supported-browser verification, hosted tenant/worker/artifact checks and isolated backup restoration. Firefox environment launch failure is not an application pass. A specified deployment requires approval.
- P6: authorized licensed-engineer/CAD-user review, a real design partner/site, applicable pilot terms and support/acceptance. Software tests cannot substitute for these people or inputs.

No deployment, purchase, paid generation or external outreach has occurred in this implementation pass. Existing user changes have been preserved.

Prepared [external-review handoff checklist](pilot-external-review-handoff-2026-10-13.md) without inventing a reviewer, partner, approval or source permission. The next software milestone is calculated layout-alternative integration; the founder-input gate is a real pilot site/jurisdiction and authorized professional/CAD reviewers. The full P1–P6 plan remains open.
