# Stop terrain sampling after provider failure

Parent: `284881a9`. Resource/latency follow-up.

After incomplete surfaces were made unavailable, sampling still continued after
a missing tile, potentially repeatedly fetching the same failing tile across
thousands of samples. The provider now returns unavailable immediately on the
first missing tile. Valid completed surfaces are unchanged; no gaps are filled.

Fresh isolated evidence:
`/tmp/civora-repair-verification.NBAOtD/results/terrain-51.xml`:
23 tests passed. A synthetic admissible100x100 grid with provider failure makes
exactly one fetch attempt; a second-sample failure stops at exactly two attempts;
all-valid2x2 sampling still makes four calls and returns the same pixels. Tile
safety, fallback provenance and TIN regressions pass. No live provider, actual
token, customer/production data, paid request or deployment used.

This is not an overall request deadline or distinct-tile budget: many successful
tiles can still take too long. Those limits, cancellation, units/datum and
engineering validation remain open. No original audit evidence was changed.
Rollback is an isolated commit revert without schema/data changes, but would
reopen repeated-failure resource waste.
