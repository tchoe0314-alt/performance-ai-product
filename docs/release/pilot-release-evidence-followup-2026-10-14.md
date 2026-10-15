# Pilot release evidence follow-up — October 14, 2026

This is a targeted follow-up, not completion of the connected pilot-to-customers plan.

## Change and reason

Release readiness previously used Python truthiness for imported JSON success flags and hosted configuration flags. Nonempty strings such as `"false"` and numeric `1` could therefore be accepted as passing evidence. These flags now require the JSON boolean `true`. Environment-variable parsing remains unchanged, since environment values are intentionally strings.

The change covers technical evidence success, hosted report success and revision-match flags, hosted support/monitoring/rollback configuration, and hosted backup configuration. Valid boolean reports retain their existing behavior. Regression cases exercise malformed technical and hosted success flags, string-false support configuration, and string-false backup configuration.

## Verification

- Release readiness plus backend startup/combined-runner tests: 42 passed, 18 subtests passed.
- Related readiness, hosted operational evidence, production environment, billing and data lifecycle/backup tests: 92 passed, 24 subtests passed, with 22 dependency deprecation warnings. This overlaps the first test group; counts are not additive. These are scoped regressions, not a new full application audit.
- Targeted diff whitespace validation passed.

## Remaining gates

The live sign-in upstream connection closure still has no verified root cause. Existing local bounded login recovery has not been deployed in this pass. No deployment, purchases, charges, outreach, or hosting configuration changes were made.

The larger plan still needs a clean release checkpoint, complete commercial workflow/performance evidence, current hosted release verification, and real-site engineering/CAD acceptance. Jurisdiction, a rights-cleared pilot site and named reviewers/customer acceptance remain external inputs. Historical hosted restore evidence exists; this pass did not perform a new hosted restore. Synthetic test results are not customer traction or professional design approval.
