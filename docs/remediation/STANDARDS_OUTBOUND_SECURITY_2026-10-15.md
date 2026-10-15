# Standards document outbound transport

Parent revision: `81f03b71`. SEC-01 extended outbound-client review.

Confirmed: three standards_discovery fetch paths used direct session.get with
automatic redirects and unpinned DNS. Source trust/allowlisting is not equivalent
to destination/network validation, especially for the general extraction helper.

All three now use the existing public-HTTPS pinned transport, retaining source
policy gates and structured failures. Real requests objects cannot be supplied
as alternative transports. Existing offline fake sessions remain supported.
The common transport adds bounded text mode, charset-aware decoding with safe
fallback, normalized response headers, and final validated URL attribution.
Default JSON behavior is retained. Production connections continue to enforce
DNS/IP/redirect validation, TLS host verification, response-size/deadline limits
and no ambient proxy credentials. Text mode does not increase the2MiB limit.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/standards-45.xml`:
144 tests+13 subtests passed;21 existing dependency deprecation warnings.
Scope: new standards private/loopback/link-local/protocol and size/charset tests,
existing outbound security suite, standards discovery/package and civil-design
readiness tests. No live URL fetched, paid API, production/customer data or
deployment used. No dependencies changed or warnings suppressed.

New independent expectations: prohibited URLs never reach the fake transport;
oversized text rejects; Unicode/declared charset decode correctly; validated URL
is retained rather than trusting a fake response's claimed redirect destination.
Existing standards extraction/allowlist workflow tests remain green.

Limitations: some old HTTP-only sources now fail closed; only HTTPS443 public
sources are supported. Other outbound clients (worldwide discovery, terrain,
imagery and operator-configured providers/scripts) remain separately reviewable.
No global outbound security or deployed egress qualification is claimed. Source
licensing, engineering authority and prompt-injection handling remain distinct.

Rollback is an isolated commit revert with no data/schema migration; it restores
direct-request risk and should not be used to re-enable an unsafe source. Add an
approved HTTPS source or reviewed transport alternative instead.
