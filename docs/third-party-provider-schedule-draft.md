# Third-Party Provider Schedule Draft

Draft status: counsel-review draft. This is not legal advice. Do not publish or attach this schedule to customer terms until counsel, privacy, security, and the business owner approve it.

This schedule is an inventory draft only. It does not authorize new providers, charging, production launch, public beta access, or changes to engineering behavior.

## Provider Schedule

| Provider/category | Purpose | Data categories that may be processed | Current status | Counsel/privacy review needed |
| --- | --- | --- | --- | --- |
| Hosting platform | Web app and API hosting | Account metadata, project records, logs, generated artifacts, operational telemetry | Draft inventory | Confirm processor/subprocessor role, region, retention, security commitments. |
| Database/storage provider | Project, upload, artifact, and job storage | Account metadata, project inputs, source files, generated outputs, logs | Draft inventory | Confirm data location, backup retention, deletion handling, access controls. |
| AI model provider | AI-assisted parsing, generation, review support, summaries, and reasoning | Prompts, project context, uploaded-source excerpts if enabled, generated outputs | Draft inventory | Confirm data-use terms, retention, opt-out, confidentiality, prohibited data handling. |
| Map/geocoding/GIS provider | Address lookup, map context, GIS source discovery, imagery or layer context | Address/location inputs, map view metadata, GIS source references, map/GIS files if imported | Draft inventory | Confirm source rights, attribution, caching, display, AI processing, and export restrictions. |
| File processing tools | PDF, CAD, image, spreadsheet, LandXML, and GIS import/export support | Uploaded files, extracted metadata, parsed geometry, generated review artifacts | Draft inventory | Confirm licensing and any subprocessors or local-only processing claims. |
| Analytics/observability | Reliability, performance, and support diagnostics | Usage events, browser/app telemetry, logs, error traces | Draft inventory | Confirm privacy notices, retention, sampling, user identifiers, and opt-out needs. |
| Support/communications | Support intake, issue tracking, notifications, and customer communication | Support messages, project IDs, screenshots or attachments if approved, contact data | Draft inventory | Confirm confidential support channel and attachment handling. |
| Payment provider | Future paid-pilot billing only if separately approved | Billing contact, payment metadata, invoices, receipts, tax records | Not enabled by this draft | Charging remains blocked until counsel-approved terms and provider setup are complete. |

## Schedule Notes

- Provider names, legal entities, data locations, subprocessors, and links to provider terms remain counsel-required placeholders.
- Billing provider entries are readiness placeholders only and do not enable charging.
- Provider status must not alter review-only labels, source-trust blockers, safety blockers, or professional responsibility boundaries.
- Map/GIS providers require separate source-rights review for upload, connection, processing, display, analysis, caching, export, attribution, and support use.
