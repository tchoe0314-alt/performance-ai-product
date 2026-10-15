# Shell saves require a source revision

Parent revision: `127530a0`. Incremental CAN-03 / SEC-10 repair, not release acceptance.

`ProjectStore.save_project_shell` rejects missing revisions after authorization
and before mutation. Full saves already require a revision. No unchecked bypass
was added. Result preservation and locked revision comparison remain.

Regression checks complete record preservation on rejection for both save methods.
Positive fixtures carry their synthetic actor's source token. A stale autosave
after candidate review now expects HTTP409 while retaining review-integrity
assertions. No production caller rereads a token merely to bypass a conflict.

## Isolated verification

Network/subprocess-denying Python guard; disposable source and SQLite under
`/tmp/civora-repair-verification.NBAOtD`; no customer data, paid calls or deployment.

- `results/shellcas-92.xml`: 158 passed, 2 failed (fixture preconditions missing).
- `results/shellcas-93.xml`: 159 passed, 1 failed (stale fixture expected success).
- `results/shellcas-94.xml`: **160 passed**, 21 dependency deprecation warnings,
  7.65 seconds. Failed reports preserved unchanged.

Ten affected modules cover revisions, fast paths, canonical gateway, history,
atomic exports, direct calculations, project/job workflows, browser result ownership
and import trust. No numerical oracle changed. `git diff --check` passed.

## Limits and recovery

Not a fresh full-suite/browser/PostgreSQL qualification. Other metadata writers,
model ownership, payload growth and independent engineering acceptance remain open.
Two previously recorded looped-water production tests remain unresolved.

Callers omitting source revisions now intentionally conflict. Carry the original
read token rather than fetching a fresh token to force a write. No schema migration.
Reverting this isolated change requires review and reopens unchecked shell writes.
