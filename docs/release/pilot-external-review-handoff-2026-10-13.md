# External review handoff — preparation only

No reviewer has been contacted and no review acceptance is recorded. Founder authorization is required before sharing project data or recruiting a partner. This checklist supports P6; it does not complete it.

## Package to supply after authorization

- Exact identified release candidate and its regression evidence: [integration progress](pilot-integration-progress-2026-10-13.md).
- Real pilot parcel/survey/control and accepted requirements, including jurisdiction and engineer-entered clearance requirements. Synthetic regression fixtures are not a real site survey.
- Saved canonical project JSON, current preliminary PDF and editable DXF from the same revision. Identify the export scope: drawing-only footprints/linework or a separately current calculated package.
- Source register, assumptions, missing inputs, stale systems, conflict disclosures and explicitly unsupported calculations.
- Preserve original documents and their attribution/usage limits. Do not assume permission to redistribute source files.

## Licensed civil engineer acceptance

Record reviewer name, qualification/jurisdiction, date, tested revision, source inputs and limitations. Ask the reviewer to:

1. Check the actual site brief and required dimensions against supplied evidence.
2. Review supported road/parking geometry, access, setbacks, easements, drainage/utility assumptions and clearance warnings.
3. Identify requirements Civora records but does not automatically evaluate. Do not accept a readiness badge as engineering verification.
4. Test representative revisions, affected recalculation and stale/history behavior.
5. Record concrete corrections and confirm the scope in which the tool is useful. Do not imply a seal, construction approval or independent verification not supplied by that reviewer.

## CAD user acceptance

Open the same DXF in the intended AutoCAD/Civil 3D version; record application/version and evidence. Check units without manual rescaling, coordinates, editable entity types, layers, closed footprints, road outline/centerline/island/markings, and any claimed parking-stall/aisle details. Compare with the canonical drawing and PDF. Identify manual redrawing or cleanup needed, rather than marking download success as editable handoff acceptance.

## Design partner acceptance

Have an authorized designer run the workflow without hidden operator intervention. Record completion time, interruptions, corrections, export reuse and whether another project is worth doing. Start with one partner before expanding to three–five firms.

Before real firm data is introduced, the founder must supply/confirm the support contact, permitted use and limitations, applicable terms and data handling, account permissions, and who accepts the pilot scope. Any legal documents need appropriate human review; this checklist is not legal advice or a published agreement.

## Release dependency

Deployment is a separate approval. Require an exact scoped checkpoint, hosted tenant/worker/artifact checks, recovery evidence and rollback instructions. The local SQLite restore drill is not evidence that hosted PostgreSQL has been restored successfully.
