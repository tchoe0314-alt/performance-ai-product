# Water arithmetic domain containment

Parent: `bfa5cbc8`. ENG-06/Q13–Q14 extreme-input follow-up.

Finite inputs alone do not guarantee finite arithmetic. Overflow, denominator
underflow and summed losses could raise or produce infinite pressure estimates.
The sizing/graph public boundaries now contain arithmetic/validation failures
and reject nonfinite computed scalar outputs. Graph failures publish no partial
pressures/segments and use min_pressure=None. Sizing failures contain no sized
segments. Friction helper raises ValueError for unsupported arithmetic; huge
integers fail finite-number admission without escaping OverflowError. Legitimate
supported arithmetic and independently specified oracles remain unchanged.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/water-71.xml`:51 tests passed.
New cases cover1e308 flow, tiny diameter denominator underflow, huge integer,
friction-length overflow and summed fixed-loss overflow. Existing topology,
invalid-input, independent EPA-unit, hydraulic/fire-flow and engine contracts
also pass. No expected numerical result relaxed or replaced with a clamp.
No provider, production/customer data, paid service or deployment used.

This contains unsupported numeric domains; it does not establish physical
design ranges, numerical conditioning across every valid scale or professional
water-network accuracy. Signed elevation, demand continuity, real network
solver/reference qualification and final build identity remain open. Rollback is
an isolated code revert, no data migration; it reopens nonfinite/partial outputs.
