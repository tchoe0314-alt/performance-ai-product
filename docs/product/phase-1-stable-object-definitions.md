# Phase 1.2 — Stable object definitions

Status: complete locally for the current canvas catalog and agreed authoring workflows. Not deployed by this milestone.

## Authoring behavior

- Draw first; classify afterward as a standard or custom object. Naming is optional.
- Custom definitions support optional text, number and checkbox properties. Reuse is project-local or account-wide, chosen by the user. Project definitions survive removal of their last instance. Account definitions require authentication and are isolated by account; account export includes them and account deletion removes them.
- Connected linework can be combined into an editable outline. Closing an incomplete outline is offered, not forced. Declining leaves an editable draft and pauses affected calculations. Disconnected, branching or duplicate-edge chains cannot silently become a footprint.
- Organizational groups keep members separate. Nested groups have a single-parent, acyclic tree. Move, resize, rotate and visibility operations preserve membership. Protected members prevent an inappropriate group transform. Copy, delete and reclassification of a group require ungrouping first.
- Semantic outlines can be edited and uncombined into their current edges, including after insertion of a vertex. Existing undo/redo paths restore those changes. Durable unified history is Phase 1.3, not claimed here.

## Authoritative record

`civora_object_v1` records contain stable ID, human name, standard/custom type, geometry and units, layer/visibility/lock, source, creator, revision, validation, dependency status, object/calculation relationships and export mapping. The shared 28-type catalog is `core/data/site_object_definitions_v1.json`.

Each canvas wrapper retains `canvas_placement_v1` as the compatibility projection and adds `object_v1` as its authoritative standardized record. Reads restore from the standardized record when present; legacy-only projects remain supported. Unrelated document sections and compatibility metadata are preserved.

The server reconstructs revisions and geometry validation at the locked save boundary. Client claims do not certify geometry. New manual/import objects receive the authenticated creator; existing creator attribution is preserved and legacy unknown creators are not retroactively assigned.

Malformed records, duplicate IDs, invalid custom libraries, missing/non-group parents and group cycles are rejected. Geometric draft errors remain saveable but pause affected calculations. Both the website and direct/queued backend execution enforce that pause; previous calculation results remain available without becoming active for the changed draft.

## Engineering boundaries

Geometric validity is not engineering approval: `engineering_verified` remains false. Custom and unknown types are reference-only and acquire no inferred engineering rules. Organizational groups are not physical obstacles. Physical members, combined outlines and ordinary hidden objects remain included in relevant physical checks; preserved source traces are not double-counted. Older program/block bounds remain editing representations, not certified physical footprint unions.

Actual utility elevations, foundations, surveys, clearance requirements and professional review remain necessary to establish real-world interference and design correctness. This milestone does not clear hosted/Postgres operational evidence or deferred release gates.

Evidence: [completion report](../release/phase-1-stable-object-definitions-completion-2026-10-04.md). The subsequent [Phase 1.3 milestone](phase-1-unified-edit-transactions.md) adds unified durable edit transactions and history.
