# Revision protection — incremental repair

Public existing-project saves now require a revision; omitted revisions return
409 and the existing browser conflict workflow offers copy/reopen/replace.
New-project creation remains possible. Role checks and stale-token rejection
remain at the normal persistence boundary. No production configuration changed.

Chat actions, chat summary writes, source context, PDF updates and metadata
fallback saves now carry both original design and result revision checks. The
shared snapshot boundary derives a precondition even for old records lacking
an explicit revision token. Delayed chat actions return409 rather than silently
replacing newer geometry; summary conflicts are reported as not saved.

Fresh isolated integrity run:201 tests and10 subtests PASS, including actual
SQLite races, delayed chat snapshots, imports, export history and public-save
preconditions. Report:
`/tmp/civora-repair-verification.NBAOtD/results/integrity-13.xml`.

This is not universal CAN-03 closure: low-level legacy save entrypoints still
accept optional revisions, the job compatibility fallback and client-supplied
result replacement need further restriction/qualification, and PostgreSQL
concurrency has not been exercised here. Preserve these open obligations.
Rollback must retain equivalent write preconditions; do not disable conflict
checks or blindly retry old engineering snapshots. No stored project rewritten.
