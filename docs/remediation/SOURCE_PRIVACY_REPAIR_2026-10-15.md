# Source integrity and learning containment

SEC-08: all three upload paths now allocate UUID source identities, stage
private complete bytes and publish without replacement. Size failure or a
target collision cleans only the temporary file, not an existing source.
Responses include SHA-256 of stored bytes. Old source filenames remain readable;
no old files were renamed or removed. Parser/resource qualification and
end-to-end hash propagation into every source/export remain separate checks.

SEC-05 containment: learning append boundaries require explicit server-side
consent independently of the payload and global enable flag. Existing callers
do not yet provide qualified consent; collection therefore remains disabled,
even if only the global flag is enabled. This is deliberate containment, not a
completed optional-learning product. Organization restrictions, minimization,
retention/withdrawal and dataset lineage need qualification before enabling it.

Fresh isolated application-upload and learning-store checks pass, including
two same-name uploads retaining distinct original bytes/hash, no partial files
on oversize, and global-on without consent writing nothing. Report:
`/tmp/civora-repair-verification.NBAOtD/results/source-11.log`.
The earlier53-test security run also covered these upload helpers.

Rollback: retain immutable IDs and no-replace publish semantics; do not return
to filename overwrite. Keep learning collection off if rolling back consent
changes. No production data, existing store, source file or deployment changed.
