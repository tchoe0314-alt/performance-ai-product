# Phase 1.1 connected canvas/calculation evidence

## Candidate and scope

Local working-tree candidate on `codex/phase-0-integration`, based on `df0443298b4846e6e4b1858043106450e3055e80`; these changes are not a committed/deployed revision. Final website build: `.next-canonical-phase1`, BUILD_ID `cjMlJepG2pjcP5pt54YvD`, served at `http://127.0.0.1:3050`. Disposable SQLite API: `http://127.0.0.1:18886`, storage `/tmp/civora-phase1-canonical.oAOyri`; AI/image providers disabled. No hosted customer writes, deployment, `main` push or purchase occurred.

The final build was made after all application edits. Earlier builds/checks were superseded as snapshot detachment and unit handling were tightened; final assertions were run against the rebuilt candidate, not a previously running website.

Relevant final source SHA-256 identifiers:

- Canvas codec: `9aa0253c3faad40716714a4789563399a7d402274aa61e69854372a4e4994b93`
- Plan execution owner: `5fb2f886f682b9a4ed6f357bee779f36d3b87ac90304cc608e08bfecb483757d`
- Backend canvas gateway: `c3fc8bc0752845b6b91bef6397eb94fce5604385d7b75adb8e9f56d62ef7bbe1`
- Backend design workflows: `d7a1433064334328201c79acdb2427bf42a1ac580fe4ac50a98b8cf65106f16d`

## Final checks

- Backend affected-area selection: **170 passed plus 16 subtests**, 2.60 seconds. Canonical documents/canvas gateway, design/project/job workflows, store fast paths, team/admin, collaboration/lifecycle, legacy migration and lifecycle/backup behavior. Includes exact geometry/unknown-data retention, malformed references, coherent legacy-writer updates, explicit empty snapshots, canonical unit precedence, unknown-unit calculation rejection, and direct/queued API model compatibility. One existing Starlette/httpx deprecation warning.
- Separate artifact-workflow selection: **44 passed**, 0.61 seconds; 21 existing Matplotlib/ezdxf/Pyparsing deprecation warnings. This is not a new full canonical export-history implementation.
- Final Chromium website selection: **51 passed**, zero failures/skips, 26.6 seconds. This selection mixes pure utility contracts, mocked browser UI workflows and real local website/API workflows; it is not 51 production end-to-end tests.
- Additional real local persistence runs: **six passed**, zero failures/skips, 15.6 seconds, across desktop WebKit, mobile Chromium and mobile WebKit. Each configuration exercised legacy-project adoption and canonical inspector-edit/chat-move/save/reopen behavior against the disposable API.
- Production build/type validation, final scoped ESLint and whitespace checks passed.

The real canonical browser case submitted a deliberate conflicting legacy x=999 shadow against canonical x=125, opened at x=125, edited in the inspector to x=150, moved through chat to x=175, then reloaded at x=175. Width 160 and custom metadata were retained. Canonical client information remained intact across both autosaves. The legacy-project case preserved owner isolation and adopted a canonical snapshot on its first verified edit/save.

Generate browser tests use mocked transport: they verify queued requests contain a canonical document matching the current drawn/combined geometry. Backend request/engine tests independently verify consumption of canonical inputs. These do not prove paid AI, a real engineering design, hosted worker completion or production migration.

## Retained evidence

Final Chromium screenshots/traces: `/tmp/civora-phase1-canonical-final-v2-results`.

Final cross-browser screenshots/traces: `/tmp/civora-phase1-canonical-final-v2-cross-browser-results`.

Desktop and mobile screenshots were inspected. Synthetic projects/accounts and local storage are retained for reproduction; no customer data was modified or deleted. Firefox was not verified in this pass; its existing platform disposition remains open.

## Not complete

This completes the first connected canvas/calculation slice, not Phase 1.1. Calculation results/quantities, sources/assumptions, alternatives/revisions/export history and cross-session revision conflicts still need canonical owners and verification. Detailed per-object/reference/geometry contracts remain Phase 1.2 work. Existing source-review metadata and unadopted legacy representations are retained, not silently promoted to surveyed engineering evidence.

Phase 0.5 storage/recovery checks remain deferred, not waived or marked complete.
