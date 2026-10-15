# Browser candidate-review preconditions

Parent `a336b5aa`; CAN-03/SEC-10 follow-up, not release acceptance.

## Gap and implementation

The review workflow previously captured a revision only when the server read the
project. It could therefore apply a browser decision after a source change the
reviewer had not seen. The public payload now requires a 64-character hexadecimal
`expected_revision`. The workflow compares it with its authorized read before
decision computation; the existing locked comparison still protects in-flight
changes. Stale requests return409 without persisting anything.

The actual UI action sends the loaded `ProjectRecord.revision_token`, never fetches
a fresh token merely to submit, and blocks missing tokens/project-ID mismatch.
On conflict it reports the error and does not update local project/result state.
Legacy trusted in-process workflow callers may omit the optional argument; they
retain the server-read plus locked comparison, not browser-snapshot protection.

## Evidence

Guarded disposable source/SQLite under `/tmp/civora-repair-verification.NBAOtD`.
No production/customer data, external requests, deployment or spending.

- `results/candidate-browser-101.xml`:80 passed/1 failed; a conditional local
  exception import shadowed the existing exception handler. Fixed import only;
  original report preserved.
- `results/candidate-browser-102.xml`:81 passed,2.64s. Includes stale-before-request
  API rejection with exact record preservation, current-revision success, malformed
  payload rejection, in-flight and simultaneous changes, revisions and fast paths.
- `results/candidate-browser-103.xml`:12 passed,21 dependency deprecation warnings,
  2.87s. Route forwards source token and all correction fields.
- Offline `node tests/candidate-review-revision.cjs`:PASS. Transpiles/evaluates the
  actual action with an injected API stub; checks missing/mismatched project
  rejection, exact token forwarding and no state changes after conflict.
- TypeScript `--noEmit --incremental false`:PASS.
- Node checks used an OS sandbox denying network and all file writes.
- `git diff --check`:PASS.

The two Python suites are non-overlapping (93 cases). These do not constitute a
complete browser/server journey or current full-suite acceptance.

## Open scope / compatibility / rollback

Older browser/third-party clients must send their original loaded revision or are
rejected422; use coordinated deployment only after release approval. No deployment
performed. Source association for transient/generated inboxes and rapid UI state
changes still need full-browser acceptance. Standalone inbox readers currently
need the project record's revision. PostgreSQL concurrency remains unverified.

No schema migration. Roll back this isolated commit only with review; removing
the public precondition reopens stale-before-request decisions. Do not replace
the token by a just-in-time server read to make requests pass.
