# Civora Private Pilot Starter Guide

This guide is for private pilot users before they begin using Civora. It explains how to prepare files, what to expect from the pilot workflow, and how to handle review-only outputs, source confidence, and blockers.

Civora is a planning workspace for review-preparation. It helps organize source-tracked project information and prepare a review package for engineer review required workflows. Civora does not make professional decisions, finalize work, or authorize use outside the pilot review process.

## What Civora Is

Civora is private pilot software for civil site planning support. It helps teams collect project intent, site information, source files, candidate geometry, assumptions, review notes, blockers, and package materials in one planning workspace.

Civora is designed to help users prepare information for review. It is not a professional decision-maker, and it does not remove the need for external review by the appropriate project team.

## What Civora Helps With

- Organizing project context, site constraints, standards, source files, and review notes in one place.
- Creating or importing candidate site information for review-preparation.
- Tracking assumptions, missing inputs, review notes, and unresolved blockers.
- Preparing source-tracked summaries, quantities, issue lists, and review package materials.
- Making it easier for the project team to see what information is supported, what needs confirmation, and where engineer review required status still applies.

## What Civora Does Not Do

Civora does not:

- make engineering decisions or take responsibility for project outcomes
- replace survey, source control, utility records, client requirements, jurisdictional standards, or project-team judgment
- turn address lookup, imagery, GIS, PDFs, sketches, or inferred geometry into trusted evidence without user review and accepted source support
- remove the need to verify sources, assumptions, calculations, geometry, quantities, conflicts, standards, and exports
- authorize field, bidding, procurement, filing, or submittal use

## What Files And Data To Prepare

Before starting a pilot project, gather as much of the following as you can:

- Project address or location description.
- Site boundary, parcel information, or a clear sketch of the intended work area.
- Survey/control information, benchmark, datum, coordinate system, or terrain data if available.
- Existing plan sheets, prior studies, utility maps, site photos, sketches, or review notes.
- Applicable owner, company, utility, and jurisdictional standards.
- Known constraints such as easements, floodplain or wetland limits, access limits, tie-ins, outfalls, utility conflicts, or project phasing.
- Notes on which files are allowed for use in the pilot account and whether any confidential data restrictions apply.

## Accepted Inputs

Accepted pilot inputs may include:

- Address or location text.
- PDF plan sheets.
- Survey CSV files and other supported terrain or source files.
- LandXML, GeoJSON, GIS/map files, map images, screenshots, sketches, and source notes when supported by the current workspace.
- Manually drawn or edited site objects in Civora.
- Standards, criteria, utility notes, and review comments entered or uploaded by the user.

Some file types may be limited by size, parsing support, coordinate metadata, source quality, or account configuration. If Civora cannot read or trust an input, it may mark the related step as blocked or source review required.

## Step-By-Step Pilot Workflow

1. Start a project in the Civora planning workspace.
2. Enter the project address or begin from a blank site.
3. Add the site boundary, project context, and any available survey/control or coordinate information.
4. Upload or enter source files, standards, constraints, notes, and supporting references.
5. Add or edit candidate site objects such as buildings, drives, parking, drainage features, utilities, or other supported items.
6. Run the supported review-preparation workflow for the project scenario.
7. Review assumptions, source confidence, blockers, missing inputs, stale outputs, and issue lists.
8. Prepare a source-tracked review package for external project review.
9. Pause or revise any item marked blocked, low confidence, or engineer review required before relying on it.

## What Review-Only Means

Review-only means the output is for discussion, checking, coordination, and review-preparation. It is not a final project decision and should not be used as a basis for field, filing, procurement, or submittal action.

When Civora shows review-only material, engineer review required still applies. Users should verify source files, assumptions, dimensions, criteria, calculations, geometry, quantities, conflicts, exports, and next actions through the normal project review process.

## What Source Confidence Means

Source confidence describes how well Civora can trace an output back to accepted project evidence.

High source confidence means the item appears connected to current, traceable inputs. It still requires user and project-team review.

Medium source confidence means Civora has some supporting information, but one or more assumptions, source gaps, or review questions remain.

Low source confidence means Civora does not have enough accepted evidence for the item to be relied on. The user should add or confirm sources before continuing.

Source confidence is not a quality guarantee. It is a source-tracking signal that helps the user decide what needs more review.

## What Blockers Mean

A blocker means Civora found a missing input, unresolved conflict, unsupported action, stale result, source gap, or review boundary issue that prevents the next review-preparation step from moving forward cleanly.

Common blockers include:

- missing site boundary, datum, coordinate context, survey/control, tie-in, outfall, or utility information
- missing or unaccepted standards
- source files that cannot be parsed or traced
- stale results after geometry or inputs changed
- unresolved conflicts between sources or candidate objects
- export or package items that need additional review before use

## What To Do When Something Is Blocked

When an item is blocked:

1. Read the blocker message and identify the missing source, conflict, or unsupported step.
2. Add the requested file, standard, dimension, source note, or project constraint if available.
3. If the source exists but Civora did not connect it correctly, add a note and report the issue.
4. Re-run or refresh the affected review-preparation step only after the missing information is corrected.
5. If the blocker involves source trust, data exposure, exports, review-boundary wording, or possible reliance on unclear output, pause use of that output and contact support.

Do not work around a blocker by treating unverified output as ready for use. A blocked item should remain in review-preparation until the source issue or workflow issue is resolved.

## How To Report Issues Or Get Support

Use the in-app Report issue panel when available. If your pilot contact provided a shared support channel, use that channel for routine questions. If no other support path was provided, send questions to support@civora.ai.

Include:

- project name or project ID
- date, time, and timezone
- browser, device, and operating system
- the action, prompt, upload, or button sequence that caused the issue
- expected result and actual result
- visible blocker, missing-input, stale-output, source-confidence, or error text
- whether confidential or restricted project data is involved

Mark the issue urgent if it involves data exposure, source trust, exports, review-boundary wording, or possible reliance on unclear output.

## Data And Confidentiality Expectations

- Use non-confidential or explicitly allowed pilot files unless your written pilot terms allow confidential project data.
- Only upload files and third-party data you have the right to use in the pilot.
- Do not send confidential files, screenshots, client names, or restricted data through public support channels.
- Keep project access limited to the people allowed for the pilot account.
- Deletion, retention, backups, derived artifacts, logs, and support records follow the written pilot terms for the account.
- Until written terms confirm a process, do not assume a specific deletion, return, anonymization, or backup-handling timeline.

## Known Pilot Limitations

- Civora is a private pilot and may change during the pilot period.
- Some imports may be limited by file type, size, coordinate metadata, source quality, or parsing support.
- Address lookup, map context, imagery, GIS, PDF extraction, and inferred objects are candidates until reviewed and connected to accepted source evidence.
- Standards must be reviewed and accepted by the user or project team before they are treated as review evidence.
- Advanced CAD handoff workflows are not externally verified in the pilot.
- DWG export is not supported in the current pilot UI.
- Review packages may be incomplete if sources are missing, blocked, stale, unsupported, or low confidence.
- Engineer review required status remains part of the workflow even when source confidence is high.

## Safe Professional Disclaimer

Civora is private pilot software for planning workspace support, source-tracked review-preparation, coordination, and review package assembly. Civora does not provide professional services, make project decisions, accept responsibility for project outcomes, or authorize use outside the pilot review process. Users remain responsible for verifying all sources, standards, assumptions, calculations, geometry, quantities, conflicts, exports, and next actions through the appropriate external project review process. Engineer review required.

## Email-Ready Version

Subject: Civora private pilot starter guide

Hi,

Thanks for joining the Civora private pilot. Before you begin, please review the starter guide below so you know what Civora is designed to help with, what it does not do, what files to prepare, and how to handle review-only outputs, source confidence, and blockers.

Civora is a planning workspace for civil site review-preparation. It helps organize source-tracked project information, assumptions, constraints, candidate site objects, blockers, and review package materials. Civora does not make professional decisions, finalize work, or authorize use outside the pilot review process. Engineer review required.

Before starting, please prepare any available project address or location description, site boundary or sketch, survey/control information, benchmark, datum, coordinate system, terrain data, plan PDFs, utility maps, standards, constraints, review notes, or other source files allowed for the pilot account.

Accepted pilot inputs may include address text, PDF plan sheets, survey CSV files, LandXML, GeoJSON, GIS/map files, map images, screenshots, sketches, source notes, manually drawn site objects, standards, criteria, and review comments when supported by the current workspace.

Recommended pilot workflow:

1. Start a project in the Civora planning workspace.
2. Enter the address or begin from a blank site.
3. Add the site boundary, project context, and available survey/control information.
4. Upload or enter source files, standards, constraints, and notes.
5. Add or edit candidate site objects.
6. Run the supported review-preparation workflow.
7. Review assumptions, source confidence, blockers, missing inputs, stale outputs, and issue lists.
8. Prepare a source-tracked review package for external project review.
9. Pause any item marked blocked, low confidence, or engineer review required before relying on it.

Review-only means Civora output is for discussion, checking, coordination, and review-preparation. Source confidence shows how well an output traces back to accepted project evidence. A blocker means Civora found a missing input, source gap, conflict, unsupported action, stale result, or review-boundary issue that needs attention before the next step.

If something is blocked, read the blocker message, add or confirm the missing source information, refresh the affected review-preparation step, and contact support if the issue involves source trust, exports, data exposure, review-boundary wording, or possible reliance on unclear output.

For support, use the in-app Report issue panel or your shared pilot support channel. Include the project name or ID, date and time with timezone, browser/device/operating system, steps to reproduce, expected and actual result, visible blocker or source-confidence text, and whether confidential or restricted project data is involved.

Please use non-confidential or explicitly allowed files unless your written pilot terms allow confidential project data. Only upload files and third-party data you have the right to use in the pilot, and do not send confidential files or restricted project information through public support channels.

Known pilot limitations include import limits by file type, size, coordinate metadata, and source quality; candidate-only status for address lookup, map context, imagery, GIS, PDF extraction, and inferred objects until reviewed; standards requiring user or project-team acceptance; unverified advanced CAD handoff workflows; no DWG export in the current pilot UI; and incomplete review packages when sources are missing, blocked, stale, unsupported, or low confidence.

Civora is private pilot software for planning workspace support, source-tracked review-preparation, coordination, and review package assembly. Users remain responsible for verifying sources, standards, assumptions, calculations, geometry, quantities, conflicts, exports, and next actions through the appropriate external project review process. Engineer review required.
