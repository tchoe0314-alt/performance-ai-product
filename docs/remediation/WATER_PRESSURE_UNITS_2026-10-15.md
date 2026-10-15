# Water friction pressure unit correction

Parent: `80beb187`. ENG-06/Q13–Q14 independent formula validation follow-up.

Confirmed defect: _hazen_williams_loss_psi_per_100ft used4.52 with GPM/inches
and then multiplied by0.433 as though the result were feet of head. That
expression already returns pressure loss. The second conversion understated
friction loss and overestimated residual pressure. For75GPM,2in,C130,100ft:
old2.419psi; corrected5.587psi. Existing two math tests repeated the erroneous
formula; they now assert the independently reviewed pressure value instead.

Independent primary reference inspected2026-10-15:
EPA EPANET2.2 User Manual, Table3.1:
https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P10113EM.TXT
https://19january2021snapshot.epa.gov/sites/static/files/2020-05/documents/epanet_userss_manual_2.2.0.pdf

The reference head-loss expression uses4.727,C exponent1.852,d exponent4.871,
feet/cfs. Four new cases independently convert US gallons231in3 to cfs and
diameter inches to feet, then head to psi. Existing rounded GPM/inch exponents
are retained; comparison tolerance1% plus0.001psi report rounding is declared
before outcome. The75GPM EPA-form reference is about5.5896psi. This corrects
units without changing roughness selections, demand curves or design standards.

Fresh isolated report:
`/tmp/civora-repair-verification.NBAOtD/results/water-67.xml`:41 tests passed.
Scope: four independent unit comparisons, water/hydraulic math and graph cases,
calculation history and obsolete result identity. No paid provider, production/
customer data, deployment, external solver execution or package installation.

Build identity advances to engineering_core_2026_10_v4. v3 and earlier outputs
remain retained/unverified and cannot activate; partial inherited checkpoints
require fresh execution. No saved calculations rewritten. A current stamp is
build/input identity, not professional acceptance. Old test expectations and
prior audit evidence remain in Git history; no failing evidence files replaced.

Open: finite/domain validation, roughness/fixture assumptions, elevation sign,
branch/path accumulation, looped-network limitations, independent reference
software and PE acceptance. The pressure-loss helper correction is not a full
water/fire-flow qualification. Rollback must not recertify incorrect prior-method
outputs; preserve history and roll forward rather than reusing old build stamps.
