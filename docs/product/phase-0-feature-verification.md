# Phase 0.2 — Current-feature verification

Recorded October 2, 2026. Status: **local verification pass completed; Phase 0.2 remains open for the findings and external evidence below**. This register maps the master roadmap's existing-feature checklist to actual evidence, not feature aspirations. Application baseline was `33c23e34`; subsequent 0.1 closeout `96be57c2` changed documentation only. This pass adds opt-in cross-browser workflow selection, repairs obscured mobile proposal/comparison controls, and makes mobile drawing controls collapsible and isolated from canvas input.

## Evidence boundaries

- Prior complete local Chromium collection: 374 passed, 16 skipped, no failures. Full unchanged backend inputs: 1,837 passed, 78 passing subtests, 42 warnings. These are baseline results, not a claim that the new mobile repair received another complete suite.
- Real-local API runs use disposable SQLite storage, provider-disabled backend at `http://127.0.0.1:18880` and local frontend at `http://localhost:3040`. No production accounts, deployment or paid provider access.
- Controlled-response browser cases prove visible UI/geometry/state behavior, not hosted authentication or persistence. Pure contracts within a browser-selected suite do not become cross-browser rendering checks simply by running under another project name.
- Desktop Safari engine workflow selection before the repair: 43 passed, 1.2 minutes. This includes real-local save/reload/owner isolation and 2D/3D/native-object interactions, not just shell navigation.
- Existing authenticated smoke workflow, enabled with a newly registered disposable local account: one passed, 2.2 seconds. Its historical “hosted” test title does not change the actual localhost target.
- Mobile reproduction: the Reject button was visible in the DOM but pointer events were intercepted by the chat drawer. The initial mobile collection was stopped after reproducing this defect; it is not a passing run. A local Firefox attempt was stopped after its graphics/content startup hung; Firefox remains unverified.
- Repair: compact-viewport proposal controls render in a viewport portal above the drawer, with bounded scrollable height. Desktop canvas positioning, geometry planning and acceptance/rejection callbacks are unchanged. Eight focused accept/reject/undo tests passed across desktop Chromium/WebKit and both mobile projects, including live resizing to 360×640 and back. No forced clicks bypassed the overlay.
- First expanded device recheck: **61 passed, four failed, 64 not run**, stopped at the configured failure limit. Two failures reproduced alternatives controls covered by the chat/command layers. The other two were desktop-style quality-toggle test steps attempting to click through a mobile drawer; their helper now closes the panel using its normal visible control before accessing the canvas.
- Alternative comparison now uses the same compact-viewport portal boundary and can be minimized/reopened while editing. The stale-apply regression explicitly exercises this user path; preview geometry and stale-transaction protection remain unchanged. The shared responsive hook is server-snapshot safe and responds to resizing.
- A subsequent combined run reached **127 passed, two failed, no skips** across desktop WebKit and both mobile viewports. Both remaining failures involved drawing on a narrow mobile-WebKit site: the toolbar occluded all sampled drawing targets. The old raw-coordinate fallback could activate Pan instead of drawing. This is a failure record, not a passing certification.
- Mobile drawing controls now minimize/reopen without dropping the active tool or draft points. Toolbar events are isolated from canvas drawing handlers. Pointer tests require an unobstructed drawing target and normal browser actionability; they no longer fall back to blindly clicking a covered location. Mobile helpers close drawers/view menus and collapse precision controls before drawing, then reopen object details for inspection.
- The final mobile drawing selection passed **six of six**, including blank-site locking, rectangle/area/line/point creation, classification, geometry handoff and history on both mobile engines. Toggle regressions assert unchanged tool and draft-point count. The final isolated production build `.next-phase0-draw-isolation` passed compilation, TypeScript and route generation. Final typecheck, changed-file lint and whitespace checks passed.
- Final combined affected-workflow selection: **172 passed, zero failed, zero skipped, 4.2 minutes**, 43 checks each on desktop Chromium, desktop WebKit, mobile Chromium and mobile WebKit. Output: `/tmp/civora-phase02-final-verified-workflows`. All application and test inputs were unchanged throughout this final run. Each project includes contract-only cases; this is not 172 separate rendered UI workflows. Real-local authentication/save/reload/owner isolation ran in all four projects. This selection supplements, rather than replaces or reclaims, the prior full baseline suite.

## Roadmap feature checklist

The named suites below were present in the complete baseline run. “Locally exercised” is not universal correctness, hosted sign-off or qualification of an engineering design.

| Roadmap feature | Existing proof / boundary |
| --- | --- |
| Canvas object creation | `drawn-boundary-finish`, `draw-drafting-usability-chat221b`, `project-object-integration`; native/drawn object browser workflows. |
| Selection | `object-manager-polish-chat230`, `dense-draw-hit-capture-chat241`, `video-website-regression`; object rows and canvas selections. |
| Movement | `object-manager-polish-chat230`, `canonical-edit-command-foundation`, cul-de-sac editor; direct/numeric/chat edits and combined-source movement. |
| Resizing | Object-manager numeric transforms, canonical edits, parametric-road and cul-de-sac suites; arbitrary edits detach template claims. |
| Rotation | Object-manager combined rotation, drafting transforms and interference geometry contracts; saved coordinates remain distinct from presentation. |
| Direct property editing | Object-manager, native pipe elevation/buffer and setback-rule UI; type/style/name/protection metadata and history. |
| Chat commands | `command-power-layer-chat229`, `canonical-edit-command-foundation`, dense commercial and workflow suites; proposed/blocked/applied outcomes distinguished. |
| Canonical-model synchronization | Canonical command, native serialization/handoff and `phase0-placement-state` contracts; project-race browser cases. Not a universal Phase 1 schema. |
| Fixed dependencies | Canonical protected-edit and fixed-relationship contracts; object-manager protection and whole protected concept replacement. |
| Following dependencies | Canonical browser follow-parking edits plus collision-aware parking reflow. |
| Asking dependencies | Whole-transaction accept/reject/undo browser cases; compact drawer occlusion reproduced and repaired in this pass. |
| Independent dependencies | Explicit unlink/relink browser and metadata precedence contracts; supported building/parking relationship only. |
| Building movement | Canonical browser chat/CAD movement, Ask/follow policies and out-of-site feedback. |
| Road movement | Cul-de-sac independent drag/group history, native parametric transform and combined-object transform contracts. Map-backed coordinate evidence remains open. |
| Parking reflow | Canonical fit/capacity, in-site alternative and resized-parent collision regressions; required stall counts preserved. |
| Cul-de-sac editing | `cul-de-sac-core`, `cul-de-sac-concept`, `cul-de-sac-editor`, `project-object-integration`; dimension ranges, smooth geometry, stale responses and JSON restore. |
| Constraint warnings | Canonical selected-object live feedback, `site-interference`, `site-object-rulebook`; category/elevation/evidence-aware assessments, not legal clearance certification. |
| Alternative generation | Canonical and `phase0-candidate-contract`; bounded search, 2–10 requests, invalid-input/no-feasible-result behavior. |
| Alternative scoring | Full valid-pool reranking and goal/priority contracts plus preview comparison browser controls. |
| Apply | Canonical preview-only alternatives and Ask acceptance; stale/cross-project guards and one undoable transaction. |
| Cancel | Alternatives cancellation, Ask rejection, drawing cancellation; source geometry remains unchanged. |
| Undo | `undo-recovery-history-chat231b`, object-manager group history, native connection metadata and dependency batch undo. |
| Layer visibility | `preview-realism-truth-chat234`, object-manager and canonical browser controls; source overlays hidden together. |
| Bulk layer selection | Canonical road layer selection and object-manager select-visible/invert/bulk transformations; protected groups handled safely. |
| Commercial workflow | `dense-commercial-concept-chat240`, protected concept-replacement and batch-transaction regressions; new program/revision and 3D massing. |
| Two-dimensional workflow | Drafting, native object, review-sheet and preview suites; canonical geometry, routes, rotation and units; map checks remain open. |
| Three-dimensional workflow | Dense campus concept, recorded-video regression and responsiveness suites; synthetic/missing terrain disclosed. Not survey-derived elevation proof. |
| Export behavior | Preliminary snapshot policy, real-local signed-in PDF/DXF job completion and browser downloads, owner isolation and persistent download history verified. Current unsaved-canvas exports and hosted proof are not claimed. |
| Authentication | Real-local persistence/support lifecycle and this pass's enabled authenticated smoke; anonymous API access rejected. Hosted login remains open. |
| Project saving and reopening | `phase0-local-persistence`, project-flow late-save/switch races and support data lifecycle. Real-local owner isolation verified; hosted storage behavior remains open. |

## Unresolved verification gaps

1. **Hosted export follow-through:** local preliminary snapshot implementation and signed-in website-to-download verification are complete for the tested paths. Construction-default exports remain guarded. Files disclose actual source geometry hash, revision, UTC timestamp, units, stale systems, conflicts, assumptions and warnings. Unknown units, corrupt/unsupported geometry and unresolved/cache-only integrity remain blocked. These are generated/saved snapshots, explicitly not newer unsaved canvas edits; current-canvas serialization is not claimed. Focused backend evidence: 95 tests plus 70 export/CAD regressions passed. Hosted exact-candidate verification remains required alongside item 3.
2. **Map-backed workflows:** provider token/build and approved provider access are required to verify real map locking, pointer-to-site conversion and delayed scale-save races. No token was fabricated or secret configuration exposed to turn skips green.
3. **Hosted authenticated workflows:** founder confirmed October 2 that only the same live website is available; there is no separate staging target. Need separate approved staging website/API, scoped test account and noncustomer database, with the exact candidate deployed under separately granted deployment approval. Local credentials cannot verify hosted auth, CORS, routing, provider configuration or persistence. Do not deploy or run data-changing tests against the live site under this verification request.
4. **Firefox/platform:** local graphics startup is unusable in this attempted run; exact-candidate Linux Firefox evidence is needed. WebKit/mobile viewport emulation is not a physical-device or all-workflow certification.
5. **Engineering/provider truth:** real source accuracy, paid high-quality imagery, actual site constraints and external CAD/professional validation require independent inputs/evidence. Their absence cannot be repaired by synthetic fixtures.

## Reproducible device selection

October 2 authenticated export closeout: added a visible **Export progress and downloads** action to Deliver because its completed artifacts otherwise lacked a direct visible navigation path. `phase0-local-export-download.spec.ts` uses real registration, project storage, export jobs, artifact authorization and browser downloads without mocked API responses. Both PDF and DXF complete with stale grading; anonymous and other-owner artifact requests are rejected. The initial download workflow passed on desktop Chromium/WebKit and mobile Chromium/WebKit. The downloaded PDF's two pages were rendered and visually inspected; source revision, stale grading, assumptions, warning and preliminary designation are visible. Synthetic geometry is not engineering evidence. Build ID: `PddzX3Y0OX7Rln9vRBdih`, isolated output `.next-phase0-export-download`. Three additional real-local save/reload/owner-isolation cases and the Generate/Deliver regression passed. TypeScript, scoped lint and production build passed. Evidence directories: `/tmp/civora-export-download-proof`, `/tmp/civora-export-device-proof`, `/tmp/civora-export-final-proof`, `/tmp/civora-export-reopen-proof`.

One follow-up literal-reload collection passed three projects but mobile WebKit reported `Download is starting` during immediate reload. The test now explicitly reopens the workspace URL after the browser download completes, rather than potentially reloading a download navigation. This is a separate reopen/history persistence check, not proof that the immediate mobile-WebKit reload edge is resolved.

Final reopen/history collection: **four passed, zero failed, zero skipped**, 30.2 seconds across desktop Chromium/WebKit and mobile Chromium/WebKit. Each case exports/downloads both formats, verifies unauthorized access rejection and reopens the workspace to find the recorded artifact after each download. This does not close the separately recorded immediate-reload edge or hosted verification.

Deployment assessment: the next deployment target should be an explicitly approved isolated staging frontend/API/database/storage, with providers disabled. Local evidence supports requesting that verification step, not promotion to the live site. There is still no separate staging target or deployment approval. Before production, record exact frontend/backend identity, run hosted authenticated/worker/persistence/export checks and isolated backup/restore and rollback verification; resolve or explicitly scope map/Firefox/provider limitations. No deployment, push or paid provider operation was performed.

October 2 preliminary-export follow-up: an additional 70 CAD roundtrip, sheet-layout, export packaging, external-verification-gate and production-depth regression tests passed. A real DXF roundtrip verifies that source revision, stale grading, preliminary designation and the final warning are present in modelspace notes. The Generate/Deliver website test now asserts the snapshot limitation and construction warning before export. These checks do not replace an authenticated website-to-download test or external CAD verification.

`CIVORA_PHASE0_CROSS_BROWSER=1` widens the four existing device/engine projects from shell-only smoke to ten named workflow suites. Default test scope is unchanged. Use `CIVORA_PHASE0_LOCAL_TESTS=1` only with explicitly local disposable API storage, and supply frontend/API targets and an isolated output directory. Select desired projects explicitly; this opt-in must not be mistaken for a permission to run against production.

0.2 stays active until remaining product-rule defects are resolved and required external feature evidence is supplied. Phase 1 has not started; no release or deployment is approved by this register.
