# Enrollment, recovery and browser integration

Parent revision: `18c8791d`. This is scoped local evidence, not release acceptance.

## Changes

- Private-alpha registration now requires an explicit public-registration policy
  or a valid address-bound invitation. No implicit first-visitor bootstrap.
- Invitation signup rechecks the single-use proof before membership is granted.
- Password recovery requires a purpose-bound, expiring mailbox proof. A successful
  reset changes the password, revokes sessions and outstanding user-bound proofs,
  and preserves designs/history. Known and unknown addresses receive the same
  public request response.
- Minimal account controls expose verification, invitation acceptance, recovery
  and password-confirmed all-device logout. Codes are not placed in URLs/storage.
- Logout clears signup mode and sensitive form state. A real browser run exposed
  the retained-signup-mode defect before that repair; its failed output is retained.
- The pre-existing sidebar contrast change was preserved and checked in-browser.

## Verification

All checks used disposable synthetic data and approved fake delivery only.
Production delivery remains unconfigured and fails closed. No production,
customer data, paid provider, real message delivery, deployment or payment used.

Reports under `/tmp/civora-repair-verification.NBAOtD/results/`:

| Evidence | Outcome |
|---|---|
| `enrollment-32.xml` / `.log` | 51 tests and 5 subtests passed; one existing httpx deprecation warning |
| `identity-ui-31` | Original browser failure preserved: logout retained registration mode |
| `identity-ui-32` | Real Chromium/API identity journey passed, including scoped accessibility and no page errors |
| `identity-ui-33` | Responsive attempt blocked by Next development indicator over mobile Brief control |
| `identity-ui-34` | Responsive stage clicks/security controls passed at 1280x800, 844x390, 390x844; scoped serious/critical axe findings zero |
| TypeScript no-emit/nonincremental | Exit 0 |

For UI34 only, `devIndicators: false` was added to the disposable copy's Next
config. No application configuration change or forced pointer click was used.
The development indicator does not exist in production. Screenshots retained.
The responsive test is not a full-page accessibility or supported-browser audit.

## Remaining boundaries

- Real delivery configuration, independent security review, PostgreSQL races,
  legacy membership review, proxy configuration and browser-session strategy
  remain unverified.
- Invitation registration preflight and account creation are separate transactions.
  A changed invitation after account creation revokes the issued session and
  returns conflict without granting membership; an account may remain and recover
  through normal sign-in. Full atomic enrollment remains a follow-up decision.
- Existing accounts are not automatically bootstrapped into operator privileges.
  Operator provisioning/delivery needs approved operational procedures.
- Fake mailbox files are private disposable harness artifacts, never an HTTP
  outbox. The fixture refuses existing storage directories and hosted execution.
- These checks do not certify all current backend/browser tests, engineering
  correctness, production configuration or any release gate.
