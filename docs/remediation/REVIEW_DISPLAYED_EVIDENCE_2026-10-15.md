# Associate review revision with displayed evidence

Parent `618b1438`; CAN-03/SEC-10 follow-up. No release gate closure.

## Evidence and repair

Source inspection showed that `PerformanceAIDashboardView` builds its displayed
candidate inbox from live site inputs and backend result metadata. The review
action previously received only the saved `currentProject`, so its revision alone
did not establish that the selected displayed candidates belonged to that record.
This was a credible state-association risk, not a demonstrated full-browser race.

The view now passes the displayed inbox through the existing action hook. Before
sending, the action rebuilds the saved inbox using the same existing builder and
requires each selected candidate to occur exactly once in both snapshots, with
all JSON evidence fields equal. Object-key ordering is ignored; array order and
candidate field values are preserved. Missing/changed/duplicate candidates block
submission with a save/reload instruction. Matching selections use the original
saved revision; server preconditions and locked comparison remain unchanged.

No geometry/schema/numerical or backend behavior changed. Generated or unsaved
candidate evidence must be saved/reloaded before review instead of being silently
paired with an unrelated saved token. Nonselected candidate differences do not
block a selection; the server still validates the whole project revision.

## Verification

Disposable tracked-source copy under
`/tmp/civora-repair-verification.NBAOtD/identity.9pTtZk/source`.

- `node tests/candidate-review-revision.cjs`:PASS. Evaluates the actual action
  and actual inbox builder. Missing project/token, mismatched project, missing
  selection, changed source, changed confidence and duplicate selected candidates
  issue no request. Equivalent key ordering permits the request, forwards the
  original revision, and server conflict leaves state setters untouched.
- `node node_modules/typescript/bin/tsc --noEmit --incremental false`:PASS.
- Both Node commands executed with OS sandbox denying network and file writes.
- `git diff --check`:PASS.

These are offline behavioral/type checks, not browser E2E or a fresh backend run.
No production/customer data, paid calls or deployment. Prior reports preserved.

## Remaining work / rollback

Complete browser source-change/autosave/review scenarios, usability of the reload
instruction, and PostgreSQL concurrency remain open. Equality validates state
association, not authenticity, source rights or engineering correctness. The
server does not trust browser equality as authorization. Older clients still need
the required revision introduced by the prior commit.

Review/revert this isolated UI change if necessary; no data migration. Reverting
reopens displayed-evidence association risk. Do not bypass by fetching a fresh
token or weakening server revision checks.
