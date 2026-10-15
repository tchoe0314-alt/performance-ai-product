# Phase 2.3 — Workspace environment

## Purpose and product rules

The master roadmap's environment controls change how the same canonical design is viewed and drafted. They do not create an alternative project model, delete hidden objects, accept calculations, or trigger an engineering rerun. The user approved remembering these settings separately for each project and browser tab.

- Keep the existing compact 2D/3D and Map controls. View mode and Draft/Plan Sheet quality restore without opening another project or requesting calculations.
- Put satellite and source-context visibility inside Layers. Satellite on uses the existing Mapbox satellite-streets style; off uses streets while retaining geographic context. The existing Map button turns map context off entirely.
- Topographic shows actual imported contours and uploaded elevation points; Survey independently shows uploaded points and survey-classified objects. Zoning requires explicit zoning metadata. Parcel boundaries controls modeled lots/imported parcels, not the canonical site extent. Utilities includes modeled utility corridors and utility appurtenances. No synthetic zoning, survey control, or engineering contours are generated.
- A source-context toggle with no renderable data says **No data** and is disabled. A setback/no-build object alone is not zoning. Missing Mapbox/location configuration says **Needs map**.
- Imperial/Metric converts canvas scale, site/cursor readouts, draft distances/areas, grid-step labels and elevation labels. It is a display preference: canonical geometry, engineering inputs and typed precision commands remain feet. The control states this when metric is selected. Full project-unit migration is outside this milestone.
- Show the actual canvas coordinate basis: unreferenced local feet, or an approximate WGS84 geographic anchor with local feet. Display settings do not invent a survey CRS or reproject imported geometry.
- Grid and snapping share a selected spacing in canonical feet. Changing the spacing immediately changes the rendered grid and actual pointer-snap coordinates. Grid visibility is independent of snapping. Existing object snaps, orthogonal drawing, keyboard shortcuts and typed commands remain available.
- Hidden objects cannot attract object snaps, but their canonical engineering constraints remain checked. Visibility changes must not clear collision warnings.

## Architecture and persistence

`workspaceEnvironment.ts` defines the versioned view schema, validates browser storage, formats display values and classifies existing objects. `useWorkspaceEnvironmentMemory` scopes optional session storage by account/project; an unsaved draft uses the workspace generation. New independent tabs have independent settings. A refresh restores the current tab. First-save and copy acknowledgements inherit the live view; true project opens restore the destination project's preferences.

Parent-owned 2D/3D and quality hydrate in `useDashboardPreviewModeState`; the canvas owns source visibility, native CAD-layer visibility, units, map style/lock, grid and snap settings. These preferences never enter project inputs, revision tokens, calculation fingerprints, Undo/Redo transactions or backend saves. Storage denial/corruption cannot block editing.

Copy inheritance also persists after hydration even when the snapshot itself is unchanged. Without that hydration dependency, an unchanged inherited view could look correct until refresh but never reach the new project's storage key. The authenticated copy-and-reload check protects this case.

`PreviewEnvironmentControls` adds compact controls inside the existing menus. Menus resize to avoid the command composer and navigation. In short mobile landscape, the composer is temporarily hidden while the menu is open; it returns on close. No persistent toolbar clutter is added.

Map style changes keep the same map instance/camera and replace the style without diffing; style-load synchronization restores Civora overlays and terrain sources in the main/fullscreen maps. This avoids dependent overlays being lost or style-change notifications being skipped.

The existing quiet Select command used during panel navigation must not force 2D. Explicit drawing tools still switch to 2D. This distinction is covered by the browser restoration/navigation checks.

## Verification and boundaries

Automated checks live in `apps/web/tests/live/phase2-workspace-environment.spec.ts`: schema/identity validation, object classification, no-data states, physical menu bounds, accessibility, actual pointer snapping, reload, independent projects/tabs, uploaded survey/elevation visibility, 2D/3D filtering and exact unchanged backend inputs/revisions. The Mapbox check uses a real browser WebGL map with completely mocked provider resources; it proves style switching, camera preservation, overlay restoration and remembered map-off behavior without provider usage.

Phase 2.3 does not certify live provider availability, surveyed accuracy, design calculations, deployment, collaboration permissions or export correctness. The pre-existing Generate/reactive-checkpoint freshness failure remains open. Phase 2.4 main actions and Phase 2.5 saved panel layouts are separate milestones.
