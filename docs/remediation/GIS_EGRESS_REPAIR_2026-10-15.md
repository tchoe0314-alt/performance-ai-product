# SEC-01 — GIS outbound transport repair

Implemented a shared bounded HTTPS transport for provider health, geocoding,
online existing-conditions JSON, ArcGIS and USGS sampling requests. The actual
connection uses a validated public IP while retaining the original TLS host.
Every redirect is revalidated. Ambient proxy credentials/cookies are not used.

Controls include protocol/port/header policy, private/link-local/transition
address rejection, mixed-DNS rejection, response size and time budgets, and
bounded resolver threads. Resolver calls already executing cannot be cancelled;
their eight-slot process cap is retained until they finish, so saturation fails
closed. Compressed responses are rejected rather than decompressed without a
budget. Existing fake provider fixtures use an explicit offline transport seam;
real requests sessions cannot be injected through that seam.

Fresh isolated run:59 tests and19 subtests PASS, no failures/skips, covering
online existing conditions, worldwide discovery, provider registry and five
new transport-security tests. The standalone core suite also passed24/24.
Temporary report: `/tmp/civora-repair-verification.NBAOtD/results/egress-08.xml`.
No live requests, production access or paid calls were made.

This closes the reproduced loopback transport path in the affected GIS calls,
not every possible outbound client in Civora. Independent AppSec review,
deployment egress policy, provider response-size qualification and final
release-wide regression remain required. Legitimate oversized/non-HTTPS/
internal providers now fail explicitly; don't bypass the policy to restore
unsupported access. Rollback must retain an equivalent restriction on these
endpoints; simply restoring unrestricted requests would reopen the finding.
