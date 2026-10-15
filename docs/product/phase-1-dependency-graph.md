# Phase 1.4 — Dependency graph

Purpose: preserve explicit relationships when users edit related objects, without silently applying an unapproved design.

## Policies and authoring

New geometry relationships default to Ask. Follow applies dependent geometry in the same transaction; Ask previews the whole transaction and leaves the working geometry unchanged until acceptance; Fixed prevents changes to the linked target until its policy is explicitly changed; Independent documents the association without driving geometry. Existing object locks and source/reference protections remain independent safeguards.

The inspector retains its existing parking controls, adds Independent, and exposes other links in a collapsed Relationships section. Compatible objects are explicitly selected, not inferred from proximity. Geometry-quantity relationships can also be selected. There are no inferred hydraulic, clearance or professional-approval claims.

Supported direction is driver → dependent:

- Road → parking: preserve offsets and parking dimensions under move/rotation.
- Building → parking: retain the existing bounded parking reflow and capacity-preservation behavior.
- Building → setback: preserve rectangular offsets during rectangular size changes; arbitrary outlines retain their geometry and require review rather than receiving an invented offset curve.
- Road → cul-de-sac: move/rotate the parametric bulb; changes to a straight rectangular road's cross-road depth rebuild its bounded 20–48 ft approach-width transition, respecting the bulb's coordinate units.
- Road → access: move/rotate the selected entrance or access geometry.
- Pond → drainage area: explicitly associate a basin with an open-space/landscape area or an object marked as a drainage area. Movement preserves its outline; it does not delineate a watershed or solve hydrology.
- Building → utility: preserve selected utility geometry's positional relationship. Routing, elevations and real-world clearance still require engineering inputs.
- Geometry → quantity: draft area or length refreshes under Follow, is proposed under Ask, remains stale under Fixed, and stays separate under Independent. Invalid outlines have unavailable quantities. These annotations do not replace engineering calculation results or make stale calculations active.

## Architecture and persistence

`meta.dependency_links_v1` stores stable edge ID, relationship kind, target ID and policy. Legacy parking relationships remain supported. Quantity policy is `meta.quantity_relationship_v1`; draft measurements retain their geometry fingerprint and review-only status. The canonical document's owned `dependencies` records are rebuilt from validated object intent at save time; unrelated dependency records are preserved.

The shared placement boundary checks every ordinary writer. Inspector/chat planners also plan the entire graph before creating a proposal. Downstream changes propagate once, while explicitly edited members of a bulk transaction are not moved twice. Missing or incompatible targets, duplicate identities, cycles and competing active geometry drivers are rejected. Independent links do not introduce active geometry cycles.

Acceptance checks exact project identity and the complete source snapshot. A stale proposal cannot replace newer geometry. Phase 1.3 persists the complete edit and its Undo/Redo history, including related objects. Restore and history replay bypass fresh proposal creation because they replay an already recorded transaction.

Layout alternatives include dependency effects before scoring and previewing. Apply approves exactly the selected preview, not extra unpreviewed moves. Fixed protections and stale-layout checks remain enforced. Backend validation rejects malformed saved graphs and direct geometry changes to continuously Fixed targets unless their relationship policy is explicitly changed.

## Boundaries

These are concept-plan relationships, not certified utility routing, survey-controlled attachments, nonrectangular offset construction, drainage delineation or engineering quantities. General moves preserve offsets/dimensions; they do not guarantee boundary clearance or freedom from collisions. Parking checks remain basic plan checks, and hidden physical obstacles are not permission to bypass engineering review. Existing live constraints, calculation invalidation and source-review gates remain required.

Verification: [local completion report](../release/phase-1-dependency-graph-completion-2026-10-04.md).
