# Private Alpha Onboarding

## What Civora Is

Civora is a private-pilot civil site planning copilot. It helps users organize site intent, source evidence, candidate geometry, engineering signals, assumptions, blockers, and review-package materials so a licensed professional or qualified reviewer can evaluate the work faster.

Civora outputs are review-preparation materials only. Field use, submittals, legal responsibility, and professional decisions remain outside Civora.

For the email-ready user guide, use [pilot-starter-guide.md](/Users/tommychoe/Documents/Playground/Civora%20AI/docs/pilot-starter-guide.md) or the in-app `/pilot/starter` page.

## What Users Should Prepare

- Project address or location description.
- Survey/control, benchmark, datum, coordinate system, or terrain data if available.
- Applicable jurisdictional, owner, company, and utility standards.
- Known utility information, tie-ins, outlets, easements, floodplain/wetland constraints, access limits, and other site constraints.
- PDFs, survey CSVs, LandXML, GIS/GeoJSON, map images, source notes, sketches, or prior review packages.
- Confirmation that each uploaded or connected source may be used within the accepted pilot scope.
- A clear note on whether confidential project data is allowed for the account.

## What Civora Can Do Today

Civora can help prepare civil site planning evidence for review. In private alpha it may:

- create and save project workspaces
- start from an address, a locked map site, a blank site, or user-drawn geometry
- help place and edit site objects such as buildings, roads, parking, paths, basins, and utilities
- generate review-only grading, drainage, sanitary, water, utility coordination, quantity, and export-package outputs
- list assumptions, missing inputs, blockers, low-confidence areas, and stale-output warnings
- package review materials for a licensed professional or qualified reviewer

## What Civora Does Not Do

Civora does not:

- make professional engineering decisions or take legal responsibility for project outcomes
- replace survey/control, datum, benchmarks, utility records, jurisdictional standards, or client requirements
- treat inferred or unaccepted standards as review evidence
- automatically turn an address into trusted site objects unless those objects are backed by accepted source evidence
- promise that exports, drawings, quantities, or calculations can be used outside the review-preparation workflow

## Review Responsibility Boundary

Civora can prepare review packages, trace assumptions, identify blockers, and show candidate plans. Civora cannot decide that work is ready for field/submittal use.

The licensed professional or qualified reviewer is responsible for:

- confirming source data, survey/control, datum, benchmarks, standards, constraints, and jurisdictional requirements
- reviewing calculations, geometry, conflicts, quantities, assumptions, and exports
- making project decisions and accepting responsibility through the appropriate external process

## First Project Workflow

1. Create a project.
2. Add an address or start from a blank site.
3. Set, draw, and lock the site boundary.
4. Add or draw objects such as buildings, roads, parking, paths, basins, and utilities.
5. Generate systems.
6. Review blockers, missing inputs, assumptions, stale outputs, and low-confidence areas.
7. Export a review package for qualified review.

## Status Terms

`Ready`
: Civora has enough current, traceable evidence for the item to be reviewed. Ready does not mean field/submittal use is appropriate.

`Needs review`
: Civora produced an output, assumption, source candidate, or recommendation that a user or qualified reviewer must check before relying on it.

`Needs source`
: Civora is missing traceable evidence, such as survey/control, standards, utility records, source files, dimensions, or accepted candidate data.

`Needs engineer review`
: A responsible professional or qualified reviewer must evaluate the output, assumptions, sources, and next action outside Civora before use.

`Blocked`
: Civora found missing evidence, stale outputs, unsupported exports, unaccepted standards, unresolved conflicts, or another condition that prevents the next review step.

`Missing input`
: Required information is absent, such as a locked site, survey/control, outlet, tie-in, datum, accepted standards, dimensions, jurisdiction, or source evidence.

`Draft/review-required`
: Civora is carrying a draft value, geometry item, status, or package forward so review can continue. The user or reviewer must verify it before reliance.

`Visual preview only`
: The screen is showing a visual aid or candidate view. It does not change canonical geometry or create review evidence by itself.

## Upload, Retention, And Confidentiality Guidance

- Use non-confidential or explicitly allowed pilot files unless written pilot terms allow confidential project data.
- Only upload files and third-party data the pilot user has the right to use.
- Do not send confidential project files, screenshots, client names, or restricted data through public support channels.
- Deletion, retention, backups, derived artifacts, logs, and support records follow the written pilot terms for the account.
- Until final terms are in place, do not promise deletion timing, backup handling, anonymization, or return processes that are not implemented.

## How To Report Issues

Pilot users should report issues through the in-app Report issue panel, the shared pilot support channel, or the direct Civora team contact. If the issue affects safety, source trust, exports, data exposure, or review-boundary language, mark it urgent and stop using the affected output until the pilot owner responds.

Before inviting pilot users, Civora operators should confirm the access, support, policy, limit, billing, and terms checklist in [pilot-business-operations.md](/Users/tommychoe/Documents/Playground/Civora%20AI/docs/pilot-business-operations.md).

## What To Include In Bug Reports

- project name or project ID
- time and date with timezone
- browser, device, and operating system
- the exact prompt, action, upload, or button sequence that triggered the issue
- expected result and actual result
- screenshots or screen recording when available
- uploaded file names and source type, without sending confidential files into public channels
- whether the issue involved address lookup, GIS or imagery candidates, geometry edits, generated systems, exports, or review status
- any blocker, missing-input, stale-output, or error text shown by Civora

## Known Limitations

- Advanced CAD handoff workflows are not externally verified.
- DWG export is unsupported.
- Standards require user/company acceptance before they can be used as review evidence.
- Survey/control, datum, benchmark, and source evidence are required for source-backed reviewer evaluation.
- Map/GIS imports require confirmation that the pilot user has rights to upload, connect, process, and use the source within the accepted pilot scope.
- Address lookup does not automatically create trusted site objects unless those objects are backed by accepted source evidence.
- GIS and imagery detections are candidates that require review.
- Exports are review packages for external review.
- Field/submittal use remains outside Civora.

## Internal Pilot Support Checklist

- Confirm the user understands Civora outputs are review-required materials.
- Confirm the project has a known owner, pilot contact, and support channel.
- Confirm the issue includes project ID, steps to reproduce, source inputs, screenshots, and visible status/error text.
- Check whether the issue touches source trust, address lookup, GIS/imagery candidates, exports, data exposure, or review-boundary language.
- Reproduce the issue in a non-production or test-safe context when possible.
- Preserve uploaded/source evidence names and timestamps; do not move confidential files into public channels.
- Triage as blocked if the issue could cause reliance on stale, missing, unsupported, or unreviewed output.
- Respond with the current status, next action, owner, and whether the user should pause reliance on the affected output.
- Keep all support responses aligned with the review-preparation boundary.
