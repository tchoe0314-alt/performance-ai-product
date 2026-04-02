# Product Foundation

## What this product is

Civora AI helps civil engineers and site designers go from rough intent to a structured concept plan faster. The product combines prompt input, sketch or image input, and editable fields so users can guide the system instead of surrendering control to it.

## Ideal first customer

- Civil engineering firms
- Land development consultants
- Internal design teams producing early feasibility studies

## Core product promise

Users should be able to describe a site, upload a rough sketch, leave unknowns blank, and receive:

- a structured plan payload
- clear assumptions
- flagged issues and confidence gaps
- one or more candidate site-planning options

## MVP scope

1. Prompt and image intake
2. Structured project setup form
3. Planner orchestration request/response loop
4. Assumptions and issue review panel
5. Exportable concept-plan artifacts

## Recommended next build priorities

1. Improve output packaging for reports and DXF downloads
2. Add a clearer review workflow for AI-made assumptions
3. Add planner-stage level tests beyond the current smoke checks
4. Upgrade from local beta auth to a production identity provider before public launch
5. Move from SQLite plus in-process workers to a production database and job system before public launch

## Positioning

This product should feel like an AI copilot for early civil layout and feasibility, not a black-box autodesign toy. The UI and messaging should emphasize:

- engineer control
- traceable assumptions
- editable structured inputs
- faster concept iteration
