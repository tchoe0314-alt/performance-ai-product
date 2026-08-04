# Independent Engineer Validation Protocol

## Purpose

Use this protocol to validate a named Civora software revision against independently prepared civil-engineering benchmark projects. This is a review and product-validation record. It does not delegate engineer-of-record responsibility or authorize construction release.

## Review Identity

- Civora revision:
- Validation report version:
- Reviewer name and organization:
- Relevant license or qualification:
- Jurisdiction and discipline:
- Review date:
- Independent from benchmark preparation: yes / no

## Input Evidence

Record every input artifact before running Civora.

| Artifact | Source/owner | SHA-256 | Coordinate system/datum | Accepted use | Limitations |
| --- | --- | --- | --- | --- | --- |
| Survey/control | | | | | |
| Terrain/surface | | | | | |
| Existing utilities | | | | | |
| Standards/criteria | | | | | |
| Rainfall/hydrology | | | | | |
| Water/fire-flow source | | | | | |
| Cost book | | | | | |

Confirm that source extents and coordinate systems register to the same project location. Record any transformation applied and who accepted it.

## Reference Projects

Use at least three materially different projects:

1. Commercial site with building, parking, detention, public utilities, roadway connection, sidewalks, ADA route, and sloped terrain.
2. Terrain/drainage-heavy site with multiple catchments, tailwater, overflow routing, and significant grading.
3. Utility/coordination-heavy site with storm, sanitary, water/fire-flow, crossings, reroutes, and profile evidence.

Include at least one intentionally incomplete project to prove that missing evidence remains visible instead of being inferred as success.

## Calculation Review

For each result, prepare the expected value independently before inspecting Civora's output.

| Discipline/check | Independent method/tool | Expected | Tolerance | Civora observed | Difference | Pass/fail | Reviewer notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Areas/lengths | | | | | | | |
| Cut/fill | | | | | | | |
| Rational peak flow | | | | | | | |
| Pipe capacity/HGL/EGL | | | | | | | |
| Detention routing | | | | | | | |
| Sanitary capacity/cover | | | | | | | |
| Water pressure/fire flow | | | | | | | |
| Road/profile/ADA | | | | | | | |
| Quantities | | | | | | | |
| Cost trace | | | | | | | |

Any tolerance must state whether it is absolute, relative, rounding-only, or method-dependent. Do not accept a result solely because Civora and the reference use the same implementation.

## Reactive Change Review

For each project, move or edit a building, basin, road, and utility object. Verify:

- The change is recorded.
- All affected systems become stale before rerun.
- Unaffected systems remain current.
- The impact explanation matches the project relationships.
- Selective rerun updates every affected result.
- Quantities and review deliverables reflect the new geometry.
- Old exports cannot be mistaken for current exports.
- Save, close, reopen, and version comparison preserve the change truthfully.

## Interoperability Review

Open exported DXF and LandXML in each named target application. Record application name/version, object counts, coordinate checks, layers, geometry, labels, profiles/surfaces, IDs or sidecar trace, losses, warnings, and screenshots. Do not infer target-tool compatibility from a successful file write alone.

## Hosted Workflow Review

Complete the full workflow twice from fresh projects on the deployed product. Record timestamps and evidence for authentication, project persistence, address/site context, drawing, semantic conversion, generation, reactive edits, review package, exports, queue completion, browser telemetry, and recovery from at least one induced provider or network failure.

## Discrepancies

| ID | Severity | Project/result | Expected | Observed | Root cause | Fix revision | Retest evidence | Disposition |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

No unresolved critical discrepancy may be hidden by wording, mock data, screenshots, or a passing unrelated test.

## Final Disposition

- Named automated gates passed:
- Named external checks passed:
- Open limitations:
- Suitable scope of use:
- Prohibited or unproven scope:
- Follow-up date:
- Reviewer signature/attestation:

The disposition applies only to the recorded revision, inputs, environments, target tools, and tested workflows.
