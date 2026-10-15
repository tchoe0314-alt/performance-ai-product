# P01 feature-family inventory

Static characterization only; no features activated. Full fields and per-entry locators are in the adjacent JSON files.

| ID | Capability | Status | Source | Linked issues |
|---|---|---|---|---|
| projects | Project creation, address, templates, settings, save/load, duplicate, archive/restore, units | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/project_store.py` | CAN-01, CAN-03, TEST-03 |
| editing | Drawing, object typing/naming, group/uncombine, snapping, dimensions, layers, undo/redo | PARTIAL / PARTIAL_IMPLEMENTATION | `apps/web/app/PerformanceAIDashboardView.tsx` | CAN-01, CAN-02, UX-01 |
| multi_tab | First-edit branch/copy/replace, concurrent tabs and recovery | PARTIAL / PARTIAL_IMPLEMENTATION | `apps/web/app/hooks/useProjectTabBranch.ts` | CAN-03, SEC-10 |
| canonical | Canonical aggregate, compatibility adapters, geometry, results, signatures and stale state | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/canonical_project.py` | CAN-01, CAN-02, CAN-04 |
| jobs | Stage orchestration, cancellation, retry, recovery, progress and queue workers | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/application/job_workflows.py` | CAN-03, CAN-04, TEST-05, TEST-06 |
| geocoding | Address geocoding, parcel discovery and context coverage | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/planning/gis_provider_registry.py` | SEC-01, ENG-06, TEST-08 |
| gis_sources | Parcels, terrain, roads/ROW, utilities, sewer/drainage layers and source gaps | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/planning/existing_conditions_importers.py` | ENG-06, TEST-08 |
| imports | Survey CSV, GIS, GeoJSON, GeoTIFF, LAS, LandXML, CAD and PDF imports | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/planning/existing_conditions_importers.py` | ENG-06, SEC-08, TEST-03 |
| crs_datum | Horizontal CRS, elevation datums, transforms, metric/imperial support | PARTIAL / PARTIAL_IMPLEMENTATION | `engines/surface_engine.py` | ENG-04, ENG-05, ENG-06 |
| provenance | Source rights/confidence, accepted candidates, missing/stale information | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/brief_sources.py` | ENG-06, TEST-03 |
| hydrology | Rational method and planner adapter | FAIL / KNOWN_DEFECT_OR_MISSING_CAPABILITY | `engines/hydrology_engine.py` | ENG-01, ENG-02 |
| detention | Basin storage, stage curves, discharge/routing/overflow/drawdown | FAIL / KNOWN_DEFECT_OR_MISSING_CAPABILITY | `engines/detention_engine.py` | ENG-03 |
| surface | TIN/grid/interpolation/breaklines/contours | PARTIAL / PARTIAL_IMPLEMENTATION | `engines/surface_engine.py` | ENG-04, ENG-05, ENG-06 |
| grading | Grade elements, slopes, grading concepts and surfaces | PARTIAL / PARTIAL_IMPLEMENTATION | `engines/grading_engine.py` | ENG-04, ENG-06 |
| earthwork | Cut/fill, stripping, shrink/swell, haul and quantity summaries | FAIL / KNOWN_DEFECT_OR_MISSING_CAPABILITY | `engines/earthwork_engine.py` | ENG-04, ENG-05 |
| storm | Catchments, inlets, drainage paths, basin connections, storm network and hydraulics | PARTIAL / PARTIAL_IMPLEMENTATION | `engines/drainage_engine.py` | ENG-06 |
| sanitary | Sanitary fixture demand, network, capacity/slope and cover | PARTIAL / PARTIAL_IMPLEMENTATION | `engines/sanitary_engine.py` | ENG-06 |
| water | Water sizing, pressure/fire flow and vent sizing | PARTIAL / PARTIAL_IMPLEMENTATION | `engines/water_sizing_engine.py` | ENG-06 |
| utilities | Utility routing, horizontal/vertical separation and conflict resolution | PARTIAL / PARTIAL_IMPLEMENTATION | `engines/utility_engine.py` | ENG-06, CAN-02 |
| roads | Corridors, station/profile, roadway sections and parametric cul-de-sac | PARTIAL / PARTIAL_IMPLEMENTATION | `apps/web/app/utils/parametricRoad.ts` | ENG-06, CAN-02 |
| layouts | Building/subdivision/bridge/structural-grid geometry and sketch-to-plan | PARTIAL / PARTIAL_IMPLEMENTATION | `planner.py` | ENG-06 |
| quantities | Geometry/discipline quantity takeoff and cost price-book estimates | PARTIAL / PARTIAL_IMPLEMENTATION | `planner.py` | ENG-06, CAN-02 |
| compliance | Rule checks, coordination, candidate autofix/optimization and review summaries | PARTIAL / PARTIAL_IMPLEMENTATION | `planner.py` | ENG-06 |
| ai_commands | Natural-language actions, drafting, context, ambiguity handling and deterministic fallback | PARTIAL / PARTIAL_IMPLEMENTATION | `parsers/ai_parser.py` | ENG-06, CAN-03, SEC-05 |
| ai_providers | OpenAI, Ollama and disabled-provider adapters | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/ai/provider.py` | SEC-05, TEST-08 |
| imagery | High-quality AI imagery/rendering, preliminary visualization and mock demos | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/application/ai_visualization_workflows.py` | TEST-08, SEC-08 |
| learning | Consent-controlled memory, chat summaries, learning logs, eval/shadow/promotion | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/chat_learning_store.py` | SEC-05, CAN-03 |
| current_export | Current geometry DXF/PDF drawing-only exports | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/application/current_geometry_export.py` | TEST-03, TEST-07 |
| calculated_exports | Calculated DXF/PDF/report/JSON, print sheets, quantity/cost schedules | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/application/artifact_workflows.py` | ENG-06, TEST-03 |
| landxml | LandXML review interchange and feet-only supported scope | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/planning/landxml_io.py` | TEST-03, ENG-06 |
| dwg | Native DWG and Civil3D compatibility declarations/conversion hooks | FAIL / KNOWN_DEFECT_OR_MISSING_CAPABILITY | `backend/planning/dwg_compatibility.py` | TEST-08 |
| auth | Account registration/login/logout, verified identity and session lifecycle | FAIL / KNOWN_DEFECT_OR_MISSING_CAPABILITY | `backend/services/auth_store.py` | SEC-02, SEC-03, SEC-04, SEC-06, SEC-09 |
| teams | Organizations, owner/editor/reviewer/viewer roles, invites and team access | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/project_store.py` | SEC-03, SEC-10 |
| collaboration | Presence, comments, review history/requests and sharing | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/project_store.py` | CAN-03, TEST-03 |
| billing | Manual pilot plan, proposed Pro79/Engineer199/Teams149/Enterprise, Stripe lifecycle | FAIL / KNOWN_DEFECT_OR_MISSING_CAPABILITY | `backend/services/billing.py` | COM-01, COM-02, TEST-08 |
| entitlements | Plan enforcement, usage/quotas and seats | FAIL / KNOWN_DEFECT_OR_MISSING_CAPABILITY | `backend/services/billing.py` | COM-01, COM-02 |
| support_onboarding | Help/pilot onboarding, support intake and administration | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/project_store.py` | UX-01, COM-03 |
| privacy_lifecycle | Account export/deletion, retention and source/data controls | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/data_lifecycle.py` | SEC-05, COM-03 |
| operations | Diagnostics, readiness/metrics, database/artifact backups and recovery | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/services/backup_restore.py` | SEC-07, TEST-05, TEST-06 |
| browser_security | Headers, CSP/token storage, third-party rendering | PARTIAL / PARTIAL_IMPLEMENTATION | `apps/web/next.config.ts` | SEC-09 |
| uploads | Source uploads, parser validation, immutable identity and collision behavior | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/application/file_workflows.py` | SEC-08 |
| deployment | Docker/Railway/Vercel, process roles, migrations and release identity | PARTIAL / PARTIAL_IMPLEMENTATION | `Dockerfile` | TEST-05, TEST-07 |
| monitoring_analytics | Runtime/queue observability, hosted canary and optional analytics | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/api/app.py` | SEC-07, TEST-05, TEST-06 |
| provider_openai | provider_openai | NOT TESTED / IMPLEMENTED_NOT_VERIFIED | `backend/ai/provider.py` | AI-01, AI-02 |
| provider_ollama | provider_ollama | NOT TESTED / IMPLEMENTED_NOT_VERIFIED | `backend/ai/provider.py` | AI-02 |
| provider_disabled | provider_disabled | NOT TESTED / IMPLEMENTED_NOT_VERIFIED | `backend/ai/provider.py` | AI-01 |
| provider_mapbox | provider_mapbox | NOT TESTED / IMPLEMENTED_NOT_VERIFIED | `apps/web/package.json` | GOV-01 |
| provider_arcgis | provider_arcgis | PARTIAL / PARTIAL_IMPLEMENTATION | `backend/planning/gis_provider_registry.py` | SEC-01, GOV-01 |
| provider_stripe | provider_stripe | PARTIAL / PLACEHOLDER_STUB | `backend/services/billing.py` | COM-01, COM-02 |
| imagery_mock | imagery_mock | PARTIAL / MOCK_MODE_NOT_REAL_PROVIDER_VERIFICATION | `backend/application/ai_visualization_workflows.py` | AI-02 |
| native_dwg | native_dwg | PARTIAL / MISSING_IMPLEMENTATION | `backend/planning/dwg_compatibility.py` | EXP-02 |
| native_civil3d | native_civil3d | PARTIAL / MISSING_IMPLEMENTATION | `backend/planning/dwg_compatibility.py` | EXP-02 |
| format_csv | Import/export format csv (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/existing_conditions_importers.py` | TEST-03, EXP-01, ENG-06 |
| format_geojson | Import/export format geojson (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/existing_conditions_importers.py` | TEST-03, EXP-01, ENG-06 |
| format_geotiff | Import/export format geotiff (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/existing_conditions_importers.py` | TEST-03, EXP-01, ENG-06 |
| format_las | Import/export format las (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/existing_conditions_importers.py` | TEST-03, EXP-01, ENG-06 |
| format_landxml | Import/export format landxml (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/landxml_io.py` | TEST-03, EXP-01, ENG-06 |
| format_pdf | Import/export format pdf (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/existing_conditions_importers.py` | TEST-03, EXP-01, ENG-06 |
| format_dxf | Import/export format dxf (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/existing_conditions_importers.py` | TEST-03, EXP-01, ENG-06 |
| format_json | Import/export format json (direction/scope requires source review) | NOT TESTED / SOURCE_PRESENT_RUNTIME_UNVERIFIED | `backend/planning/existing_conditions_importers.py` | TEST-03, EXP-01, ENG-06 |

Source locators: {"api_route": 125, "configuration_reference": 245, "engine_module": 34, "environment_lookup": 225, "frontend_entry": 8, "ui_control": 662}

All discovered locators are NOT TESTED at runtime. Family PARTIAL/FAIL labels describe scoped code/evidence status, not completed end-to-end verification.
Dynamic constructs and custom UI tags can escape lexical discovery; this is not a claim of 100% feature coverage.
