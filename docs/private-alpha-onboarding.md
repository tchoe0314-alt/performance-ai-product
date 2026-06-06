# Private Alpha Onboarding

## What Civora Can Do In Private Alpha

Civora can help prepare engineer-review-ready civil site planning evidence. In private alpha it may:

- create and save project workspaces
- start from an address, a locked map site, a blank site, or user-drawn geometry
- help place and edit site objects such as buildings, roads, parking, paths, basins, and utilities
- generate review-only grading, drainage, sanitary, water, utility coordination, quantity, and export-package outputs
- list assumptions, missing inputs, blockers, low-confidence areas, and stale-output warnings
- package review materials for a licensed engineer or qualified reviewer

## What Civora Cannot Do Yet

Civora does not stamp, seal, sign, certify, approve construction, submit construction documents, or act as engineer of record.

Civora is not construction-ready in private alpha. Every output remains engineer-review-required unless an external licensed engineer reviews and approves it outside Civora.

Civora also cannot yet:

- verify Civil3D production compatibility
- export DWG files
- treat inferred or unaccepted standards as compliance evidence
- replace survey/control, datum, benchmark, or source documentation
- replace external engineer approval

## First-Use Workflow

1. Create a project.
2. Add an address or start from a blank site.
3. Set, draw, and lock the site boundary.
4. Add or draw objects such as buildings, roads, parking, paths, basins, and utilities.
5. Generate systems.
6. Review blockers, missing inputs, assumptions, stale outputs, and low-confidence areas.
7. Export an engineer-review package.

## Status Terms

`ready_for_engineer_review`
: The output has enough traceable evidence to be reviewed by an engineer. It is not approved, sealed, stamped, submitted, or construction-ready.

`construction_blocked`
: Civora found missing evidence, stale outputs, unsupported exports, unaccepted standards, unresolved blockers, or another condition that prevents construction release.

`missing inputs`
: Required information is absent, such as a locked site, survey/control, outlet, tie-in, datum, accepted standards, dimensions, or source evidence.

`assumptions`
: Values Civora inferred or used as placeholders so work can continue in review-only mode. Assumptions must be checked by the user or engineer.

`stale outputs`
: Outputs no longer match the current project state because geometry, inputs, standards, or upstream systems changed after they were generated.

`low confidence`
: Civora produced a result but does not have enough evidence or validation depth to treat it as reliable without closer review.

## Known Limitations

- Civil3D workflows are not externally verified.
- DWG export is unsupported.
- Standards require user/company acceptance before they can be used as review evidence.
- Survey/control, datum, benchmark, and source evidence are required for production-grade review.
- External licensed engineer approval is required before construction use, stamping, sealing, signing, or submission.
