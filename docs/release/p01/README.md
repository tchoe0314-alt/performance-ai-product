# P01 — Evidence preservation and static all-feature inventory

Scope: TEST-01, TEST-07, TEST-08 only. No numerical, security, billing, feature-activation, configuration or application changes. This package does not pass a release gate.

Application baseline: `ab7db888e85fb9b6125551ecff769d08e0ca7322`.
Development branch: `codex/remediation-p01-evidence-inventory`.

The eight pre-existing, untracked `docs/remediation/CIVORA_*.md` files were read completely, fingerprinted and left unchanged/uncommitted. P01 has no upstream package dependencies. Its scope and acceptance contract are in `CIVORA_IMPLEMENTATION_BACKLOG.md`, P01, plus the all-feature supplement. No later package is authorized by this work.

## Contents

- `tests/remediation/test_oct15_audit.py`: 24 reconstructed normal assertions. Their current failures are intentionally visible, **not** xfail/skip/expected-success substitutions.
- `tests/remediation/p01_evidence.py`: source scanner, original-function AST extraction, side-effect assertion guard and create-only evidence-bundle writer/verifier.
- `tests/remediation/test_p01_evidence.py`: integrity, guard and inventory tests using newly created disposable directories only.
- `tests/remediation/run_p01.py`: creates a unique evidence run, privately preserves historical test reports, fingerprints inputs and runs the two distinct test lanes.
- `tests/remediation/p01_feature_families.json`: human-curated capability/provider/format map.
- `evidence/<run-id>/`: manifests, JSON/JUnit outcomes, source locators, family inventory, historical hashes/counts, gaps and execution log. Never replace an older run.

## Safe verification runbook

Review the harness and source baseline before running. Use an existing approved Python 3.11+ interpreter; no package install is needed. Do not use pytest against the root application fixtures or start the application. Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/civora-connected-runtime.L1svVb/runtime/bin/python -I -B tests/remediation/test_p01_evidence.py
PYTHONDONTWRITEBYTECODE=1 /tmp/civora-connected-runtime.L1svVb/runtime/bin/python -I -B tests/remediation/run_p01.py --run-id NEW_UNIQUE_RUN_ID
```

The interpreter path is the observed local runtime, not a portability guarantee. Use another explicitly approved existing interpreter if it is no longer available. Replace `NEW_UNIQUE_RUN_ID`; reusing a run ID fails. These commands create only new test/evidence outputs and private archive copies; they do not modify old reports. The combined command **returns 1** when product assertions fail, even if harness-integrity tests pass. Never append `|| true` or treat the harness-green lane as a product-green lane.

The runner requires the eight planning documents and checks the baseline/source hashes. It refuses unexpected application changes or an application revision change. A later P01-only commit is recorded separately from the application baseline. Repair packages will need a separately reviewed candidate-reconciliation extension; P01 does not silently certify later application revisions.

Assertions run with `-I -B` and a Python audit hook blocking network/socket construction, subprocesses, SQLite connections, environment mutations and file writes. Direct imports are restricted by design to reviewed pure engine/document modules; risky runtime/API functions are extracted from their actual AST bodies without module initialization. A21 uses a recording fake session. A11 fixes the synthetic intensity to the audited 4 in/hr. No `.env` values, existing databases, uploads or production records are read. The audit hook is a defense-in-depth test guard, **not a hardened OS sandbox for hostile code**.

Harness unit tests write only under fresh temporary directories; source inventory is read-only. New durable historical archives are outside Git under `../.civora-p01-evidence/`, with restrictive directory/file permissions. Original `/tmp` reports are untouched. Do not publish raw reports without separate privacy review; they can contain test identities or sensitive log text. The first development run used a temporary private archive; later runs use the durable private location.

## Integrity and custody

`manifest.json` lists exact artifact hashes/lengths, source baseline, checkout identity and metadata. `manifest.sha256` is a convenience copy. Verification must use the **separately retained expected digest**, not merely trust the adjacent file. Completion documentation anchors accepted run hashes; committing that record gives Git-history linkage but is not third-party attestation. The verifier rejects source mismatch, altered artifacts/manifests, wrong anchors, extra/missing files, symlinks and unsafe paths. Writer rejects duplicate runs. A partially failed publication must be retained and investigated, not reused.

Local append-only-by-tool files are not WORM storage and cannot stop an administrator rewriting both history and anchors. A protected external artifact store/signing service remains a later governance/operations requirement. No such service was provisioned here.

## Evidence and coverage limitations

The pasted October 15 audit and remediation table are the reconstruction sources. The original complete executable, raw command transcript and independent signed audit were not recovered as standalone artifacts. A01–A24 are reconstruction IDs from the plan, not claimed original executable IDs. Four available historical machine-readable reports are hashed and preserved privately; unavailable originals are recorded, not invented.

The historical browser mismatch remains unresolved: pasted audit `700 / 21 failures / 1 error / 16 skips`; currently available XML `701 / 23 failures / 0 errors / 15 skips`. Neither is accepted as current candidate verification. Backend suite/subtest totals also remain distinct from testcase-node totals.

Numeric oracles come from analytical arithmetic/geometry, structural contracts and the audit's stated expectations. Diagnostic decimal precision reproduces the baseline; it is **not a PE-approved engineering tolerance**. A10 retains the original direct-versus-curve consistency assertion; future P04 acceptance must additionally compare both to the independent integral within approved bounds, not simply make them agree incorrectly. AST checks are not application integration or live security exploitation.

The inventory scans tracked Python/TypeScript/JavaScript source in the listed application/tooling directories and records every discovered route, engine module, frontend entry, environment lookup/reference and matching JSX control. It includes disabled/optional/mock/missing-capability families without enabling them. Effective enablement, authorization, units and side effects are explicitly UNKNOWN where static inspection cannot establish them. Dynamic names/routes, custom interactive tags and runtime composition may be missed; discovered-entry disposition is not 100% feature or test coverage. P20 owns later authorized runtime characterization and interactions.

## Rollback and handoff

No database/schema/model/project migration exists to roll back. If rollback is authorized, revert only P01-owned harness/docs; retain all written evidence and private originals. Never reset the repository, delete audit artifacts or alter pre-existing plans. Independent QA-lead/release-engineer review is still required. PE acceptance, security closure and all product release gates remain open.

P02 and independent P07/P08/P17 lanes may be proposed after P01 review/acceptance; they must receive separate authorization. P10 additionally depends on P02. Stop after this package.
