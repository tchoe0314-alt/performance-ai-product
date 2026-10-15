# Server snapshot metadata compare-and-swap

Parent: `5c8fa735`. CAN-03/SEC-10 metadata-only lost-update risk.

Confirmed: design/result revisions intentionally exclude metadata. A delayed
server snapshot could pass both checks after newer review metadata committed,
then overwrite that newer metadata in a full save. Workflow-specific merge
protection did not cover arbitrary review/evidence keys.

Added an independent deterministic metadata revision. The server snapshot helper
and chat-memory writer supply it; ProjectStore checks it while holding the same
write lock as design/result checks, before content merge/persistence. Changed
metadata produces the existing conflict/retry disposition. Current snapshots
still update metadata normally. This does not turn metadata edits into geometry
revisions or rewrite saved records. No schema migration required.

Fresh isolated reports in the existing verification root/results:
- metadata-81:88 tests passed,1.13s; revision races/snapshots, project/job workflows.
- chat-82:85 tests+10 subtests passed,0.70s; chat workflow regressions.
Selections do not overlap. New test proves geometry revision unchanged by the
new review metadata, then requires stale snapshot409 and exact record
preservation. Separate positive test permits current snapshot metadata change.
No provider, production/customer data, paid service, deployment or original
audit evidence mutation used.

Remaining: mandatory all-writer enforcement, public metadata ownership/permissions,
scoped patch semantics, PostgreSQL execution and independent concurrency/AppSec
qualification. The low-level optional token remains for legacy callers; this
does not claim complete CAS closure. Rollback is a code revert with no database
rollback but restores stale review-metadata overwrite in these server paths.
