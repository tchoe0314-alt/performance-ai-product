# Existing-project browser metadata ownership

Parent: `52f77cf1`. CAN-03/SEC-10 public autosave boundary.

Inspection: useDashboardProjectSave submits only auto_named/auto_file_named
metadata, but public existing-project saves accepted arbitrary metadata keys.
That permitted a stale echo to overwrite newer server review/recovery/policy
metadata without changing the design revision. Server snapshot CAS alone does
not protect client-supplied arbitrary records.

Existing-project public saves now admit only the two boolean naming preferences.
Other echoed metadata is ignored and existing stored values remain intact;
nonboolean naming flags reject422 before persistence. Dedicated server review,
metadata patch, recovery and workflow operations are unchanged. No stored
custom metadata deleted. New-project/import/copy metadata behavior is unchanged
and remains a separate trust boundary requiring review. This is not universal
metadata authorization closure or protection for all project_input extensions.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/browsermeta-83.xml`:66 tests passed,
1.50seconds. Real-store public-save tests prove newer review evidence and server
calculation facets survive stale/fabricated client echoes, boolean false remains
editable and stale revisions conflict. Four invalid flag forms reject before
persistence. Related public-save preconditions, revisions and application project
workflows pass. No production/customer data, provider, paid service or deployment.

Open: new-project/import trust, dedicated metadata namespace/role model,
all-writer enforcement, PostgreSQL execution and browser release qualification.
Rollback is an isolated code revert without schema changes, but restores the
arbitrary-client metadata overwrite path. Do not widen allowed keys without an
explicit client-owned schema and concurrency/authorization tests.
