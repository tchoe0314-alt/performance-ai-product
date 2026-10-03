# Phase 0.4 dependency review — October 3, 2026

This is local advisory evidence, not deployed-artifact or complete security certification. No dependency versions were changed and no paid services were used.

## Verified scope

- `npm audit --omit=dev --json`: zero reported production dependency vulnerabilities.
- Full npm audit: five high-severity affected dependency nodes arising from one advisory, not five independent defects. Installed chain: development-only `eslint-config-next@16.3.8` → `@next/eslint-plugin-next@16.3.8` → `fast-glob@3.3.1` → `micromatch@4.0.8` → `braces@3.0.3` (`npm explain braces`).
- Backend declared requirements: all 61 pinned packages audited with pip-audit 2.9.0, zero known vulnerabilities.
- Installed disposable backend/test runtime at `/tmp/civora-phase0-runtime.gMVYHN/lib/python3.11/site-packages`: zero known vulnerabilities, including its installed transitive packages. This is not the hosted backend environment.
- Optional AI renderer, imagery gateway and vision-training requirements: 13 distinct declared pins audited together, zero known vulnerabilities. `--no-deps --disable-pip` verifies declarations only, not resolved optional-profile transitives or provider functionality.

## Open finding

[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) affects braces through 3.0.3: deeply nested patterns can exhaust the JavaScript stack. The advisory lists no patched version; the currently published braces version is 3.0.3. npm reports no available fix.

The installed dependency path is lint tooling, not a production package. Do not accept untrusted glob-pattern input into lint/build tooling. This scope reduces customer-runtime exposure but does not erase the finding or certify CI safety. Do not force an incompatible package override or claim remediation. Re-audit before release and adopt a published compatible fix when available, with lint/build regression verification. Phase 0.4 retains this finding explicitly pending remediation or a documented release-risk disposition.

## Still required for release

Audit the exact hosted backend environment and final website lockfile/artifact; verify optional provider environments if enabled. Advisory scans cannot prove authentication, authorization, secret handling, upload safety, recovery, or absence of application bugs. Existing tests for those concerns remain separate evidence.
