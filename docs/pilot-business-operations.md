# Pilot Business Operations Packet

Use this packet before charging customers, inviting pilot users, or expanding access beyond a controlled private pilot.

Permanent responsibility rule: Civora never stamps, seals, signs, certifies, approves construction, submits construction documents, or acts as engineer of record. Only the licensed engineer or user can review, approve, stamp, seal, sign, submit, and take legal responsibility.

This is an operational draft, not legal advice. Owner and counsel must approve the policy language before it is sent to users or incorporated into customer terms.

## Launch Gate

Do not invite or charge a user until all required rows are complete.

| Area | Required before invite | Required before charging |
| --- | --- | --- |
| Pilot roster | Named user, company, role, cohort, owner, and status | Same, plus billing contact and account owner |
| Access | Invite-only account path confirmed | Account provisioning, disable path, and billing status process confirmed |
| Support | Shared support channel and escalation owner named | Response expectations, incident handling, and support coverage approved |
| Policies | Confidential input, retention, deletion, and pilot terms drafts acknowledged | Counsel-approved terms, privacy posture, retention, deletion, and billing language |
| Limits | Pilot usage limits communicated | Paid limits, overage policy, refund policy, and service-level expectations approved |
| Evidence | Review-only onboarding and limitations shared | Same, plus commercial terms and responsibility boundary accepted |

## Pilot Invite And Access Flow

Access is invite-only during pilot. Public self-serve signup should remain disabled unless the owner explicitly changes the pilot mode.

1. Add the prospective user to the pilot roster.
2. Assign an internal account owner and support owner.
3. Confirm allowed scope: test-only, internal feasibility, or other approved scope.
4. Send the pilot invite packet:
   - app URL
   - onboarding guide
   - support channel
   - known limitations
   - confidential input policy
   - data retention and deletion draft
   - pilot terms checklist or terms link
5. Require written acceptance of review-only scope, engineer responsibility boundary, confidentiality expectations, and usage limits.
6. Create or enable the user account only after acceptance is recorded.
7. Confirm first login and first project creation.
8. Mark the roster status as `Active`.
9. Revoke access when the pilot ends, terms are rejected, billing is not approved, or a P0/P1 issue requires a pause.

Pilot roster status values:

| Status | Meaning |
| --- | --- |
| `Prospect` | Candidate only; no access allowed |
| `Approved` | Owner approved invite; terms not yet accepted |
| `Invited` | Invite sent; access not confirmed |
| `Active` | User accepted terms and can use the pilot |
| `Paused` | Access should be disabled or monitored pending issue resolution |
| `Removed` | User no longer has pilot access |

## Roles And Admin Basics

Define these roles operationally even if they are managed manually during pilot.

| Role | Allowed actions | Not allowed |
| --- | --- | --- |
| Pilot user | Create projects, upload approved inputs, generate review-only outputs, report issues | Invite other users, approve construction, change account limits |
| Licensed reviewer | Review outputs outside Civora and decide whether work can be relied on | Treat Civora as engineer of record or approval authority |
| Company/account owner | Approve pilot participants for their team, receive account notices, coordinate billing readiness | Bypass individual responsibility acknowledgements |
| Civora support owner | Triage issues, collect reproduction details, coordinate workarounds | Make professional approval decisions for users |
| Civora admin | Provision, pause, remove, and audit pilot access | Use user project data outside the agreed support, debugging, safety, and operations scope |
| Billing owner | Approve plan, limits, invoicing, and payment readiness | Enable charging without accepted terms and policy approval |

Minimum admin controls before charging:

- owner-approved process to add, pause, and remove users
- record of accepted terms per user or account
- record of account owner and billing owner
- manual audit of active users at least weekly
- documented incident path for access mistakes or data exposure

## Support Process

Support should use a single shared channel plus a direct escalation path for urgent issues.

| Severity | Use when | Target response | Required action |
| --- | --- | --- | --- |
| P0 | Data exposure, source-trust failure, safety risk, wrong responsibility boundary, or likely reliance on invalid output | Same business day, immediately when seen | Pause affected use, notify owner, preserve evidence, start incident record |
| P1 | Key workflow blocked, export/report misleading, access broken for active pilot user | Same business day | Triage, provide workaround or status, assign owner |
| P2 | Recoverable bug, confusing copy, visual issue, non-blocking workflow friction | Next business day | Log, reproduce when possible, batch into roadmap |
| P3 | Feedback, enhancement, nice-to-have request | Best effort | Add to backlog with account context |

Support intake must record:

- reporter, company, email, and role
- project name or ID
- date/time with timezone
- environment, browser, device, and operating system
- steps to reproduce
- expected result and actual result
- visible status, warning, blocker, or error text
- input file names and source type
- whether confidential input is involved
- whether the issue touches address lookup, GIS/imagery candidates, generated systems, exports, review status, source trust, or responsibility language
- severity, owner, next action, and user reliance guidance

Support response rule: if a reported issue may affect source trust, safety, exports, review status, or professional responsibility, tell the user to pause reliance on the affected output until resolved or externally reviewed.

## Bug Report Intake

Use this template for pilot bugs.

```text
Title:
Reporter:
Company/team:
Email:
Role:
Project name or ID:
Date/time with timezone:
Environment: local / staging / pilot deployment
Browser/device/OS:

What were you trying to do?

Steps to reproduce:
1.
2.
3.

Expected result:

Actual result:

Visible status/warning/error text:

Files or inputs involved:

Does this include confidential input? Yes / No / Unsure

Did this involve address lookup, GIS/imagery candidates, drawn geometry, generated systems, exports, source trust, or review status?

Screenshots or recording:

Can the affected output be relied on? No / Unknown / User paused / Externally reviewed

Internal owner:
Severity:
Next action:
Target response date:
Resolution:
```

## Data Retention And Deletion Policy Draft

Draft policy position for pilot:

- Keep pilot account, project, upload, artifact, job, and support records only as long as needed for pilot operation, debugging, safety review, legal compliance, and agreed customer support.
- Treat project uploads, generated artifacts, prompts, outputs, and support attachments as customer-provided or customer-derived data.
- Do not use pilot project data for marketing, public demos, or unrelated model/product examples without written permission.
- Do not put confidential files, screenshots, or project details in public channels.
- Keep deletion requests tied to account owner authorization when company data is involved.
- Preserve minimum incident evidence when deletion would conflict with security, abuse, billing, legal, or safety obligations.

Proposed default pilot retention:

| Data type | Draft retention | Deletion path |
| --- | --- | --- |
| User/account records | Pilot duration plus 90 days | Remove or anonymize after account close unless needed for legal/billing records |
| Project records | Pilot duration plus 90 days | Delete by project ID after account owner approval |
| Uploaded files | Pilot duration plus 90 days | Delete associated stored file and support copies |
| Generated artifacts/exports | Pilot duration plus 90 days | Delete with project or artifact request |
| Job/runtime logs | 30 days where practical | Redact or delete sensitive entries when feasible |
| Support tickets | Pilot duration plus 1 year | Redact confidential attachments on request, preserve operational summary |
| Billing records | As required for accounting and tax | Follow billing provider and legal retention requirements |

Owner must decide final retention periods, deletion SLA, whether backups are included, and whether any data can be retained in anonymized or aggregated form.

## Confidential Input Policy Draft

Default pilot position: users should start with non-confidential or approved test inputs unless the owner has explicitly allowed confidential project inputs for that account.

If confidential inputs are allowed:

- Require account-level approval before upload.
- Limit access to named Civora admins and support owners with a need to know.
- Keep support discussion to file names, source types, project IDs, and reproduction summaries unless a private channel is approved.
- Do not paste confidential project data into public issue trackers, public AI tools, public chat channels, or marketing materials.
- Ask users to remove sensitive personal data that is not needed for civil site review.
- Tell users Civora is pilot software and outputs remain review-required even when inputs are confidential.

Do not accept:

- regulated personal data that is not needed for the pilot
- trade secrets or client-restricted files unless the account owner confirms permission
- production construction documents if the user expects Civora to approve, stamp, seal, certify, submit, or release them
- data governed by a contractual security requirement Civora has not accepted in writing

## Usage Limits

Draft pilot limits to communicate before access:

| Limit | Default pilot cap | Owner decision needed |
| --- | --- | --- |
| Users per company | 1 to 3 | Exact cap per account |
| Projects per user | 5 active pilot projects | Whether archive projects count |
| Uploaded file size | Small test/source files only; no bulk archives | Final MB limit |
| Generated runs | Reasonable testing only; no load testing without approval | Daily or monthly run cap |
| Exports | Review package testing only | Export count or file size cap |
| Support coverage | Business days only unless escalated | Support hours and holiday coverage |
| Confidential projects | Disabled by default | Which accounts may enable |
| Commercial use | Internal feasibility/review only unless approved | Whether paid pilots may use real client work |

Throttle or pause accounts that exceed limits, create operational risk, submit unsupported file types, attempt construction-release use, or ignore the responsibility boundary.

## Billing Readiness Checklist

Do not charge until these are complete.

- Pricing basis chosen: per seat, per company, per project, usage-based, or flat pilot fee.
- Billing owner named.
- Payment method, invoicing flow, tax handling, refund policy, and cancellation path approved.
- Trial, free pilot, paid pilot, and conversion rules documented.
- Usage limits and overage policy approved.
- Support expectations and any service-level commitments approved.
- Terms, privacy posture, confidentiality language, data retention/deletion policy, and responsibility boundary approved by owner and counsel.
- Account suspension and non-payment process documented.
- Receipts, invoices, and billing records stored outside engineering logs.
- Billing status does not change engineering truth labels, review-only state, blockers, or responsibility boundaries.

## Paid Pilot Terms Checklist

Before a paid pilot starts, owner and counsel must decide and record:

| Term area | Decision required before charging |
| --- | --- |
| Customer identity | Legal customer name, account owner, billing owner, authorized users, and notice contacts |
| Pilot scope | Whether paid use is test-only, internal feasibility, real client work, or another approved scope |
| Deliverable status | Written statement that all outputs remain draft/review packages unless externally approved by the responsible licensed engineer |
| Responsibility acceptance | User/account acceptance that Civora is not engineer of record and does not stamp, seal, sign, certify, approve, submit, or release construction documents |
| Term length | Start date, end date, renewal path, conversion path, and termination rights |
| Fees | Price, currency, billing cadence, due date, late-payment treatment, and taxes |
| Limits | Seats, projects, upload volume, run volume, exports, support scope, and any overage handling |
| Support | No-SLA or SLA language, response expectations, support hours, escalation path, and excluded support |
| Data | Retention, deletion, backup, support access, confidentiality, and incident notification commitments |
| Changes | Right to modify pilot features, pause access, disable risky workflows, and correct output language |
| End of pilot | Data export, deletion request path, unpaid-balance handling, and access removal |

Paid pilot agreements must not imply that payment changes engineering responsibility, review-only labels, source-trust blockers, safety blockers, or the permanent responsibility rule.

## Privacy Policy Gaps Checklist

Do not expand access or charge until the privacy posture clearly explains:

- What data Civora collects: account records, prompts, uploaded files, project data, generated outputs, artifacts, logs, usage events, support messages, payment metadata, and billing records.
- Why data is processed: account operation, project generation, support, debugging, safety review, security, billing, legal compliance, and product improvement if allowed.
- Who can access customer data internally and for what operational reasons.
- Which vendors or processors may receive data, including hosting, storage, AI providers, maps/geocoding, analytics, support, and payment providers.
- Whether prompts, uploads, generated outputs, or support materials may be used for product improvement, model improvement, evaluation, examples, marketing, or demos.
- Whether customers can opt out of product-improvement use.
- How deletion, export, correction, and account closure requests are submitted and approved.
- Retention periods for each data category, including logs, backups, billing records, support records, and incident evidence.
- Security limitations of the pilot environment and what types of confidential or regulated data are not accepted.
- Incident notification process for suspected unauthorized access, exposure, or loss.
- Jurisdiction-specific notices, consumer rights, and business-customer roles if applicable.

Owner must decide whether Civora is positioned as a service provider/processor for customer project data and whether any customer data processing agreement is required before paid pilots.

## Data Retention And Deletion Finalization

Before charging, replace draft retention periods with owner-approved values.

| Question | Owner decision required |
| --- | --- |
| Default retention | How long account, project, upload, artifact, job, and support records stay after pilot end |
| Backups | Whether deletion includes backups, delayed backup expiry, or backup exclusion language |
| Deletion SLA | How many business days Civora has to complete approved deletion requests |
| Authorization | Who can request deletion for company-owned project data |
| Legal holds | When Civora may preserve records for billing, tax, security, abuse, legal, or safety reasons |
| Anonymized data | Whether Civora may retain aggregated or anonymized usage/product data |
| Support copies | How support attachments, screenshots, recordings, and repro files are deleted or redacted |
| Incident evidence | Minimum evidence retained after data exposure, safety, billing, or responsibility incidents |

Deletion requests should be tracked with requestor, account owner approval, affected project IDs, data categories, completion date, exceptions, and retained evidence rationale.

## Confidential Input Acceptance Policy

Before accepting confidential project inputs, owner must approve the account and record:

- account owner authorization that the customer has rights to provide the files to Civora
- allowed confidential data types and prohibited data types
- named internal Civora users who may access the data
- approved support channel for confidential issues
- whether third-party AI, map, hosting, storage, support, or payment providers may process related data
- retention and deletion handling for confidential uploads, generated artifacts, logs, and support records
- incident notification contact

Confidential input remains blocked when:

- the customer requires security terms Civora has not accepted in writing
- the file contains regulated personal data that is unnecessary for civil site review
- the customer expects Civora to approve, stamp, seal, certify, submit, or release construction work
- support or debugging would require sharing data through an unapproved channel or vendor

## Support SLA Or No-SLA Language

Before charging, choose one support posture.

| Option | Required language |
| --- | --- |
| No SLA | State that support is business-hours/best-effort, response targets are operational goals only, and Civora may pause affected use while investigating |
| Limited SLA | Define covered users, support hours, response targets, exclusions, remedies if any, and emergency escalation |

Regardless of support posture, P0/P1 issues involving data exposure, source trust, safety, responsibility boundaries, or likely reliance on invalid output require same-business-day internal escalation when seen.

## Refund, Cancellation, Tax, And Payment Provider Checklist

Owner must decide before charging:

- payment provider and account owner
- payment methods accepted
- invoice or self-serve checkout flow
- sales tax/VAT responsibility and tax calculation provider if needed
- refund policy for flat pilot fees, monthly fees, failed runs, support outages, early cancellation, and non-use
- cancellation notice period and effective date
- account suspension path for failed payment or non-payment
- chargeback/dispute owner
- where receipts, invoices, tax records, and payment provider events are stored
- who may access billing records

Billing records must stay separate from engineering logs and project records. Payment status must never alter engineering warnings, source-trust status, review-only labels, blockers, or engineer responsibility language.

## Engineer Responsibility Acceptance Record

Before charging or broadening pilot access, every account must have a recorded acceptance that:

- Civora is not the engineer of record.
- Civora does not stamp, seal, sign, certify, approve, submit, or release construction documents.
- Civora outputs are draft, candidate, or review-package materials unless externally reviewed and approved by the responsible licensed engineer outside Civora.
- The user and their licensed reviewer remain responsible for source verification, professional judgment, jurisdictional requirements, client requirements, construction release, and legal responsibility.
- Payment for Civora does not transfer professional engineering responsibility to Civora.

Record acceptance date, accepting person, account/company, authorized users covered, terms version, privacy version, and any exceptions.

## External Approval And Stamp Record Disclaimer

If a customer records external approval, stamp, seal, or submission status, the record must be treated as customer-provided metadata only.

Required disclaimer:

```text
Approval, stamp, seal, signature, submission, permit, and construction-release records are provided by the customer or responsible licensed professional outside Civora. Civora does not verify, grant, certify, or replace that approval and does not act as engineer of record.
```

Before adding or exposing any approval/stamp record flow, owner must decide who can enter the record, what evidence is attached, whether Civora stores a copy, how disputes are handled, and how records are deleted at pilot end.

## Incident Response Checklist

Open an incident record for suspected data exposure, unauthorized access, confidentiality violation, source-trust failure, wrong responsibility boundary, billing error, or likely reliance on invalid output.

Minimum incident record:

- incident ID, date/time, reporter, severity, owner, and affected accounts
- data categories, project IDs, uploads, artifacts, logs, and support channels involved
- whether confidential input, billing data, personal data, or external approval/stamp metadata is involved
- immediate containment action
- user reliance guidance
- preservation steps for logs, screenshots, artifacts, and reproduction data
- customer notification decision and owner
- legal/counsel escalation decision
- root cause, fix, rollback/disable action, and re-enable criteria
- final customer communication and post-incident follow-up

Containment options include pausing affected users, disabling features, rotating credentials, revoking access, rolling back deployment, stopping the backend, removing exposed support attachments, or suspending billing actions until corrected.

## Security And Confidential Data Handling Checklist

Before charging, owner must confirm:

- production/pilot secrets are not shared in screenshots, docs, logs, support tickets, or browser recordings
- CORS is restricted to intended frontend origins
- temporary local QA access flags are disabled after testing
- persistent storage is configured for deployed pilot environments
- billing records are held in the payment provider or finance system, not engineering logs
- support staff know the confidential input policy and approved channels
- customer files are not copied to public repos, public issue trackers, public AI tools, or marketing materials
- access to customer project data is limited to named admins/support owners with a need to know
- account removal, password/token rotation, and deployment rollback paths are documented
- security incidents have an owner and notification path

## Billing Activation Checklist

Charging is blocked until every item is complete.

| Activation item | Required evidence |
| --- | --- |
| Legal terms | Counsel-approved pilot or paid-pilot terms version |
| Privacy | Counsel-approved privacy posture and data processing position |
| Responsibility acceptance | Signed or recorded account/user acceptance of permanent responsibility rule |
| Account ownership | Account owner, billing owner, support owner, and authorized users recorded |
| Scope | Allowed project/use scope and confidential input status recorded |
| Retention/deletion | Final retention periods, deletion SLA, backup posture, and exceptions approved |
| Support | No-SLA or SLA language approved and support channel ready |
| Incident response | Incident owner, escalation path, notification process, and evidence handling ready |
| Payment provider | Provider configured, tax handling decided, receipts/invoices working |
| Refund/cancellation | Refund, cancellation, non-payment, and dispute process approved |
| Security | Confidential data handling checklist completed |
| Operational rollback | Access pause/removal and deployment rollback owners named |
| Billing isolation | Billing status cannot affect engineering output status or responsibility boundaries |

After activation, preserve a billing-start record with account, plan, limits, terms version, privacy version, acceptance record, billing owner, support owner, activation date, and approving owner.

## Pilot Terms Checklist

The owner and counsel should ensure pilot terms cover:

- invite-only access and revocation rights
- review-only and no construction-release scope
- permanent engineer responsibility rule
- user responsibility for source verification and professional judgment
- acceptable use and prohibited uses
- confidential input rules
- data retention, deletion, backup, and support-access rules
- security limitations of pilot software
- known limitations and unsupported features
- support process and response expectations
- usage limits and account suspension
- fees, taxes, payment, refunds, cancellation, and non-payment if charging
- feedback rights and product improvement boundaries
- disclaimers, limitation of liability, indemnity, governing law, and dispute process
- pilot end date, renewal, conversion, or data export/delete process

## Owner Decisions Required

- Who owns the pilot roster and where it is stored.
- Who can approve invites, pauses, removals, and confidential input access.
- Whether pilot users may use confidential project inputs.
- Final retention periods, deletion SLA, backup deletion posture, and anonymized-data policy.
- Support channel, support hours, after-hours escalation owner, and incident response owner.
- Exact usage limits per user and per company.
- Whether paid pilot use may include real client work or only internal feasibility.
- Pricing, billing provider, refund/cancellation policy, and taxes.
- Final pilot terms and privacy language after legal review.
- Whether any additional security controls are required before charging.
- Whether paid pilot terms permit real client work or only internal/testing use.
- Whether Civora will offer no-SLA support or a limited SLA.
- Whether customer data may be used for product improvement, and whether opt-out is available.
- Whether a customer data processing agreement is required.
- Who signs off on billing activation for each account.
- What exact records prove engineer responsibility acceptance.
- Whether external approval, stamp, seal, submission, or permit records may be stored as customer-provided metadata.

## Remaining Business And Legal Gaps

- Counsel-approved pilot terms.
- Counsel-approved privacy, data retention, deletion, and confidentiality language.
- Security review for confidential customer inputs.
- Billing provider setup and financial controls.
- Written support SLA or no-SLA language.
- Incident response procedure for data exposure.
- Company/account-level authorization model.
- Data export path at pilot end.
- Customer consent process for using feedback, screenshots, or anonymized examples.

## Blocks Charging

Charging must not start until these are complete:

- counsel-approved paid pilot terms or customer agreement
- counsel-approved privacy posture, retention/deletion policy, and confidentiality language
- recorded engineer responsibility acceptance for the account or each user
- final paid scope, usage limits, support posture, and known limitations
- named account owner, billing owner, support owner, and authorized users
- final refund, cancellation, non-payment, tax, invoice/receipt, and payment provider process
- confidential input decision for the account
- incident response owner and notification path
- billing activation record and owner approval

## Can Wait Until Broader Pilot

These can wait for broader pilot if the paid pilot remains manual, invite-only, and owner-approved:

- fully automated self-serve billing
- automated role-based administration beyond manual roster controls
- formal customer admin dashboard
- broad public privacy center or self-serve deletion portal
- automated usage metering and overage billing
- multi-tier SLA program
- public status page
- automated external approval/stamp metadata workflow
- formal enterprise security questionnaire package, unless a paid customer requires it
