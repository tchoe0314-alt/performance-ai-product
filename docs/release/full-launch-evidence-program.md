# Civora Full-Launch Evidence Program

This program covers engineering validation, source infrastructure, meaningful-change confirmation, whole-product reliability, external readiness, and real-project validation. Product-contract and data/privacy work are intentionally tracked separately.

Run the fail-closed aggregator from the repository root:

```bash
python3 backend/scripts/run_full_launch_readiness.py
```

The command writes `reports/release/full-launch-readiness.json`. Missing files or incomplete records remain blockers. Automated success never fills in external evidence.

## Required Inputs

- `rc1-engineering-validation.json`: ten or more deterministic scenarios, eight or more real-file fixtures, and no failed expected-versus-observed comparison.
- `source-infrastructure-evidence.json`: queryable source inventory, market coverage, traceability proof, missing-source behavior proof, and an accepted source-rights review.
- `major-change-confirmation-evidence.json`: browser and contract evidence for detected-condition acceptance, standards changes, major fixes, reroutes, protected deletion, affected-system regeneration, and review-package creation.
- `rc1-evidence-manifest.json`: exact-revision backend, frontend, security dependency, real-file engineering, browser, cross-device, concurrency, and hosted evidence.
- `hosted-operational-evidence.json`: the exact revision and at least two passed authenticated workflows.
- `external-readiness-evidence.json`: dated, owner-attributed HTTPS evidence for professional review, source rights, security, incident response, support, recovery, insurance, legal, and billing gates.
- `real-project-validation.json`: at least three independently reviewed real site-development projects on the exact revision, including input hashes, tolerances, observed results, reviewer qualification, and disposition.

Start from the blank JSON files in `docs/release/evidence-templates`. Copy completed records into `reports/release` or `reports/validation`; do not place passwords, API keys, session tokens, private customer files, or other secrets in evidence JSON.

## Evidence Rules

1. Evidence is revision-bound and becomes stale when software changes.
2. Credentials, tokens, passwords, private keys, and cookies must never appear in reports.
3. A URL alone is insufficient; external evidence also needs an accountable owner and date.
4. Real-project comparisons must record expected values, observed values, tolerances, and pass/fail disposition.
5. Missing provider data must remain missing. It must not be replaced with inferred success.
6. Full-launch readiness is a product and operational gate. It is not construction authorization or professional approval.
7. The evaluator rejects stale evidence, duplicate project IDs, out-of-tolerance comparisons, revision mismatches, and confirmation claims without integration and browser proof.
8. Sensitive-looking keys are redacted from generated reports as a final safeguard.

## Recommended Execution Order

1. Run RC1 engineering validation.
2. Refresh source inventory and rights evidence.
3. Run major-change confirmation browser coverage.
4. Run the revision-bound RC verification suite.
5. Run hosted operational evidence twice with credentials supplied only through environment variables.
6. Attach external owner evidence.
7. Complete three real-project comparison records.
8. Run the full-launch aggregator and resolve every blocker.
