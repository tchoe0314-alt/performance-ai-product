# Civora Backend Engine Architecture

## North Star

Civora is a living civil engineering intelligence platform. The backend must behave like one coordinated engineering model, not a set of disconnected calculators.

Every engine must:

- read from canonical state
- write only the canonical fields it owns
- mark downstream systems dirty when its owned state changes
- validate its own output before handoff
- expose assumptions, fallbacks, and blocked states explicitly
- provide export-ready and production-ready evidence before deliverables claim readiness

Generated preview/CAD actions are views of canonical truth. They are never the primary source of engineering truth when canonical model objects or summaries exist.

## Backend Layers

1. **AI / Interaction Layer**
   - Parses prompt, image, and structured inputs.
   - Preserves user intent and field source states.
   - Must not silently convert unknown requirements into engineering assumptions in manual or production modes.

2. **Planner / Orchestrator**
   - Chooses stages, reruns dirty dependencies, and explains why each stage ran.
   - Coordinates manual, assisted, and strict behavior.
   - Owns workflow state, not discipline-specific engineering truth.

3. **Canonical Engine System**
   - `ProjectModel` and `ProjectManager` are the shared backend state.
   - Discipline engines write canonical summaries, objects, graphs, surfaces, profiles, conflicts, metrics, and validation records.
   - Each canonical field has one accountable owner.

4. **Coordination / Validation**
   - Coordination resolves multi-system conflicts using rollback-safe candidates.
   - QA validates the final canonical state and reports blocked/incomplete truth.
   - Validation must distinguish errors, warnings, assumptions, fallbacks, and engineer-review items.

5. **Deliverables / Reports / Exports**
   - DXF, sheets, profiles, sections, quantities, and reports are generated from canonical state.
   - Export readiness must be validated before claiming production readiness.

## Canonical Ownership Rules

- Geometry owns canonical spatial primitives and topology.
- Terrain/surface owns existing and proposed surfaces.
- Grading owns finished-grade elements, contours, spot grades, and grading repairs.
- Drainage owns surface-water features, low points, flow paths, drainage basins, and drainage export validation.
- Storm pipe owns storm pipe networks, hydraulics, HGL checks, inlet/outfall graph data, and storm validation.
- Sanitary owns sanitary segments, manholes, services, cover/slope validation, and sanitary graph validation.
- Water owns pressurized utility segments, hydrants, fire-flow checks, pressure zones, and water validation.
- Utility coordination owns multi-utility conflict state, resolution history, candidate scoring, and coordination realism.
- Roadway/corridor owns alignments, profiles, intersections, crowns, sidewalks, and corridor sections.
- Structure owns retaining walls, foundations, bridges, excavation interactions, and civil/structural conflicts.
- Earthwork owns cut/fill, balancing, excavation limits, material movement, and phasing intelligence.
- Hydrology owns runoff methods, storm events, hydrographs, detention sizing basis, and flood routing.
- Conflict resolution owns rollback-safe solving, cluster grouping, ownership rules, and candidate acceptance.
- QA owns completeness, code, constructability, production-readiness, and reviewer-prediction checks.
- Quantity owns traceable material, pipe, pavement, earthwork, wall, excavation, and cost quantities.
- Export/CAD owns DXF/Civil3D/LandXML/sheet/package deliverables and export audit.
- Profile/section owns live profile and section views tied to canonical alignments and systems.
- GIS/existing conditions owns parcels, zoning, floodplain, wetlands, imagery, survey, existing utilities, and coordinate systems.
- AI orchestration owns interpretation, subsystem workflow, explanations, assumptions, and intelligent reruns.
- Reactive model owns change propagation, dirty-state reasons, partial reruns, and live update reports.

## Mode Rules

### Manual / Production Mode

Manual and production behavior must not hide backend uncertainty.

Forbidden:

- silent critical fallback use
- assumption-based closure of critical conflicts
- claiming export readiness with missing canonical data
- claiming hydraulic completeness with geometry-only pipe data
- using preview actions as the only source for quantities when canonical state exists

Required:

- explicit failure codes
- source fields
- reason class
- affected system
- missing computation
- unresolved conflicts with location when available
- engineer-review flags when a check cannot be automated safely

### Assisted Mode

Assisted mode may continue with assumptions, but must label them and preserve enough context for review.

Required:

- assumption records
- candidate/failure reasoning
- reviewer-facing warnings
- no mutation of user-locked fields without explicit acceptance

## Reactive Dependency Rules

The backend must be able to answer: "What changed, what became dirty, what reran, and why?"

Minimum dependency expectations:

- geometry changes dirty layout-derived geometry, grading, drainage, storm, sanitary, utilities, coordination, earthwork, profiles, quantities, QA, and exports
- terrain/surface changes dirty grading, drainage, storm, earthwork, profiles, QA, and exports
- road/corridor changes dirty grading, drainage, storm, utilities, ADA checks, profiles, sections, quantities, QA, and exports
- grading changes dirty drainage, storm, sanitary cover, utilities cover, earthwork, profiles, QA, and exports
- drainage changes dirty storm pipes, detention, hydrology checks, quantities, QA, and exports
- storm changes dirty coordination, sanitary checks, utility checks, profiles, quantities, QA, and exports
- sanitary changes dirty coordination, earthwork, profiles, quantities, QA, and exports
- water/utility changes dirty coordination, earthwork, profiles, quantities, QA, and exports
- structures change dirty grading, drainage, utilities, excavation, quantities, QA, and exports
- coordination changes dirty earthwork, profiles, quantities, QA, and exports
- hydrology changes dirty drainage, storm, detention, quantities, QA, and exports

## Engine Contract Requirements

Every backend engine must have a machine-readable contract with:

- engine id and human name
- purpose
- current modules
- owned canonical fields
- read dependencies
- downstream dirty targets
- required validations
- final capabilities
- manual-mode forbidden behavior
- production-readiness gates
- export-readiness gates where relevant
- golden scenarios it must pass

The contract registry lives in `backend/planning/engine_contracts.py`.

## Golden Scenario Requirements

Backend readiness is measured against repeatable scenarios:

- small commercial pad
- multifamily site
- mixed-use 14-acre site
- sloped detention site
- roadway corridor
- utility-conflict-heavy site
- floodplain/wetland constrained site
- retaining wall site
- incomplete/bad input case
- manual production-gate case

Each scenario must eventually define:

- expected canonical fields
- expected blocked states
- expected QA failures/warnings
- expected quantities
- expected export readiness
- expected rerun propagation when a key object changes

## Current Backend Priority

Backend work should proceed in this order:

1. enforce contract registry and canonical ownership
2. deepen dirty-state/reactive graph behavior
3. make every engine rerunnable from canonical state
4. replace hidden assumptions/fallbacks with blocked states in manual/production mode
5. deepen terrain, hydraulics, grading, and corridor realism
6. tie profiles, sections, quantities, QA, and exports strictly to canonical truth
7. add golden real-world scenarios as non-negotiable regression tests

