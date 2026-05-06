# Civora Conversation QA Checklist

Use this checklist before starting broad new workflow phases. The goal is to keep Civora feeling like a professional engineering copilot, not a backend validator leaking implementation details.

## Core Response Rules

- Truthful: does not claim grading, drainage, utilities, or exports succeeded unless the result actually contains that output.
- Actionable: gives the next useful user action instead of a dead-end error.
- No hallucinations: does not invent a site boundary, outlet, grading source, dimensions, or tie-ins when Assisted is off.
- No backend jargon: does not show raw validation/internal-engine phrases such as manual validation failures, tracebacks, or implementation exceptions.
- Missing info explained: states what is missing and why it is needed.
- Assumptions labeled: when Assisted is on, inferred values appear as assumptions in metadata/context.
- Remembers context: does not repeatedly ask for inputs already provided in the chat or stored project state.
- Engineering terminology understandable: uses terms like terrain-derived, user-provided, inferred, missing, blocked, and ready consistently.

## Manual Conversational Cases

| Area | Scenario | Expected Result |
| --- | --- | --- |
| Missing info, Assisted off | Ask Civora to design without a site boundary. | Civora asks for a locked site boundary or suggests turning on Assisted. No design success claim. |
| Missing info, Assisted off | Ask for drainage without a basin/outfall/drainage direction. | Civora says a drainage outlet/target is needed and explains why. |
| Missing info, Assisted off | Ask for grading without survey/terrain/fallback permission. | Civora says a grading source is needed and distinguishes terrain/survey/fallback. |
| Missing info, Assisted off | Ask to place a building without dimensions or program. | Civora asks for rough building/program dimensions before finalizing. |
| Missing info, Assisted off | Ask for utilities without tie-in/source info. | Civora asks for source/tie-in context or Assisted permission. |
| Assisted on | Repeat the same underspecified request with Assisted on. | Civora proceeds only where safe and lists every inferred value as an assumption. |
| Truthfulness | Trigger a blocked grading/drainage case. | Civora says it is blocked and shows the blocker or missing input, not success. |
| Source labeling | Run Detect Grading from locked map site. | Result says terrain-derived / Mapbox Terrain-RGB when terrain is used, not survey. |
| Source labeling | Upload or provide survey/topo. | Result says survey/user-provided when survey is used. |
| Memory | Provide site size/program, then ask “what do you remember?” | Civora repeats the remembered site/program and does not ask again unnecessarily. |
| Regression | Apply Address → Lock Site → Detect Grading. | Map/site/grading flow still works; terrain grading renders. |
| Regression | Run drainage after terrain grading. | Drainage reads the terrain-derived grading surface and does not fall back silently. |

## Failure Classification

- UX: wording is confusing, too technical, or not actionable.
- Validation: missing fields are wrong, absent, or not explained.
- Memory: chat forgets information already supplied.
- Orchestration: wrong mode, wrong requested system, or planner runs when it should ask for more info.
- Truthfulness: claims success, survey, geometry, or engineering completeness without support.
