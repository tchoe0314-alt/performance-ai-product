# Phase 3.1 — Active Brief Summary

## Purpose and scope

Show the live project's targets, constraints and missing information before generation. A read-only card appears in Brief / Setup and in the optional professional Brief/chat dock. Four primary rows are immediately visible; the remaining requirements use a compact disclosure. Existing project identity, Edit brief navigation, chat and setup controls remain available.

The summary lists all 18 categories in roadmap 3.1: gross and usable acreage, building-area and storey targets, use, parking ratio and required parking, aisle dimensions, access and egress, setbacks, height, lot coverage, maximum impervious coverage, open space, stormwater assumptions, protected geometry and optimization priorities.

## Source of truth

`activeBriefSummary.ts` projects the existing live payload without creating React state, persisting new values or changing calculations. Protected-object status uses the existing canonical protection helper. Valid polygon acreage uses its actual outline, never its bounding rectangle. Valid rectangular sites or explicit dimensions can supply rectangular acreage. Ambiguous/invalid geometry and unsupported or absent units remain unknown. Feet and meters have explicit acreage conversion.

Entered parking controls take precedence over drawn stall totals. Blank controls remain unknown; zero is preserved where valid, fractional parking counts rejected. Usable acreage, building height or storeys are not inferred from crude bounds or drawn geometry. No missing code requirement is auto-filled or claimed compliant.

Two legacy stored program fields (building-area target and building use) can fall back to the current saved project's explicit program when the live control projection omits them. Explicit live values, including invalid/blank values, take precedence. Saved geometry, old parking counts and previous calculation results are not restored by that fallback.

Unsupported or absent values visibly read **Not set**. Requirement classification, richer trust/source records and editing these currently absent fields are subsequent milestones 3.2 and 3.3, not claimed complete here. Opening this summary does not establish input completeness or engineering validity, and does not bypass generation/review gates.

## Execution rule

Focused affected-workflow checks close individual milestones. The founder's broader Phase 0–current audit is repeated at the end of each complete phase. Hosted candidate verification, external engineering and CAD review remain independent release/pilot gates.
