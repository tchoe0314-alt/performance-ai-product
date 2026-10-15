# Server checkpoint precedence

Parent: `e9692b06`. Related findings: CAN-02/03 and engineering input lineage.

Confirmed defect: prepare_reactive_orchestration_payload selected client resume
aliases before its explicitly supplied server checkpoint. setdefault then kept
the old client plan and stage statuses, even when the saved project differed.
An explicitly empty server plan could also fall back to a fabricated client plan.

Repair: when the server-checkpoint argument is supplied (including an empty
dictionary), remove client runtime_resume aliases, top-level final_plan and
previous partial-rerun/checkpoint flags before selecting a checkpoint. The server
plan becomes authoritative. Full requests do not inherit those client snapshots;
focused requests with no server checkpoint do not invent one. Unrelated controls
and explicit standalone helper behavior with no server argument are preserved.
The input request is detached and not mutated. No numerical methods changed.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/checkpoint-42.xml`:
84 tests and5 subtests passed across new conflicting/empty/full checkpoint cases,
queue ownership, design/job application workflows and canonical canvas gateway.
No production/customer data, external APIs, deployment or payments used.

Remaining: this establishes helper/queue precedence, not complete job lifecycle
snapshot isolation, direct standalone API trust, source freshness qualification,
all-writer concurrency or approval of inherited engineering stages. Old saved
client checkpoints are not deleted by this change. Broader qualification remains
required; no release or engineering-grade claim follows from these tests.

Rollback: revert this isolated commit; no data/schema rollback required. Doing
so restores unsafe client precedence, so retain equivalent protection before
exposing project-bound partial reruns.
