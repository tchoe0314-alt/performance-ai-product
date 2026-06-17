# Private Alpha Onboarding

## What Civora Is

Civora is a private-pilot civil site planning copilot. It helps users organize site intent, candidate geometry, engineering signals, assumptions, blockers, and review-package materials so a licensed engineer or qualified reviewer can evaluate the work faster.

Civora is not a construction release system. Civora never stamps, seals, signs, certifies, approves construction, submits construction documents, or acts as engineer of record. Only the licensed engineer or user can review, approve, stamp, seal, sign, submit, and take legal responsibility.

## What Civora Can Do Today

Civora can help prepare engineer-review-ready civil site planning evidence. In private alpha it may:

- create and save project workspaces
- start from an address, a locked map site, a blank site, or user-drawn geometry
- help place and edit site objects such as buildings, roads, parking, paths, basins, and utilities
- generate review-only grading, drainage, sanitary, water, utility coordination, quantity, and export-package outputs
- list assumptions, missing inputs, blockers, low-confidence areas, and stale-output warnings
- package review materials for a licensed engineer or qualified reviewer

## What Civora Cannot Do Yet

Civora is not construction-ready in private alpha. Every output remains engineer-review-required unless an external licensed engineer reviews and approves it outside Civora.

Civora also cannot yet:

- stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record
- verify Civil3D production compatibility
- export DWG files
- treat inferred or unaccepted standards as compliance evidence
- replace survey/control, datum, benchmark, or source documentation
- replace external engineer approval
- automatically turn an address into trusted site objects unless those objects are backed by accepted source evidence

## Engineer-Review Responsibility Boundary

Civora can prepare review packages, trace assumptions, identify blockers, and show candidate plans. Civora cannot decide that work is legally approved or ready for construction.

The licensed engineer or user is responsible for:

- confirming source data, survey/control, datum, benchmarks, standards, constraints, and jurisdictional requirements
- reviewing calculations, geometry, conflicts, quantities, assumptions, and exports
- approving, stamping, sealing, signing, submitting, or releasing any documents outside Civora
- taking professional and legal responsibility for project decisions

## First Project Workflow

1. Create a project.
2. Add an address or start from a blank site.
3. Set, draw, and lock the site boundary.
4. Add or draw objects such as buildings, roads, parking, paths, basins, and utilities.
5. Generate systems.
6. Review blockers, missing inputs, assumptions, stale outputs, and low-confidence areas.
7. Export an engineer-review package.

## Status Terms

`Ready`
: Civora has enough current, traceable evidence for the item to be reviewed. Ready does not mean approved, stamped, sealed, submitted, certified, or construction-ready.

`Needs review`
: Civora produced an output, assumption, source candidate, or recommendation that a user or licensed engineer must check before relying on it.

`Blocked`
: Civora found missing evidence, stale outputs, unsupported exports, unaccepted standards, unresolved conflicts, or another condition that prevents the next review step.

`Missing input`
: Required information is absent, such as a locked site, survey/control, outlet, tie-in, datum, accepted standards, dimensions, jurisdiction, or source evidence.

`Draft/review-required`
: Civora is carrying a draft value, geometry item, status, or package forward so review can continue. The user or engineer must verify it before reliance.

`Visual preview only`
: The screen is showing a visual aid or candidate view. It does not change canonical geometry or create construction-ready output by itself.

## How To Report Issues

Pilot users should report issues in the shared pilot support channel or directly to the Civora team contact. If the issue affects safety, source trust, exports, or engineer-review boundaries, mark it as urgent and stop using the affected output until we respond.

Before inviting pilot users, Civora operators should confirm the access, support, policy, limit, billing, and terms checklist in [pilot-business-operations.md](/Users/tommychoe/Documents/Playground/Civora%20AI/docs/pilot-business-operations.md).

## What To Include In Bug Reports

Please include:

- project name or project ID
- time and date of the issue
- browser, device, and operating system
- the exact prompt, action, upload, or button sequence that triggered the issue
- expected result and actual result
- screenshots or screen recording when available
- uploaded file names and source type, without sending confidential files into public channels
- whether the issue involved address lookup, GIS or imagery candidates, geometry edits, generated systems, exports, or review status
- any blocker, missing-input, stale-output, or error text shown by Civora

## Known Limitations

- Civil3D workflows are not externally verified.
- DWG export is unsupported.
- Standards require user/company acceptance before they can be used as review evidence.
- Survey/control, datum, benchmark, and source evidence are required for source-backed reviewer evaluation.
- Map/GIS imports require confirmation that the pilot user has rights to upload, connect, process, and use the source within the approved pilot scope.
- Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.
- Address lookup does not automatically create trusted site objects unless those objects are backed by accepted source evidence.
- GIS and imagery detections are candidates that require review.
- Exports are review packages unless externally approved by a licensed engineer outside Civora.
- Construction release remains outside Civora.

## Internal Pilot Support Checklist

Use this checklist before onboarding or responding to a pilot issue:

- Confirm the user understands Civora outputs are review-required and not construction-ready.
- Confirm the project has a known owner, pilot contact, and support channel.
- Confirm the issue includes project ID, steps to reproduce, source inputs, screenshots, and visible status/error text.
- Check whether the issue touches source trust, address lookup, GIS/imagery candidates, exports, or professional responsibility language.
- Reproduce the issue in a non-production or test-safe context when possible.
- Preserve uploaded/source evidence names and timestamps; do not move confidential files into public channels.
- Triage as blocked if the issue could cause reliance on stale, missing, unsupported, or unreviewed output.
- Respond with the current status, next action, owner, and whether the user should pause reliance on the affected output.
- Keep all support responses aligned with the permanent engineer responsibility rule.
