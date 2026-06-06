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
