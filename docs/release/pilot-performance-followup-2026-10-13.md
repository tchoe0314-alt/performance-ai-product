# Pilot performance and release-evidence follow-up

October 13, 2026. Local candidate only; no deployment or professional acceptance.

## Implemented

1. Conflict detection prepares each sampled path once and each system-pair rule once per detection call. Previously both were repeatedly prepared inside the pair loop. Candidate order, distance calculations, clearance thresholds, conflict records and rollback remain unchanged. Cache lifetime is one call, so later candidate edits cannot reuse stale geometry. The six-segment regression proves six sampling calls rather than 21, one rule lookup rather than 15, exact expected conflict pairs, unchanged inputs and fresh checks after moving a segment.
2. Commercial benchmark revision identity now includes a dirty flag for tracked or untracked working-tree changes. Independent-review acceptance fails closed for dirty or unknown checkpoints, even if supplied evidence matches that label. A clean identifiable commit remains required. Tests explicitly distinguish clean synthetic review evidence, dirty/unknown rejection and tracked/untracked changes. No changed paths or confidential contents are published by this flag.

## Verification

- Coordination/conflict/isolation/state/quantity suites: 45 passed, four subtests passed, 21 dependency deprecation warnings, 2.26 seconds.
- Manual-mode and final preparation-cache suites: 23 passed, 21 warnings, 81.51 seconds.
- Benchmark acceptance and preparation-cache suites: 15 passed, 21 warnings, 0.86 seconds.
- These overlap: 77 distinct affected backend cases, not 83 or a new full-backend regression.
- The heavy assisted/manual case passed separately before the edit (56.87 seconds total) and after it (55.71 seconds total; 55.20-second test call). One sample per condition, overlapping diagnostic activity and normal timing variance preclude a meaningful speedup or capacity claim. Candidate evaluation/recomputation remains the larger performance issue.
- Ran the actual commercial-pad benchmark with paid AI/image providers disabled: automated checks passed, no failed comparisons, independent review pending, construction acceptance not granted. Evidence: `/tmp/civora-commercial-benchmark-followup-20261013.json`. Revision is correctly marked `df0443298b4846e6e4b1858043106450e3055e80-dirty`, not a clean release.
- Firefox bounded launch probe timed out after 10 seconds before website assertions, reporting sandbox-extension and SWGL framebuffer failures. The owned browser exited; sandbox protections were not disabled. Firefox remains unverified.
- Read-only hosted checks: current configured API `/api/health` returned 200; unauthenticated `/api/projects` returned 401. Public web release identity remains `ee2055de42b3561eab8822257f911c2dfb693e26`. The older Railway hostname from deployment docs returned 404; that is not evidence of failure of the configured API. These simple checks do not prove authenticated tenant separation, worker recovery, artifacts, hosted backup restoration or deployment of this candidate.
- `git diff --check` passed. No frontend source changed in this pass; the previous browser/build evidence is not presented as a new whole-website retest.

## Still required

Performance remains open: establish representative supported pilot limits and improve candidate recomputation with equivalence checks; this small cleanup alone does not close P5. Firefox needs a functioning test environment or a founder-approved supported-browser limitation. Isolate and verify a clean release checkpoint from the inherited dirty working tree, then run hosted authenticated, worker/artifact and isolated recovery checks before seeking deployment approval.

External engineering/CAD acceptance requires a real site/jurisdiction and authorized qualified reviewers. The automated benchmark cannot replace them. Broader recorded requirements, detailed CAD reuse and the complete commercial calculation/pricing workflow remain as documented in the previous reports.

No purchases, paid provider calls, production writes, deployment, external messages or whole-tree commits occurred. Existing user changes were preserved.
