from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from .common import safe_dict, safe_list, safe_str
from .existing_conditions import summarize_existing_conditions
from .existing_conditions_importers import (
    import_geojson,
    import_landxml_metadata,
    import_surface_grid_csv,
    import_survey_csv,
    merge_imported_existing_conditions,
    validate_imported_existing_conditions_package,
)
from .existing_conditions_package import build_existing_conditions_package


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
REAL_FILE_FIXTURE_SPECS: Dict[str, Dict[str, Any]] = {
    "small_commercial_pad": {
        "fixture_type": "commercial_pad_real_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson"},
    },
    "multifamily_site": {
        "fixture_type": "multifamily_real_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson"},
    },
    "mixed_use_14_acre_site": {
        "fixture_type": "landxml_mixed_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson", "landxml": "surface.landxml"},
    },
    "sloped_detention_site": {
        "fixture_type": "sloped_detention_real_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson"},
    },
    "roadway_corridor": {
        "fixture_type": "roadway_corridor_landxml_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson", "landxml": "corridor.landxml"},
    },
    "utility_conflict_heavy_site": {
        "fixture_type": "utility_heavy_real_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson"},
    },
    "floodplain_wetland_constrained_site": {
        "fixture_type": "floodplain_wetland_real_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson"},
    },
    "retaining_wall_site": {
        "fixture_type": "retaining_wall_landxml_package",
        "files": {"survey_csv": "survey.csv", "geojson": "constraints.geojson", "landxml": "wall_surface.landxml"},
    },
}


def real_file_fixture_scenario_ids() -> List[str]:
    return sorted(REAL_FILE_FIXTURE_SPECS)


def _fixture_path(scenario_id: str, relative_name: str) -> Path:
    return FIXTURE_ROOT / scenario_id / relative_name


def _fixture_imports(scenario_id: str, spec: Dict[str, Any], coordinate_system: Dict[str, Any]) -> List[Dict[str, Any]]:
    files = safe_dict(spec.get("files"))
    imports: List[Dict[str, Any]] = []
    survey_name = safe_str(files.get("survey_csv"))
    if survey_name:
        survey_path = _fixture_path(scenario_id, survey_name)
        imports.append(import_survey_csv(survey_path, coordinate_system=coordinate_system))
        surface = import_surface_grid_csv(survey_path, coordinate_system=coordinate_system)
        if surface.get("success"):
            imports.append(surface)
    geojson_name = safe_str(files.get("geojson"))
    if geojson_name:
        imports.append(import_geojson(_fixture_path(scenario_id, geojson_name), coordinate_system=coordinate_system))
    landxml_name = safe_str(files.get("landxml"))
    if landxml_name:
        imports.append(import_landxml_metadata(_fixture_path(scenario_id, landxml_name), coordinate_system=coordinate_system))
    return imports


def golden_real_file_payload_overrides(scenario_id: str) -> Dict[str, Any]:
    spec = safe_dict(REAL_FILE_FIXTURE_SPECS.get(scenario_id))
    if not spec:
        return {}
    coordinate_system = {
        "epsg": "EPSG:2276",
        "units": "ft",
        "source": f"{scenario_id}_fixture_control",
    }
    imports = _fixture_imports(scenario_id, spec, coordinate_system)
    merged = merge_imported_existing_conditions(*imports)
    merged["survey"].update(
        {
            "benchmark": f"{scenario_id.upper()}-BM-1",
            "datum": "NAVD88",
            "control_verified": True,
        }
    )
    merged["import_validation"] = validate_imported_existing_conditions_package(merged)
    source_types = [safe_str(item.get("source_type")) for item in safe_list(merged.get("sources")) if safe_str(item.get("source_type"))]
    fixture_files = {
        key: str(_fixture_path(scenario_id, safe_str(value)))
        for key, value in safe_dict(spec.get("files")).items()
        if safe_str(value)
    }
    package_meta = {
        "survey": merged.get("survey"),
        "gis_layers": merged.get("gis_layers"),
        "existing_conditions": merged.get("gis_layers"),
        "coordinate_system": merged.get("coordinate_system"),
        "surfaces": merged.get("surfaces"),
        "sources": merged.get("sources"),
        "existing_conditions_import_validation": merged.get("import_validation"),
        "grading": {"source_quality": "survey"},
        "existing_conditions_package": {
            "acceptance": {
                "accepted": True,
                "accepted_by": "golden_fixture",
                "notes": "Accepted for backend regression coverage only; not professional survey certification.",
            }
        },
        "existing_conditions_fixture": {
            "scenario_id": scenario_id,
            "fixture_type": safe_str(spec.get("fixture_type")),
            "fixture_files": fixture_files,
            "source_types": source_types,
            "real_file_fixture": True,
            "truth_label": "Committed golden fixture files prove importer/package behavior; they do not make the scenario construction-ready.",
        },
    }
    package_meta["existing_conditions_summary"] = summarize_existing_conditions({"meta": package_meta})
    package_meta["existing_conditions_package"] = build_existing_conditions_package({"meta": package_meta})
    return {"meta": deepcopy(package_meta)}


__all__ = ["golden_real_file_payload_overrides", "real_file_fixture_scenario_ids"]
