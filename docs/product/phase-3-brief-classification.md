# Phase 3.2 — Requirement classification

## Behavior

The founder approved explicit selection of Required versus Preferred. Existing and new unclassified values are **Unknown**, not guessed. A known value's compact disclosure offers Required, Preferred, Assumed or clearing the choice. Missing values cannot acquire a requirement or confirmation. Assumed records intent, not a construction-level approval or permission to run an otherwise blocked calculation.

Every row exposes its trust status. The versioned model supports User entered, User confirmed, Sourced, Calculated, Externally verified and Unverified. Computed acreage starts Calculated; legacy program and other values are conservatively Unverified. User confirmed requires an explicit button press. The UI does not offer automatic sourced/external verification promotion. Stored Sourced/Externally verified records require a reference and remain user-recorded provenance, not authentication of an external reviewer or platform certification. Source attachment and fuller provenance editing remain 3.3.

## Persistence and freshness

The sole persisted record is `meta.site_inputs.active_brief_classifications_v1`, carried through the existing canonical project adapter, project saving and edit snapshots. No separate React classification store or database table is added. Each entry has a priority, trust status and exact value/source binding; sourced/external entries also have a reference. Raw values are bound before display rounding. Changed or absent inputs show Unknown/unverified (Calculated for computed acreage) and a review indication instead of activating an old confirmation.

The existing calculation fingerprint includes site inputs. Classification changes therefore invalidate previous input bindings and conservatively mark engineering systems stale; old results are not republished merely because only displayed numbers stayed the same. Undo/redo uses the existing transactional edit history. Failed saves preserve local choices and visibly report failure.

Owners/editors may classify; viewer/reviewer views expose no editing controls and the existing API permissions still enforce writes. Invalid versions, field IDs, priorities, statuses and references are rejected at frontend canonical serialization and backend project validation. Malformed data is not treated as verified.

## Scope boundary

This milestone records requirement intent and provenance. It does **not** relax existing hard constraints, invent jurisdictional rules or claim that legacy solvers now implement every preference/assumption type. Full brief value/unit editing, source attachment/reset and relaxation workflow are 3.3; broader requirement-to-solver policy is separate roadmap work. Unknown fields from 3.1 remain visibly missing until those inputs exist.

## Compatibility repair

A real-local save test reproduced loss of a legacy `building_program_sf` field during classification autosave. Both the live payload and direct calculation builders now preserve the explicit saved building-area/use fields when the current builder does not supply them. Explicit live values win. Geometry, parking quantities and previous results are never restored from the saved project by this helper.
