# Mandatory existing-project full-save revision

Parent: `6283c0dd`. CAN-03/SEC-10 low-level write discipline.

Public save required revision, but ProjectStore.save_project still allowed an
existing-project full overwrite without one. The store now authorizes the actor,
then rejects missing revisions as ProjectRevisionConflict before content writes.
Stale revisions continue to reject. Creation/managed duplication remains allowed
without an existing revision. Server snapshot/chat/public save paths already
supply revisions; real unbound job completion archives instead of full saving.

Sequential compatibility/history fixtures now explicitly supply the revision
of the snapshot they are editing. Numerical/geometry expectations unchanged.
Negative authorization tests still fail at authorization before CAS. The new
negative test requires missing-revision rejection and exact record preservation.

Fresh isolated evidence under the existing verification root/results:
- fullcas-89:155 passes/1 failure, preserved. The editor-collaboration fixture
  omitted a revision despite already reading the shared snapshot.
- fullcas-90:156 passes, one existing httpx warning,5.01s; revisions, fast paths,
  application project/jobs, calculation history, team/collaboration, canonical
  record gateway, browser/import ownership.
- fullcas-91:2 passes,21 dependency warnings,7.06s; named edit-history surface
  and real-firm synthetic end-state workflow, using their original read revisions.
The last two selections do not overlap:158 tests pass. No original audit report
or failed evidence removed; no expected value relaxed to make tests pass.

No schema migration, saved data rewrite, provider, production/customer data,
deployment or paid service used. Existing clients calling the store directly
must now read/retain a revision; there is no unchecked-write escape hatch.
Public browser API already had that requirement.

Open: shell-save low-level mandatory token, alternate-store legacy job fallback,
field-specific result/metadata ownership, PostgreSQL and browser qualification.
This is not all-writer concurrency closure. Rollback is code-only but reopens
the full-save bypass; prefer updating a caller to carry its source revision,
never re-read at the final write merely to manufacture a fresh token.
