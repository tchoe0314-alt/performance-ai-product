> Authoritative product roadmap. Adopted October 2, 2026. The founder-approved product-governance rules appended below take precedence over conflicting older plans. This document defines intended requirements, not evidence that features or readiness gates are complete.

# Civora Master Product and Execution Roadmap

## 1. Product mission

Civora will be a preliminary civil feasibility and concept-design platform that allows professionals to:

- Establish a structured project brief.
- Import real site information.
- Draw site elements manually.
- Generate site concepts conversationally.
- Manipulate geometry directly and see immediate updates.
- Generate multiple meaningful alternatives.
- Apply civil constraints and dependencies.
- Compare tradeoffs.
- Trace calculations, assumptions, and sources.
- Export useful geometry to existing CAD workflows.
- Produce professional preliminary-feasibility reports.

Civora will initially assist licensed professionals. It will not claim to replace the Engineer of Record, produce stamp-ready construction documents, or guarantee municipal approval.

## 2. Primary product milestone

The first major commercial milestone is:

> Three to five boutique civil-engineering or land-development firms use Civora on at least ten real preliminary feasibility studies, save at least 50% of concept-development time, export usable geometry into their CAD environment without redrawing, and encounter no critical trust or data-loss failures.

Success also requires:

- At least two pilot firms willing to continue paying.
- At least one usable case study.
- Evidence that Civora improves an existing workflow.
- A prioritized roadmap based on observed customer behavior.

---

# Phase 0 — Consolidation and product stabilization

## Objective

Turn the current collection of working features and experiments into one dependable product baseline.

No major new product area should be started until this phase is complete.

## 0.1 Repository and feature consolidation

- Inventory all current files, branches, experiments, and uncommitted changes.
- Identify changes produced across different development chats.
- Determine which implementation is authoritative when features overlap.
- Identify duplicate components and duplicated business logic.
- Remove abandoned experiments after confirming they are no longer needed.
- Preserve useful prototypes separately when appropriate.
- Create a single integration branch.
- Establish a known-good product version.
- Record all currently supported features.
- Record all known limitations.

## 0.2 Current-feature verification

Test all existing functionality, including:

- Canvas object creation.
- Selection.
- Movement.
- Resizing.
- Rotation.
- Direct property editing.
- Chat commands.
- Canonical-model synchronization.
- Fixed, following, asking, and independent dependencies.
- Building movement.
- Road movement.
- Parking reflow.
- Cul-de-sac editing.
- Constraint warnings.
- Alternative generation.
- Alternative scoring.
- Apply, cancel, and undo.
- Layer visibility.
- Bulk layer selection.
- Commercial workflow.
- Two-dimensional workflow.
- Three-dimensional workflow.
- Export behavior.
- Authentication.
- Project saving and reopening.

## 0.3 Test-system repair

- Finish the interrupted candidate-solver tests.
- Replace tests that rely on hard-coded alternative names.
- Repair stale selectors.
- Add stable test identifiers.
- Run the complete automated test suite together.
- Add regression tests for previously fixed bugs.
- Separate unit, integration, workflow, and browser tests.
- Create a release-critical test suite.
- Add a repeatable end-state validation command.
- Document which tests require external credentials.
- Test failure and recovery behavior.

## 0.4 Code maintainability

- Break oversized page components into focused modules.
- Break the main preview or canvas component into smaller systems.
- Separate interface code from geometry and calculation logic.
- Centralize project-state operations.
- Centralize command execution.
- Centralize constraint evaluation.
- Remove parallel sources of truth.
- Establish clear module ownership.
- Document core architecture.
- Resolve safe dependency upgrades.
- Track remaining dependency advisories.

## 0.5 Release engineering

- Establish development, staging, and production environments.
- Define environment variables and secret handling.
- Create a deployment checklist.
- Add database migration procedures.
- Add backup procedures.
- Add rollback procedures.
- Create versioned release notes.
- Deploy the consolidated build to staging.
- Test the exact deployed build.
- Verify authenticated workflows.
- Promote only verified releases to production.

## Exit criteria

Phase 0 is complete when:

- One clean product version exists.
- All release-critical tests pass.
- Core workflows work from beginning to end.
- The deployed build matches the tested build.
- No known critical data-loss or geometry-corruption defect remains.
- The recent candidate-search implementation is either fully verified or safely removed from the release.

---

# Phase 1 — Canonical project model and design system

## Objective

Create the stable foundation that every interface and engineering function uses.

## 1.1 Canonical project model

Create one authoritative project model containing:

- Project information.
- Client information.
- Site information.
- Units.
- Coordinate system.
- Parcel geometry.
- Buildings.
- Roads.
- Access points.
- Cul-de-sacs.
- Parking.
- Sidewalks.
- Setbacks.
- Easements.
- Landscape areas.
- Stormwater features.
- Grading concepts.
- Utilities.
- Annotations.
- Constraints.
- Dependencies.
- Sources.
- Assumptions.
- Calculation results.
- Quantities.
- Alternatives.
- Revisions.
- Export history.

## 1.2 Stable object definitions

Create standardized schemas for every object type.

Each object should have:

- Stable unique ID.
- Human-readable name.
- Object type.
- Geometry.
- Layer.
- Visibility status.
- Lock status.
- Dependency status.
- Source.
- Created-by information.
- Revision metadata.
- Validation status.
- Calculation relationships.
- Export mapping.

## 1.3 Unified transaction system

Every operation must pass through one transaction system:

- Chat commands.
- Canvas manipulation.
- Inspector edits.
- Imported geometry.
- Generated alternatives.
- Suggested conflict resolutions.
- Bulk actions.

Each transaction should record:

- Previous values.
- New values.
- Affected objects.
- Reason for the change.
- User or system responsible.
- Calculation invalidations.
- Warnings.
- Timestamp.
- Undo instructions.

## 1.4 Dependency graph

Support four relationship behaviors:

- **Follow:** Related geometry updates automatically.
- **Ask:** Civora previews the related change and requests confirmation.
- **Fixed:** The object cannot move or change without explicit override.
- **Independent:** The object does not react to the relationship.

Dependencies should support:

- Road-to-parking relationships.
- Building-to-parking relationships.
- Building-to-setback relationships.
- Road-to-cul-de-sac relationships.
- Access-to-road relationships.
- Pond-to-drainage-area relationships.
- Utility-to-building relationships.
- Quantity-to-geometry relationships.

## 1.5 Design system

Define a consistent system for:

- Typography.
- Spacing.
- Panel sizes.
- Buttons.
- Inputs.
- Menus.
- Cards.
- Tooltips.
- Dialogs.
- Inline confirmations.
- Tables.
- Charts.
- Notifications.
- Empty states.
- Loading states.
- Error states.

Define distinct visual treatments for:

- Selected.
- Hovered.
- Hidden.
- Locked.
- Fixed.
- Following.
- Stale.
- Updating.
- Blocked.
- Unverified.
- Conflicting.
- Assumed.
- Verified.

Do not rely solely on color. Use labels, icons, and patterns as well.

## Exit criteria

- All major editing methods update the same model.
- Every operation can be undone.
- Object schemas are documented.
- Dependency behavior is consistent.
- No duplicated project-state system remains.
- Interface states are visually consistent.

---

# Phase 2 — Broad workspace shell

## Objective

Create the complete interface structure while keeping the default experience simple.

## 2.1 Global navigation and project header

Add:

- Editable project name.
- Client name or ID.
- Site ID.
- Address.
- APN or parcel identifier.
- Project stage.
- Active revision.
- Saved or unsaved status.
- Online or offline status.
- Last successful save.
- Last successful calculation.
- Project-health badge.

## 2.2 Five workspace stages

Use these stages:

1. Brief
2. Explore
3. Analyze
4. Review
5. Deliver

These are workspace presets, not restrictive wizard steps.

A user may return to any stage without losing work.

## 2.3 Environment controls

Add:

- Instant 2D/3D toggle.
- Satellite layer.
- Topographic layer.
- Zoning layer.
- Parcel-boundary layer.
- Survey layer.
- Utility layer.
- Imperial/metric control.
- Coordinate-system display.
- Grid controls.
- Snapping controls.

## 2.4 Main action controls

Add clear actions for:

- Share session.
- Save milestone.
- Generate report.
- Export DXF.
- Export supported LandXML data.
- Open revision history.
- Open project settings.

## 2.5 Flexible workspace panels

The main structure will contain:

- Left brief/chat panel.
- Central design canvas.
- Right inspector/health panel.
- Bottom Live Delta Bar.

All panels should be:

- Collapsible.
- Resizable.
- Context-sensitive.
- Keyboard accessible.

Add:

- Full-canvas focus mode.
- Saved workspace layouts.
- Simple mode.
- Professional mode.

## Exit criteria

- The interface works at common laptop and desktop sizes.
- The canvas remains usable with both panels open.
- Users can hide every supporting panel.
- Navigation stages do not block editing.
- The active project, stage, revision, and health state are always understandable.

---

# Phase 3 — Project brief and source-data foundation

## Objective

Give Civora a clear, structured understanding of the project before generating designs.

## 3.1 Active Brief Summary

Include:

- Gross acreage.
- Usable acreage.
- Building-area target.
- Storey target.
- Building-use type.
- Parking ratio.
- Required parking.
- Drive-aisle dimensions.
- Access requirements.
- Egress requirements.
- Setbacks.
- Height limits.
- Lot coverage.
- Maximum impervious coverage.
- Open-space target.
- Stormwater assumptions.
- Protected geometry.
- Desired optimization priorities.

## 3.2 Requirement classification

Every brief value should be classified as:

- Required.
- Preferred.
- Assumed.
- Unknown.

Every value should also carry a trust status:

- User entered.
- User confirmed.
- Sourced.
- Calculated.
- Externally verified.
- Unverified.

## 3.3 Brief editing

Create an Edit Brief drawer that supports:

- Direct value editing.
- Unit editing.
- Priority selection.
- Source attachment.
- Confirmation status.
- Requirement relaxation.
- Reset to source value.
- Viewing dependent calculations.

## 3.4 Source-data workspace

Support:

- Survey files.
- Parcel records.
- GIS information.
- Aerial imagery.
- Terrain.
- Contours.
- Zoning documents.
- Municipal standards.
- Easements.
- Rights-of-way.
- Wetland information.
- Flood information.
- Geotechnical reports.
- Traffic information.
- Utility records.

Each source should record:

- Name.
- Type.
- Origin.
- Applicable jurisdiction.
- Effective date.
- Imported date.
- Version.
- User acceptance.
- Verification status.
- Superseded status.
- Dependent objects and calculations.

## 3.5 Missing-information system

Civora should explain:

- What information is missing.
- Why it matters.
- Which calculations it blocks.
- Which calculations can proceed provisionally.
- What assumption Civora could use.
- What professional verification remains necessary.

## Exit criteria

- A user can create a complete preliminary brief.
- Missing information is visible.
- Every important requirement has a source or status.
- Generation uses the structured brief.
- Changing the brief updates or invalidates dependent results correctly.

---

# Phase 4 — TestFit-like direct design experience

## Objective

Make drawing and editing feel fast, live, and intuitive.

## 4.1 Core selection

Implement:

- Click selection.
- Hover highlighting.
- Shift multi-selection.
- Box selection.
- Select by object type.
- Select all visible objects.
- Selection isolation.
- Zoom to selection.
- Selection breadcrumbs for nested objects.

## 4.2 Direct manipulation

Support:

- Move.
- Rotate.
- Resize.
- Scale.
- Reshape.
- Offset.
- Vertex editing.
- Curve editing.
- Radius editing.
- Numeric dimension entry.
- Direct property entry.

## 4.3 Precision controls

Implement:

- Grid snapping.
- Object snapping.
- Endpoint snapping.
- Midpoint snapping.
- Perpendicular snapping.
- Tangent snapping.
- Alignment guides.
- Angle snapping.
- Temporary dimensions.
- Distance measurements.
- Bearing measurements.

## 4.4 Productivity controls

Add:

- Copy.
- Duplicate.
- Mirror.
- Array.
- Group.
- Ungroup.
- Align.
- Distribute.
- Delete.
- Cancel current command.
- Repeat last command.
- Keyboard shortcuts.
- Context menus.

## 4.5 Live reactive behavior

When geometry changes:

- Dependent geometry updates according to its relationship mode.
- Fast calculations update immediately.
- Expensive calculations become stale or begin updating.
- Active conflicts update.
- Quantities update.
- Live Delta Bar updates.
- The action enters revision history.
- The user can undo the complete operation.

## Exit criteria

- A designer can build and revise a basic concept without using chat.
- Direct manipulation remains responsive.
- Every visual change matches the canonical model.
- Constraints and dependencies respond consistently.
- Undo restores the exact previous project state.

---

# Phase 5 — Conversational design interface

## Objective

Make chat a reliable interface for controlling the same project model.

## 5.1 Conversational feed

Support:

- User instructions.
- Structured interpretation cards.
- Design summaries.
- Assumption requests.
- Warnings.
- Alternatives.
- Revision-difference cards.
- Partial-success reports.
- Error explanations.

## 5.2 Smart command bar

Add:

- Natural-language input.
- Object mentions.
- Selection-aware prompting.
- Slash commands.
- Command suggestions.
- Recent commands.
- Voice input when reliable.
- Stop or cancel generation.
- Undo and redo.
- History access.

Possible slash commands:

- `/parking`
- `/building`
- `/road`
- `/pond`
- `/setbacks`
- `/utilities`
- `/alternatives`
- `/compare`
- `/validate`
- `/export`

## 5.3 Interpretation confirmation

For complex commands, show an inline card that states:

- What Civora understood.
- Which objects will change.
- Which objects are protected.
- What requirements are active.
- What assumptions are being used.
- How many alternatives will be created.
- What optimization priorities will be applied.

Allow:

- Generate.
- Edit interpretation.
- Protect another object.
- Change priorities.
- Cancel.

Avoid requiring confirmation for every small, reversible operation.

## 5.4 Command capabilities

Chat should support:

- Creating objects.
- Moving objects.
- Resizing objects.
- Rotating objects.
- Changing dimensions.
- Locking objects.
- Changing dependency behavior.
- Editing the brief.
- Changing priorities.
- Generating alternatives.
- Comparing alternatives.
- Applying an option.
- Combining alternative elements.
- Explaining a score.
- Explaining a conflict.
- Undoing a specific change.
- Starting an export.

## 5.5 Safety and reliability

Implement:

- Capability registry.
- Structured command schemas.
- Parameter validation.
- Object-ID validation.
- Deterministic geometry operations.
- Constraint checking before acceptance.
- Clear unsupported-action responses.
- Protection against invented standards.
- No direct unvalidated model output entering project geometry.
- Logging of interpretation and execution.
- Recovery from interrupted commands.

## 5.6 Revision-difference summaries

After every meaningful command, report:

- Objects changed.
- Distances moved.
- Dimensions changed.
- Parking change.
- Building-area change.
- Impervious-area change.
- New or resolved conflicts.
- Calculations made stale.
- Assumptions introduced.
- Remaining unverified items.

## Exit criteria

- Chat and direct manipulation produce equivalent valid results.
- Users can reference selected objects naturally.
- Civora does not claim unsupported capabilities.
- Every conversational edit can be previewed, applied, canceled, and undone.
- Every change has a clear explanation.

---

# Phase 6 — Constraints, dependencies, and alternatives

## Objective

Transform Civora from an editing tool into a reliable feasibility exploration system.

## 6.1 Formal constraint engine

Support:

- Hard requirements.
- Soft preferences.
- Design targets.
- Protected geometry.
- Derived requirements.
- User-disabled rules.
- Jurisdictional rules.
- Geometric rules.
- Operational rules.
- Conflicting requirements.

Each constraint should contain:

- Name.
- Type.
- Value.
- Unit.
- Source.
- Priority.
- Applicable objects.
- Pass/fail state.
- Current/stale status.
- Explanation.
- Possible resolution.

## 6.2 Impossibility explanations

When a valid result cannot be created, Civora should explain:

- Which constraints conflict.
- How large the shortfall is.
- Which requirements may be relaxed.
- What would change under each relaxation.
- Whether partial alternatives are available.

## 6.3 Candidate generation

Implement:

- Larger deterministic candidate pool.
- Constraint-aware candidate creation.
- Early rejection of impossible candidates.
- Rejection of boundary violations.
- Rejection of forbidden overlaps.
- Protection of fixed objects.
- Duplicate removal.
- Near-duplicate removal.
- Diversity scoring.
- Performance limits.
- Reproducible saved alternatives.

## 6.4 Ranking

Score candidates using configurable priorities such as:

- Compliance.
- Parking.
- Building area.
- Circulation.
- Open space.
- Stormwater feasibility.
- Earthwork.
- Cost.
- Impervious coverage.
- Constructability.

Priority changes must rerank the complete candidate pool, not merely reorder the already selected top options.

## 6.5 Alternative comparison workspace

Add:

- Side-by-side comparison.
- Overlay comparison.
- Synchronized pan and zoom.
- Difference highlighting.
- Movement arrows.
- Changed-object list.
- Consistent scorecards.
- Tradeoff explanations.
- Pinned metrics.
- Pinned objects.
- Combine-elements workflow.
- Promote option to working design.
- Preserve rejected options.
- Return to an earlier alternative.

## Exit criteria

- Generated alternatives are valid and meaningfully different.
- Fixed objects never move silently.
- Ranking responds correctly to changed priorities.
- Users understand why each option scored differently.
- The system explains when no valid option exists.

---

# Phase 7 — Layers, health, calculations, and quantities

## Objective

Make the design understandable and professionally inspectable.

## 7.1 Layer system

Support semantic layers for:

- Parcels.
- Setbacks.
- Easements.
- Buildings.
- Roads.
- Access points.
- Parking.
- Sidewalks.
- Landscaping.
- Stormwater.
- Grading.
- Utilities.
- Dimensions.
- Annotations.
- Conflicts.
- Source data.

Each layer should support:

- Show/hide.
- Select all.
- Lock/unlock.
- Isolate.
- Opacity.
- Color.
- Line type.
- Line weight.
- Export mapping.
- Saved presets.

## 7.2 Live Delta Bar

Allow users to pin metrics such as:

- Building area.
- Parking provided.
- Parking required.
- Impervious coverage.
- Open space.
- Preliminary cut.
- Preliminary fill.
- Stormwater storage.
- Road length.
- Active conflicts.
- Preliminary cost.

Show:

- Current value.
- Change from previous state.
- Target.
- Status.
- Freshness.

## 7.3 Civil-system freshness

Track:

- Boundaries.
- Building yield.
- Parking and access.
- Stormwater and grading.
- Utilities.
- Quantities.

Use these statuses:

- Current.
- Updating.
- Stale.
- Blocked.
- Unverified.

Show why a system has its current status.

## 7.4 Recalculation behavior

- Recalculate lightweight systems automatically.
- Debounce calculations during active dragging.
- Recalculate when manipulation ends.
- Queue expensive calculations.
- Permit deliberate manual recalculation.
- Preserve older results as stale instead of silently deleting them.
- Report partial success clearly.

## 7.5 Calculation provenance

Every calculation should provide:

- Result.
- Unit.
- Inputs.
- Formula.
- Method.
- Source.
- Source date.
- Confidence.
- Applicable geometry.
- Revision.
- Freshness.
- Verification status.

## 7.6 Quantities

Calculate and link:

- Asphalt area.
- Concrete area.
- Sidewalk area.
- Curb length.
- Parking counts.
- Striping.
- Pipe lengths.
- Building footprint.
- Landscaping.
- Pond storage.
- Preliminary cut and fill.

Clicking a quantity should highlight all contributing geometry. Clicking geometry should show its quantity contribution.

## 7.7 Preliminary cost estimates

Each estimate should include:

- Quantity.
- Unit cost.
- Cost range.
- Source.
- Source date.
- Geographic market.
- Confidence.
- Escalation assumption.
- Contingency.
- Included items.
- Excluded items.

All early estimates must be labeled conceptual.

## Exit criteria

- Every visible metric is traceable.
- Stale and unverified results cannot be mistaken for current verified results.
- Quantity-to-geometry relationships work in both directions.
- Partial calculation failures are clearly explained.

---

# Phase 8 — Revisions, saving, collaboration, and recovery

## Objective

Make users confident that project work is safe and reviewable.

## 8.1 Saving

Implement:

- Autosave.
- Visible save status.
- Save retry.
- Offline warning.
- Recovery from interrupted saves.
- Project duplication.
- Exported backup.
- Database backup.

## 8.2 Revision history

Support:

- Undo.
- Redo.
- Named milestones.
- Automatic revisions for major operations.
- Detailed revision timeline.
- Before-and-after comparison.
- Restore as a new revision.
- Revision notes.
- Author.
- Timestamp.
- Attached chat command.
- Changed assumptions.
- Changed calculations.
- Export history.

## 8.3 Collaboration

Add:

- Firm accounts.
- Project membership.
- Admin role.
- Editor role.
- Reviewer role.
- Viewer role.
- Shareable review sessions.
- Object-based comments.
- Mentions.
- Review requests.
- Approval status.
- Activity history.
- Client presentation mode.

## 8.4 Concurrent editing

Initially:

- Warn when another user is editing.
- Prevent silent overwrites.
- Allow controlled refresh and merge.
- Record conflicting changes.

Advanced real-time multiplayer editing may come later.

## Exit criteria

- Work survives refreshes, crashes, and failed saves.
- Earlier versions can be recovered.
- Changes are attributable.
- Multiple users cannot silently overwrite each other.
- Sharing respects project permissions.

---

# Phase 9 — CAD interoperability and external data exchange

## Objective

Make Civora useful inside an existing civil-engineering workflow.

## 9.1 DXF export

Export real, editable geometry with appropriate layers such as:

- `C-PROP`
- `C-BLDG`
- `C-ROAD`
- `C-PARK`
- `C-SIDEWALK`
- `C-STRM`
- `C-UTIL`
- `C-LAND`
- `C-ANNO`

Verify:

- Units.
- Coordinates.
- Scale.
- Closed polylines.
- Arcs.
- Curves.
- Text.
- Dimensions.
- Layer names.
- Object continuity.
- Re-import consistency.

## 9.2 LandXML

Support only clearly defined objects that can be represented reliably.

Possible early support:

- Parcel boundaries.
- Alignments.
- Profiles.
- Surfaces when validated.

Unsupported information must be clearly disclosed.

## 9.3 Import

Develop controlled import for:

- DXF geometry.
- Parcel boundaries.
- Survey geometry.
- Contours.
- Selected LandXML data.

Imported objects must retain:

- Original layer.
- Source file.
- Units.
- Coordinate system.
- Import time.
- Verification status.

## 9.4 Export record

Every export should include:

- Project revision.
- Units.
- Coordinate system.
- Layer mapping.
- Current calculations.
- Stale calculations.
- Assumptions.
- Unverified information.
- Unsupported information.
- Export timestamp.
- Exporting user.

## 9.5 External verification

Test files inside:

- AutoCAD.
- Civil 3D.
- At least one secondary CAD viewer.
- The workflows actually used by pilot firms.

Record every failure and correction.

Native DWG export is not required during the pilot phase.

## Exit criteria

- Pilot engineers can open and edit Civora geometry without tracing it.
- Units and coordinates are correct.
- Exports disclose limitations.
- External verification evidence is documented.

---

# Phase 10 — Civil validation and responsible 3D

## Objective

Validate the engineering behavior and expand visual analysis without overstating reliability.

## 10.1 Independent engineering review

Licensed professionals should review:

- Parcel calculations.
- Setbacks.
- Building envelopes.
- Parking geometry.
- Accessible parking concepts.
- Drive aisles.
- Access.
- Cul-de-sacs.
- Fire-access concepts.
- Turning geometry.
- Road geometry.
- Preliminary grading.
- Slopes.
- Drainage.
- Stormwater methods.
- Utility separation concepts.
- Quantity calculations.

## 10.2 Benchmark projects

Create benchmark cases with known expected results.

Each benchmark should include:

- Input data.
- Expected result.
- Tolerance.
- Applicable standard.
- Reviewer.
- Review date.
- Civora result.
- Difference.
- Resolution.

## 10.3 Two-dimensional validation

Confirm that 2D remains the authoritative editing environment during the early pilot.

Verify:

- Geometry accuracy.
- Measurements.
- Constraint visualization.
- Calculation linkage.
- Export consistency.

## 10.4 Three-dimensional view

Add progressively:

- Building massing.
- Terrain.
- Roads.
- Parking.
- Preliminary grading.
- Slope heatmap.
- Cut/fill visualization.
- Drainage-direction visualization.
- Synchronized 2D/3D selection.
- Alternative comparison.
- Optional sun and shadow analysis.

Do not allow 3D visual polish to delay the reliable 2D workflow.

## Exit criteria

- Core feasibility calculations have independent review.
- Known tolerances are documented.
- 3D accurately reflects the canonical model.
- Civora clearly distinguishes visual estimates from verified engineering calculations.

---

# Phase 11 — Review, conflicts, reports, and delivery

## Objective

Turn project information into an understandable professional review package.

## 11.1 Conflict matrix

For each issue, show:

- Conflict type.
- Severity.
- Affected objects.
- Requirement.
- Source.
- Evidence.
- Blocking status.
- Freshness.
- Suggested resolutions.
- Downstream consequences.
- Assigned reviewer.
- Resolution status.

## 11.2 Suggested resolutions

Use language such as:

- Preview resolution.
- Generate solutions.
- Review suggested change.
- Apply selected resolution.

Before application, show:

- Objects that will move.
- Objects that remain fixed.
- Requirement being resolved.
- Potential new conflicts.
- Calculations that will become stale.
- Whether the resolution is calculated or heuristic.

## 11.3 Preliminary Feasibility Package

Include configurable sections:

- Executive summary.
- Project brief.
- Source register.
- Selected concept.
- Alternative comparison.
- Site metrics.
- Constraint results.
- Conflict log.
- Assumption log.
- Calculation-status table.
- Quantity takeoff.
- Preliminary cost range.
- Open questions.
- Limitations.
- Professional-review requirements.
- Preliminary-use disclaimer.

## 11.4 Client summary

Create a one-page non-technical summary containing:

- Site image.
- Selected concept.
- Building area.
- Parking.
- Main constraints.
- Major opportunities.
- Major risks.
- Recommended next steps.

## 11.5 Delivery controls

Allow users to:

- Choose a revision.
- Choose report sections.
- Choose visible layers.
- Add firm branding.
- Add project notes.
- Review warnings.
- Generate PDF.
- Export CAD.
- Share a review session.

Do not use “Engineer Reliance Package” until legal counsel explicitly approves that wording.

## Exit criteria

- Reports match the selected project revision.
- Assumptions and limitations are visible.
- Clients receive an understandable summary.
- Engineers receive a traceable technical record.
- No report can accidentally present stale or unverified information as verified.

---

# Phase 12 — Pilot preparation and execution

## Objective

Put Civora into real professional use and measure its value.

## 12.1 Ideal pilot customer

Target:

- Boutique civil or land-development firms.
- Approximately 5–20 employees.
- Frequent commercial feasibility work.
- Repetitive site-layout studies.
- Existing AutoCAD or Civil 3D workflow.
- A principal willing to supervise testing.
- A designer willing to use Civora weekly.

## 12.2 Pilot scope

Use Civora for:

- Preliminary zoning feasibility.
- Building fit.
- Parking yield.
- Access concepts.
- Basic road layouts.
- Cul-de-sac concepts.
- Setback evaluation.
- Early alternatives.
- Preliminary quantities.
- CAD handoff.

Do not use the pilot for final grading plans, final utility design, construction documents, or professional stamping.

## 12.3 Pilot materials

Prepare:

- Pilot agreement.
- Confidentiality terms.
- Onboarding guide.
- Sample project.
- Fifteen-minute training.
- Supported-feature list.
- Known-limitations list.
- Support contact.
- Feedback form.
- Issue-reporting process.
- Weekly check-in format.

## 12.4 Pilot measurements

Measure:

- Time to first concept.
- Time to five alternatives.
- Total concept-development time.
- Manual correction count.
- Unsupported chat-command count.
- Undo frequency.
- Calculation failures.
- Export success.
- Geometry requiring redrawing.
- User confidence.
- Projects completed.
- Weekly active users.
- Willingness to pay.

## 12.5 Feedback process

For every major issue, record:

- User.
- Firm.
- Project type.
- Task being attempted.
- Expected result.
- Actual result.
- Severity.
- Workaround.
- Applicable project revision.
- Supporting screenshot or export.
- Resolution.
- Retest status.

## 12.6 Case studies

Document:

- Previous workflow.
- Previous time requirement.
- Civora workflow.
- Civora time requirement.
- Number of alternatives evaluated.
- CAD handoff result.
- User quote.
- Quantified benefit.
- Remaining limitations.

## Exit criteria

- Three to five firms complete the pilot.
- At least ten real projects are attempted.
- Time savings are measured.
- CAD handoff is externally proven.
- Critical trust problems are resolved.
- At least two firms demonstrate willingness to pay.
- At least one credible case study is available.

---

# Phase 13 — Production operations, security, and legal readiness

## Objective

Create the controls required for broader paid use.

## 13.1 Authentication and access

Implement:

- Secure authentication.
- Account recovery.
- Organization membership.
- Role-based access.
- Session management.
- Tenant isolation.
- Project-level permissions.
- Administrative controls.

## 13.2 Security

Add:

- Encryption in transit.
- Encryption at rest.
- Secure file upload.
- File-type validation.
- Malware scanning where appropriate.
- Rate limiting.
- Abuse prevention.
- Secure secret storage.
- Dependency scanning.
- Vulnerability monitoring.
- Audit logging.
- Access logging.

## 13.3 Reliability

Add:

- Production monitoring.
- Error reporting.
- Uptime monitoring.
- Queue monitoring.
- Provider-failure monitoring.
- Database backups.
- Restoration drills.
- Incident-response procedure.
- Status communication process.
- Support escalation.

## 13.4 Privacy and data controls

Support:

- Data-retention policies.
- Project deletion.
- Account deletion.
- Data export.
- Firm ownership.
- User access records.
- AI data-use disclosure.
- Sensitive logging controls.
- Vendor disclosure.

## 13.5 Legal foundation

Obtain professional review for:

- Pilot agreement.
- Terms of service.
- Privacy policy.
- Data-processing terms.
- Subscription agreement.
- Acceptable-use policy.
- Intellectual-property terms.
- Confidentiality.
- Data ownership.
- AI disclosures.
- Professional-use boundaries.
- Limitation of liability.
- Preliminary-use disclaimers.
- Insurance requirements.

## Exit criteria

- Firm data is isolated.
- Backups can be restored.
- Incidents can be detected and handled.
- Legal documents match the actual product behavior.
- Customers understand the supported use boundary.

---

# Phase 14 — Billing, sales, and investor readiness

## Objective

Turn validated product use into a sustainable business.

## 14.1 Pricing

Test possible models:

- Per firm.
- Per user.
- Per project.
- Usage based.
- Paid pilot converted into subscription.

Pricing should reflect:

- Time saved.
- Number of projects.
- Firm size.
- Professional workflow value.
- Support requirements.

## 14.2 Billing

Initially support:

- Manual pilot invoicing.
- Pilot start and end dates.
- Seat tracking.
- Payment status.
- Renewal tracking.

Later add:

- Automated subscriptions.
- Invoice and receipt generation.
- Seat management.
- Failed-payment handling.
- Cancellation.
- Usage limits.

## 14.3 Sales system

Develop:

- Ideal customer profile.
- Firm prospect list.
- Outreach messages.
- Discovery-call script.
- Pilot offer.
- Demo script.
- Follow-up process.
- Customer relationship tracking.
- Objection handling.
- Conversion process.

## 14.4 Investor package

Prepare:

- Pitch deck.
- One-page overview.
- Product demo.
- Founder story.
- Market analysis.
- Competitive analysis.
- Business model.
- Pilot results.
- Case studies.
- Product metrics.
- Financial model.
- Eighteen-month use-of-funds plan.
- Hiring plan.
- Technical roadmap.
- Risk analysis.
- Data room.

## Exit criteria

- Pricing has customer evidence.
- Paying-customer conversion is measurable.
- Sales activity is repeatable.
- Investor claims are supported by actual data.
- Funding requirements connect to specific milestones.

---

# Phase 15 — Performance and scaling

## Objective

Ensure Civora remains responsive as projects and customer usage grow.

## 15.1 Browser performance

Test:

- Hundreds of objects.
- Thousands of objects.
- Large parcel boundaries.
- Numerous parking stalls.
- Frequent dragging.
- Continuous resizing.
- Large undo histories.
- Alternative generation.
- 2D/3D switching.
- Large imports.
- Large exports.
- Lower-powered computers.

## 15.2 Performance improvements

Implement as required:

- Spatial indexing.
- Incremental recalculation.
- Geometry caching.
- Visible-object rendering.
- Debounced calculations.
- Web Workers.
- Background queues.
- Memory limits.
- File-size limits.
- Progress reporting.
- Safe cancellation.

## 15.3 Service scaling

Test:

- Concurrent projects.
- Concurrent calculations.
- Provider timeouts.
- Queue failures.
- Retry behavior.
- Cost per project.
- Database growth.
- Storage growth.
- Backup duration.
- Restore duration.

## Exit criteria

- A normal commercial site remains responsive.
- Large operations show progress.
- Expensive tasks do not freeze the interface.
- Failures do not corrupt the project.
- Usage cost and performance are measurable.

---

# Phase 16 — Later platform expansion

These are future opportunities, not immediate pilot requirements.

Potential additions include:

- Advanced grading optimization.
- Detailed cut/fill balancing.
- Road profiles.
- Road sections.
- Curb returns.
- Detailed ADA analysis.
- Storm-pipe networks.
- Sanitary networks.
- Water distribution.
- Fire-flow concepts.
- Expanded turning analysis.
- Broader municipal-rule databases.
- Firm-specific standards.
- Advanced cost databases.
- Broader GIS integrations.
- Construction-document integrations.
- Advanced real-time collaboration.
- Larger master-planned developments.
- Deeper terrain visualization.
- Expanded enterprise administration.

Each addition should require evidence that customers need it and will pay for it.

---

# Continuous workstreams

The following work continues throughout every phase.

## A. Usability testing

- Test with users who did not build Civora.
- Give users tasks without explaining the interface.
- Observe hesitation and confusion.
- Record missed controls.
- Measure task completion.
- Simplify before adding more controls.

## B. Accessibility

- Keyboard navigation.
- Focus management.
- Screen-reader labels.
- Color-independent status indicators.
- Contrast compliance.
- Scalable text.
- Accessible dialogs and menus.

## C. Product analytics

Track:

- Time to first value.
- Feature usage.
- Failed commands.
- Failed calculations.
- Export failures.
- Undo frequency.
- Alternative selection.
- Abandoned workflows.
- Pilot activity.
- Customer retention.

## D. Trust and truth status

Every significant value should disclose whether it is:

- Sourced.
- Calculated.
- Assumed.
- User confirmed.
- Externally verified.
- Current.
- Updating.
- Stale.
- Blocked.
- Unverified.

## E. Documentation

Maintain:

- Supported-capability register.
- Known limitations.
- Calculation methods.
- Object schemas.
- Export specifications.
- Release notes.
- Operational procedures.
- Pilot training.
- Customer help material.

## F. Quality control

For each feature:

1. Define expected behavior.
2. Implement it against the canonical model.
3. Add automated tests.
4. Test failure conditions.
5. Test undo and recovery.
6. Test accessibility.
7. Test performance.
8. Test the deployed version.
9. Document limitations.
10. Observe real users.

---

# Features that should not be immediate priorities

Do not delay the pilot to build:

- A complete Civil 3D replacement.
- Native DWG creation.
- Stamp-ready construction documents.
- Automatic professional approval.
- A complete national municipal-code database.
- Every possible utility-design system.
- Advanced 500-acre master planning.
- Highly sophisticated real-time multiplayer editing.
- Demo-only visual features.
- Features without customer evidence.

---

# Immediate execution order

The next work should proceed in this exact sequence:

## Step 1: Stabilize

- Consolidate the current workspace.
- Finish testing.
- Resolve regressions.
- Produce one dependable release.

## Step 2: Confirm the canonical model

- Verify that chat, canvas, inspector, alternatives, history, calculations, and exports all use the same authoritative state.

## Step 3: Build the broad workspace shell

- Add the simplified stage system.
- Add contextual panels.
- Add project identity and health.
- Preserve maximum canvas space.

## Step 4: Complete one end-to-end pilot workflow

The first complete workflow should be:

1. Create a project.
2. Establish the brief.
3. Import or draw the parcel.
4. Draw or generate a concept.
5. Manipulate it directly.
6. Modify it through chat.
7. Generate alternatives.
8. Compare alternatives.
9. Inspect conflicts and assumptions.
10. Select a design.
11. Save a milestone.
12. Export a usable DXF.
13. Generate a preliminary PDF.
14. Close and reopen the project without losing information.

## Step 5: Validate externally

- Open exports in AutoCAD and Civil 3D.
- Have licensed civil engineers review calculations and workflow behavior.
- Correct the failures found.

## Step 6: Begin controlled pilots

- Recruit three to five firms.
- Use Civora on real preliminary projects.
- Measure time savings and workflow success.
- Fix pilot-blocking issues before expanding functionality.

## Step 7: Prepare for wider paid use

- Complete security, monitoring, backups, legal agreements, support, and billing.

## Step 8: Expand from evidence

- Prioritize the next engineering system based on customer demand, repeated usage, business value, and technical feasibility.

---

# Final product principle

Civora should feel simple during design, detailed during analysis, and fully traceable during review.

The final experience should let a user:

> Tell Civora what they want, draw it manually, or manipulate it directly—and receive the same immediate, constraint-aware, explainable result through every method.

The core competitive advantage will not be the number of tools on the screen. It will be the combination of:

- Fast live design.
- Conversational control.
- Civil-specific intelligence.
- Traceable calculations.
- Clear uncertainty.
- Meaningful alternatives.
- Professional CAD handoff.
- Evidence that the product saves real engineers real time.

---

# Founder-approved product governance — October 2, 2026

# Civora Roadmap Decisions and Product Rules

## 1. Roadmap authority

**Decision: Yes.**

The new master roadmap becomes the authoritative plan whenever it conflicts with older plans.

This means:

- Stabilization comes before major feature expansion.
- Pilot-critical usability comes before visual spectacle.
- Reliable 2D comes before advanced 3D.
- CAD interoperability comes before advanced utility design.
- External validation comes before construction-level claims.
- Customer evidence determines later expansion.

Previous work should not automatically be discarded. It should be evaluated and then:

- Integrated if stable and relevant.
- Preserved but disabled if potentially useful later.
- Refactored if it conflicts with the canonical model.
- Removed if obsolete or dangerous.

Advanced utilities, detailed grading, expanded 3D, and nonessential visual improvements are postponed unless they are required to stabilize an existing workflow.

---

## 2. First project type

**Decision: Start with a small-to-medium commercial office or retail site.**

The first complete workflow should handle:

- One parcel.
- One primary commercial building.
- One or two access points.
- Surface parking.
- Internal drive aisles.
- Setbacks.
- Easements.
- Sidewalks.
- Landscaping or open-space areas.
- A preliminary stormwater-reserve area.
- Basic site quantities.
- Conceptual cost ranges.
- DXF and PDF delivery.

### Why commercial is the best starting point

Commercial sites offer the clearest combination of:

- Building-area targets.
- Parking requirements.
- Access constraints.
- Setbacks.
- Impervious-area considerations.
- Fast alternative generation.
- Easily measured time savings.
- Frequent preliminary feasibility work.

Multifamily introduces density, unit mix, fire access, amenity, and structured-parking complications.

Residential subdivisions introduce lot generation, roadway networks, profiles, intersections, utilities, phasing, and much larger dependency systems.

Those should follow after the commercial workflow is proven.

---

## 3. First jurisdiction

**Decision: The pilot should initially use engineer-entered or engineer-confirmed requirements. Civora should not automatically claim local-code compliance.**

The initial system may help store and organize local requirements, but the engineer remains responsible for confirming them.

Civora should label requirements as:

- User entered.
- User confirmed.
- Document sourced.
- Automatically extracted but unconfirmed.
- Externally verified.

The first jurisdiction-specific implementation should be selected after identifying the first serious pilot firm. We should target the jurisdiction where that firm completes the most repetitive commercial-feasibility work.

This is better than choosing a city before we have a customer.

### Initial compliance language

Civora may say:

> No conflicts were detected against the currently entered project requirements.

Civora should not initially say:

> This design complies with all applicable local codes.

---

## 4. Existing projects

**Decision: Preserve existing projects whenever technically possible.**

Previously saved projects should remain readable.

The consolidation process should include:

- Schema version detection.
- Automatic migration where safe.
- Backup before conversion.
- Migration report.
- Validation after migration.
- Clear warnings for unsupported legacy information.
- Read-only access if safe automatic conversion is impossible.

Experimental projects may require conversion, but Civora must explain:

- What will be converted.
- What may change.
- What cannot be preserved.
- Whether the original will remain available.

No existing project should be silently changed or deleted.

---

## 5. Navigation transition

**Decision: Brief / Explore / Analyze / Review / Deliver should become the final navigation.**

The current navigation should remain temporarily available through a controlled transition.

Proposed mapping:

| Existing stage | New stage |
|---|---|
| Setup | Brief |
| Draw | Explore |
| Generate | Explore |
| Review | Review |
| Deliver | Deliver |
| Engineering calculations | Analyze |

### Transition approach

- Introduce the new navigation behind a controlled feature flag.
- Preserve existing routes and saved stage references.
- Redirect old stages into the corresponding new workspace.
- Test current workflows in the new structure.
- Remove the old navigation after it no longer provides unique functionality.

Generation should not remain a separate stage because drawing, direct manipulation, and conversational generation are three ways of exploring the same design.

---

## 6. Hard-rule violations during manual editing

**Decision: Allow manual exploration, but clearly mark the design invalid. Reject invalid generated alternatives by default.**

If a user manually moves a building across a required setback:

- Allow the movement.
- Display the violation immediately.
- Highlight the affected geometry.
- Mark the active design invalid.
- Explain the violated requirement.
- Show the amount of violation.
- Mark affected calculations appropriately.
- Offer undo and possible resolutions.

Generated alternatives should satisfy all enabled hard requirements unless the user explicitly asks to explore infeasible outcomes.

Civora should never silently relax a hard requirement.

For especially dangerous or destructive operations, Civora may require confirmation even during manual exploration.

---

## 7. “Ask” dependency behavior

**Decision: Preview the entire connected change before applying any portion of it.**

If moving a building requires:

- Moving parking.
- Reflowing drive aisles.
- Adjusting landscaping.
- Invalidating stormwater results.

Civora should preview the complete transaction.

The user should see:

- Objects that will move.
- Objects that will remain fixed.
- Expected metric changes.
- New conflicts.
- Resolved conflicts.
- Calculations that will become stale.

The user may then:

- Apply the complete change.
- Edit the proposed response.
- Detach a dependency.
- Cancel.

The project should not enter a half-applied state.

---

## 8. Meaning of “fixed”

**Decision: Fixed status should support separate scopes.**

Users should be able to fix:

- Position.
- Geometry.
- Dimensions.
- Rotation.
- Elevation.
- Classification.
- All properties.

The interface may offer simple presets:

- Fix position.
- Fix shape and size.
- Fix everything.

### Override authority

During the pilot:

- An editor may override a fixed object after explicit confirmation.
- Every override must be recorded in revision history.
- Civora must never silently override it.
- Viewers and reviewers cannot override it.

Later, organizations may configure certain objects so only an administrator or project manager can override them.

---

## 9. Missing engineering information

**Decision: Civora may proceed with explicitly accepted assumptions when the missing information does not invalidate the requested activity.**

Example:

Without survey elevations, Civora may still generate:

- Building placement.
- Parking arrangements.
- Access concepts.
- Setback checks.
- Preliminary horizontal geometry.

It must withhold or mark unverified:

- Grading.
- Cut/fill.
- Drainage direction.
- Pond elevation.
- Pipe slopes.
- Elevation-dependent accessibility analysis.

### Three missing-information behaviors

Every required input should be classified as:

1. **Nonblocking:** The requested operation does not depend on it.
2. **Assumption permitted:** The user may accept a documented provisional assumption.
3. **Blocking:** The operation cannot responsibly proceed without the input.

All accepted assumptions must be visible and traceable.

---

## 10. Exports with unresolved issues

**Decision: Permit preliminary exports with disclosed issues, except when the export itself would be misleading or technically corrupted.**

Users may export a DXF or PDF containing:

- Design conflicts.
- Stale calculations.
- Unverified sources.
- Accepted assumptions.
- Incomplete analysis.

However, the export must include:

- A visible preliminary designation.
- Conflict summary.
- Stale-system summary.
- Assumption log.
- Verification status.
- Project revision.
- Export timestamp.
- Applicable warnings.

Export should be blocked when:

- Units are unknown.
- Coordinate conversion has failed.
- Geometry is corrupted.
- The requested export cannot accurately represent the project.
- A critical security or data-integrity failure exists.

Engineering conflicts alone should not block a clearly disclosed preliminary export.

---

## 11. Alternative generation

**Decision: Five alternatives should be the normal default.**

Users may request between two and ten options, subject to performance limits.

The default five should aim for meaningful strategic differences, such as:

- Maximum building area.
- Maximum parking.
- Best circulation.
- Lowest impervious coverage.
- Best balanced result.

### When no option is fully valid

Civora should:

1. Explain why valid generation failed.
2. Identify the conflicting requirements.
3. Quantify the shortfall.
4. Suggest requirements that could be relaxed.
5. Offer to display the closest unsuccessful options.

Invalid options must never appear as normal successful alternatives. They should be clearly labeled:

> Exploratory—does not satisfy all hard requirements.

---

## 12. Meaning of “no redrawing”

**Decision: The first pilot exports must contain editable design geometry, not presentation-only outlines.**

Parking should include:

- Individually editable stall lines or logically grouped stall geometry.
- Accessible-stall markings when supported.
- Drive-aisle edges.
- Parking-field boundaries.
- Distinct layer assignments.

Roads should include:

- Editable road edges.
- Centerlines.
- Curves and arcs where applicable.
- Closed pavement boundaries where appropriate.
- Cul-de-sac geometry.
- Distinct access geometry.

Buildings should include:

- Closed footprint polylines.
- Separate building objects.
- Building name or identifier.

The first pilot does not require native intelligent Civil 3D objects.

Essential first-pilot output is reliable CAD geometry that can be edited in AutoCAD or Civil 3D without tracing. Intelligent alignments, profiles, corridors, pipe networks, and native Civil 3D objects can follow later.

---

## 13. Pilot collaboration

**Decision: One primary working account per pilot firm is acceptable initially, but secure firm separation is mandatory.**

The pilot should support:

- Separate firm organizations.
- Separate project ownership.
- Secure tenant isolation.
- At least one primary editor.
- Optional read-only review sharing.
- Internal administrative support access with auditing.

Full multi-user permissions are not required before the first pilot, but the underlying ownership model must not prevent their later addition.

After initial pilot stability, add:

- Admin.
- Editor.
- Reviewer.
- Viewer.

---

## 14. Release authority

**Decision: Continue requiring explicit approval before both staging and production deployment.**

Development and local testing may continue without separate deployment approval.

Before requesting deployment approval, provide:

- What changed.
- Tests completed.
- Known limitations.
- Migration impact.
- Deployment target.
- Rollback plan.
- Post-deployment checks.

Staging and production must be treated as separate approvals unless you later authorize automatic staging deployments.

No production deployment should occur merely because tests passed.

---

## 15. Deadline and readiness authority

**Decision: Do not set an arbitrary public-launch deadline yet. Establish milestone gates first.**

A realistic target date should be selected only after Phase 0 reveals:

- Current regression count.
- Migration difficulty.
- Deployment condition.
- CAD-export reliability.
- Amount of unfinished pilot-critical work.

### Readiness authority

No single person should make the entire decision.

#### Technical readiness

Determined by:

- Automated tests.
- Manual workflow testing.
- Deployment verification.
- Security and recovery checks.
- Civora development review.

#### Engineering readiness

Determined by:

- At least one appropriately licensed civil engineer.
- Documented calculation review.
- External CAD verification.
- Clear use limitations.

#### Workflow readiness

Determined by:

- At least one pilot designer completing the full workflow.
- The pilot firm confirming that the output is useful.
- No critical usability blocker.

#### Business readiness

Determined by you as founder based on:

- Product evidence.
- Customer willingness.
- Legal readiness.
- Support capacity.
- Financial considerations.

### Final pilot-readiness rule

Civora is ready for the first controlled pilot when:

- The technical gate passes.
- The preliminary engineering gate passes.
- The CAD handoff gate passes.
- The complete workflow can be demonstrated.
- Known limitations are documented.
- The pilot firm accepts the defined scope.

### Final public-beta rule

Civora is ready for public beta only when:

- Pilot evidence exists.
- Critical pilot findings are resolved.
- Security and tenant isolation are verified.
- Backups and recovery are proven.
- Monitoring and support exist.
- Legal documents are complete.
- Billing or controlled account provisioning works.
- Public claims match verified capabilities.

---

# Governing decisions summary

| Question | Decision |
|---|---|
| Authoritative roadmap | New master roadmap |
| First project | Small/medium commercial site |
| First jurisdiction | Determined by first pilot firm |
| Initial code compliance | Engineer-entered and confirmed requirements |
| Existing projects | Preserve and migrate |
| Final navigation | Brief / Explore / Analyze / Review / Deliver |
| Manual violations | Allowed but clearly invalid |
| Invalid generated options | Rejected by default |
| Ask dependencies | Preview complete connected change |
| Fixed objects | Scoped protection with explicit override |
| Missing data | Proceed only where responsible |
| Preliminary export with issues | Allowed with prominent disclosure |
| Default alternatives | Five |
| CAD requirement | Editable geometry without tracing |
| Pilot accounts | One primary account permitted |
| Firm separation | Mandatory |
| Staging deployment | Requires approval |
| Production deployment | Requires separate approval |
| Pilot readiness | Technical + engineering + workflow gates |
| Public-beta readiness | Pilot, security, legal, operational gates |

These decisions should be added to the master roadmap as Civora’s initial product-governance rules.

## October 3, 2026 — Founder-approved Phase 0.2 closeout scope

The founder approved closing Phase 0.2 for the verified feature set, explicitly retaining unverified map/provider/Firefox behavior and carrying hosted deployment checks into Phase 0.5. This scope adjustment supersedes earlier requirements that kept 0.2 open solely for those external checks; it does not waive their evidence requirements or mark skipped tests as passed.

Firefox/test-platform coverage remains tracked under 0.3 and must have recorded verification or approved limitations before release. Exact-candidate hosted authentication, persistence, exports, worker operation, migration/recovery, backup and rollback remain 0.5 gates. Real map/provider behavior requires approved access and verification or explicit exclusion from the released scope. Independent engineering, source and external CAD validation remain relevant pilot-readiness gates.

The evidence register is `phase-0-feature-verification.md`. Overall Phase 0 remains active; next milestone is 0.3. Phase 1 still waits for the complete Phase 0 exit criteria. This closeout is not deployment approval, permission to spend money or a claim that Civora is fully verified or ready for a controlled pilot/public launch.
