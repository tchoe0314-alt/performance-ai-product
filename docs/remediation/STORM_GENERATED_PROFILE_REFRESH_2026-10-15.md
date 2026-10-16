# Refresh generated hydraulic profile views

Parent `246bfe24`; CAN-02/ENG-06 follow-up. No release gate approval.

## Reproduced defects

Storm enrichment recalculated per-pipe evidence but populated root HGL/EGL views
only if absent. A second calculation after raising segment inverts retained the
old displayed profiles. Removing all segments likewise left old generated rows.
Both new regression cases failed before the repair; input immutability is required.

## Repair and ownership boundary

Capture the prior generated evidence before recalculating. Root profiles matching
that prior evidence are identifiable cached views:replace them with current rows,
or clear them when current evidence is unavailable. Empty views populate normally.
Unrecognized/provided profiles are retained exactly, marked `provided_unverified`,
with a separate explicit path to the current calculated evidence. They are not
silently overwritten or promoted to engineering truth. No profile-history pruning
or original source-input mutation.

The new `hydraulic_profile_views` metadata distinguishes generated-current,
unavailable and provided-unverified views. It is provenance/freshness, not proof
of hydraulic accuracy. Full frontend treatment of provided-profile state and
ownership of old records without generated evidence remain open. Other cached
hydraulic summaries/nodes also require separate propagation verification.

No formula/design tolerance changed. Buildv15 marks older results historical/
unverified until actual execution;v14 is added to historical-version regression.

## Evidence

Guarded disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`;
no production/customer data, external/paid requests, deployment or configuration change.

- `results/profiles-166.xml`:2 failed, stale generated views reproduced.
- `results/profiles-167.xml`: **448 passed /81 subtests**,22 dependency deprecation
  warnings,7.89s. All remediation, including original24 audit cases, new freshness,
  provided-source preservation, unit/source, security and persistence checks.
- `results/profiles-depth-168.xml`: **26 passed /3 failed**,21 warnings,4.79s.
  Unchanged looped-water pressure/fire-flow and manual storm-export expectations
  still fail. Other4 of the earlier7 engineering failures were not rerun here;
  none are claimed closed. Failed reports preserved, no oracle weakened.
- Selections overlap; do not sum totals. `git diff --check`:PASS.

## Recovery / remaining requirements

Branched storm method, looped water, independent reference/reviewer acceptance,
browser/state interpretation, PostgreSQL and full candidate regression remain
required. Review/revert this isolated commit if needed;no schema migration. Keep
engine identifiers distinct and previous results historical. Reverting reopens
generated-view staleness;never replace expected elevations to match old output.

Progress:original reconstructed audit24/24 (**100%**);release0/5 gates (**0%**).
Overall implementation completion remains unmeasured, not100%.
