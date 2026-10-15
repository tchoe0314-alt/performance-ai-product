# Result identity after terrain unit correction

Parent: `7f0b6f97`. ENG result lineage/CAN freshness follow-up.

The terrain metre-to-foot correction changes computed results. The current
coarse calculation build identity is now engineering_core_2026_10_v3. Existing
v2 results remain stored as historical evidence and are unverified when input
geometry matches; they cannot activate through calculation publication. Existing
partial-run protection also prevents inherited v2 checkpoints being recertified
by rerunning only a different discipline. Ordinary bind/load/import operations
do not stamp the new identity. A fresh supported execution is required.

This conservatively invalidates all v2 outputs, including those not known to
use terrain, because the present identity is whole-build rather than per-engine.
No existing data was deleted or migrated and no professional verification is
implied by a current build stamp. Scoped engine dependency identities remain an
architectural follow-up, not a reason to leave wrong-method outputs current.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/version-54.xml`:70 tests passed.
Scope: explicit matching-input v2 freshness/rebind/new-execution invariants,
history retention and nonactivation, design workflow inherited-checkpoint
protection, browser result ownership and project revisions. No live providers,
production/customer data, paid service or deployment used.

Rollback must not make known pre-correction terrain results current again.
Prefer roll-forward or a distinct unverified build disposition, preserving history.
No schema rollback required. Full candidate/backend/browser export qualification,
independent terrain controls and datum alignment remain open.
