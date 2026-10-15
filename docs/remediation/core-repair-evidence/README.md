# Focused repair evidence

Create-only runs from `tests/remediation/run_core_repair_checks.py`; older P01,
P02 and follow-up results remain unchanged. The report records the exact source
commit, working-tree status and aggregate Python-source fingerprint. A later
commit does not inherit certification merely because it contains this report.

`core-20261015-01`:90 checks PASS across24 reconstructed audit assertions,
24 core analytical/security regressions and42 compatibility/session/transport/
numerical/fake-email checks. No skips. Manifest SHA-256 anchor:
`f953e2f26f75bae0641fe3b4f594d2c5579e0f9f41780177c276c74689866747`.

Source identity: `64e1fdf6` plus the explicitly fingerprinted new test harness
and the working-tree state recorded in the manifest. Original expected audit
values were not changed. Local hashes are tamper-evidence, not third-party
attestation, WORM storage, PE approval or a launch gate. Separate ASGI/identity
and broad backend results are not silently combined into these90 checks.
