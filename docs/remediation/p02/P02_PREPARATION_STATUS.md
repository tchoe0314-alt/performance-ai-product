# P02 preparation handoff

Date: October 15, 2026. **Internal P01 review and P02 draft/compatibility preparation delivered. P02 formal approval remains PENDING. No release gate passed.**

## Identity and scope

- HEAD before/through execution: `ef22d42c4647e15cd0d6815b9d3816702cf9dbb4` (P01 delivery).
- Application baseline unchanged: `ab7db888e85fb9b6125551ecff769d08e0ca7322`.
- New branch: `codex/remediation-p02-contract-decisions`.
- Pre-existing changes: eight untracked `docs/remediation/CIVORA_*.md` plans. They were not modified, staged or committed.
- P02 additions are uncommitted; no push/deployment. All new files are within the scope recorded in `EXECUTION_SCOPE_AND_PRODUCT_RULES.md`.
- No application/config/dependency, database, customer/project record, numerical method, schema or historical evidence was modified. No external/paid API or real payment was used; no application/browser server started.

## What changed and why

| New files | Purpose |
|---|---|
| `EXECUTION_SCOPE_AND_PRODUCT_RULES.md` | Record the founder's limited internal-review/preparation authorization and no-signing/no-sealing boundary without weakening software correctness |
| `P01_INTERNAL_REVIEW.md` | Reinspect existing harness/expectations and document a self-review verdict with gaps; not independent acceptance |
| `P02_DECISION_RECORDS.md` | Six explicit owner/error/sampling/registration/reproducibility/revision decisions, alternatives, review dependencies and rollback constraints |
| `P02_COMPATIBILITY_AND_MIGRATION.md` | List tested representation arrows, selected migration fixtures, preservation rules and untested boundaries |
| `tests/remediation/fixtures/p02_empty_v1.json` | Hand-authored v1 schema/unknown-unit snapshot |
| `tests/remediation/fixtures/p02_legacy_input.json` | Synthetic metric geometry/source/unknown-extension fixture |
| `tests/remediation/test_p02.py` | 26 isolated compatibility checks; no code repair or numerical engines |
| `tests/remediation/run_p02.py` | New evidence, source/fixture/draft fingerprints and separate P01/P02 result lanes |
| `evidence/p02-preparation-20261015-01/` and `02/` | Separate initial/final results/logs/manifests; original P01 evidence retained unchanged |
| This record | Results, limitations and next authorization boundary |

## Fresh verification

Final command: `PYTHONDONTWRITEBYTECODE=1 /tmp/civora-connected-runtime.L1svVb/runtime/bin/python -I -B tests/remediation/run_p02.py --run-id p02-preparation-20261015-02`.

| Lane | Tests | Passed | Failed | Errors | Skips |
|---|---:|---:|---:|---:|---:|
| P02 compatibility | 26 | 26 | 0 | 0 | 0 |
| P01 harness integrity | 18 | 18 | 0 | 0 | 0 |
| P01 reconstructed product assertions | 24 | 14 | 10 | 0 | 0 |

Combined exit code **1**, intentionally reporting actual unresolved product failures. Do not combine the green compatibility/harness lanes into a false product-acceptance claim. No xfail or skipped assertions. Diagnostic expected values unchanged. No full backend/browser/load/hosted/PE acceptance suite was run.

Final run `02` manifest anchor: `f28ed154ec42c823bf05b6db09a140b8500031dac712361e7c3900824db3203d`.

Initial run `01` is preserved with anchor `0e13d6c39ed5585d3d8bf71e94c3fec83aa7a12fbc17eaeb73f386f60691272f`. It preceded the internal-review result paragraph and runner clarification separating this handoff from test inputs. Run `02` fingerprints the final tests, runner, fixtures and four decision/review/scope documents; all results remain the same. Neither run overwrites the other.

The runner verified all three anchored P01 bundles and protected recorded inputs. This handoff is outcome documentation excluded explicitly from the final test-input hash list to avoid self-referential evidence. No post-run documentation update certifies changed source/harness/fixtures. The initial evidence preserves its own pre-run document hashes rather than silently replacing them.

## What this proves

The selected current Python adapters preserve the authored synthetic geometry/IDs/order/metadata through canonical and JSON roundtrips, retain explicit unknown units/datums, reject tested unsupported versions/malformed references/nonfinite JSON, restore synthetic result facets and preserve tested no-edit history. A static check compares TS/Python section names; it does not execute the frontend.

It does **not** prove every historic project, real database, browser editing flow, concurrency path, transform, engineering calculation or export. Existing numerical/security failures remain open. The static type-definition JSON is repository source loaded by a reviewed pure import, not customer data. The Python guard is not a hostile-code OS sandbox.

## Acceptance and next work

| Criterion | State |
|---|---|
| Internal P01 source/evidence review and fresh checks | Complete within disclosed self-review limits |
| Owner matrix, failure/zero contract recommendation, node/cell/TIN distinctions, registration and migration proposal | Prepared, not implemented |
| Selected v1/legacy/future-version compatibility tests | PASS, 26 methods |
| Preserve original plans/audit/application behavior | Verified in recorded hashes/scope and final working-tree check |
| Named architect/numerical/geospatial/method acceptance | PENDING; none fabricated |
| Full P02 package or independent P01 gate acceptance | NOT CLAIMED |
| Professional certification, signing/sealing or launch readiness | NOT PROVIDED / outside this package |

Next: review the concrete ADR choices, especially typed errors vs structured engine failures; explicit zero/no-catchment policy; fixed-triangle vs bilinear node integration; registration/resampling; supported methods/tolerances. Accept the relevant decisions before numerical implementation. External method review is distinct from Civora signing/sealing; the end-user engineer retains their own project review, but software must still be independently benchmarked for its advertised scope.

P03 would then repair the hydrology result contract and invalid-input handling. It remains unstarted and needs separate authorization; no security or other package began. Rollback for this preparation is new-doc/test-only, retaining written evidence and untouched originals; do not reset user work or remove audit history.
