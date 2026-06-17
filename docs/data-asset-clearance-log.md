# Data Asset Clearance Log

Draft status: counsel-review draft. This is not legal advice. Do not treat this log as proof that a source is cleared until the business owner and counsel approve the entry.

This log does not enable charging, production launch, public beta access, or construction reliance. It is a risk-reduction tracker for pilot source review only.

## Clearance Rules

- Record one row for each dataset, file family, provider feed, map/GIS source, imagery source, standard, CAD/PDF import source, or customer-owned source category before pilot use.
- Confirm the pilot user has rights to upload, connect, process, display, analyze, and use map/GIS sources and related metadata in Civora.
- Do not mark an asset cleared if license terms prohibit AI processing, derivative output generation, sharing with subprocessors, storage, caching, export, or pilot support review.
- Do not use this log to approve construction, certify source accuracy, replace survey/control review, or make legal conclusions.

## Clearance Log

| Asset/source | Asset type | Source owner/licensor | Intended pilot use | Rights evidence needed | Subprocessor/provider exposure | Clearance status | Owner | Counsel notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Customer-uploaded survey/control files | Survey/control | Customer or customer licensor | Source-backed reviewer evaluation and review package context | Customer authorization, project rights, confidentiality approval, coordinate/datum metadata | Hosting, storage, file processing, AI if enabled for pilot scope | Draft - needs counsel review | TBD | Confirm client/owner restrictions. |
| Customer-uploaded CAD/PDF files | CAD/PDF/imported files | Customer or customer licensor | Imported review context and draft output support | Customer authorization, file provenance, revision status, confidentiality approval | Hosting, storage, file processing, AI if enabled for pilot scope | Draft - needs counsel review | TBD | Confirm no prohibited confidential or third-party design files. |
| Map snapshots | Map/imagery | Map provider or customer source | Visual review context only | Provider terms, screenshot/export rights, attribution requirements, caching limits | Hosting, storage, AI/image processing if enabled | Draft - needs counsel review | TBD | Confirm source-rights caveat before import. |
| GIS exports | GIS/source data | Jurisdiction, utility, customer, or data vendor | Candidate source evidence for reviewer evaluation | License/export terms, permitted uses, attribution, redistribution/storage limits | Hosting, storage, file processing, AI if enabled | Draft - needs counsel review | TBD | Do not treat GIS candidates as accepted project evidence without user review. |
| Standards and ordinance excerpts | Standards/legal/code text | Jurisdiction, publisher, customer, or standards body | Review context and blocker/source tracking | License, public access terms, citation/update process, use restrictions | Hosting, storage, AI if enabled | Draft - needs counsel review | TBD | Confirm no claim of live legal/code compliance. |
| Generated Civora outputs | Generated review material | Customer content plus Civora-generated material | Draft, candidate, support, or engineer-review package materials | Terms coverage for ownership, license, feedback, retention, export | Hosting, storage, AI/provider logs depending on configuration | Draft - needs counsel review | TBD | Outputs remain not for construction. |

## Open Decisions

- Whether confidential project data is allowed during the next pilot cohort.
- Whether third-party AI processing is allowed for each data category.
- Whether map/GIS provider terms permit uploads, screenshots, caching, derived outputs, and support review.
- Required attribution, notices, or legends for map/GIS and standards sources.
- Retention and deletion requirements by asset category.
