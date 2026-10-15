# Public new-project calculation provenance

Parent: `6f2c1a72`. CAN result identity/SEC import boundary.

Confirmed: public creation accepted client-supplied current engine stamps in
latest_result or canonical inline result_v1. Input matching alone does not prove
server execution; a client could copy the current stamp into fabricated output.

Public creation now preserves those result payloads/geometry but removes active
root/final-plan engine stamps, retaining the claim under client_import_v1 with
verified_execution=false. Canonical inline results receive the same treatment.
Loading/persistence cannot restore current status from those claims. Malformed
result/plan metadata returns422 before storage. This boundary is not used by
actual execution or the authorized server-managed duplicate operation.

Fresh isolated reports in the existing verification root/results:
- import-84:70 tests passed, earlier focused run.
- import-85:71 tests passed, final run with real-store save/reopen and managed
  duplication. These selections overlap and must not be summed.

Oracles: exact user geometry/actions retained and original request not mutated;
sidecar/inline imported results unverified; API import remains unverified after
database reopen; trusted synthetic server duplicate retains its method identity
and geometry. Existing save/revision/workflow tests pass. No provider, production/
customer data, paid service, deployment or existing-data migration used.

Compatibility: client-cached calculations saved into a brand-new project now
require a project-bound rerun before method-current engineering export. No
execution receipt exists to authenticate such transient client copies. They are
not deleted. Existing server-managed duplication is the trusted copy path.

Open: signed execution receipts for transient runs, imported approvals/source
confidence and other extension ownership, browser warning/flow qualification,
upload/import-specific endpoints and independent security/engineering review.
This is not universal import validation or full release acceptance. Rollback
reopens stamp forgery and must not be used to recertify client-provided claims.
