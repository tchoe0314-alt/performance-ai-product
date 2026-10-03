# Phase 0.4 dependency review — October 3, 2026

This is local advisory evidence, not deployed-artifact or complete security certification. A compatible lint-tool patch was applied at the final 0.4 checkpoint; no paid services were used.

## Final maintainability patch and support disposition

ESLint 9.39.4 was updated to pinned 9.39.5. Its lockfile also resolves newer `@eslint/js`, `@eslint/eslintrc`, acorn and ajv development packages. Production dependencies are unchanged; production-only npm audit still reports zero vulnerabilities. This patch does not resolve the separate braces advisory below.

The registry deprecates ESLint 9.39.5 as unsupported. This is a tracked toolchain-support risk, not a claim that the patch makes the entire toolchain current. ESLint 10 requires Node 20.19+/22.13+/24+, whereas the existing ESLint 9 floor accepts Node 20.9+. The major upgrade and runtime-floor/CI alignment require a separately verified migration; an untested major switch or incompatible Next lint-config downgrade was not forced into this stabilization checkpoint. Reassess before release together with the unpatched advisory. No release-risk waiver is implied.

## Verified scope

- `npm audit --omit=dev --json`: zero reported production dependency vulnerabilities.
- Full npm audit: five high-severity affected dependency nodes arising from one advisory, not five independent defects. Installed chain: development-only `eslint-config-next@16.3.8` → `@next/eslint-plugin-next@16.3.8` → `fast-glob@3.3.1` → `micromatch@4.0.8` → `braces@3.0.3` (`npm explain braces`).
- Backend declared requirements: all 61 pinned packages audited with pip-audit 2.9.0, zero known vulnerabilities.
- Installed disposable backend/test runtime at `/tmp/civora-phase0-runtime.gMVYHN/lib/python3.11/site-packages`: zero known vulnerabilities, including its installed transitive packages. This is not the hosted backend environment.
- Optional AI renderer, imagery gateway and vision-training requirements: 13 distinct declared pins audited together, zero known vulnerabilities. `--no-deps --disable-pip` verifies declarations only, not resolved optional-profile transitives or provider functionality.

## Open finding

Rechecked during the October 3 follow-up: braces is still published at 3.0.3 and the advisory still lists no patch. npm now proposes a semver-major downgrade of `eslint-config-next` to 14.2.35, rather than remediation of braces. That does not establish compatibility with Next 16.3.8 and was not applied. Production-only npm audit still reports zero vulnerabilities. The full development finding remains open; this is not a claim that npm has no suggested change at this later checkpoint.

[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) affects braces through 3.0.3: deeply nested patterns can exhaust the JavaScript stack. The advisory lists no patched version; the currently published braces version is 3.0.3. npm reports no available fix.

The installed dependency path is lint tooling, not a production package. Do not accept untrusted glob-pattern input into lint/build tooling. This scope reduces customer-runtime exposure but does not erase the finding or certify CI safety. Do not force an incompatible package override or claim remediation. Re-audit before release and adopt a published compatible fix when available, with lint/build regression verification. Phase 0.4 retains this finding explicitly pending remediation or a documented release-risk disposition.

## Still required for release

Audit the exact hosted backend environment and final website lockfile/artifact; verify optional provider environments if enabled. Advisory scans cannot prove authentication, authorization, secret handling, upload safety, recovery, or absence of application bugs. Existing tests for those concerns remain separate evidence.
