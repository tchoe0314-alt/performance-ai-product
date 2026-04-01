from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client: OpenAI | None = None


def _get_client() -> OpenAI:
    global client
    if client is not None:
        return client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to your environment or .env file before using AI prompt parsing.")

    client = OpenAI(api_key=api_key)
    return client


# =============================================================================
# OPTION 2 / THREE-STATE FIELD CONTRACT HELPERS
# =============================================================================

FIELD_SOURCE_USER = "user"
FIELD_SOURCE_INFER = "infer"
FIELD_SOURCE_OMIT = "omit"
FIELD_SOURCES = {FIELD_SOURCE_USER, FIELD_SOURCE_INFER, FIELD_SOURCE_OMIT}
FIELD_WRAPPER_KEYS = {"value", "source", "assumption", "confidence"}

OPTIONAL_TOP_LEVEL_FIELDS = {
    "setback", "site_type", "street_edge", "layout_strategy", "intensity",
    "terrain", "acreage", "road", "bridge", "pool", "drainage",
    "subdivision", "grading", "utility_network",
}

OPTIONAL_NESTED_FIELD_PATHS = {
    "site_plan.parking_count", "site_plan.building_width", "site_plan.building_depth",
    "site_plan.driveway_width", "site_plan.driveway_side", "site_plan.parking_rows",
    "site_plan.parking_stall_width", "site_plan.parking_stall_depth",
    "road.lane_count", "road.lane_width", "road.shoulder_width", "road.sidewalk_width",
    "road.median_width", "road.design_speed_mph", "road.max_grade_pct",
    "drainage.inlet_count", "drainage.pipe_count", "drainage.pond_count",
    "drainage.trunk_line_count", "drainage.outfall_side", "drainage.routing_required",
    "drainage.grading_required", "drainage.detention_required",
    "subdivision.lot_count", "subdivision.road_width", "subdivision.culdesac_count",
    "subdivision.include_detention_ponds", "subdivision.include_utility_corridors",
    "subdivision.need_profiles", "subdivision.need_cross_sections",
    "subdivision.need_earthwork_report", "subdivision.need_proposed_contours",
    "grading.pad_count", "grading.spot_grade_count", "grading.flow_arrow_count",
    "grading.min_slope_pct", "grading.contours_required",
}

OMIT_KEYWORD_MAP = {
    "drainage": [
        r"no drainage", r"without drainage", r"omit drainage", r"skip drainage",
        r"drainage omitted", r"omit storm", r"no storm", r"storm omitted",
    ],
    "utility_network": [
        r"no utilit(?:y|ies)", r"without utilit(?:y|ies)", r"omit utilit(?:y|ies)",
        r"skip utilit(?:y|ies)", r"utilities omitted", r"utility omitted",
        r"without utility service", r"no utility service",
    ],
    "grading": [
        r"no grading", r"without grading", r"omit grading", r"skip grading",
        r"grading omitted",
    ],
    "site_plan.parking_count": [
        r"no parking", r"without parking", r"omit parking", r"skip parking",
        r"parking omitted",
    ],
    "drainage.pond_count": [
        r"no detention", r"without detention", r"omit detention", r"skip detention",
        r"no pond", r"without pond", r"pond omitted", r"detention omitted",
    ],
}


def make_field(value: Any = None, source: str = FIELD_SOURCE_INFER, assumption: str | None = None, confidence: float | None = None) -> Dict[str, Any]:
    src = source if source in FIELD_SOURCES else FIELD_SOURCE_INFER
    return {
        "value": value,
        "source": src,
        "assumption": assumption,
        "confidence": confidence,
    }


def is_field_wrapper(value: Any) -> bool:
    return isinstance(value, dict) and "source" in value and "value" in value


def normalize_field_wrapper(value: Any, *, default_source: str = FIELD_SOURCE_INFER) -> Dict[str, Any]:
    if is_field_wrapper(value):
        return make_field(
            value=value.get("value"),
            source=value.get("source", default_source),
            assumption=value.get("assumption"),
            confidence=value.get("confidence"),
        )
    source = FIELD_SOURCE_USER if value not in (None, "", [], {}) else default_source
    return make_field(value=value, source=source)


def _field_source_for_prompt(prompt_text: str, path: str, raw_value: Any) -> str:
    text = (prompt_text or "").lower()
    compact_text = re.sub(r"\s+", " ", text).strip()
    for pattern in OMIT_KEYWORD_MAP.get(path, []):
        if re.search(pattern, compact_text):
            return FIELD_SOURCE_OMIT
    if is_field_wrapper(raw_value):
        src = raw_value.get("source")
        if src in FIELD_SOURCES:
            return src
    if raw_value not in (None, "", [], {}):
        return FIELD_SOURCE_USER
    return FIELD_SOURCE_INFER


def _set_path_value(root: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = root
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict) or is_field_wrapper(nxt):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _get_path_value(root: Dict[str, Any], path: str) -> Any:
    cur: Any = root
    for part in path.split('.'):
        if not isinstance(cur, dict) or is_field_wrapper(cur):
            return None
        cur = cur.get(part)
    return cur


def _should_skip_three_state_contract_path(path: str) -> bool:
    path = str(path or "").strip()
    if not path:
        return False
    return path == "meta.field_states" or path.startswith("meta.field_states.")


def _is_three_state_wrapper(value: Any) -> bool:
    return isinstance(value, dict) and "source" in value and "value" in value


def _mark_omit_family(data: Dict[str, Any], field_states: Dict[str, Any], family: str, assumption: str) -> None:
    top = make_field(value=None, source=FIELD_SOURCE_OMIT, assumption=assumption, confidence=1.0)
    if family == "site_plan.parking_count":
        top["value"] = 0
    if "." in family:
        _set_path_value(data, family, deepcopy(top))
    else:
        if family in {"drainage", "road", "bridge", "pool", "subdivision", "grading"}:
            existing = _get_path_value(data, family)
            if isinstance(existing, dict) and not is_field_wrapper(existing):
                for subkey in list(existing.keys()):
                    existing[subkey] = make_field(value=None, source=FIELD_SOURCE_OMIT, assumption=assumption, confidence=1.0)
                data[family] = existing
            else:
                data[family] = deepcopy(top)
        else:
            data[family] = deepcopy(top)
    field_states[family] = deepcopy(top)

    prefix = family + "."
    for path in list(OPTIONAL_NESTED_FIELD_PATHS):
        if path.startswith(prefix):
            child = make_field(value=None, source=FIELD_SOURCE_OMIT, assumption=assumption, confidence=1.0)
            if path == "site_plan.parking_count":
                child["value"] = 0
            _set_path_value(data, path, deepcopy(child))
            field_states[path] = deepcopy(child)


def _apply_three_state_field_contract(data: Dict[str, Any], prompt_text: str = "") -> Dict[str, Any]:
    data.setdefault("meta", {})
    assumptions_text = " ".join(str(x) for x in (data.get("assumptions") or []) if x)
    detection_text = f"{prompt_text} {assumptions_text}".strip()
    existing_meta = data["meta"] if isinstance(data.get("meta"), dict) else {}
    existing_field_states = existing_meta.get("field_states")
    field_states: Dict[str, Any] = {}

    if isinstance(existing_field_states, dict):
        for k, v in existing_field_states.items():
            if _should_skip_three_state_contract_path(k):
                continue
            if _is_three_state_wrapper(v):
                field_states[k] = deepcopy(normalize_field_wrapper(v))

    for key in OPTIONAL_TOP_LEVEL_FIELDS:
        if _should_skip_three_state_contract_path(key):
            continue
        raw_value = data.get(key)
        source = _field_source_for_prompt(detection_text, key, raw_value)
        wrapped = normalize_field_wrapper(raw_value, default_source=source)
        wrapped["source"] = source
        data[key] = wrapped
        field_states[key] = deepcopy(wrapped)

    for path in OPTIONAL_NESTED_FIELD_PATHS:
        if _should_skip_three_state_contract_path(path):
            continue
        raw_value = _get_path_value(data, path)
        if raw_value is None and path.split('.')[0] not in data:
            continue
        source = _field_source_for_prompt(detection_text, path, raw_value)
        wrapped = normalize_field_wrapper(raw_value, default_source=source)
        wrapped["source"] = source
        _set_path_value(data, path, wrapped)
        field_states[path] = deepcopy(wrapped)

    # Heuristic reinforcement from prompt/assumption text for omitted disciplines.
    omit_reason_map = {
        "drainage": "User explicitly omitted drainage.",
        "utility_network": "User explicitly omitted utilities.",
        "grading": "User explicitly omitted grading.",
        "site_plan.parking_count": "User explicitly omitted parking.",
    }
    for omit_path, omit_reason in omit_reason_map.items():
        if _field_source_for_prompt(detection_text, omit_path, None) == FIELD_SOURCE_OMIT:
            _mark_omit_family(data, field_states, omit_path, omit_reason)

    existing_meta["field_states"] = field_states
    existing_meta["field_contract_version"] = "option2_v1"
    data["meta"] = existing_meta
    return data


def unwrap_fields_for_execution(value: Any) -> Any:
    if isinstance(value, dict):
        if "source" in value and "value" in value:
            if value.get("source") == FIELD_SOURCE_OMIT:
                return None
            return unwrap_fields_for_execution(value.get("value"))
        return {k: unwrap_fields_for_execution(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap_fields_for_execution(v) for v in value]
    return value


CHAT_SYSTEM_PROMPT = """
You are a helpful AI civil engineering assistant.

Be practical, clear, direct, and commercially useful.

Help explain design choices, layouts, and calculations for:
- commercial site plans
- residential subdivisions
- multifamily developments
- mixed-use developments
- grading and drainage concepts
- roads and corridors
- storm drainage
- detention ponds
- utility corridors
- parking layouts
- bridges
- pools
- general civil drafting concepts
- sketch-to-plan workflows

When answering, prefer real engineering logic over generic advice.
"""


COMMAND_SYSTEM_PROMPT = """
You are an AI civil drafting and planning parser.

Convert the user's request into structured JSON.

Return ONLY valid JSON matching the schema.
No markdown.
No explanation.
No prose outside the JSON.

Important goals:
- Preserve backward compatibility with legacy planner fields.
- Interpret broad civil/site requests correctly.
- Do NOT collapse multifamily, drainage, subdivision, or utility-heavy requests into a generic single building pad unless the prompt truly asks for that.
- Use normalized planner-friendly top-level fields whenever possible.
- Prefer concept-level but realistic civil/site structure.
- Keep legacy summary fields populated for compatibility.
- Also populate expanded arrays for multiple buildings, drainage structures, ponds, utilities, parking areas, sidewalks, and similar features when the prompt implies them.
- When the request clearly implies multiple site objects, prefer expanded arrays over a single simplified building-only summary.
- For building-rich sites, include building use and footprint type when inferable.

Top-level mode choices:
- site_plan
- subdivision
- road
- bridge
- pool
- drainage
- direct_actions

Top-level project_type choices:
- commercial_pad
- office_site
- strip_center
- industrial_site
- multifamily_site
- residential_subdivision
- corridor_roadway
- bridge
- pool
- drainage_network
- generic_site
- direct_geometry

Building use choices when inferable:
- generic
- office
- retail
- industrial
- multifamily

Footprint type choices when inferable:
- bar
- slab
- compact
- l_shape
- u_shape
- courtyard
- h_shape

Rules:
1. For commercial/civil site layout requests, populate:
   - mode
   - project_type
   - lot
   - setback
   - site_type
   - street_edge
   - layout_strategy
   - intensity
   - assumptions
   - buildings when multiple buildings are implied
   - parking_areas / drive_aisles / sidewalks / fire_lanes when relevant

2. For drainage/storm requests, use:
   - mode = "drainage"
   - project_type = "drainage_network"
   - drainage object populated in detail
   - include lot if available
   - do not force building/parking unless explicitly requested
   - populate drainage_structures, pipe_network, ponds when relevant

3. For residential subdivision requests, use:
   - mode = "subdivision"
   - project_type = "residential_subdivision"
   - populate subdivision object in detail
   - use expanded arrays only when clearly needed, but keep subdivision object filled

4. For road-only corridor requests, use mode = "road".

5. For requests that directly describe shapes/entities, use mode = "direct_actions".

6. Keep labels short.

7. Use null where a field is unknown or not applicable.

8. Layers should come from:
   SITE, SETBACK, BUILDING, PAVEMENT, ANNO, SYMBOL, STRUCTURE, WATER, ROAD, LOT,
   SURFACE, EG_CONTOUR, FG_CONTOUR, DRAIN_FLOW, LOW_POINTS, SPOT_EG, SPOT_FG,
   PIPE, BASIN_BOUNDARY, UTILITY, SAN, STORM, DRAIN, ROUTE, FIRE, WALK, PARKING

9. Do not invent highly precise engineering calculations.
   Use concept-level values and assumptions when needed.

10. Legacy compatibility matters:
   - Keep old top-level fields populated.
   - building_width/building_depth should represent the primary or typical building if multiple exist.
   - drainage counts should summarize total systems when possible.
   - subdivision fields should stay populated for subdivision-style prompts.

11. Expanded arrays should be used when prompts imply multiple objects:
   - buildings
   - parking_areas
   - drive_aisles
   - sidewalks
   - fire_lanes
   - drainage_structures
   - pipe_network
   - ponds
   - utility_network

12. deliverables should list requested output intent such as:
   - site_plan
   - grading_plan
   - drainage_plan
   - utility_plan
   - roadway_plan
   - proposed_contours
   - profiles
   - cross_sections
   - earthwork_report
   - dxf_geometry

13. For buildings array, include when possible:
   - use
   - footprint_type
   - frontage_edge

14. For multifamily and mixed-use type site requests:
   - do not default to one building unless the prompt clearly says one building
   - prefer multiple buildings or a larger building with richer site content when the request implies a development
"""


NUM_OR_NULL = {"anyOf": [{"type": "number"}, {"type": "null"}]}
INT_OR_NULL = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
STR_OR_NULL = {"anyOf": [{"type": "string"}, {"type": "null"}]}
BOOL_OR_NULL = {"anyOf": [{"type": "boolean"}, {"type": "null"}]}

POINT_OR_NULL = {
    "anyOf": [
        {
            "type": "array",
            "items": {"type": "number"},
            "minItems": 2,
            "maxItems": 2,
        },
        {"type": "null"},
    ]
}

POINT_LIST_OR_NULL = {
    "anyOf": [
        {
            "type": "array",
            "items": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
        },
        {"type": "null"},
    ]
}


COMMAND_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        # -----------------------------
        # LEGACY / CORE FIELDS
        # -----------------------------
        "project_name": {"type": "string"},
        "units": {"type": "string"},
        "mode": {
            "type": "string",
            "enum": [
                "site_plan",
                "subdivision",
                "road",
                "bridge",
                "pool",
                "drainage",
                "direct_actions",
            ],
        },
        "project_type": {
            "type": "string",
            "enum": [
                "commercial_pad",
                "office_site",
                "strip_center",
                "industrial_site",
                "multifamily_site",
                "residential_subdivision",
                "corridor_roadway",
                "bridge",
                "pool",
                "drainage_network",
                "generic_site",
                "direct_geometry",
            ],
        },
        "lot": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "x": NUM_OR_NULL,
                        "y": NUM_OR_NULL,
                        "w": NUM_OR_NULL,
                        "h": NUM_OR_NULL,
                    },
                    "required": ["x", "y", "w", "h"],
                },
                {"type": "null"},
            ]
        },
        "setback": NUM_OR_NULL,
        "site_type": STR_OR_NULL,
        "street_edge": STR_OR_NULL,
        "layout_strategy": STR_OR_NULL,
        "intensity": STR_OR_NULL,
        "building_width": NUM_OR_NULL,
        "building_depth": NUM_OR_NULL,
        "terrain": STR_OR_NULL,
        "acreage": NUM_OR_NULL,

        "site_plan": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "lot_width": NUM_OR_NULL,
                        "lot_depth": NUM_OR_NULL,
                        "lot_origin": POINT_OR_NULL,
                        "building_width": NUM_OR_NULL,
                        "building_depth": NUM_OR_NULL,
                        "building_centered": BOOL_OR_NULL,
                        "setback": NUM_OR_NULL,
                        "driveway_width": NUM_OR_NULL,
                        "driveway_side": STR_OR_NULL,
                        "parking_count": INT_OR_NULL,
                        "stall_width": NUM_OR_NULL,
                        "stall_depth": NUM_OR_NULL,
                        "aisle_width": NUM_OR_NULL,
                        "include_labels": BOOL_OR_NULL,
                        "include_dimensions": BOOL_OR_NULL,
                        "include_north_arrow": BOOL_OR_NULL,
                    },
                    "required": [
                        "lot_width",
                        "lot_depth",
                        "lot_origin",
                        "building_width",
                        "building_depth",
                        "building_centered",
                        "setback",
                        "driveway_width",
                        "driveway_side",
                        "parking_count",
                        "stall_width",
                        "stall_depth",
                        "aisle_width",
                        "include_labels",
                        "include_dimensions",
                        "include_north_arrow",
                    ],
                },
                {"type": "null"},
            ]
        },

        "road": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "length": NUM_OR_NULL,
                        "lanes": INT_OR_NULL,
                        "lane_width": NUM_OR_NULL,
                        "shoulder_width": NUM_OR_NULL,
                        "median_width": NUM_OR_NULL,
                        "origin": POINT_OR_NULL,
                        "include_labels": BOOL_OR_NULL,
                        "max_grade_pct": NUM_OR_NULL,
                        "sidewalk_width": NUM_OR_NULL,
                        "ada_required": BOOL_OR_NULL,
                        "centerline_points": POINT_LIST_OR_NULL,
                    },
                    "required": [
                        "length",
                        "lanes",
                        "lane_width",
                        "shoulder_width",
                        "median_width",
                        "origin",
                        "include_labels",
                        "max_grade_pct",
                        "sidewalk_width",
                        "ada_required",
                        "centerline_points",
                    ],
                },
                {"type": "null"},
            ]
        },

        "bridge": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "span_length": NUM_OR_NULL,
                        "deck_width": NUM_OR_NULL,
                        "support_count": INT_OR_NULL,
                        "span_count": INT_OR_NULL,
                        "origin": POINT_OR_NULL,
                        "include_labels": BOOL_OR_NULL,
                    },
                    "required": [
                        "span_length",
                        "deck_width",
                        "support_count",
                        "span_count",
                        "origin",
                        "include_labels",
                    ],
                },
                {"type": "null"},
            ]
        },

        "pool": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "pool_length": NUM_OR_NULL,
                        "pool_width": NUM_OR_NULL,
                        "origin": POINT_OR_NULL,
                        "shallow_note": STR_OR_NULL,
                        "deep_note": STR_OR_NULL,
                    },
                    "required": [
                        "pool_length",
                        "pool_width",
                        "origin",
                        "shallow_note",
                        "deep_note",
                    ],
                },
                {"type": "null"},
            ]
        },

        "drainage": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "inlet_count": INT_OR_NULL,
                        "pipe_count": INT_OR_NULL,
                        "trunk_line_count": INT_OR_NULL,
                        "pond_count": INT_OR_NULL,
                        "routing_required": BOOL_OR_NULL,
                        "grading_required": BOOL_OR_NULL,
                        "pipe_diameter": NUM_OR_NULL,
                        "outfall_side": STR_OR_NULL,
                        "connect_to_pond": BOOL_OR_NULL,
                        "include_flow_arrows": BOOL_OR_NULL,
                        "include_labels": BOOL_OR_NULL,
                    },
                    "required": [
                        "inlet_count",
                        "pipe_count",
                        "trunk_line_count",
                        "pond_count",
                        "routing_required",
                        "grading_required",
                        "pipe_diameter",
                        "outfall_side",
                        "connect_to_pond",
                        "include_flow_arrows",
                        "include_labels",
                    ],
                },
                {"type": "null"},
            ]
        },

        "subdivision": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "acreage": NUM_OR_NULL,
                        "terrain": STR_OR_NULL,
                        "lot_count": INT_OR_NULL,
                        "target_lot_width": NUM_OR_NULL,
                        "target_lot_depth": NUM_OR_NULL,
                        "road_width": NUM_OR_NULL,
                        "roadway_max_grade_pct": NUM_OR_NULL,
                        "minimum_drainage_slope_pct": NUM_OR_NULL,
                        "include_culdesacs": BOOL_OR_NULL,
                        "culdesac_count": INT_OR_NULL,
                        "include_utility_corridors": BOOL_OR_NULL,
                        "include_detention_ponds": BOOL_OR_NULL,
                        "detention_pond_count": INT_OR_NULL,
                        "ada_sidewalk_required": BOOL_OR_NULL,
                        "balanced_cut_fill_target": BOOL_OR_NULL,
                        "need_proposed_contours": BOOL_OR_NULL,
                        "need_profiles": BOOL_OR_NULL,
                        "need_cross_sections": BOOL_OR_NULL,
                        "need_earthwork_report": BOOL_OR_NULL,
                        "origin": POINT_OR_NULL,
                        "site_width": NUM_OR_NULL,
                        "site_depth": NUM_OR_NULL,
                        "street_frontage_edge": STR_OR_NULL,
                    },
                    "required": [
                        "acreage",
                        "terrain",
                        "lot_count",
                        "target_lot_width",
                        "target_lot_depth",
                        "road_width",
                        "roadway_max_grade_pct",
                        "minimum_drainage_slope_pct",
                        "include_culdesacs",
                        "culdesac_count",
                        "include_utility_corridors",
                        "include_detention_ponds",
                        "detention_pond_count",
                        "ada_sidewalk_required",
                        "balanced_cut_fill_target",
                        "need_proposed_contours",
                        "need_profiles",
                        "need_cross_sections",
                        "need_earthwork_report",
                        "origin",
                        "site_width",
                        "site_depth",
                        "street_frontage_edge",
                    ],
                },
                {"type": "null"},
            ]
        },

        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "task": {
                        "type": "string",
                        "enum": [
                            "rectangle",
                            "text_note",
                            "polygon",
                            "polyline",
                            "circle",
                            "arc",
                            "north_arrow",
                            "point",
                        ],
                    },
                    "origin": POINT_OR_NULL,
                    "points": POINT_LIST_OR_NULL,
                    "closed": BOOL_OR_NULL,
                    "width": NUM_OR_NULL,
                    "height": NUM_OR_NULL,
                    "label": STR_OR_NULL,
                    "layer": STR_OR_NULL,
                    "text": STR_OR_NULL,
                    "text_height": NUM_OR_NULL,
                    "center": POINT_OR_NULL,
                    "radius": NUM_OR_NULL,
                    "start_angle": NUM_OR_NULL,
                    "end_angle": NUM_OR_NULL,
                },
                "required": [
                    "task",
                    "origin",
                    "points",
                    "closed",
                    "width",
                    "height",
                    "label",
                    "layer",
                    "text",
                    "text_height",
                    "center",
                    "radius",
                    "start_angle",
                    "end_angle",
                ],
            },
        },

        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
        },

        # -----------------------------
        # EXPANDED FIELDS
        # -----------------------------
        "buildings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "x": NUM_OR_NULL,
                    "y": NUM_OR_NULL,
                    "w": NUM_OR_NULL,
                    "d": NUM_OR_NULL,
                    "floors": INT_OR_NULL,
                    "use": STR_OR_NULL,
                    "footprint_type": STR_OR_NULL,
                    "frontage_edge": STR_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": [
                    "label",
                    "x",
                    "y",
                    "w",
                    "d",
                    "floors",
                    "use",
                    "footprint_type",
                    "frontage_edge",
                    "layer",
                ],
            },
        },

        "parking_areas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "x": NUM_OR_NULL,
                    "y": NUM_OR_NULL,
                    "w": NUM_OR_NULL,
                    "h": NUM_OR_NULL,
                    "stall_count": INT_OR_NULL,
                    "stall_width": NUM_OR_NULL,
                    "stall_depth": NUM_OR_NULL,
                    "aisle_width": NUM_OR_NULL,
                    "layout": STR_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": [
                    "label",
                    "x",
                    "y",
                    "w",
                    "h",
                    "stall_count",
                    "stall_width",
                    "stall_depth",
                    "aisle_width",
                    "layout",
                    "layer",
                ],
            },
        },

        "drive_aisles": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "points": POINT_LIST_OR_NULL,
                    "width": NUM_OR_NULL,
                    "type": STR_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "points", "width", "type", "layer"],
            },
        },

        "roads_network": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "points": POINT_LIST_OR_NULL,
                    "width": NUM_OR_NULL,
                    "lanes": INT_OR_NULL,
                    "type": STR_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "points", "width", "lanes", "type", "layer"],
            },
        },

        "sidewalks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "points": POINT_LIST_OR_NULL,
                    "width": NUM_OR_NULL,
                    "ada_required": BOOL_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "points", "width", "ada_required", "layer"],
            },
        },

        "fire_lanes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "points": POINT_LIST_OR_NULL,
                    "width": NUM_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "points", "width", "layer"],
            },
        },

        "drainage_structures": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "x": NUM_OR_NULL,
                    "y": NUM_OR_NULL,
                    "type": STR_OR_NULL,
                    "rim_elev": NUM_OR_NULL,
                    "invert_out": NUM_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "x", "y", "type", "rim_elev", "invert_out", "layer"],
            },
        },

        "pipe_network": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "start": POINT_OR_NULL,
                    "end": POINT_OR_NULL,
                    "diameter": NUM_OR_NULL,
                    "type": STR_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "start", "end", "diameter", "type", "layer"],
            },
        },

        "ponds": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "x": NUM_OR_NULL,
                    "y": NUM_OR_NULL,
                    "w": NUM_OR_NULL,
                    "h": NUM_OR_NULL,
                    "type": STR_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "x", "y", "w", "h", "type", "layer"],
            },
        },

        "utility_network": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "label": STR_OR_NULL,
                    "points": POINT_LIST_OR_NULL,
                    "utility_type": STR_OR_NULL,
                    "diameter": NUM_OR_NULL,
                    "layer": STR_OR_NULL,
                },
                "required": ["label", "points", "utility_type", "diameter", "layer"],
            },
        },

        "grading": {
            "anyOf": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "pad_count": INT_OR_NULL,
                        "spot_grade_count": INT_OR_NULL,
                        "flow_arrow_count": INT_OR_NULL,
                        "contours_required": BOOL_OR_NULL,
                        "min_slope_pct": NUM_OR_NULL,
                    },
                    "required": [
                        "pad_count",
                        "spot_grade_count",
                        "flow_arrow_count",
                        "contours_required",
                        "min_slope_pct",
                    ],
                },
                {"type": "null"},
            ]
        },

        "disciplines": {
            "type": "array",
            "items": {"type": "string"},
        },

        "deliverables": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "project_name",
        "units",
        "mode",
        "project_type",
        "lot",
        "setback",
        "site_type",
        "street_edge",
        "layout_strategy",
        "intensity",
        "building_width",
        "building_depth",
        "terrain",
        "acreage",
        "site_plan",
        "road",
        "bridge",
        "pool",
        "drainage",
        "subdivision",
        "actions",
        "assumptions",
        "buildings",
        "parking_areas",
        "drive_aisles",
        "roads_network",
        "sidewalks",
        "fire_lanes",
        "drainage_structures",
        "pipe_network",
        "ponds",
        "utility_network",
        "grading",
        "disciplines",
        "deliverables",
    ],
}


def _safe_number(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _normalize_direction(value: Any, default: str | None = None) -> str | None:
    if value is None:
        return default

    text = str(value).strip().lower()
    mapping = {
        "north": "top",
        "south": "bottom",
        "east": "right",
        "west": "left",
        "top": "top",
        "bottom": "bottom",
        "left": "left",
        "right": "right",
        "front": "bottom",
    }
    if text in mapping:
        return mapping[text]

    tokens = text.replace("-", " ").replace("_", " ").split()
    token_map = {
        "n": "top",
        "north": "top",
        "s": "bottom",
        "south": "bottom",
        "e": "right",
        "east": "right",
        "w": "left",
        "west": "left",
    }
    for token in tokens:
        if token in token_map:
            return token_map[token]

    return default if default is not None else text


def _normalize_layout_strategy(value: Any, street_edge: Any) -> tuple[str, str | None]:
    raw = str(value or "").strip().lower()
    edge = _normalize_direction(street_edge, None)

    if not raw:
        return "front_parking", edge

    text = raw.replace("-", "_").replace(" ", "_")

    if "east" in text and edge is None:
        edge = "right"
    elif "west" in text and edge is None:
        edge = "left"
    elif "north" in text and edge is None:
        edge = "top"
    elif "south" in text and edge is None:
        edge = "bottom"

    if "front" in text:
        return "front_parking", edge
    if "rear" in text:
        return "rear_parking", edge
    if "side" in text:
        return "side_parking", edge
    if "street" in text:
        return "street_building", edge
    if "court" in text or "cluster" in text:
        return "building_courts", edge
    if "subdivision" in text:
        return "subdivision_layout", edge
    if "drain" in text:
        return "drainage_layout", edge

    return text, edge


def _dedupe_keep_order(items: List[str] | None) -> List[str]:
    if not items:
        return []
    out: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _normalize_point(pt: Any) -> Any:
    if pt is None:
        return None
    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
        return [_safe_number(pt[0], 0.0), _safe_number(pt[1], 0.0)]
    return None


def _normalize_points(points: Any) -> Any:
    if points is None:
        return None
    if not isinstance(points, list):
        return None
    out = []
    for pt in points:
        norm = _normalize_point(pt)
        if norm is not None:
            out.append(norm)
    return out if out else None


def _ensure_list(data: Dict[str, Any], key: str) -> List[Any]:
    val = data.get(key)
    if isinstance(val, list):
        return val
    data[key] = []
    return data[key]


def _maybe_infer_lot_from_site_plan(data: Dict[str, Any]) -> None:
    site_plan = data.get("site_plan")
    if data.get("lot") is None and isinstance(site_plan, dict):
        lot_width = _safe_number(site_plan.get("lot_width"))
        lot_depth = _safe_number(site_plan.get("lot_depth"))
        lot_origin = site_plan.get("lot_origin") or [0.0, 0.0]
        if lot_width is not None and lot_depth is not None:
            data["lot"] = {
                "x": _safe_number(lot_origin[0], 0.0),
                "y": _safe_number(lot_origin[1], 0.0),
                "w": lot_width,
                "h": lot_depth,
            }


def _maybe_infer_lot_from_subdivision(data: Dict[str, Any]) -> None:
    subdivision = data.get("subdivision")
    if data.get("lot") is None and isinstance(subdivision, dict):
        site_width = _safe_number(subdivision.get("site_width"))
        site_depth = _safe_number(subdivision.get("site_depth"))
        origin = subdivision.get("origin") or [0.0, 0.0]
        if site_width is not None and site_depth is not None:
            data["lot"] = {
                "x": _safe_number(origin[0], 0.0),
                "y": _safe_number(origin[1], 0.0),
                "w": site_width,
                "h": site_depth,
            }


def _normalize_lot(data: Dict[str, Any]) -> None:
    lot = data.get("lot")
    if isinstance(lot, dict):
        lot["x"] = _safe_number(lot.get("x"), 0.0)
        lot["y"] = _safe_number(lot.get("y"), 0.0)
        lot["w"] = _safe_number(lot.get("w"))
        lot["h"] = _safe_number(lot.get("h"))


def _populate_legacy_building_summary_from_buildings(data: Dict[str, Any]) -> None:
    buildings = data.get("buildings") or []
    if not buildings:
        return

    first = None
    for b in buildings:
        if isinstance(b, dict):
            first = b
            break

    if first is None:
        return

    if data.get("building_width") is None:
        data["building_width"] = _safe_number(first.get("w"))
    if data.get("building_depth") is None:
        data["building_depth"] = _safe_number(first.get("d"))

    site_plan = data.get("site_plan")
    if isinstance(site_plan, dict):
        if site_plan.get("building_width") is None:
            site_plan["building_width"] = _safe_number(first.get("w"))
        if site_plan.get("building_depth") is None:
            site_plan["building_depth"] = _safe_number(first.get("d"))


def _populate_legacy_drainage_summary_from_expanded(data: Dict[str, Any]) -> None:
    drainage = data.get("drainage")
    if not isinstance(drainage, dict):
        return

    structures = data.get("drainage_structures") or []
    pipes = data.get("pipe_network") or []
    ponds = data.get("ponds") or []

    if drainage.get("inlet_count") is None:
        drainage["inlet_count"] = len(structures) if structures else None
    if drainage.get("pipe_count") is None:
        drainage["pipe_count"] = len(pipes) if pipes else None
    if drainage.get("pond_count") is None:
        drainage["pond_count"] = len(ponds) if ponds else None

    if drainage.get("trunk_line_count") is None and pipes:
        drainage["trunk_line_count"] = max(1, min(3, len(pipes)))


def _normalize_site_plan(data: Dict[str, Any]) -> None:
    site_plan = data.get("site_plan")
    if not isinstance(site_plan, dict):
        return

    site_plan["lot_width"] = _safe_number(site_plan.get("lot_width"))
    site_plan["lot_depth"] = _safe_number(site_plan.get("lot_depth"))
    site_plan["lot_origin"] = _normalize_point(site_plan.get("lot_origin")) or [0.0, 0.0]
    site_plan["building_width"] = _safe_number(site_plan.get("building_width"))
    site_plan["building_depth"] = _safe_number(site_plan.get("building_depth"))
    site_plan["setback"] = _safe_number(site_plan.get("setback"), 10.0)
    site_plan["driveway_width"] = _safe_number(site_plan.get("driveway_width"))
    site_plan["driveway_side"] = _normalize_direction(site_plan.get("driveway_side"), "right")
    site_plan["parking_count"] = _safe_int(site_plan.get("parking_count"))
    site_plan["stall_width"] = _safe_number(site_plan.get("stall_width"))
    site_plan["stall_depth"] = _safe_number(site_plan.get("stall_depth"))
    site_plan["aisle_width"] = _safe_number(site_plan.get("aisle_width"))


def _normalize_road(data: Dict[str, Any]) -> None:
    road = data.get("road")
    if not isinstance(road, dict):
        return

    road["length"] = _safe_number(road.get("length"))
    road["lanes"] = _safe_int(road.get("lanes"))
    road["lane_width"] = _safe_number(road.get("lane_width"))
    road["shoulder_width"] = _safe_number(road.get("shoulder_width"))
    road["median_width"] = _safe_number(road.get("median_width"))
    road["origin"] = _normalize_point(road.get("origin")) or [0.0, 0.0]
    road["max_grade_pct"] = _safe_number(road.get("max_grade_pct"))
    road["sidewalk_width"] = _safe_number(road.get("sidewalk_width"))
    road["centerline_points"] = _normalize_points(road.get("centerline_points"))


def _normalize_bridge(data: Dict[str, Any]) -> None:
    bridge = data.get("bridge")
    if not isinstance(bridge, dict):
        return

    bridge["span_length"] = _safe_number(bridge.get("span_length"))
    bridge["deck_width"] = _safe_number(bridge.get("deck_width"))
    bridge["support_count"] = _safe_int(bridge.get("support_count"))
    bridge["span_count"] = _safe_int(bridge.get("span_count"))
    bridge["origin"] = _normalize_point(bridge.get("origin")) or [0.0, 0.0]


def _normalize_pool(data: Dict[str, Any]) -> None:
    pool = data.get("pool")
    if not isinstance(pool, dict):
        return

    pool["pool_length"] = _safe_number(pool.get("pool_length"))
    pool["pool_width"] = _safe_number(pool.get("pool_width"))
    pool["origin"] = _normalize_point(pool.get("origin")) or [0.0, 0.0]


def _normalize_drainage(data: Dict[str, Any]) -> None:
    drainage = data.get("drainage")
    if not isinstance(drainage, dict):
        return

    drainage["inlet_count"] = _safe_int(drainage.get("inlet_count"))
    drainage["pipe_count"] = _safe_int(drainage.get("pipe_count"))
    drainage["trunk_line_count"] = _safe_int(drainage.get("trunk_line_count"))
    drainage["pond_count"] = _safe_int(drainage.get("pond_count"))
    drainage["pipe_diameter"] = _safe_number(drainage.get("pipe_diameter"))
    drainage["outfall_side"] = _normalize_direction(drainage.get("outfall_side"), "bottom")


def _normalize_subdivision(data: Dict[str, Any]) -> None:
    subdivision = data.get("subdivision")
    if not isinstance(subdivision, dict):
        return

    subdivision["acreage"] = _safe_number(subdivision.get("acreage"))
    subdivision["lot_count"] = _safe_int(subdivision.get("lot_count"))
    subdivision["target_lot_width"] = _safe_number(subdivision.get("target_lot_width"))
    subdivision["target_lot_depth"] = _safe_number(subdivision.get("target_lot_depth"))
    subdivision["road_width"] = _safe_number(subdivision.get("road_width"))
    subdivision["roadway_max_grade_pct"] = _safe_number(subdivision.get("roadway_max_grade_pct"))
    subdivision["minimum_drainage_slope_pct"] = _safe_number(subdivision.get("minimum_drainage_slope_pct"))
    subdivision["culdesac_count"] = _safe_int(subdivision.get("culdesac_count"))
    subdivision["detention_pond_count"] = _safe_int(subdivision.get("detention_pond_count"))
    subdivision["origin"] = _normalize_point(subdivision.get("origin")) or [0.0, 0.0]
    subdivision["site_width"] = _safe_number(subdivision.get("site_width"))
    subdivision["site_depth"] = _safe_number(subdivision.get("site_depth"))
    subdivision["street_frontage_edge"] = _normalize_direction(
        subdivision.get("street_frontage_edge"),
        "bottom",
    )


def _normalize_building_use(value: Any, project_type: Any) -> str:
    text = str(value or "").strip().lower()

    mapping = {
        "apartment": "multifamily",
        "apartments": "multifamily",
        "multifamily": "multifamily",
        "residential": "multifamily",
        "office": "office",
        "retail": "retail",
        "shell": "retail",
        "industrial": "industrial",
        "warehouse": "industrial",
        "generic": "generic",
    }
    if text in mapping:
        return mapping[text]

    ptype = str(project_type or "").strip().lower()
    if ptype == "multifamily_site":
        return "multifamily"
    if ptype == "office_site":
        return "office"
    if ptype == "strip_center":
        return "retail"
    if ptype == "industrial_site":
        return "industrial"

    return "generic"


def _normalize_footprint_type(value: Any, use: str) -> str:
    text = str(value or "").strip().lower()
    allowed = {"bar", "slab", "compact", "l_shape", "u_shape", "courtyard", "h_shape"}
    aliases = {
        "l-shape": "l_shape",
        "u-shape": "u_shape",
        "l": "l_shape",
        "u": "u_shape",
        "court": "courtyard",
    }

    text = aliases.get(text, text)
    if text in allowed:
        return text

    if use == "multifamily":
        return "bar"
    if use == "office":
        return "slab"
    if use == "retail":
        return "bar"
    if use == "industrial":
        return "compact"
    return "bar"


def _normalize_expanded_objects(data: Dict[str, Any]) -> None:
    project_type = data.get("project_type")
    site_edge = _normalize_direction(data.get("street_edge"), "bottom")

    for b in _ensure_list(data, "buildings"):
        if isinstance(b, dict):
            b["x"] = _safe_number(b.get("x"))
            b["y"] = _safe_number(b.get("y"))
            b["w"] = _safe_number(b.get("w"))
            b["d"] = _safe_number(b.get("d"))
            b["floors"] = _safe_int(b.get("floors"))
            b["use"] = _normalize_building_use(b.get("use"), project_type)
            b["footprint_type"] = _normalize_footprint_type(b.get("footprint_type"), b["use"])
            b["frontage_edge"] = _normalize_direction(b.get("frontage_edge"), site_edge)
            b["layer"] = b.get("layer") or "BUILDING"

    for p in _ensure_list(data, "parking_areas"):
        if isinstance(p, dict):
            p["x"] = _safe_number(p.get("x"))
            p["y"] = _safe_number(p.get("y"))
            p["w"] = _safe_number(p.get("w"))
            p["h"] = _safe_number(p.get("h"))
            p["stall_count"] = _safe_int(p.get("stall_count"))
            p["stall_width"] = _safe_number(p.get("stall_width"))
            p["stall_depth"] = _safe_number(p.get("stall_depth"))
            p["aisle_width"] = _safe_number(p.get("aisle_width"))
            p["layer"] = p.get("layer") or "PARKING"

    for d in _ensure_list(data, "drive_aisles"):
        if isinstance(d, dict):
            d["points"] = _normalize_points(d.get("points"))
            d["width"] = _safe_number(d.get("width"))
            d["layer"] = d.get("layer") or "PAVEMENT"

    for r in _ensure_list(data, "roads_network"):
        if isinstance(r, dict):
            r["points"] = _normalize_points(r.get("points"))
            r["width"] = _safe_number(r.get("width"))
            r["lanes"] = _safe_int(r.get("lanes"))
            r["layer"] = r.get("layer") or "ROAD"

    for s in _ensure_list(data, "sidewalks"):
        if isinstance(s, dict):
            s["points"] = _normalize_points(s.get("points"))
            s["width"] = _safe_number(s.get("width"))
            s["layer"] = s.get("layer") or "WALK"

    for f in _ensure_list(data, "fire_lanes"):
        if isinstance(f, dict):
            f["points"] = _normalize_points(f.get("points"))
            f["width"] = _safe_number(f.get("width"))
            f["layer"] = f.get("layer") or "FIRE"

    for ds in _ensure_list(data, "drainage_structures"):
        if isinstance(ds, dict):
            ds["x"] = _safe_number(ds.get("x"))
            ds["y"] = _safe_number(ds.get("y"))
            ds["rim_elev"] = _safe_number(ds.get("rim_elev"))
            ds["invert_out"] = _safe_number(ds.get("invert_out"))
            ds["layer"] = ds.get("layer") or "DRAIN"

    for pipe in _ensure_list(data, "pipe_network"):
        if isinstance(pipe, dict):
            pipe["start"] = _normalize_point(pipe.get("start"))
            pipe["end"] = _normalize_point(pipe.get("end"))
            pipe["diameter"] = _safe_number(pipe.get("diameter"))
            pipe["layer"] = pipe.get("layer") or "PIPE"

    for pond in _ensure_list(data, "ponds"):
        if isinstance(pond, dict):
            pond["x"] = _safe_number(pond.get("x"))
            pond["y"] = _safe_number(pond.get("y"))
            pond["w"] = _safe_number(pond.get("w"))
            pond["h"] = _safe_number(pond.get("h"))
            pond["layer"] = pond.get("layer") or "BASIN_BOUNDARY"

    for u in _ensure_list(data, "utility_network"):
        if isinstance(u, dict):
            u["points"] = _normalize_points(u.get("points"))
            u["diameter"] = _safe_number(u.get("diameter"))
            utility_type = str(u.get("utility_type") or "").lower()
            if u.get("layer") is None:
                if utility_type in {"water"}:
                    u["layer"] = "WATER"
                elif utility_type in {"sanitary", "san"}:
                    u["layer"] = "SAN"
                elif utility_type in {"storm"}:
                    u["layer"] = "STORM"
                else:
                    u["layer"] = "UTILITY"

    grading = data.get("grading")
    if isinstance(grading, dict):
        grading["pad_count"] = _safe_int(grading.get("pad_count"))
        grading["spot_grade_count"] = _safe_int(grading.get("spot_grade_count"))
        grading["flow_arrow_count"] = _safe_int(grading.get("flow_arrow_count"))
        grading["min_slope_pct"] = _safe_number(grading.get("min_slope_pct"))


def _populate_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    if data.get("setback") is None and isinstance(data.get("site_plan"), dict):
        data["setback"] = _safe_number(data["site_plan"].get("setback"), 10.0)

    if data.get("acreage") is None and isinstance(data.get("subdivision"), dict):
        data["acreage"] = _safe_number(data["subdivision"].get("acreage"))

    if data.get("terrain") is None:
        subdivision = data.get("subdivision")
        drainage = data.get("drainage")
        if isinstance(subdivision, dict) and subdivision.get("terrain") is not None:
            data["terrain"] = subdivision.get("terrain")
        elif isinstance(drainage, dict) and drainage.get("grading_required"):
            data["terrain"] = "graded"
        else:
            data["terrain"] = "flat"

    data["street_edge"] = _normalize_direction(data.get("street_edge"), "bottom")

    layout_strategy, normalized_edge = _normalize_layout_strategy(
        data.get("layout_strategy"),
        data.get("street_edge"),
    )
    data["layout_strategy"] = layout_strategy
    if normalized_edge is not None:
        data["street_edge"] = normalized_edge

    if data.get("site_type") is None:
        project_type = data.get("project_type")
        if project_type in {
            "commercial_pad",
            "office_site",
            "strip_center",
            "industrial_site",
            "multifamily_site",
        }:
            data["site_type"] = project_type
        elif project_type == "drainage_network":
            data["site_type"] = "drainage_network"
        elif project_type == "residential_subdivision":
            data["site_type"] = "residential_subdivision"
        else:
            data["site_type"] = "generic_site"

    if data.get("layout_strategy") is None:
        if data.get("project_type") == "residential_subdivision":
            data["layout_strategy"] = "subdivision_layout"
        elif data.get("project_type") == "drainage_network":
            data["layout_strategy"] = "drainage_layout"
        elif data.get("project_type") == "multifamily_site":
            data["layout_strategy"] = "building_courts"
        else:
            data["layout_strategy"] = "front_parking"

    if data.get("intensity") is None:
        data["intensity"] = "medium"

    if data.get("setback") is None:
        data["setback"] = 10.0

    if data.get("actions") is None:
        data["actions"] = []

    if data.get("assumptions") is None:
        data["assumptions"] = []

    if data.get("disciplines") is None:
        data["disciplines"] = []

    if data.get("deliverables") is None:
        data["deliverables"] = []

    return data


def _infer_disciplines_and_deliverables(data: Dict[str, Any]) -> None:
    disciplines = _dedupe_keep_order(data.get("disciplines"))
    deliverables = _dedupe_keep_order(data.get("deliverables"))

    if data.get("mode") in {"site_plan", "subdivision"}:
        disciplines.append("layout")
        deliverables.append("site_plan")
        deliverables.append("dxf_geometry")

    if data.get("parking_areas"):
        disciplines.append("parking")

    if data.get("drive_aisles") or data.get("roads_network"):
        disciplines.append("access")

    if data.get("road") is not None or data.get("roads_network"):
        disciplines.append("roadway")
        deliverables.append("roadway_plan")

    if data.get("sidewalks"):
        disciplines.append("sidewalks")

    if isinstance(data.get("road"), dict) and data["road"].get("ada_required"):
        disciplines.append("ada")

    if data.get("fire_lanes"):
        disciplines.append("fire_access")

    if isinstance(data.get("drainage"), dict):
        drainage = data["drainage"]
        if any(
            drainage.get(k) not in (None, 0, False)
            for k in ["inlet_count", "pipe_count", "pond_count", "routing_required"]
        ) or data.get("drainage_structures") or data.get("pipe_network") or data.get("ponds"):
            disciplines.append("drainage")
            deliverables.append("drainage_plan")

        if drainage.get("pond_count") not in (None, 0, False) or data.get("ponds"):
            disciplines.append("detention")

        if drainage.get("grading_required"):
            disciplines.append("grading")
            deliverables.append("grading_plan")

    if data.get("utility_network"):
        disciplines.append("utilities")
        deliverables.append("utility_plan")

    grading = data.get("grading")
    if isinstance(grading, dict):
        if grading.get("pad_count") not in (None, 0) or grading.get("spot_grade_count") not in (None, 0):
            disciplines.append("grading")
            deliverables.append("grading_plan")
        if grading.get("contours_required"):
            disciplines.append("contours")
            deliverables.append("proposed_contours")

    subdivision = data.get("subdivision")
    if isinstance(subdivision, dict):
        if subdivision.get("need_proposed_contours"):
            disciplines.append("contours")
            deliverables.append("proposed_contours")
        if subdivision.get("need_profiles"):
            disciplines.append("profiles")
            deliverables.append("profiles")
        if subdivision.get("need_cross_sections"):
            disciplines.append("cross_sections")
            deliverables.append("cross_sections")
        if subdivision.get("need_earthwork_report"):
            disciplines.append("earthwork")
            deliverables.append("earthwork_report")
        if subdivision.get("include_utility_corridors"):
            disciplines.append("utilities")
            deliverables.append("utility_plan")
        if subdivision.get("include_detention_ponds"):
            disciplines.append("detention")
            deliverables.append("drainage_plan")
        if subdivision.get("ada_sidewalk_required"):
            disciplines.append("ada")
            disciplines.append("sidewalks")

    if data.get("bridge") is not None and data.get("mode") == "bridge":
        disciplines.append("bridge")
        deliverables.append("bridge_concept")

    if data.get("pool") is not None and data.get("mode") == "pool":
        disciplines.append("pool")
        deliverables.append("pool_plan")

    data["disciplines"] = _dedupe_keep_order(disciplines)
    data["deliverables"] = _dedupe_keep_order(deliverables)


def _normalize_command_data(data: Dict[str, Any], prompt_text: str = "") -> Dict[str, Any]:
    _populate_defaults(data)
    _maybe_infer_lot_from_site_plan(data)
    _maybe_infer_lot_from_subdivision(data)
    _normalize_lot(data)

    _normalize_site_plan(data)
    _normalize_road(data)
    _normalize_bridge(data)
    _normalize_pool(data)
    _normalize_drainage(data)
    _normalize_subdivision(data)
    _normalize_expanded_objects(data)

    _populate_legacy_building_summary_from_buildings(data)
    _populate_legacy_drainage_summary_from_expanded(data)
    _infer_disciplines_and_deliverables(data)
    _apply_three_state_field_contract(data, prompt_text=prompt_text)

    return data


def ask_mode(user_text: str) -> str:
    response = _get_client().responses.create(
        model="gpt-5",
        input=[
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    return response.output_text


def command_mode(user_text: str) -> Dict[str, Any]:
    response = _get_client().responses.create(
        model="gpt-5",
        input=[
            {"role": "system", "content": COMMAND_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "civil_ai_plan_compatible_expanded_v2",
                "schema": COMMAND_SCHEMA,
                "strict": True,
            }
        },
    )
    data = json.loads(response.output_text)
    return _normalize_command_data(data)
