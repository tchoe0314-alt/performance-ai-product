
# core/config.py
# TRUE MAX MERGED CIVIL-GRADE VERSION

"""
Central product/runtime/configuration layer for the AI civil / CAD platform.

This file preserves the original design constants and expands them into a fuller
product-level configuration surface for:

- planner
- planner_intelligence
- planner_orchestrator
- project_classifier
- coordination_engine
- project_manager
- system_runner
- report_builder
- session_state
- future UI/runtime controls

Design rule:
Do not remove core engineering defaults. Expand control and product readiness.
"""

import os

# =========================================================
# APP / PRODUCT SETTINGS
# =========================================================

APP_NAME = "Civil AI Assistant"
APP_VERSION = "0.1.0"
DEBUG = True

# Runtime identity / product mode
def _env_flag(name: str, default: bool) -> bool:
    raw = str(os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _normalized_product_mode(raw: str) -> str:
    value = str(raw or "").strip().lower().replace("-", "_")
    aliases = {
        "alpha": "private_alpha",
        "review": "private_alpha",
        "review_only": "private_alpha",
        "beta": "public_beta",
    }
    return aliases.get(value, value or "private_alpha")


PRODUCT_MODE = _normalized_product_mode(
    os.getenv("CIVORA_PRODUCT_MODE") or os.getenv("PERFORMANCE_AI_PRODUCT_MODE") or "private_alpha"
)  # development | private_alpha | public_beta | production
REVIEW_ONLY_PRODUCT_MODES = {"development", "private_alpha", "public_beta"}
ALPHA_REVIEW_ONLY = PRODUCT_MODE in REVIEW_ONLY_PRODUCT_MODES
CONSTRUCTION_RELEASES_ENABLED = PRODUCT_MODE == "production" and _env_flag(
    "CIVORA_ENABLE_CONSTRUCTION_RELEASES",
    True,
)
ENABLE_VERBOSE_TRACE = True
ENABLE_AUDIT_LOGGING = True

# =========================================================
# FILES / DATA
# =========================================================

DEFAULT_SURVEY_FILENAME = "survey_points.csv"
DEFAULT_EXPORT_DIR = "exports"
DEFAULT_REPORT_DIR = "reports"
DEFAULT_SESSION_CACHE_DIR = "sessions"

# =========================================================
# SURFACE / TERRAIN
# =========================================================

CELL_SIZE = 5.0
SURFACE_PADDING = 0.0
CONTOUR_INTERVAL = 2.0

# =========================================================
# DISPLAY / OUTPUT DENSITY
# =========================================================

SPOT_SAMPLE_STEP = 20
DRAIN_SAMPLE_STEP = 5

DEBUG_SPOT_MULTIPLIER = 3
DEBUG_MIN_SPOT_STEP = 12

MAX_WARNINGS = 8
DEBUG_WARNING_LIMIT = 3

# =========================================================
# DESIGN / DRAINAGE RULES
# =========================================================

MIN_SLOPE = 0.002
POND_RADIUS = 8.0

# Pipe network concept settings
PIPE_RUNOFF_C = 0.85
PIPE_INTENSITY_IN_HR = 4.0
PIPE_MIN_SLOPE = 0.003
PIPE_MANNINGS_N = 0.013
PIPE_MIN_COVER_FT = 3.0
PIPE_MAX_INLETS = 8
PIPE_INLET_MIN_SPACING = 12.0

# Utility concept defaults
UTILITY_MIN_HORIZONTAL_SEPARATION_FT = 3.0
UTILITY_MIN_VERTICAL_SEPARATION_FT = 1.0
UTILITY_DEFAULT_DEPTH_FT = 4.0

# Parking / conceptual planning defaults
DEFAULT_PARKING_STALL_WIDTH = 9.0
DEFAULT_PARKING_STALL_DEPTH = 18.0
DEFAULT_PARKING_AISLE_WIDTH = 24.0

# Basic concept grading / circulation defaults
DEFAULT_SIDEWALK_WIDTH = 5.0
DEFAULT_DRIVE_AISLE_WIDTH = 24.0
DEFAULT_MAX_CONCEPT_ROAD_GRADE = 0.08
DEFAULT_MAX_CONCEPT_PARKING_SLOPE = 0.05
DEFAULT_MAX_CONCEPT_SIDEWALK_SLOPE = 0.05

# =========================================================
# TEXT / ANNOTATION
# =========================================================

TEXT_HEIGHT_SMALL = 0.45
TEXT_HEIGHT_MED = 1.0
TEXT_HEIGHT_LARGE = 2.0

WARNING_NOTE_SPACING = 2.0

# =========================================================
# VIEW MODES
# =========================================================

VIEW_EXISTING = "existing"
VIEW_GRADING = "grading"
VIEW_DRAINAGE = "drainage"
VIEW_FULL = "full"

VALID_VIEW_MODES = {
    VIEW_EXISTING,
    VIEW_GRADING,
    VIEW_DRAINAGE,
    VIEW_FULL,
}

# =========================================================
# LAYERS
# =========================================================

LAYER_ANNO = "ANNO"
LAYER_SITE = "SITE"
LAYER_SETBACK = "SETBACK"
LAYER_BUILDING = "BUILDING"
LAYER_PAVEMENT = "PAVEMENT"
LAYER_SYMBOL = "SYMBOL"
LAYER_STRUCTURE = "STRUCTURE"
LAYER_WATER = "WATER"
LAYER_ROAD = "ROAD"
LAYER_LOT = "LOT"
LAYER_SURFACE = "SURFACE"

LAYER_EG_CONTOUR = "EG_CONTOUR"
LAYER_FG_CONTOUR = "FG_CONTOUR"
LAYER_SPOT_EG = "SPOT_EG"
LAYER_SPOT_FG = "SPOT_FG"
LAYER_DRAIN = "DRAIN_FLOW"
LAYER_LOW = "LOW_POINTS"
LAYER_BASIN = "BASIN_BOUNDARY"
LAYER_PIPE = "PIPE"

# Optional future-friendly aliases
LAYER_PIPE_LABELS = LAYER_ANNO
LAYER_WARNINGS = LAYER_ANNO

# =========================================================
# DEFAULT DEMO LAYOUT
# =========================================================

DEFAULT_LOT_X = 0.0
DEFAULT_LOT_Y = 0.0
DEFAULT_LOT_WIDTH = 100.0
DEFAULT_LOT_HEIGHT = 100.0
DEFAULT_SETBACK = 10.0

DEFAULT_PAD_X = 30.0
DEFAULT_PAD_Y = 35.0
DEFAULT_PAD_WIDTH = 40.0
DEFAULT_PAD_DEPTH = 25.0
DEFAULT_PAD_ELEV = 102.0

DEFAULT_PARK_X = 15.0
DEFAULT_PARK_Y = 5.0
DEFAULT_PARK_WIDTH = 70.0
DEFAULT_PARK_DEPTH = 20.0
DEFAULT_PARK_START_ELEV = 101.0
DEFAULT_PARK_SLOPE_Y = 0.02

DEFAULT_ROAD_X = 0.0
DEFAULT_ROAD_Y = 45.0
DEFAULT_ROAD_WIDTH = 100.0
DEFAULT_ROAD_DEPTH = 16.0
DEFAULT_ROAD_START_ELEV = 101.5
DEFAULT_ROAD_SLOPE_X = 0.01

DEFAULT_POND_A_X = 10.0
DEFAULT_POND_A_Y = 90.0
DEFAULT_POND_B_X = 90.0
DEFAULT_POND_B_Y = 10.0

DEFAULT_POND_GRADE_X1 = 0.0
DEFAULT_POND_GRADE_Y1 = 80.0
DEFAULT_POND_GRADE_W1 = 20.0
DEFAULT_POND_GRADE_D1 = 20.0
DEFAULT_POND_GRADE_ELEV1 = 99.0
DEFAULT_POND_EDGE_RISE1 = 3.0

DEFAULT_POND_GRADE_X2 = 80.0
DEFAULT_POND_GRADE_Y2 = 0.0
DEFAULT_POND_GRADE_W2 = 20.0
DEFAULT_POND_GRADE_D2 = 20.0
DEFAULT_POND_GRADE_ELEV2 = 98.5
DEFAULT_POND_EDGE_RISE2 = 3.0

# =========================================================
# PRODUCT / SAFETY FLAGS
# =========================================================

ENABLE_AUTOFIX = True
ENABLE_VALIDATION = True
ENABLE_PIPE_NETWORK = True

# New backend control flags
ENABLE_COORDINATION = True
ENABLE_INTELLIGENCE = True
ENABLE_CLASSIFIER_ROUTING = True
ENABLE_REPORT_BUILDER = True
ENABLE_SESSION_STATE = True

# Input / assumption behavior
DEFAULT_STRICT_INPUTS = False
DEFAULT_ALLOW_ASSUMPTIONS = True
DEFAULT_STRICT_MODE = False

# Prevent unnecessary subsystem forcing
SKIP_UNUSED_DISCIPLINES = True
REQUIRE_EXPLICIT_UTILITY_SIGNAL = False
REQUIRE_EXPLICIT_DRAINAGE_SIGNAL = False

# =========================================================
# ITERATION / CONVERGENCE CONTROLS
# =========================================================

DEFAULT_GLOBAL_ITERATIONS = 3
DEFAULT_EVOLUTION_ROUNDS = 3
DEFAULT_COORDINATION_ITERATIONS = 3
DEFAULT_PLANNER_PASSES = 2

STOP_WHEN_CLEAN = True
STOP_WHEN_SCORE_STALLS = True
DEFAULT_SCORE_IMPROVEMENT_EPSILON = 1.0

# Intelligence defaults
DEFAULT_MAX_CANDIDATES = 10
DEFAULT_TOP_K_OPTIONS = 4
DEFAULT_OPTIMIZATION_GOAL = "balanced"

# =========================================================
# ROUTING / PIPELINE DEFAULTS
# =========================================================

DEFAULT_INPUT_MODE = "prompt"
DEFAULT_WORKFLOW = "auto"               # auto | single_plan | multi_option | full_design_loop
DEFAULT_PLAN_TYPE_HINT = None
DEFAULT_FULL_DESIGN_MODE = None         # None lets classifier/orchestrator decide

# Coordination defaults
DEFAULT_USE_COORDINATION_ENGINE = True
DEFAULT_COORDINATION_STOP_WHEN_CLEAN = True
DEFAULT_COORDINATION_STOP_WHEN_SCORE_STALLS = True

# =========================================================
# REPORT / SESSION / EXPORT DEFAULTS
# =========================================================

DEFAULT_CREATE_REPORT = True
DEFAULT_PERSIST_SESSION = False
DEFAULT_SESSION_KEEP_RUN_HISTORY = True
DEFAULT_SESSION_MAX_RUN_HISTORY = 50
DEFAULT_SAVED_OPTION_LIMIT = 20

DEFAULT_EXPORT_REPORT_PAYLOAD = True
DEFAULT_EXPORT_DXF = False
DEFAULT_EXPORT_PREVIEW_PAYLOAD = True

# =========================================================
# UI / EXPORT DEFAULTS
# =========================================================

DEFAULT_SURFACE_VIEW_MODE = VIEW_FULL
DEFAULT_ENGINE_TEST_VIEW_MODE = VIEW_DRAINAGE

# UI-ready response behavior
INCLUDE_ALTERNATIVES_IN_RESPONSE = True
INCLUDE_ITERATION_HISTORY_IN_RESPONSE = True
INCLUDE_MANAGER_METRICS_IN_RESPONSE = True
INCLUDE_MANAGER_CONFLICTS_IN_RESPONSE = True
