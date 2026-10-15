# Numerical repair batch — not a release certificate

## Implemented

- ENG-01/02: authoritative `total_runoff_cfs` contract, explicit engine input
  rejection, no silent missing-field zero, and tagged planner assumptions.
- ENG-03: exact expanding rectangular-basin integral shared by every stage;
  bounded implicit routing with interval continuity quantities and explicit
  rejection beyond the supplied storage domain. Not a backwater/overflow solver.
- ENG-04/05: shared node-triangle versus explicit constant-cell integration,
  zero-crossing cut/fill partitioning, domain/registration comparisons, and
  rejection of ambiguous, incomplete or unsupported clipped/rotated grids.

Numerical convention: nodes bound cells; fixed lower-left to upper-right
triangle diagonal defines the supported piecewise-linear surface. Explicit
cell-value arrays integrate their stated full cells. This is not an assertion
of bilinear, arbitrary TIN or clipped-boundary equivalence. Missing registration
does not establish a surveyed CRS/datum; explicit mismatches are rejected.

## Compatibility and rollback

Existing contradictory hand-built whole-cell fixtures now explicitly identify
`sampling="cells"`; their domain-volume expectations remain unchanged. TIN
comparison totals use independently integrated node-domain values, not the old
overcount. The previously undersized detention fixture remains a negative case
in the new core regression suite; positive routing uses sufficient capacity.

Saved data and audit evidence were not rewritten. Consumers of unsupported or
ambiguous grids must supply a reviewed conversion rather than bypass validation.
Reverting code must not relabel post-change results as old-method verified;
calculation method identity and re-execution remain required for safe release.

## Fresh checks on the working candidate

- Original reconstructed audit assertions:24/24 PASS, expectations unchanged.
- New core analytical/security checks:24/24 PASS, including numerical-overflow
  bounds. These span additional uncommitted security work, not this batch alone.
- P02 synthetic compatibility tests:26/26 PASS.
- Isolated targeted integration run:193 PASS,21 dependency deprecation warnings,
  no test skips. Includes GIS, readiness, deliverables, LandXML, calculation
  history, exports, revision conflicts and existing numerical/TIN tests.
  Temporary report: `/tmp/civora-repair-verification.NBAOtD/results/target-07.xml`.

The integration run used a source copy, synthetic storage, disabled providers
and a Python audit guard blocking network/subprocess/outside writes. It is not
an OS security boundary. It included other working-tree repairs; the numerical
commit is not claimed to reproduce all193 checks without those pending changes.

Full backend/browser acceptance, independently reviewed hydraulic methods,
general supported-engine benchmarks and production verification remain open.
No deployment, package installation, customer-data operation or paid call.
