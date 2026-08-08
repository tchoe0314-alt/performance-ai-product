# Civora RC1 Engineer UAT Packet

This packet must be completed by a qualified civil engineer who was not responsible for implementing the tested behavior. Automated tests cannot complete or sign this packet.

## UAT Record

| Field | Value |
| --- | --- |
| Engineer/reviewer | Pending |
| Organization | Pending |
| Relevant license/jurisdiction, if applicable | Pending |
| Civora release revision | Pending |
| Hosted frontend/backend deployment IDs | Pending |
| Test dates | Pending |
| Evidence folder/link | Pending |

## Scenario A: 4.2-Acre Commercial Site

Use a real or permission-cleared site with an approximately 28,000 SF office, 140 parking spaces, detention, public water, sanitary, storm sewer, driveway, sidewalks, ADA route, and sloped terrain.

1. Start a clean project from an address.
2. Define and lock the site.
3. Review parcel, road, building, terrain, flood, wetland, and utility source results.
4. Accept or reject detected candidates and record why.
5. Import survey/control data where available.
6. Draw at least one building, parking area, driveway, basin, utility path, and structure.
7. Generate available grading, drainage, storm, sanitary, water, roadway, earthwork, and quantity results.
8. Move one major object and verify affected-system and stale-output behavior.
9. Create a review package and supported exports.
10. Compare Civora outputs against independently prepared calculations and geometry.

## Scenario B: Constrained Infill Site

Use a different jurisdiction and a compact or irregular site with close property constraints, an existing building or pavement, a roadway tie-in, and incomplete utility evidence.

Verify that Civora:

- does not invent missing survey, utility, datum, or standards evidence;
- makes irregular geometry selectable and editable;
- detects or explains topology errors;
- handles an unavailable provider without silent failure;
- preserves unaffected work after an edit;
- produces an understandable review package with missing items stated plainly.

## Scenario C: Complex Real-File Import

Use permission-cleared PDF plus at least one supported spatial or survey file such as DXF, LandXML, GeoJSON, GeoTIFF, LAS/LAZ, or survey CSV.

Verify:

- source metadata and original-file trace are preserved;
- supported records import and unsupported records are reported;
- imported/detected candidates require review before becoming canonical objects;
- accepted geometry can be selected, converted, edited, saved, reopened, and exported;
- units, scale, coordinates, elevations, and object IDs remain consistent;
- the review package does not silently include stale or rejected content.

## Independent Comparison Table

Attach independent calculations, source files, screenshots, and marked-up exports. Add rows as needed.

| Scenario | Discipline/output | Independent expected result | Civora result | Tolerance | Difference | Acceptable? | Evidence link |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | Site geometry/area | Pending | Pending | Pending | Pending | Pending | Pending |
| A | Grading/cut-fill | Pending | Pending | Pending | Pending | Pending | Pending |
| A | Hydrology/storm | Pending | Pending | Pending | Pending | Pending | Pending |
| A | Sanitary | Pending | Pending | Pending | Pending | Pending | Pending |
| A | Water/fire flow | Pending | Pending | Pending | Pending | Pending | Pending |
| A | Quantities | Pending | Pending | Pending | Pending | Pending | Pending |
| B | Constraints/conflicts | Pending | Pending | Pending | Pending | Pending | Pending |
| C | Import/export roundtrip | Pending | Pending | Pending | Pending | Pending | Pending |

## Experience Review

Rate each item from 1 to 5 and record evidence for scores below 4.

| Area | Score | Notes/evidence |
| --- | --- | --- |
| First-project clarity | Pending | Pending |
| Site setup | Pending | Pending |
| Drafting precision | Pending | Pending |
| Object meaning and inspector | Pending | Pending |
| Existing-condition trust | Pending | Pending |
| Generate workflow | Pending | Pending |
| Change reaction and stale truth | Pending | Pending |
| Review explanations | Pending | Pending |
| Deliverables | Pending | Pending |
| Performance and stability | Pending | Pending |

## Defect Record

Every safety/source-trust/data-loss issue is P0. Every blocker in the primary scenario, misleading calculation, stale-output failure, inaccessible primary control, or repeatable severe performance failure is P1.

| ID | Severity | Scenario/step | Expected | Actual | Reproducible? | Owner | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |

## Human Decision

- [ ] All P0 and P1 findings are resolved and retested.
- [ ] Numeric and geometric comparisons are acceptable for the explicitly tested review scope.
- [ ] Source and assumption language is understandable.
- [ ] The reviewer understands Civora output still requires qualified professional review.
- [ ] Recommend controlled invite-only use for the recorded scope.

Reviewer decision: **Pending**

Reviewer name: **Pending**

Date/time/timezone: **Pending**

Evidence link: **Pending**
