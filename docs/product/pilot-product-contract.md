# Civora Pilot Product Contract

## Pilot promise

Civora turns a user's project intent and site context into an editable conceptual
site plan, then helps the user review the engineering consequences and prepare a
review package. The pilot is for planning and qualified human review. It does not
produce construction authorization or replace professional judgment.

The initial pilot should optimize for one repeatable commercial-site workflow
before expanding to additional project categories.

## Primary workflow

1. Describe the project intent.
2. Add an address, boundary, survey, imagery, GIS, terrain, and known constraints.
3. Review the extracted project brief, sources, assumptions, and missing inputs.
4. Generate one or more conceptual site-plan candidates.
5. Edit the selected candidate directly on the plan.
6. Review which engineering systems became stale because of each edit.
7. Regenerate only the affected systems after user confirmation.
8. Review assumptions, conflicts, quantities, and unresolved items.
9. Create technical, clean-concept, and high-quality presentation views.
10. Export an engineer-review package with traceable status and sources.

## Direct editing is required

The first generated concept is a starting point, not a final answer. A pilot user
must be able to:

- select, move, rotate, resize, duplicate, lock, unlock, and delete buildings;
- draw a new building or other supported site object;
- edit geometry directly and edit important dimensions numerically;
- move or revise entrances, roads, parking, utilities, ponds, and major site objects;
- undo and redo changes without losing the previous concept;
- compare the edited concept with an earlier version; and
- request an equivalent change in plain language when the action is supported.

User intent has priority. Locked objects may not move during regeneration. Deleted
objects may not silently return. Unsupported changes must fail visibly with a useful
next action.

## Engineering response to edits

Editing an object is not only a drawing operation. Civora must identify the systems
affected by the change and mark their results and exports stale. Moving a building,
for example, may affect setbacks, access, parking, grading, drainage, utilities,
quantities, and presentation imagery.

Visual movement should feel immediate. Expensive engineering recalculation should
remain under user control. Civora should explain the affected systems and ask for
confirmation before a broad rerun. Accepted reruns should preserve locked geometry,
recompute only the necessary downstream systems, and report material changes.

## Visualization modes

Civora should expose distinct views with distinct truth guarantees:

- **Technical plan:** measurable geometry, sources, constraints, dimensions,
  engineering systems, assumptions, and review markers.
- **Clean concept:** a simplified presentation plan derived from the same geometry.
- **High-quality aerial:** realistic presentation imagery derived from the current
  plan, with illustrative visual details clearly identified.
- **3D perspective:** a presentation view from user-selected cameras.
- **Comparison:** existing versus proposed, or previous versus current concept.

High-quality imagery is never the engineering source of truth. The canonical plan
and its object state must drive every visualization.

## High-quality imagery fidelity gate

A high-quality image is not current unless all of the following remain consistent
with the canonical plan:

- building count, footprint, placement, orientation, and approximate height;
- entrances, roads, parking layout, and approximate stall count;
- property boundary and protected or constrained areas;
- detention, major drainage, and other material site features;
- visibility and placement of user-locked objects; and
- absence of objects the user deleted.

Landscaping, vehicles, facade detail, materials, lighting, season, and atmospheric
detail may be illustrative. The interface must say so. A plan edit makes affected
visualizations stale until they are regenerated and pass fidelity checks.

Recommended quality levels:

- **Draft:** fast spatial preview for iteration.
- **Standard:** clearer concept imagery for routine review.
- **Presentation:** highest-quality output with stricter fidelity verification.

## Pilot success criteria

The pilot succeeds when qualified users can complete the workflow without hidden
operator intervention and the following evidence is recorded:

- time from raw inputs to a usable first concept;
- time saved relative to the user's normal workflow;
- number and severity of manual corrections;
- geometry and visualization fidelity failures;
- percentage of exported work that remains reusable downstream;
- repeat use on another project; and
- willingness to pay for the workflow.

Feature expansion should remain secondary to correctness, editability, traceability,
and demonstrated time savings in this workflow.
