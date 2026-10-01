# Native site objects and concept interference

The Libraries panel adds a native parametric cul-de-sac or a pipe draft, and can
import the standalone study JSON alongside existing objects. Native objects use
the editor's selection, undo, stale-state and project persistence paths. Road
dimensions rebuild geometry; arbitrary vertex/size edits detach the parametric
model rather than claiming the edited shape is still an exact cul-de-sac.

The Draw panel reports type-aware interference. Buildings and occupied surfaces
conflict in plan; road/sidewalk overlaps require a documented intentional connection. A road crossing
a cul-de-sac island remains a review issue. Restrictions and uncertain objects
require review. Hidden physical objects still count; combined editing hulls do
not duplicate their preserved source objects.

A pipe crossing a building is not automatically safe or automatically a clash.
Both objects need reviewed occupied vertical envelopes, including foundations,
on the same named datum, with evidence and explicit required clearance. A pipe
also needs an outside diameter consistent with its envelope. Missing evidence
or clearance means review; intersecting volumes or insufficient clearance mean
conflict. A separated result only proves separation of these supplied envelopes.

Parameters and evidence are preserved in project JSON and canonical engineering
attributes. The 2D and 3D road previews include the island and center markings.
Vertical evidence is not automatically converted into terrain-relative 3D height.

## Limits before engineering reliance

This is concept screening, not construction approval or code compliance. Rules
do not invent local regulatory clearances. Global envelopes cannot represent
varying pipe profiles or detailed foundations. Pipe footprint end caps are
conservative. Boundary screening is preliminary, and downstream CAD/export
consumers still need explicit verification of island holes and semantic data.
Real surveyed elevations, foundation/utility information and engineering review
are required before trusting a separated crossing in a real project.

## Expanded object rulebook

Every SiteObjectType has an explicit category and engineering guidance in
`siteObjectRulebook.ts`. Bridges and custom geometry remain evidence-required,
not silently classified as safe. Site/lot planning containers are not solids.

Selected objects expose compatibility requirements in a collapsed editor section.
Reviewed horizontal buffers can represent roots, foundation projections,
maintenance access or separation. They extend beyond the modeled footprint;
two objects' buffers add. Contact with these buffers requires review even if
the physical objects are separated vertically or intentionally connected.
Blank/malformed/unreviewed buffer evidence is not treated as verified clearance.
These isotropic buffers are conservative screening, not detailed root, footing
or access geometry, and are not rendered as separate solids.

Setback geometry explicitly means either an excluded area or a buildable area,
with an entered list of applicable object types and reviewed source. Missing
meaning/scope/evidence requires review. No jurisdictional distances are invented.
Containment checks split polygon edges at boundary crossings to catch concave
notches instead of checking corners alone. Boundary contact is allowed for
containment, but counts as contact with an excluded area.

Intentional connections are limited to surface/surface and utility/fixture
relationships, never a blanket waiver for a building. Network connections stay
review-required for fitting, network compatibility and access checks. The new
metadata is preserved through project JSON and canonical engineering attributes.
Mixed coordinate units are flagged rather than compared as if identical.
