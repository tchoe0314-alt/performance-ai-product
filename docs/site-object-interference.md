# Native site objects and concept interference

The Libraries panel adds a native parametric cul-de-sac or a pipe draft, and can
import the standalone study JSON alongside existing objects. Native objects use
the editor's selection, undo, stale-state and project persistence paths. Road
dimensions rebuild geometry; arbitrary vertex/size edits detach the parametric
model rather than claiming the edited shape is still an exact cul-de-sac.

The Draw panel reports type-aware interference. Buildings and occupied surfaces
conflict in plan; connected road/sidewalk surfaces may overlap. A road crossing
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
