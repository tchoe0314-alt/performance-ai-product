# Credential-bearing detector POST redirects

Parent: `52d4ec87`. SEC outbound-provider follow-up.

Roboflow JSON/query and generic detector POST calls used requests' implicit
redirect behavior. A redirect could forward request content to a new destination;
credential-bearing JSON/query data and source references require explicit bounds.
All three now send allow_redirects=False and reject non-integer/non-2xx status
before parsing JSON. requests.raise_for_status alone does not reject3xx. Error
messages are generic and do not include credential-bearing endpoint URLs.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/provider-65.xml`:
47 tests passed, one existing httpx warning. New21 cases cover3 provider modes
against301/302/303/307/308/401/500: exactly one POST attempt, redirects disabled,
response body never parsed. Existing successful provider detection tests retain
positive coverage and now explicitly assert redirects disabled in their fakes.
No live providers/credentials, production/customer data, deployment, charges or
payments used. Existing actual provider response schemas remain unchanged.

Open: configured endpoint trust/pinning and tenant data-sharing policies,
response-size budgets, retries/time limits, provider error sanitization beyond
this boundary and deployed egress/AppSec review. This is redirect containment,
not global provider security or AI correctness qualification. Providers requiring
redirects must be configured at their final approved endpoint; no insecure retry
fallback is provided. Rollback is a code revert without schema/data migration,
but would restore credential-forwarding risk.
