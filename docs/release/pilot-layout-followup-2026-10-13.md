# Pilot layout follow-up — October 13, 2026

Local candidate only. The full P1–P6 plan is not complete. This supersedes the earlier progress report's assumption that no geometry alternatives existed: Civora already had a separate spatial search, preview and explicit Apply path, besides its written-strategy panel. This pass reused and strengthened that path, not a newly built engineering solver.

## Changes and reasons

- Added a concise Compare layouts action requesting five alternatives by default. Responses report the actual accepted count or rejection reasons rather than always claiming five.
- Search checks entered building setbacks, declared units, required parking versus specified stalls, outside-boundary footprints, unsupported parking shapes/dimensions and explicit object/vertex limits. Metric movement and parking calculations preserve physical dimensions. These are model checks, not jurisdictional approval.
- Apply is bound to the project, placements and live calculation inputs. Changed brief inputs invalidate old previews; shared viewers cannot apply them. Preview alone does not change saved geometry.
- Fixed two actual parking-count loss bugs, in project restoration and raw Undo snapshot restoration. Explicit zero and valid quantities survive without rounding invalid counts.
- Protected sourced parking/setback values from older command/control writes and sourced building-program targets from legacy drawing tags. Source changes require Override and lose confirmation. This is not server-wide protection for every legacy entry point.
- Unknown saved units remain unknown. An editor can explicitly interpret existing coordinates as feet or metres, with confirmation, no rescaling, unverified metadata, persistence and Undo. This does not convert known drawing units.
- PDF visual QA caught an unjustified fixed-scale label. PDF exports now say Fit to page and disclose that they are not plotted for measurement; PDF sidecar metadata records this limitation. Recorded viewport scale remains intact.

## Evidence

- Production build `.next-pilot-layout12`, including TypeScript, passed against the disposable local backend. `.next-pilot-layout11` also built after correcting types, but its runtime test configuration pointed at the wrong backend; failed browser attempts are not verification.
- Latest build: 13 Chromium checks passed, comprising seven pure brief contracts and six authenticated website flows; 21 additional pure restoration/search/history contracts passed; four stock/current PDF/DXF checks passed, comprising website, real API and pure readiness checks.
- Targeted lint and production dependency audit passed; production audit found zero known vulnerabilities. The earlier development dependency advisory remains open.
- Affected backend export suites: 83 passed, 35 dependency deprecation warnings, 3.69 seconds. This is not a new whole-backend regression; the previous report retains the earlier 2,149-test checkpoint.
- Latest-build authenticated geometry-loop rerun: three WebKit and three mobile Chromium cases passed, 11.9 seconds. An earlier batch stopped at signup HTTP 429 before assertions; the unchanged tests passed after spacing runs, without weakening signup protection.
- Five additional authenticated Chromium persistence/two-tab checks passed in 9.0 seconds: stale result rejection, geometry save/reload, and first-edit copy/replace/cancel. Their earlier signup-limited run is not counted as a pass.
- Targeted dashboard/component/hook lint completed with zero errors and one existing unused-variable warning (`primaryWorkflowItems`). `git diff --check` passed. Test totals above are affected-flow checks, not an exhaustive new all-browser suite or capacity certification.
- Both regenerated two-page PDF examples were rendered and all four pages inspected after the scale fix. No clipping or overlapping page content was observed in those fixtures. Synthetic exports are not real-site or external CAD acceptance.
- Signup-limit failures and the incorrect local API build were retained, not waived. Further rerun results are appended when completed.
- Firefox remains unverified: the alternative headed launch did not reach browser automation readiness; one interrupted check and one unrun check are not application passes.

## Remaining gates

The bounded search still needs a full commercial engineering/calculation run and sourced pricing, not just geometric options. Additional recorded requirements are not all automatically enforced. Performance (~62-second prior assisted case), Firefox, exact release checkpoint isolation, hosted tenant/worker/artifact/recovery checks and external CAD reuse remain open. A real pilot site/jurisdiction, licensed reviewer, CAD user and applicable pilot terms/acceptance remain necessary. Software tests cannot fabricate those inputs.

No deployment, purchase, paid generation or external outreach occurred. Only regenerable caches from this agent's obsolete pilot builds were removed to free local disk; source, saved projects, inherited edits and test evidence were retained.
