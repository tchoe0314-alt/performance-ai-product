# Civora — focused pilot execution plan

Date: October 12, 2026

## Purpose and authority

Prove one useful commercial-site workflow before expanding the product. Remain web-first and reuse the existing backend, Mapbox, accounts and subscriptions.

This is a near-term execution plan under the authoritative [master roadmap](civora-master-product-roadmap.md), not a replacement for its product rules or a declaration that unfinished phases are complete. The founder requested this plan after the [independent audit](../release/independent-audit-2026-10-12.md). Expansion items remain in the backlog; material scope changes require founder confirmation.

No new purchases, paid provider calls or deployments are authorized by this document. Deployment requires a specific release request with changes, tests, limitations, migration impact, target and rollback plan. No arbitrary launch date or unsupported full-capacity promise.

## First pilot scope

- Small-to-medium office or retail project on one parcel.
- One primary building, one or two access points, surface parking and drive aisles.
- Setbacks, easements, sidewalks, landscaping/open space and a preliminary stormwater-reserve area.
- Basic quantities and clearly sourced conceptual cost ranges; unavailable evidence stays unknown.
- Engineer-entered or engineer-confirmed requirements; no automatic municipal-compliance claim.
- Editable DXF and preliminary PDF; no native intelligent Civil 3D objects required initially.
- Secure firm/project separation. Preserve existing view-only-by-default sharing, optional edit permission, named edit history and user preferences. Do not build a new real-time collaboration platform or require a new milestone-saving mechanism.

Existing working features are reused and verified, not rebuilt merely because they appear in a later master phase.

## Execution sequence

### P1 — Correct the confirmed defects and release risks

Master mapping: stabilization/security; canonical state; Brief summary/classification.

1. Patch the production image-processing dependency and verify the actual dependency graph. Resolve the development lint/glob advisory chain separately with compatibility checks.
2. Preserve valid explicit zero setback/parking values through controls, active brief, calculation requests, canonical save and reload. Check other zero-valid fields without relaxing strictly positive dimensions. Blank, zero and invalid negative values must remain distinct.
3. Diagnose and correct accepted-save versus live-state divergence for sparse/legacy projects. Show Saved only after the server accepts the current inputs; keep pending edits, offline failures and genuine conflicts honest.
4. Retain the audit's regression probes. Maintain a complete, pinned test environment with dependency/import integrity checks. Investigate save-hook dependency warnings where relevant to the fixes.

Done when: defect probes pass through the actual local website and backend; negative/offline/two-tab cases still behave correctly; affected tests, type checks and production build pass; production dependency advisory is resolved. Do not waive failing assertions or force the header to say Saved.

### P2 — Finish a usable project brief and evidence record

Master mapping: 3.3 Brief editing, 3.4 source workspace, 3.5 missing information.

1. Build Edit Brief around the existing authoritative state: values, units, priority, confirmation, source attachment, relaxation, reset to source and affected-calculation visibility.
2. Preserve original sourced values. Recommended protection: explicit Override for protected/sourced requirements, with recorded history and Reset available; confirm unresolved policy details before implementation.
3. Record source identity/type, origin, jurisdiction, effective/import dates, version, acceptance, verification, supersession and dependent objects/calculations. Keep unsupported extraction explicit; a document attachment is not verified engineering data.
4. Explain missing inputs in concise language: what is missing, why it matters, what is blocked, what can proceed provisionally, proposed assumptions and who must verify them.
5. Exercise the pilot's actual boundary/survey/GIS/document inputs. Preserve legacy projects and original files.

Done when: a user can establish and edit the pilot brief, trace its requirements, save/reopen and undo/redo edits, and see dependent results become stale. Viewers cannot edit. Missing or changed evidence cannot silently become verified. If only pilot-specific source handling is complete, record that scope; do not mark the whole master milestone complete without its full acceptance checks.

### P3 — Prove the complete design loop on the website

Master mapping: existing canonical/object/transaction foundation; pilot-critical parts of direct editing, chat, alternatives, freshness, quantities and history.

Demonstrate, without hidden operator intervention:

1. Create a commercial project and establish its brief and parcel.
2. Draw or generate a concept using the existing features.
3. Select, move, resize, rotate, duplicate, lock and delete objects; group/combine/uncombine where supported.
4. Make an equivalent supported change through chat; preview/confirm connected changes when required.
5. Generate the governed default five alternatives where feasible, compare them and select one. Explain infeasibility instead of presenting invalid options as valid. Do not rebuild the search engine if existing behavior meets the pilot need.
6. Review conflicts, assumptions, basic quantities and sourced conceptual cost ranges. Missing pricing/engineering data stays disclosed.
7. Recalculate only affected systems with confirmation. Late or stale calculations remain history, not active results. Locked geometry and deletions remain respected.
8. Save, close, reopen and exercise edit history/undo/redo and two-tab copy-or-replace behavior.

Done when: one documented end-to-end browser run passes with matched canonical data and usable outputs; no critical editing, state, permission or recovery blocker remains. All objects may be edited, but only documented supported calculations can be claimed.

### P4 — Deliver a genuinely reusable preliminary package

Master mapping: export governance Decision 10; pilot-critical CAD/export and delivery work.

1. Add a separate safe current-geometry preliminary export path with explicit acknowledgment. Include revision, timestamp, assumptions, source/verification status, conflicts and stale-system disclosures.
2. Keep stale calculation results from being labeled current. Block unknown units, failed coordinate conversion, corrupt geometry, misleading representation and critical security/data-integrity failures.
3. Check editable building footprints, road edges/centerlines/curves, access, parking stalls/aisles and distinct CAD layers. Preserve supported markings; disclose unsupported items.
4. Verify PDF/DXF download, ownership isolation and reopening. Inspect the PDF visually and check geometry, units and coordinates against the canonical project.
5. Validate technical and clean-concept views from the same plan. Preserve existing high-quality/3D features; verify fidelity before making promises about them. Real billed AI calls require approval, and images are never engineering evidence. Any limited imagery capability must be disclosed in the pilot offer.

Done when: the package accurately represents the selected current geometry and disclosures, passes artifact checks, and is ready for external editable-CAD verification. A downloaded file alone does not establish “no redrawing.”

### P5 — Establish an exact, recoverable hosted release

Master mapping: release engineering; security, reliability and pilot-size performance.

1. Create a scoped release checkpoint from the large inherited working tree. Preserve unrelated work and identify exactly what is being released.
2. Run full backend and relevant browser regressions on that exact candidate, plus build, dependency integrity/security and accessibility checks. Restore Firefox verification in a working environment, or explicitly restrict supported pilot browsers; do not call the Firefox launch failure an application pass.
3. Profile the observed heavy coordination/candidate-copying path. Measure representative pilot inputs, agree supported size limits, and keep expensive work asynchronous with truthful progress/failure handling. A short two-window check is not a capacity certification.
4. Verify existing hosted account access, tenant isolation, configured capabilities, worker recovery, artifact durability and rollback readiness. Prove backup restoration into an isolated recovery destination, never over customer production data.
5. Request approval for the specified deployment. After approval, deploy using existing infrastructure and run authenticated checks with authorized disposable test data. Verify the new interface and build identity are actually live; roll back if release gates fail.

Done when: the approved candidate is identifiable, hosted checks pass, recovery is demonstrated and limitations are documented. No new paid staging service is assumed; if existing infrastructure cannot safely support a check, report the exact access/resource gap rather than improvising destructive production tests.

### P6 — Obtain external validation, then begin controlled pilots

Master mapping: CAD handoff, independent engineering review, pilot operations and feedback.

1. Supply the selected package and benchmark evidence to an appropriately licensed civil engineer and a CAD user with founder authorization.
2. Verify editable handoff in AutoCAD/Civil 3D, geometry/units, assumptions and preliminary calculation limitations. Repair the failures found and repeat affected checks.
3. Have a qualified designer complete the whole workflow and confirm that the output is useful.
4. Confirm pilot use limits, data handling, support contact, applicable terms, account provisioning and acceptance of scope before real firm data is used. Existing subscriptions/billing are reused; broader commercial expansion is not a prerequisite for a controlled pilot.
5. Start with one design partner; expand toward the roadmap's three-to-five firms after the first workflow is stable. Record time saved, manual corrections, export reuse, repeat usage and willingness to pay.

Done when: technical, preliminary engineering, editable-CAD, workflow and founder business gates pass, and the pilot firm accepts the documented scope. Software tests alone cannot close the engineering gate. Do not send files, recruit/message firms or accept professional findings on their behalf without authority.

## What waits, without being removed

- Desktop packaging and platform expansion.
- Additional project categories and large master-planning sites.
- National/local-code automation beyond the first firm's confirmed requirements.
- Advanced utility/hydraulic/foundation capabilities and native intelligent Civil 3D objects beyond verified pilot needs.
- A new sophisticated real-time multiplayer system.
- Unneeded visual polish, speculative AI features or expensive rendering expansion.
- Large-scale infrastructure, public-launch marketing and wider pricing/sales expansion before pilot evidence.

Safety, source honesty, tenant isolation, basic support/terms, recovery and usability do **not** wait. Existing essential features must continue working. Deferred master items retain their original IDs and unfinished status; any pilot need can bring one forward explicitly.

## Working and reporting rules

- Complete each numbered P milestone against its exit checks, then report what changed, why, what passed, what remains and the next work's purpose.
- Ask specific questions before making consequential assumptions. Do not stop for optional details that can safely remain Unknown.
- After each individual change, test the affected behavior. At each major milestone/phase exit, run the broader regression audit and the real website workflow.
- Count skips, flaky recoveries, environment failures and unverified hosted/provider behavior honestly.
- Record pilot-readiness evidence separately from whole-master-phase completion.
- No purchases, deployment, customer-data experiments or external coordination merely because a test passed.

## Immediate next action

Start P1 with the production dependency patch, then zero-input preservation and saved-state reconciliation. Keep existing functionality intact and turn the corresponding audit probes green with meaningful fixes. Do not start a broad new feature build first.
