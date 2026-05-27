
from __future__ import annotations

"""
engines/storm/storm_types.py (TRUE MAX VERSION)

Purpose
-------
Shared data models for the storm module.

This file is the backbone for:
- inlet placement
- catchment delineation
- storm network generation
- basin / detention connection
- hydraulic analysis
- planner / compliance / conflict / routing integration

Design goals
------------
- full typed backbone for the storm module
- concept-to-preliminary engineering depth
- no toy placeholders
- future-ready fields added now
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# ENUMS
# =============================================================================

class StormNodeType(str, Enum):
    INLET = "inlet"
    JUNCTION = "junction"
    MANHOLE = "manhole"
    BASIN_CONNECTION = "basin_connection"
    OUTFALL = "outfall"
    HEADWALL = "headwall"
    FLARED_END = "flared_end"
    UNKNOWN = "unknown"


class StormPipeType(str, Enum):
    LATERAL = "lateral"
    MAIN = "main"
    TRUNK = "trunk"
    LEAD = "lead"
    OUTFALL = "outfall"
    BYPASS = "bypass"


class InletType(str, Enum):
    AREA = "area"
    CURB = "curb"
    COMBINATION = "combination"
    GRATE = "grate"
    DROP = "drop"
    YARD = "yard"
    UNKNOWN = "unknown"


class BasinType(str, Enum):
    DETENTION = "detention"
    RETENTION = "retention"
    BIORETENTION = "bioretention"
    SWALE = "swale"
    INFILTRATION = "infiltration"
    OUTFALL_RECEIVER = "outfall_receiver"
    UNKNOWN = "unknown"


class FlowPathType(str, Enum):
    SURFACE = "surface"
    GUTTER = "gutter"
    PIPE = "pipe"
    CHANNEL = "channel"
    OVERFLOW = "overflow"


class CapacityStatus(str, Enum):
    OK = "ok"
    MARGINAL = "marginal"
    DEFICIENT = "deficient"
    UNKNOWN = "unknown"


# =============================================================================
# CORE GEOMETRY / POINT MODELS
# =============================================================================

@dataclass
class StormPoint:
    x: float
    y: float
    z: Optional[float] = None
    label: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageStoragePoint:
    elevation_ft: float
    storage_cf: float
    water_surface_area_sf: float = 0.0
    average_area_sf: float = 0.0
    outflow_cfs: float = 0.0
    hgl_ft: Optional[float] = None
    notes: List[str] = field(default_factory=list)


# =============================================================================
# CATCHMENT / RUNOFF MODELS
# =============================================================================

@dataclass
class CatchmentSurfaceBreakdown:
    impervious_area_sf: float = 0.0
    roof_area_sf: float = 0.0
    pavement_area_sf: float = 0.0
    landscaped_area_sf: float = 0.0
    weighted_runoff_c: float = 0.0
    tc_minutes: float = 0.0
    intensity_in_hr: float = 0.0


@dataclass
class StormCatchment:
    name: str
    area_sf: float
    runoff_c: float
    tc_minutes: float
    intensity_in_hr: float
    peak_runoff_cfs: float = 0.0
    outlet_node_name: Optional[str] = None
    centroid: Optional[StormPoint] = None
    boundary_points: List[Tuple[float, float]] = field(default_factory=list)
    surface_breakdown: CatchmentSurfaceBreakdown = field(default_factory=CatchmentSurfaceBreakdown)
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# NODE / INLET / BASIN MODELS
# =============================================================================

@dataclass
class InletCaptureResult:
    intercepted_cfs: float = 0.0
    bypass_cfs: float = 0.0
    capture_efficiency: float = 0.0
    spread_ft: float = 0.0
    depth_ft: float = 0.0
    warnings: List[str] = field(default_factory=list)


@dataclass
class StormNode:
    name: str
    node_type: str = StormNodeType.UNKNOWN.value
    point: StormPoint = field(default_factory=lambda: StormPoint(0.0, 0.0, None))
    rim_elev_ft: Optional[float] = None
    invert_elev_ft: Optional[float] = None
    structure_diameter_ft: Optional[float] = None
    connected_pipe_names: List[str] = field(default_factory=list)
    incoming_catchment_names: List[str] = field(default_factory=list)
    contributing_area_sf: float = 0.0
    contributing_runoff_cfs: float = 0.0
    bypass_runoff_cfs: float = 0.0
    max_hgl_ft: Optional[float] = None
    surcharge_risk: bool = False
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StormInlet(StormNode):
    inlet_type: str = InletType.UNKNOWN.value
    throat_width_ft: float = 0.0
    grate_length_ft: float = 0.0
    grate_width_ft: float = 0.0
    curb_opening_ft: float = 0.0
    sag_point: bool = False
    on_grade: bool = True
    gutter_spread_limit_ft: float = 8.0
    capture: InletCaptureResult = field(default_factory=InletCaptureResult)
    bypass_to_node_name: Optional[str] = None
    local_low_point_score: float = 0.0
    placement_reason: str = ""


@dataclass
class StormBasin:
    name: str
    basin_type: str = BasinType.UNKNOWN.value
    bottom_area_sf: float = 0.0
    top_area_sf: float = 0.0
    depth_ft: float = 0.0
    side_slope_h_to_1v: float = 4.0
    bottom_elev_ft: Optional[float] = None
    overflow_elev_ft: Optional[float] = None
    release_cfs: float = 0.0
    required_storage_cf: float = 0.0
    provided_storage_cf: float = 0.0
    drawdown_hours: Optional[float] = None
    stage_storage_curve: List[StageStoragePoint] = field(default_factory=list)
    connection_node_name: Optional[str] = None
    boundary_points: List[Tuple[float, float]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# PIPE / NETWORK MODELS
# =============================================================================

@dataclass
class HydraulicCheck:
    design_flow_cfs: float = 0.0
    full_capacity_cfs: float = 0.0
    velocity_fps: float = 0.0
    flow_depth_ratio: float = 0.0
    normal_depth_ft: float = 0.0
    flow_area_sf: float = 0.0
    hgl_upstream_ft: Optional[float] = None
    hgl_downstream_ft: Optional[float] = None
    egl_upstream_ft: Optional[float] = None
    egl_downstream_ft: Optional[float] = None
    capacity_status: str = CapacityStatus.UNKNOWN.value
    warnings: List[str] = field(default_factory=list)


@dataclass
class StormPipe:
    name: str
    pipe_type: str = StormPipeType.LATERAL.value
    upstream_node_name: str = ""
    downstream_node_name: str = ""
    diameter_in: float = 0.0
    material: str = "RCP"
    length_ft: float = 0.0
    slope: float = 0.0
    min_slope: float = 0.003
    max_slope: Optional[float] = None
    mannings_n: float = 0.013
    cover_ft: Optional[float] = None
    upstream_invert_ft: Optional[float] = None
    downstream_invert_ft: Optional[float] = None
    assignable: bool = True
    route_points: List[Tuple[float, float]] = field(default_factory=list)
    contributing_catchment_names: List[str] = field(default_factory=list)
    assigned_runoff_cfs: float = 0.0
    hydraulic: HydraulicCheck = field(default_factory=HydraulicCheck)
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StormFlowPath:
    name: str
    flow_path_type: str = FlowPathType.SURFACE.value
    from_name: str = ""
    to_name: str = ""
    path_points: List[Tuple[float, float]] = field(default_factory=list)
    slope: float = 0.0
    contributing_area_sf: float = 0.0
    assigned_flow_cfs: float = 0.0
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StormNetwork:
    name: str
    nodes: List[StormNode] = field(default_factory=list)
    inlets: List[StormInlet] = field(default_factory=list)
    basins: List[StormBasin] = field(default_factory=list)
    pipes: List[StormPipe] = field(default_factory=list)
    catchments: List[StormCatchment] = field(default_factory=list)
    flow_paths: List[StormFlowPath] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# REQUEST / RESULT MODELS
# =============================================================================

@dataclass
class InletPlacementRequest:
    low_points: List[StormPoint] = field(default_factory=list)
    candidate_points: List[StormPoint] = field(default_factory=list)
    max_inlets: int = 12
    min_spacing_ft: float = 20.0
    default_inlet_type: str = InletType.AREA.value
    use_sag_points: bool = True
    use_on_grade_points: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InletPlacementResult:
    success: bool
    inlets: List[StormInlet] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StormNetworkRequest:
    network_name: str = "Storm Network"
    catchments: List[StormCatchment] = field(default_factory=list)
    inlets: List[StormInlet] = field(default_factory=list)
    basins: List[StormBasin] = field(default_factory=list)
    outfalls: List[StormNode] = field(default_factory=list)
    default_pipe_material: str = "RCP"
    default_mannings_n: float = 0.013
    min_pipe_slope: float = 0.003
    min_cover_ft: float = 3.0
    min_diameter_in: float = 12.0
    auto_route: bool = True
    route_system_type: str = "storm"
    use_trunks: bool = True
    use_laterals: bool = True
    connect_to_basin: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StormNetworkResult:
    success: bool
    network: StormNetwork = field(default_factory=StormNetwork)
    total_runoff_cfs: float = 0.0
    total_pipe_length_ft: float = 0.0
    total_pipe_count: int = 0
    total_inlet_count: int = 0
    total_structure_count: int = 0
    warnings: List[str] = field(default_factory=list)
    explain: Dict[str, Any] = field(default_factory=dict)
    optimize_hooks: Dict[str, Any] = field(default_factory=dict)
    conflict_hooks: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BasinConnectionRequest:
    basin: StormBasin
    inflow_nodes: List[StormNode] = field(default_factory=list)
    outfall_node: Optional[StormNode] = None
    allow_overflow_path: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BasinConnectionResult:
    success: bool
    basin: Optional[StormBasin] = None
    connection_node: Optional[StormNode] = None
    overflow_path: Optional[StormFlowPath] = None
    warnings: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HydraulicAnalysisRequest:
    pipes: List[StormPipe] = field(default_factory=list)
    nodes: List[StormNode] = field(default_factory=list)
    conservative: bool = True
    compute_hgl: bool = True
    compute_egl: bool = True
    allow_partial_flow: bool = True
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HydraulicAnalysisResult:
    success: bool
    pipes: List[StormPipe] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# SUMMARY HELPERS
# =============================================================================

def summarize_storm_network(network: StormNetwork) -> Dict[str, Any]:
    total_runoff = sum(c.peak_runoff_cfs for c in network.catchments)
    total_pipe_length = sum(p.length_ft for p in network.pipes)
    total_capacity = sum(p.hydraulic.full_capacity_cfs for p in network.pipes)
    deficient = sum(1 for p in network.pipes if p.hydraulic.capacity_status == CapacityStatus.DEFICIENT.value)

    return {
        "node_count": len(network.nodes),
        "inlet_count": len(network.inlets),
        "basin_count": len(network.basins),
        "pipe_count": len(network.pipes),
        "catchment_count": len(network.catchments),
        "flow_path_count": len(network.flow_paths),
        "total_runoff_cfs": round(total_runoff, 3),
        "total_pipe_length_ft": round(total_pipe_length, 3),
        "total_pipe_capacity_cfs": round(total_capacity, 3),
        "deficient_pipe_count": deficient,
        "warning_count": (
            len(network.warnings)
            + sum(len(x.warnings) for x in network.catchments)
            + sum(len(x.warnings) for x in network.inlets)
            + sum(len(x.warnings) for x in network.nodes)
            + sum(len(x.warnings) for x in network.pipes)
            + sum(len(x.warnings) for x in network.basins)
            + sum(len(x.warnings) for x in network.flow_paths)
        ),
    }
