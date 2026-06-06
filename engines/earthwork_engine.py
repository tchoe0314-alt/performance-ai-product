# engines/earthwork_engine.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .surface_engine import GridSurface


Number = float


@dataclass
class EarthworkCellResult:
    row: int
    col: int
    existing_elev: float
    proposed_elev: float
    delta_z: float
    cell_area: float
    raw_volume_cf: float
    classification: str  # "cut" | "fill" | "neutral"


@dataclass
class EarthworkComputationResult:
    success: bool
    message: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "issues": list(self.issues),
            "assumptions": list(self.assumptions),
            "metadata": dict(self.metadata),
            "results": dict(self.results),
        }


def _new_result() -> EarthworkComputationResult:
    return EarthworkComputationResult(
        success=False,
        message="Earthwork computation not started.",
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _safe_float(value: Any) -> float:
    return float(value)


def _validate_surface_object(
    surface: Any,
    name: str,
    result: EarthworkComputationResult,
) -> bool:
    if surface is None:
        result.errors.append(f"{name} surface is required.")
        return False

    required_attrs = ("nrows", "ncols", "cell_size", "values")
    missing = [attr for attr in required_attrs if not hasattr(surface, attr)]
    if missing:
        result.errors.append(
            f"{name} surface is missing required attributes: {', '.join(missing)}."
        )
        return False

    ok = True

    if not _is_number(surface.nrows) or int(surface.nrows) <= 0:
        result.errors.append(f"{name}.nrows must be a positive integer-like value.")
        ok = False

    if not _is_number(surface.ncols) or int(surface.ncols) <= 0:
        result.errors.append(f"{name}.ncols must be a positive integer-like value.")
        ok = False

    if not _is_number(surface.cell_size) or float(surface.cell_size) <= 0.0:
        result.errors.append(f"{name}.cell_size must be a positive number.")
        ok = False

    if not isinstance(surface.values, Sequence):
        result.errors.append(f"{name}.values must be a row-major sequence.")
        ok = False

    if not ok:
        return False

    nrows = int(surface.nrows)
    ncols = int(surface.ncols)

    if len(surface.values) != nrows:
        result.errors.append(
            f"{name}.values row count ({len(surface.values)}) does not match nrows ({nrows})."
        )
        ok = False
    else:
        for r, row in enumerate(surface.values):
            if not isinstance(row, Sequence):
                result.errors.append(f"{name}.values[{r}] must be a sequence.")
                ok = False
                continue

            if len(row) != ncols:
                result.errors.append(
                    f"{name}.values[{r}] column count ({len(row)}) does not match ncols ({ncols})."
                )
                ok = False
                continue

            for c, value in enumerate(row):
                if value is None:
                    result.errors.append(
                        f"{name}.values[{r}][{c}] is None. Surface elevations must be numeric."
                    )
                    ok = False
                elif not _is_number(value):
                    result.errors.append(
                        f"{name}.values[{r}][{c}] must be numeric, got {type(value).__name__}."
                    )
                    ok = False

    return ok


def _validate_compatible_surfaces(
    existing: GridSurface,
    proposed: GridSurface,
    *,
    tolerance: float = 1e-9,
) -> None:
    if existing.nrows != proposed.nrows:
        raise ValueError("Existing and proposed surfaces must have the same number of rows.")

    if existing.ncols != proposed.ncols:
        raise ValueError("Existing and proposed surfaces must have the same number of columns.")

    if abs(existing.cell_size - proposed.cell_size) > tolerance:
        raise ValueError("Existing and proposed surfaces must have the same cell size.")


def validate_compatible_surfaces(
    existing: GridSurface,
    proposed: GridSurface,
    *,
    mode: str = "strict",
    tolerance: float = 1e-9,
) -> Dict[str, Any]:
    result = _new_result()
    normalized_mode = _normalize_mode(mode, result)
    if normalized_mode is None:
        result.message = "Surface compatibility validation failed."
        return result.to_dict()

    existing_ok = _validate_surface_object(existing, "existing", result)
    proposed_ok = _validate_surface_object(proposed, "proposed", result)

    if not existing_ok or not proposed_ok:
        result.message = "Surface compatibility validation failed."
        return result.to_dict()

    if int(existing.nrows) != int(proposed.nrows):
        result.errors.append(
            f"Row count mismatch: existing={existing.nrows}, proposed={proposed.nrows}."
        )

    if int(existing.ncols) != int(proposed.ncols):
        result.errors.append(
            f"Column count mismatch: existing={existing.ncols}, proposed={proposed.ncols}."
        )

    cell_size_diff = abs(float(existing.cell_size) - float(proposed.cell_size))
    if cell_size_diff > tolerance:
        result.errors.append(
            "Cell size mismatch exceeds tolerance: "
            f"existing={existing.cell_size}, proposed={proposed.cell_size}, "
            f"tolerance={tolerance}."
        )

    if result.errors:
        result.message = "Surface compatibility validation failed."
        result.metadata = {
            "mode": normalized_mode,
            "tolerance": tolerance,
            "existing_shape": [int(existing.nrows), int(existing.ncols)],
            "proposed_shape": [int(proposed.nrows), int(proposed.ncols)],
            "existing_cell_size": float(existing.cell_size),
            "proposed_cell_size": float(proposed.cell_size),
        }
        return result.to_dict()

    result.success = True
    result.message = "Surface compatibility validation passed."
    result.metadata = {
        "mode": normalized_mode,
        "tolerance": tolerance,
        "shape": [int(existing.nrows), int(existing.ncols)],
        "cell_size": float(existing.cell_size),
    }
    return result.to_dict()


def _normalize_mode(
    mode: str,
    result: EarthworkComputationResult,
) -> Optional[str]:
    if not isinstance(mode, str):
        result.errors.append("Mode must be a string: 'strict' or 'assisted'.")
        return None

    normalized = mode.strip().lower()
    if normalized not in {"strict", "assisted"}:
        result.errors.append("Mode must be either 'strict' or 'assisted'.")
        return None
    return normalized


def _sanitize_optional_numeric(
    value: Any,
    *,
    field_name: str,
    mode: str,
    result: EarthworkComputationResult,
    default: Optional[float] = None,
    minimum: Optional[float] = None,
) -> Optional[float]:
    if value is None:
        if default is not None:
            if mode == "assisted":
                result.assumptions.append(
                    f"{field_name} not provided; assumed default value {default}."
                )
            return float(default)
        return None

    if not _is_number(value):
        result.errors.append(f"{field_name} must be numeric.")
        return None

    numeric = float(value)
    if minimum is not None and numeric < minimum:
        result.errors.append(f"{field_name} must be >= {minimum}.")
        return None

    return numeric


def _surface_elevation_extents(surface: GridSurface) -> Tuple[float, float]:
    min_z = float("inf")
    max_z = float("-inf")

    for row in surface.values:
        for value in row:
            z = float(value)
            if z < min_z:
                min_z = z
            if z > max_z:
                max_z = z

    return min_z, max_z


def _build_cell_results(
    existing: GridSurface,
    proposed: GridSurface,
    *,
    strip_depth_ft: float,
    neutral_tolerance_ft: float,
) -> List[EarthworkCellResult]:
    nrows = int(existing.nrows)
    ncols = int(existing.ncols)
    cell_area = float(existing.cell_size) * float(existing.cell_size)

    cells: List[EarthworkCellResult] = []

    for row in range(nrows):
        for col in range(ncols):
            ex = float(existing.values[row][col])
            pr = float(proposed.values[row][col])

            adjusted_existing = ex - strip_depth_ft
            delta_z = pr - adjusted_existing
            raw_volume_cf = delta_z * cell_area

            if abs(delta_z) <= neutral_tolerance_ft:
                classification = "neutral"
            elif raw_volume_cf > 0.0:
                classification = "fill"
            else:
                classification = "cut"

            cells.append(
                EarthworkCellResult(
                    row=row,
                    col=col,
                    existing_elev=ex,
                    proposed_elev=pr,
                    delta_z=delta_z,
                    cell_area=cell_area,
                    raw_volume_cf=raw_volume_cf,
                    classification=classification,
                )
            )

    return cells


def _summarize_cells(
    cells: Sequence[EarthworkCellResult],
    *,
    shrink_factor: float,
    swell_factor: float,
    topsoil_shrink_factor: float,
    strip_depth_ft: float,
) -> Dict[str, Any]:
    cut_cf = 0.0
    fill_cf = 0.0
    stripped_volume_cf = 0.0

    cut_cells = 0
    fill_cells = 0
    neutral_cells = 0

    max_cut_depth_ft = 0.0
    max_fill_depth_ft = 0.0

    for cell in cells:
        stripped_volume_cf += strip_depth_ft * cell.cell_area

        if cell.classification == "cut":
            cell_cut = -cell.raw_volume_cf
            cut_cf += cell_cut
            cut_cells += 1
            if -cell.delta_z > max_cut_depth_ft:
                max_cut_depth_ft = -cell.delta_z

        elif cell.classification == "fill":
            cell_fill = cell.raw_volume_cf
            fill_cf += cell_fill
            fill_cells += 1
            if cell.delta_z > max_fill_depth_ft:
                max_fill_depth_ft = cell.delta_z

        else:
            neutral_cells += 1

    cut_cy = cut_cf / 27.0
    fill_cy = fill_cf / 27.0
    stripped_volume_cy = stripped_volume_cf / 27.0

    adjusted_cut_available_cf = cut_cf * swell_factor
    adjusted_cut_available_cy = adjusted_cut_available_cf / 27.0

    adjusted_fill_required_cf = fill_cf * shrink_factor
    adjusted_fill_required_cy = adjusted_fill_required_cf / 27.0

    topsoil_loss_cf = stripped_volume_cf * topsoil_shrink_factor
    topsoil_loss_cy = topsoil_loss_cf / 27.0

    net_cf = fill_cf - cut_cf
    net_cy = net_cf / 27.0

    adjusted_net_cf = adjusted_fill_required_cf - adjusted_cut_available_cf
    adjusted_net_cy = adjusted_net_cf / 27.0

    if adjusted_net_cf > 1e-9:
        balance_status = "borrow_required"
        import_required_cf = adjusted_net_cf
        export_surplus_cf = 0.0
    elif adjusted_net_cf < -1e-9:
        balance_status = "export_required"
        import_required_cf = 0.0
        export_surplus_cf = -adjusted_net_cf
    else:
        balance_status = "balanced"
        import_required_cf = 0.0
        export_surplus_cf = 0.0

    import_required_cy = import_required_cf / 27.0
    export_surplus_cy = export_surplus_cf / 27.0

    return {
        "cut_cf": cut_cf,
        "fill_cf": fill_cf,
        "net_cf": net_cf,
        "cut_cy": cut_cy,
        "fill_cy": fill_cy,
        "net_cy": net_cy,
        "stripped_volume_cf": stripped_volume_cf,
        "stripped_volume_cy": stripped_volume_cy,
        "topsoil_loss_cf": topsoil_loss_cf,
        "topsoil_loss_cy": topsoil_loss_cy,
        "adjusted_cut_available_cf": adjusted_cut_available_cf,
        "adjusted_cut_available_cy": adjusted_cut_available_cy,
        "adjusted_fill_required_cf": adjusted_fill_required_cf,
        "adjusted_fill_required_cy": adjusted_fill_required_cy,
        "adjusted_net_cf": adjusted_net_cf,
        "adjusted_net_cy": adjusted_net_cy,
        "import_required_cf": import_required_cf,
        "import_required_cy": import_required_cy,
        "export_surplus_cf": export_surplus_cf,
        "export_surplus_cy": export_surplus_cy,
        "balance_status": balance_status,
        "cut_cells": cut_cells,
        "fill_cells": fill_cells,
        "neutral_cells": neutral_cells,
        "max_cut_depth_ft": max_cut_depth_ft,
        "max_fill_depth_ft": max_fill_depth_ft,
    }


def _build_volume_maps(
    cells: Sequence[EarthworkCellResult],
    nrows: int,
    ncols: int,
) -> Dict[str, List[List[float]]]:
    cut_map_cf: List[List[float]] = [[0.0 for _ in range(ncols)] for _ in range(nrows)]
    fill_map_cf: List[List[float]] = [[0.0 for _ in range(ncols)] for _ in range(nrows)]
    net_map_cf: List[List[float]] = [[0.0 for _ in range(ncols)] for _ in range(nrows)]
    delta_map_ft: List[List[float]] = [[0.0 for _ in range(ncols)] for _ in range(nrows)]

    for cell in cells:
        net_map_cf[cell.row][cell.col] = cell.raw_volume_cf
        delta_map_ft[cell.row][cell.col] = cell.delta_z

        if cell.classification == "cut":
            cut_map_cf[cell.row][cell.col] = -cell.raw_volume_cf
        elif cell.classification == "fill":
            fill_map_cf[cell.row][cell.col] = cell.raw_volume_cf

    return {
        "cut_map_cf": cut_map_cf,
        "fill_map_cf": fill_map_cf,
        "net_map_cf": net_map_cf,
        "delta_z_map_ft": delta_map_ft,
    }


def _build_cell_statistics(
    cells: Sequence[EarthworkCellResult],
) -> Dict[str, Any]:
    if not cells:
        return {
            "cell_count": 0,
            "mean_delta_z_ft": 0.0,
            "min_delta_z_ft": 0.0,
            "max_delta_z_ft": 0.0,
            "mean_abs_delta_z_ft": 0.0,
        }

    deltas = [cell.delta_z for cell in cells]
    abs_deltas = [abs(cell.delta_z) for cell in cells]

    return {
        "cell_count": len(cells),
        "mean_delta_z_ft": sum(deltas) / len(deltas),
        "min_delta_z_ft": min(deltas),
        "max_delta_z_ft": max(deltas),
        "mean_abs_delta_z_ft": sum(abs_deltas) / len(abs_deltas),
    }


def _build_mass_balance_validation(summary: Dict[str, Any], *, tolerance_cf: float) -> Dict[str, Any]:
    adjusted_cut = float(summary.get("adjusted_cut_available_cf", 0.0))
    adjusted_fill = float(summary.get("adjusted_fill_required_cf", 0.0))
    adjusted_net = float(summary.get("adjusted_net_cf", 0.0))
    denominator = max(adjusted_cut, adjusted_fill, 1.0)
    imbalance_ratio = abs(adjusted_net) / denominator
    return {
        "valid": abs(adjusted_net) <= max(0.0, tolerance_cf),
        "status": summary.get("balance_status", "unknown"),
        "adjusted_net_cf": adjusted_net,
        "adjusted_net_cy": float(summary.get("adjusted_net_cy", 0.0)),
        "imbalance_ratio": imbalance_ratio,
        "tolerance_cf": max(0.0, tolerance_cf),
        "requires_import_cf": float(summary.get("import_required_cf", 0.0)),
        "requires_export_cf": float(summary.get("export_surplus_cf", 0.0)),
        "truth_label": "Mass balance uses shrink/swell adjusted cut availability and compacted fill demand.",
    }


def _build_haul_balance(summary: Dict[str, Any], *, average_haul_distance_ft: float) -> Dict[str, Any]:
    adjusted_cut_cf = float(summary.get("adjusted_cut_available_cf", 0.0))
    adjusted_fill_cf = float(summary.get("adjusted_fill_required_cf", 0.0))
    onsite_reuse_cf = min(adjusted_cut_cf, adjusted_fill_cf)
    import_required_cf = float(summary.get("import_required_cf", 0.0))
    export_surplus_cf = float(summary.get("export_surplus_cf", 0.0))
    haul_distance = max(0.0, average_haul_distance_ft)
    return {
        "balance_status": summary.get("balance_status", "unknown"),
        "onsite_reuse_cf": onsite_reuse_cf,
        "onsite_reuse_cy": onsite_reuse_cf / 27.0,
        "import_required_cf": import_required_cf,
        "import_required_cy": import_required_cf / 27.0,
        "export_surplus_cf": export_surplus_cf,
        "export_surplus_cy": export_surplus_cf / 27.0,
        "adjusted_net_cf": float(summary.get("adjusted_net_cf", 0.0)),
        "adjusted_net_cy": float(summary.get("adjusted_net_cy", 0.0)),
        "average_haul_distance_ft": haul_distance,
        "onsite_haul_cy_ft": (onsite_reuse_cf / 27.0) * haul_distance,
        "requires_offsite_haul": import_required_cf > 0.0 or export_surplus_cf > 0.0,
        "truth_label": "Haul balance is derived from shrink/swell adjusted onsite reuse, import, and export volumes.",
    }


def compute_earthwork(
    existing: GridSurface,
    proposed: GridSurface,
    *,
    mode: str = "strict",
    shrink_factor: Optional[float] = 1.0,
    swell_factor: Optional[float] = 1.0,
    strip_depth_ft: Optional[float] = 0.0,
    topsoil_shrink_factor: Optional[float] = 1.0,
    neutral_tolerance_ft: Optional[float] = 0.000001,
    average_haul_distance_ft: Optional[float] = None,
    include_cell_maps: bool = True,
    include_cell_details: bool = False,
    use_surface_model: Optional[bool] = None,
    use_grading_model: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Production-oriented earthwork computation between existing and proposed grid surfaces.

    Engineering notes:
    - Positive delta_z means proposed is above adjusted existing surface -> fill.
    - Negative delta_z means proposed is below adjusted existing surface -> cut.
    - strip_depth_ft lowers the effective existing grade before comparison,
      representing topsoil stripping or unsuitable material removal.
    - shrink_factor adjusts compacted fill demand.
    - swell_factor adjusts excavated cut availability.
    - topsoil_shrink_factor provides optional bookkeeping for stripped material loss.

    Returns a structured result with validation, warnings, issues, assumptions, metadata, and results.
    """
    result = _new_result()
    normalized_mode = _normalize_mode(mode, result)
    if normalized_mode is None:
        result.message = "Earthwork computation failed."
        return result.to_dict()

    existing_ok = _validate_surface_object(existing, "existing", result)
    proposed_ok = _validate_surface_object(proposed, "proposed", result)

    if not existing_ok or not proposed_ok:
        result.message = "Earthwork computation failed during surface validation."
        return result.to_dict()

    tolerance = 1e-9

    if int(existing.nrows) != int(proposed.nrows):
        result.errors.append(
            f"Existing/proposed row mismatch: {existing.nrows} vs {proposed.nrows}."
        )

    if int(existing.ncols) != int(proposed.ncols):
        result.errors.append(
            f"Existing/proposed column mismatch: {existing.ncols} vs {proposed.ncols}."
        )

    if abs(float(existing.cell_size) - float(proposed.cell_size)) > tolerance:
        result.errors.append(
            f"Existing/proposed cell size mismatch: {existing.cell_size} vs {proposed.cell_size}."
        )

    normalized_use_surface_model = use_surface_model
    if normalized_use_surface_model is None:
        normalized_use_surface_model = True
        if normalized_mode == "assisted":
            result.assumptions.append(
                "use_surface_model not provided; assumed True."
            )

    normalized_use_grading_model = use_grading_model
    if normalized_use_grading_model is None:
        normalized_use_grading_model = True
        if normalized_mode == "assisted":
            result.assumptions.append(
                "use_grading_model not provided; assumed True."
            )

    shrink_factor_value = _sanitize_optional_numeric(
        shrink_factor,
        field_name="shrink_factor",
        mode=normalized_mode,
        result=result,
        default=1.0,
        minimum=0.0,
    )
    swell_factor_value = _sanitize_optional_numeric(
        swell_factor,
        field_name="swell_factor",
        mode=normalized_mode,
        result=result,
        default=1.0,
        minimum=0.0,
    )
    strip_depth_value = _sanitize_optional_numeric(
        strip_depth_ft,
        field_name="strip_depth_ft",
        mode=normalized_mode,
        result=result,
        default=0.0,
        minimum=0.0,
    )
    topsoil_shrink_factor_value = _sanitize_optional_numeric(
        topsoil_shrink_factor,
        field_name="topsoil_shrink_factor",
        mode=normalized_mode,
        result=result,
        default=1.0,
        minimum=0.0,
    )
    neutral_tolerance_value = _sanitize_optional_numeric(
        neutral_tolerance_ft,
        field_name="neutral_tolerance_ft",
        mode=normalized_mode,
        result=result,
        default=0.000001,
        minimum=0.0,
    )
    average_haul_distance_value = _sanitize_optional_numeric(
        average_haul_distance_ft,
        field_name="average_haul_distance_ft",
        mode=normalized_mode,
        result=result,
        default=0.0,
        minimum=0.0,
    )

    if result.errors:
        result.message = "Earthwork computation failed during validation."
        return result.to_dict()

    assert shrink_factor_value is not None
    assert swell_factor_value is not None
    assert strip_depth_value is not None
    assert topsoil_shrink_factor_value is not None
    assert neutral_tolerance_value is not None
    assert average_haul_distance_value is not None

    if shrink_factor_value == 0.0:
        result.issues.append(
            "shrink_factor is 0.0. Adjusted fill demand will be zero, which is unusual for real projects."
        )

    if swell_factor_value == 0.0:
        result.issues.append(
            "swell_factor is 0.0. Adjusted cut availability will be zero, which is unusual for real projects."
        )

    if strip_depth_value > 2.0:
        result.warnings.append(
            f"strip_depth_ft={strip_depth_value} ft is unusually large for topsoil stripping."
        )

    if shrink_factor_value < 0.8 or shrink_factor_value > 1.3:
        result.warnings.append(
            f"shrink_factor={shrink_factor_value} is outside a typical conceptual range."
        )

    if swell_factor_value < 0.8 or swell_factor_value > 1.5:
        result.warnings.append(
            f"swell_factor={swell_factor_value} is outside a typical conceptual range."
        )

    existing_min, existing_max = _surface_elevation_extents(existing)
    proposed_min, proposed_max = _surface_elevation_extents(proposed)

    if abs(proposed_max - existing_min) > 1000.0 or abs(existing_max - proposed_min) > 1000.0:
        result.warnings.append(
            "Very large elevation range difference detected between existing and proposed surfaces. "
            "Verify vertical datum and units."
        )

    cells = _build_cell_results(
        existing,
        proposed,
        strip_depth_ft=strip_depth_value,
        neutral_tolerance_ft=neutral_tolerance_value,
    )

    summary = _summarize_cells(
        cells,
        shrink_factor=shrink_factor_value,
        swell_factor=swell_factor_value,
        topsoil_shrink_factor=topsoil_shrink_factor_value,
        strip_depth_ft=strip_depth_value,
    )
    mass_balance_tolerance_cf = max(float(existing.cell_size) * float(existing.cell_size), 100.0)
    mass_balance_validation = _build_mass_balance_validation(
        summary,
        tolerance_cf=mass_balance_tolerance_cf,
    )
    haul_balance = _build_haul_balance(summary, average_haul_distance_ft=average_haul_distance_value)

    stats = _build_cell_statistics(cells)

    nrows = int(existing.nrows)
    ncols = int(existing.ncols)
    cell_area = float(existing.cell_size) * float(existing.cell_size)

    volume_maps: Dict[str, Any] = {}
    if include_cell_maps:
        volume_maps = _build_volume_maps(cells, nrows, ncols)

    if summary["cut_cells"] == 0 and summary["fill_cells"] == 0:
        result.issues.append(
            "Existing and proposed surfaces are effectively identical within the neutral tolerance."
        )

    if summary["fill_cells"] > 0 and summary["cut_cells"] == 0:
        result.issues.append(
            "Site is fill-dominant with no cut cells detected."
        )

    if summary["cut_cells"] > 0 and summary["fill_cells"] == 0:
        result.issues.append(
            "Site is cut-dominant with no fill cells detected."
        )
    if haul_balance["balance_status"] in {"borrow_required", "export_required"}:
        result.warnings.append(
            f"Earthwork haul balance is {haul_balance['balance_status']} with adjusted net {haul_balance['adjusted_net_cy']:.3f} cy."
        )

    cell_details: List[Dict[str, Any]] = []
    if include_cell_details:
        cell_details = [
            {
                "row": cell.row,
                "col": cell.col,
                "existing_elev": cell.existing_elev,
                "proposed_elev": cell.proposed_elev,
                "delta_z": cell.delta_z,
                "cell_area": cell.cell_area,
                "raw_volume_cf": cell.raw_volume_cf,
                "classification": cell.classification,
            }
            for cell in cells
        ]

    result.success = True
    result.message = "Earthwork computation completed successfully."
    result.metadata = {
        "mode": normalized_mode,
        "engine": "earthwork_engine",
        "method": "grid_surface_cell_comparison",
        "shape": [nrows, ncols],
        "cell_size": float(existing.cell_size),
        "cell_area": cell_area,
        "cell_count": nrows * ncols,
        "units": {
            "horizontal": "ft",
            "vertical": "ft",
            "area": "sf",
            "volume_primary": "cf",
            "volume_secondary": "cy",
        },
        "parameters": {
            "shrink_factor": shrink_factor_value,
            "swell_factor": swell_factor_value,
            "strip_depth_ft": strip_depth_value,
            "topsoil_shrink_factor": topsoil_shrink_factor_value,
            "neutral_tolerance_ft": neutral_tolerance_value,
            "average_haul_distance_ft": average_haul_distance_value,
            "include_cell_maps": include_cell_maps,
            "include_cell_details": include_cell_details,
            "use_surface_model": normalized_use_surface_model,
            "use_grading_model": normalized_use_grading_model,
        },
        "surface_extents": {
            "existing_min_z": existing_min,
            "existing_max_z": existing_max,
            "proposed_min_z": proposed_min,
            "proposed_max_z": proposed_max,
        },
    }

    result.results = {
        **summary,
        "statistics": stats,
        "mass_balance": {
            "status": summary["balance_status"],
            "adjusted_cut_available_cf": summary["adjusted_cut_available_cf"],
            "adjusted_cut_available_cy": summary["adjusted_cut_available_cy"],
            "adjusted_fill_required_cf": summary["adjusted_fill_required_cf"],
            "adjusted_fill_required_cy": summary["adjusted_fill_required_cy"],
            "adjusted_net_cf": summary["adjusted_net_cf"],
            "adjusted_net_cy": summary["adjusted_net_cy"],
            "import_required_cf": summary["import_required_cf"],
            "import_required_cy": summary["import_required_cy"],
            "export_surplus_cf": summary["export_surplus_cf"],
            "export_surplus_cy": summary["export_surplus_cy"],
            "imbalance_ratio": mass_balance_validation["imbalance_ratio"],
        },
        "mass_balance_validation": mass_balance_validation,
        "haul_balance": haul_balance,
        "volume_maps": volume_maps,
        "cell_details": cell_details,
    }

    return result.to_dict()


def compute_cut_fill(
    existing: GridSurface,
    proposed: GridSurface,
) -> Dict[str, float]:
    """
    Backward-compatible wrapper preserving the original interface.

    Returns:
        cut_cf, fill_cf, net_cf  -> cubic feet
        cut_cy, fill_cy, net_cy  -> cubic yards
    """
    _validate_compatible_surfaces(existing, proposed)

    result = compute_earthwork(
        existing,
        proposed,
        mode="strict",
        shrink_factor=1.0,
        swell_factor=1.0,
        strip_depth_ft=0.0,
        topsoil_shrink_factor=1.0,
        neutral_tolerance_ft=0.000001,
        include_cell_maps=False,
        include_cell_details=False,
        use_surface_model=True,
        use_grading_model=True,
    )

    if not result["success"]:
        errors = result.get("errors", [])
        raise ValueError(
            "Earthwork computation failed: " + ("; ".join(errors) if errors else result["message"])
        )

    values = result["results"]
    return {
        "cut_cf": float(values["cut_cf"]),
        "fill_cf": float(values["fill_cf"]),
        "net_cf": float(values["net_cf"]),
        "cut_cy": float(values["cut_cy"]),
        "fill_cy": float(values["fill_cy"]),
        "net_cy": float(values["net_cy"]),
    }


def compute_cut_fill_detailed(
    existing: GridSurface,
    proposed: GridSurface,
    *,
    mode: str = "strict",
    shrink_factor: Optional[float] = 1.0,
    swell_factor: Optional[float] = 1.0,
    strip_depth_ft: Optional[float] = 0.0,
    topsoil_shrink_factor: Optional[float] = 1.0,
    neutral_tolerance_ft: Optional[float] = 0.000001,
    average_haul_distance_ft: Optional[float] = None,
    include_cell_maps: bool = True,
    include_cell_details: bool = False,
    use_surface_model: Optional[bool] = None,
    use_grading_model: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Detailed earthwork API for orchestrators and future UI/FastAPI usage.
    """
    return compute_earthwork(
        existing,
        proposed,
        mode=mode,
        shrink_factor=shrink_factor,
        swell_factor=swell_factor,
        strip_depth_ft=strip_depth_ft,
        topsoil_shrink_factor=topsoil_shrink_factor,
        neutral_tolerance_ft=neutral_tolerance_ft,
        average_haul_distance_ft=average_haul_distance_ft,
        include_cell_maps=include_cell_maps,
        include_cell_details=include_cell_details,
        use_surface_model=use_surface_model,
        use_grading_model=use_grading_model,
    )
