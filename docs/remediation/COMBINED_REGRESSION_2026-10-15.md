# Combined remediation regression checkpoint

Tested source revision: `de0a0149f1059c3976cccb1b5cf47f2ce88609c7`.
Original worktree clean before and after tests. This document adds evidence only.

Fresh results in `/tmp/civora-repair-verification.NBAOtD/results/`:

| Run | Result | Scope |
|---|---|---|
| combined-43 | 244 tests +65 subtests passed,5.39s | Numerical contracts, raster/unit contracts, model adapter validation, outbound HTTP, shared abuse limits, sessions, invitation proofs/enrollment/recovery, browser result ownership, candidate review conflict, queue/checkpoint precedence, unbound job archiving, calculation history, revisions and project/job/design application workflows |
| boundaries-44 | 61 tests passed,1.19s | Account support, release safety, file/upload workflows, chat learning and vision learning |

These two test selections do not overlap. They establish305 passing tests plus
65 passing subtests for the stated scopes, not a repository-wide pass rate.
Each run records one existing FastAPI/Starlette httpx test-client deprecation
warning. No dependency was installed or changed to suppress it.

## Reproduction and isolation

Tracked files were copied from the clean candidate with git ls-files/rsync into
`/tmp/civora-repair-verification.NBAOtD/identity.9pTtZk/source`.
The Python runtime was the existing disposable3.11 runtime at
`/tmp/civora-connected-runtime.L1svVb/runtime/bin/python`.
Each invocation used env-i, explicit temporary storage, blank DATABASE_URL,
providers disabled, bytecode/cache generation disabled and a fresh pytest
basetemp. The previously reviewed sitecustomize guard denied external network,
subprocesses and writes outside the owned verification root. All database and
file mutations were synthetic and isolated. No production/customer data, paid
API, deployment, real payment or existing user database was used.

Run43 explicitly selected remediation tests excluding original audit baselines,
P01/P02 evidence coordinators and their self-audits. It additionally selected:
test_calculation_history, test_project_revision_conflicts,
test_application_job_workflows, test_application_design_workflows,
test_application_project_workflows and test_project_store_fast_paths.
Run44 selected test_api_account_support, test_chat_learning_store,
test_api_release_safety, test_vision_detection_learning and
test_application_file_workflows. The original failing audit assertions/reports
remain unchanged; these are fresh regression results, not replacement evidence.

Run43 SHA256:
- XML: `babb6e69db702bca39621567000b181253845e1f9a23f663f024d9808641d892`
- Log: `b201ffc2276dcd9ca8453dcf157c7b84878e5e1b408a9713b712299d40c8004b`

## Gate disposition

No release gate passed. Full backend/browser suites on the final frozen release,
PostgreSQL concurrency, all advertised engineering families, independent
analytical/reference qualification, external engineer/security acceptance,
deployment identity, restoration/performance and commercial/legal requirements
remain open. Earlier browser results apply only to their documented source and
scope, not automatically to this candidate. Temp reports must be preserved for
final packaging; hashes alone are not substitutes for their contents.
