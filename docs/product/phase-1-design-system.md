# Phase 1.5 — Compact light workspace design system

## Purpose and product decisions

Keep Civora's existing light appearance. Give the plan more space by removing redundant control text, not by hiding safety information or reducing touch usability. User-approved direction: smaller, cleaner controls; recognizable pictures need no repeated visible names; content must remain centered/contained across aspect ratios and resolutions.

## Foundation

`apps/web/app/design-system.css` is imported by the global stylesheet and scoped to workspace surfaces. Existing color/surface/radius variables are retained. Spacing uses a 4/8/12/16 px scale; compact control height is 32 px, raised to 44 px for coarse pointers. Default panel width remains 320 px on desktop; mobile panels use the available viewport width. Typography remains the existing system sans-serif with 12 px compact control text and readable paragraph/measurement labels.

Controls use flex/grid centering rather than fixed icon offsets. Icon-only tools retain accessible names, descriptive native tooltips and a keyboard focus ring. Distinct or ambiguous actions (Polyline, Arc, transform variants, Uncombine, approval decisions) retain text. Units, quantities and actual error messages are not removed.

## Component conventions

- Buttons: `civora-icon-control` for obvious icon actions; the shared `SmallButton` for labeled actions. Selected/pressed states retain existing behavior. Disabled controls keep their reason/help text.
- Inputs: contained width, compact height/radius; checkboxes, radio buttons, color pickers and ranges are not stretched into text inputs. Text remains left-aligned where editing requires it.
- Panels/cards: 12 px base spacing, 44 px drawer header, restrained borders and 8 px inner corners. Existing panel routing and disclosure behavior are unchanged.
- Menus: bounded height with internal scrolling. Narrow-phone view menus anchor to the full toolbar container, not an individual icon. Short landscape drawers temporarily hide the command composer while open and leave navigation available; closing restores it.
- Tooltips: concise native `title` descriptions and accessible names, including tool name plus operation hint. Do not depend on hover for understanding an ambiguous action.
- Dialogs/confirmations: `civora-dialog` bounds width/height and permits internal scrolling. Accept/Reject and copy/replace/cancel decisions keep explicit words and normal keyboard behavior.
- Tables: compact rows, explicit headers, wrapping cell content; existing wide quantity tables scroll in their own wrapper, not the page.
- Charts: use the `civora-chart-frame` wrapper for new scalable chart graphics. Keep chart axes, units and existing plan/profile geometry intact; do not apply a blanket aspect-ratio rule to engineering drawings.
- Notifications/errors: restrained inline surfaces; existing alert/status paragraphs have border accents in addition to text. No error becomes a success solely through restyling.
- Empty states: `civora-empty-state` centers a concise next action. Loading retains explicit working text and reduced-motion-safe spinner treatment.

## Visual states and truth

`WorkspaceStateBadge` defines selected, hovered, hidden, locked, fixed, following, stale, updating, blocked, unverified, conflicting, assumed and verified, plus Ask and Independent relationships. Every state has text and an icon. Hidden/assumed use dashed borders, Fixed a double border, Locked a heavier border, and Conflicting a dashed warning border. Selection retains geometry handles as a non-color cue; row selection has an inset accent. Hover retains a border change and focus remains independently visible.

Actual object rows show selection, lock, visibility and draft/inferred status. Relationship controls show their stored policy, and canvas links distinguish solid Follow, dashed Ask/Fixed and dotted Independent patterns with an accessible title. Quantity status is draft or stale, never engineering verification. Interference results have explicit Conflict/Review/Separated indicators; Separated is not relabeled Verified. Job working/stale states and source evidence use the same badge vocabulary.

`sourceVisualState` only permits Verified when the source explicitly reports `verified: true` without outstanding verification/survey-control flags. Stale, dirty and missing evidence takes precedence. Higher confidence alone never means verified. Workflow completion/readiness is not engineering certification.

## Tests and limits

`phase1-design-system.spec.ts` exercises 320×568, 390×844, 844×390, 1024×600, 1280×720, 1920×1080 and 2560×1440. It measures icon centering, panel/menu containment, short-screen behavior, control heights, keyboard activation, visible focus, reduced motion and every state badge. Existing drawer overlap, accessibility, Deliver/Draw boundary and authenticated edit/history tests remain in force.

These representative viewports are regression evidence, not a claim that every possible browser, OS font, resolution or future panel has been manually inspected. Geometry/collision/math behavior is not changed by presentation tokens.
