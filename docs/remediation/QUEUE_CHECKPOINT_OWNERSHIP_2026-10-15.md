# Queue checkpoint ownership

Parent: `c2a62b82`. Finding CAN-04: execution payload copied into editable state.

Confirmed cause: queue_orchestrate_job prepared a reactive payload containing
the latest final plan under multiple resume/checkpoint paths, then used that
expanded execution payload both as editable project input and request_payload.
Canonical adapters can additionally mirror those controls. This is not necessary
to run the queued job and makes editable input depend on output size.

Repair: detach the original editable request before checkpoint preparation.
Seed the project/request snapshot from that original, while submitting the full
prepared execution payload to the job queue unchanged. User geometry, controls,
sources, original request values and existing stored result remain intact.
The updated existing test formerly expected execution checkpoint duplication;
it now independently checks that execution still receives the checkpoint while
saved editable meta equals the original request, rather than encoding the defect.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/queue-41.xml`:64 tests passed,
covering the queue regression, application jobs, calculation history and store
fast paths. The new fake-store boundary test runs100 submissions with a100KB
synthetic checkpoint: serialized editable inputs stay constant below1000bytes,
while both job checkpoint locations retain the complete expected plan. This is
a boundary/ownership measurement, not a database or full lifecycle load test.

No existing data was cleaned, migrated, compressed or deleted. No numerical
assumptions, job resume semantics, production, customer data or paid services
were changed/accessed. Rollback requires only reverting this commit; it restores
the duplication risk but requires no schema rollback.

Remaining: callers may already supply embedded execution snapshots; existing
saved snapshots are deliberately retained; job/result/history payloads can still
duplicate ancestors. This does not establish the medium5MiB budget,100 complete
apply/undo/reopen cycles, worker RSS bounds or immutable checkpoint-reference
storage. Those require further scoped changes and measured realistic fixtures.
