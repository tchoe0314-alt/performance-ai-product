# Refresh route-producing summaries after coordination

Parent `bcaa7601`. ENG-06 / CAN-02 follow-up. No release approval.

## Root causes from retained integration failures

The strict takeoff check exposed stale producer data, not a reason to relax
quantity reconciliation. Guarded synthetic diagnostics127 showed pre-coordination
changing storm paths/depths without refreshing hydraulic and length aggregates.
Storm recomputation also rounded individual lengths to1decimal while aggregating
unrounded values. Utility recomputation refreshed route geometry but not each
record's cached length; water enrichment could prefer a stale derived list over
the current conflict-hook route list.

## Repairs

- Storm pre-coordination changes invoke existing storm recomputation after
  publishing the detached changed state, refreshing lengths/slopes/hydraulics.
- Storm segment lengths use existing3decimal canonical precision, with published
  aggregate length equal to the sum of published segment measurements.
- Utility recomputation refreshes each route length from its accepted path before
  aggregating, not only the top-level total.
- Water enrichment uses accepted conflict-hook routes before older derived views.
- Buildv11 keeps prior calculations historical/unverified; no recertifying import
  or migration, no stored-data modification.

This is propagation/representation consistency, not approval of reroute choices,
hydraulic assumptions, depths or civil-engineering criteria. No quantity comparison
or existing integration expected result was weakened.

## Evidence

Disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`, guarded
against outside writes/network/subprocesses. No production/customer data or paid calls.

- Prior `quantity-planner-124.xml`:15 passed/6 failed, preserved.
- `producer-diagnostic-127.log`:trace of stale producer values.
- `producer-diagnostic-128.log`/`129.log`: quantity consistency restored in the
  synthetic manual plan; refreshed storm hydraulics now expose tailwater surcharge.
- `producer-130.log`:harness initialization error, duplicate AnyIO registration
  because auto-discovery was not disabled. No tests ran; no XML certificate.
- `producer-131.xml`: **130 passed**,21 dependency deprecation warnings,3.62s.
  Actual manual-plan quantity consistency, stale water-view precedence, primitive,
  polygon/route/unit regressions, coordination, versions/exports and cost.
- `producer-planner-132.xml`: **15 passed / 6 failed**,21 dependency deprecation
  warnings,107.10s. The original manual success cases still fail; quantity
  consistency is now covered by the passing direct integration regression, but
  refreshed hydraulic evidence produces unresolved manual storm completeness/
  backwater failures. This is not a clean planner acceptance result.
- `git diff --check`:PASS.

## Remaining limitations / recovery

The original synthetic success workflow's storm backwater/surcharge is not waived.
Looped-water solver acceptance also remains open from earlier evidence. Supported
hydraulic design, corrected independent positive fixtures and PE review are still
required. Full browser/PostgreSQL/all-engine acceptance is not established.

Storm recomputation now runs after pre-coordination changes, adding necessary
work. Existing bounded/truncated stage snapshots are a separate architectural risk.
Additional producer fields/scopes and per-engine version identity remain open.

Rollback:review/revert this isolated change, no schema migration. Retain distinct
engine identity and old results as historical. Reverting reopens stale route
propagation and can again hide hydraulic invalidity; do not disable validation to
recover a green test. No release gate passed.

Progress:0/5 release gates approved (0%), not coding completion.
