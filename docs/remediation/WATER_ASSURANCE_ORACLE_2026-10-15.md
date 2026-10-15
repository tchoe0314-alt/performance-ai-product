# Water internal assurance oracle reconciliation

Parent: `f608dd14`. ENG-06/TEST-02 regression-oracle integrity.

The internal assurance crosscheck still repeated the former double conversion
and expected2.419psi after the engine was corrected to5.587psi. This would reject
corrected output while accepting the original unit defect. The expected value
is now an explicit5.587psi fixed oracle for75GPM/2in/C130/100ft, with a correctly
named GPM/inch pressure reference. Absolute tolerance remains1e-9; it was not
loosened. Independent EPA feet/cfs formula comparisons remain separate tests
documented in WATER_PRESSURE_UNITS_2026-10-15.md.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/assurance-74.xml`:13 tests passed,
21 existing dependency warnings. Includes assurance/interoperability tests and
independent water-unit comparisons. New negative test injects the old2.419psi
implementation result and requires both water check and aggregate assurance to
fail while preserving independent_external_review=false. No reference result
was changed to match an incorrect engine and no original audit evidence replaced.

No provider, production/customer data, paid service or deployment used. Fixture
pressure acceptance remains open; this intervening oracle correction was found
while tracing that workflow. Internal checks are not independent professional
acceptance. Rollback of oracle alone would restore stale unit expectations and
should only accompany an explicitly reviewed change of numerical contract.
