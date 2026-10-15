# Phase 2.2 — Non-restrictive workspace stages

## Purpose and roadmap authority

Brief, Explore, Analyze, Review and Deliver are workspace presets, not a gated wizard or engineering approval states. All five remain available with an empty, incomplete, stale or unsaved drawing. Existing tools share the same canonical project and calculation authority.

## Tool grouping

- Brief: site context, survey import, data, standards, templates and files.
- Explore: Draw & Objects, Generate, model, layers, details and libraries.
- Analyze: grading, drainage, sanitary, water, utilities, roadway, landscape, quantities, jobs, catalogs and system workbenches.
- Review: analysis and dashboard.
- Deliver: deliverables and reports.

One compact panel picker exposes each stage's tools. Chat, Projects, Help and Settings remain global utilities; opening them does not overwrite a remembered stage destination. Existing object-inspector, keyboard and command navigation also updates the stage destination when it opens a stage-owned panel.

## Memory and persistence boundaries

The user selected remembering each stage's last-opened panel. Versioned, validated session storage scopes preferences by account and project within each browser tab. Refresh restores the active stage and its panel. Separate tabs and projects have independent preferences. Malformed or unavailable storage cannot block navigation. First-save and first-edit copies retain the current view; opening another project hydrates that project's preferences.

Stage preferences are not engineering inputs, project metadata, Undo transactions or calculation results. Switching never creates a project revision, marks geometry stale, starts calculations, requests a copy, or changes the saved design. Existing save, conflict and Undo/Redo mechanisms retain authority. Refresh cannot recover an unsaved edit solely through stage memory; existing persistence rules still apply.

## Scope

This milestone organizes existing tools and preserves editing behavior. It does not implement Phase 2.3's map/layer/view functionality or Phase 2.5's saved workspace layouts. Paid providers, hosted deployment and engineering validation remain separate requirements.
