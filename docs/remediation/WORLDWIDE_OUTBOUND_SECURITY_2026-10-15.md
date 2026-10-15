# Worldwide-source outbound protection

Parent: `f0fe05f7`. SEC-01 additional outbound-client closure slice.

Confirmed direct request path: worldwide_source_discovery._get_json accepted
configurable endpoint URLs and used automatic requests redirects/unpinned DNS.
It now delegates to the established bounded public-HTTPS pinned transport.
Query parameters and JSON output are preserved. No arbitrary request headers,
ambient credentials or alternate real requests transport are forwarded. Existing
provider error/fallback handling remains responsible for reporting unavailable
sources rather than inventing data. HTTP/private endpoints now fail closed.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/worldwide-46.xml`:
26 tests+13 subtests passed. Scope: original worldwide discovery tests, common
outbound negative/redirect/DNS/timeout tests and new worldwide endpoint/query
checks. All transports were offline fakes; no production/customer data, external
request, paid service, deployment or dependency change used.

No migration or existing source record changed. Rollback is this isolated commit
revert; reverting restores unsafe configurable-endpoint transport and is not an
approved way to support private providers. A separately reviewed private-network
connector would need explicit authorization and a distinct threat boundary.

Remaining outbound inventory includes binary terrain/imagery paths, configured
AI services and operator scripts. This is not a global egress qualification,
dataset licensing approval or engineering accuracy claim. Source attribution and
missing-data behavior remain as tested by existing discovery coverage.
