from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from .common import safe_dict, safe_float, safe_list, safe_str


SHADOW_REPORT_VERSION = "civora_vision_shadow_report_v1"


def build_shadow_comparison_report(
    baseline_detections: Iterable[Dict[str, Any]],
    shadow_detections: Iterable[Dict[str, Any]],
    *,
    baseline_provider: str,
    shadow_model: Dict[str, Any],
    iou_threshold: float = 0.25,
) -> Dict[str, Any]:
    baseline = [safe_dict(item) for item in baseline_detections if safe_dict(item)]
    shadow = [safe_dict(item) for item in shadow_detections if safe_dict(item)]
    matched_baseline: set[int] = set()
    matched_shadow: set[int] = set()
    labels = sorted({_label(item) for item in baseline + shadow if _label(item)})
    per_class: Dict[str, Any] = {}
    for label in labels:
        baseline_indexes = [index for index, item in enumerate(baseline) if _label(item) == label]
        shadow_indexes = [index for index, item in enumerate(shadow) if _label(item) == label]
        matches = _match_indexes(
            baseline,
            shadow,
            baseline_indexes=baseline_indexes,
            shadow_indexes=shadow_indexes,
            iou_threshold=iou_threshold,
        )
        matched_baseline.update(item[0] for item in matches)
        matched_shadow.update(item[1] for item in matches)
        baseline_count = len(baseline_indexes)
        shadow_count = len(shadow_indexes)
        matched_count = len(matches)
        per_class[label] = {
            "baseline_count": baseline_count,
            "shadow_count": shadow_count,
            "matched_count": matched_count,
            "count_delta": shadow_count - baseline_count,
            "agreement_rate": round(matched_count / max(baseline_count, shadow_count, 1), 4),
            "mean_matched_iou": round(sum(item[2] for item in matches) / matched_count, 4) if matches else 0.0,
        }
    matched_count = len(matched_baseline)
    return {
        "version": SHADOW_REPORT_VERSION,
        "status": "ready",
        "baseline_provider": safe_str(baseline_provider, "unknown"),
        "shadow_model": {
            "model_name": safe_str(shadow_model.get("model_name")),
            "model_version": safe_str(shadow_model.get("model_version")),
            "model_sha256": safe_str(shadow_model.get("model_sha256")),
            "promotion_status": safe_str(shadow_model.get("promotion_status"), "candidate_shadow_only"),
        },
        "iou_threshold": round(max(0.0, min(1.0, safe_float(iou_threshold, 0.25))), 4),
        "baseline_count": len(baseline),
        "shadow_count": len(shadow),
        "matched_count": matched_count,
        "agreement_rate": round(matched_count / max(len(baseline), len(shadow), 1), 4),
        "per_class": per_class,
        "influenced_user_candidates": False,
        "contains_shadow_geometry": False,
        "quality_claim_allowed": False,
        "truth_label": (
            "Shadow agreement compares two detectors without ground truth. It cannot establish accuracy and the shadow "
            "output did not alter user-visible candidates."
        ),
    }


def build_shadow_status_report(
    status: str,
    *,
    reason: str = "",
    shadow_model: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    model = safe_dict(shadow_model)
    return {
        "version": SHADOW_REPORT_VERSION,
        "status": safe_str(status, "not_run"),
        "reason": safe_str(reason),
        "shadow_model": {
            "model_name": safe_str(model.get("model_name")),
            "model_version": safe_str(model.get("model_version")),
            "model_sha256": safe_str(model.get("model_sha256")),
            "promotion_status": safe_str(model.get("promotion_status"), "candidate_shadow_only"),
        },
        "influenced_user_candidates": False,
        "contains_shadow_geometry": False,
        "quality_claim_allowed": False,
        "truth_label": "No shadow result changed user-visible detections or created an accuracy claim.",
    }


def _match_indexes(
    baseline: List[Dict[str, Any]],
    shadow: List[Dict[str, Any]],
    *,
    baseline_indexes: List[int],
    shadow_indexes: List[int],
    iou_threshold: float,
) -> List[Tuple[int, int, float]]:
    candidates: List[Tuple[float, int, int]] = []
    for baseline_index in baseline_indexes:
        for shadow_index in shadow_indexes:
            overlap = _bbox_iou(_bbox(baseline[baseline_index]), _bbox(shadow[shadow_index]))
            if overlap >= iou_threshold:
                candidates.append((overlap, baseline_index, shadow_index))
    used_baseline: set[int] = set()
    used_shadow: set[int] = set()
    matches: List[Tuple[int, int, float]] = []
    for overlap, baseline_index, shadow_index in sorted(candidates, reverse=True):
        if baseline_index in used_baseline or shadow_index in used_shadow:
            continue
        used_baseline.add(baseline_index)
        used_shadow.add(shadow_index)
        matches.append((baseline_index, shadow_index, overlap))
    return matches


def _label(item: Dict[str, Any]) -> str:
    return safe_str(item.get("kind") or item.get("feature_type") or item.get("label"))


def _bbox(item: Dict[str, Any]) -> List[float]:
    value = item.get("bbox")
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        try:
            return [float(value[0]), float(value[1]), float(value[2]), float(value[3])]
        except (TypeError, ValueError):
            return []
    geometry = safe_dict(item.get("geometry") or item.get("pixel_geometry"))
    points: List[Tuple[float, float]] = []

    def collect(candidate: Any) -> None:
        if (
            isinstance(candidate, (list, tuple))
            and len(candidate) >= 2
            and isinstance(candidate[0], (int, float))
            and isinstance(candidate[1], (int, float))
        ):
            points.append((float(candidate[0]), float(candidate[1])))
        elif isinstance(candidate, (list, tuple)):
            for child in candidate:
                collect(child)

    collect(geometry.get("coordinates"))
    if not points:
        return []
    x0, x1 = min(point[0] for point in points), max(point[0] for point in points)
    y0, y1 = min(point[1] for point in points), max(point[1] for point in points)
    return [x0, y0, x1 - x0, y1 - y0]


def _bbox_iou(first: List[float], second: List[float]) -> float:
    if len(first) < 4 or len(second) < 4:
        return 0.0
    ax1, ay1, aw, ah = first
    bx1, by1, bw, bh = second
    ax2, ay2 = ax1 + max(0.0, aw), ay1 + max(0.0, ah)
    bx2, by2 = bx1 + max(0.0, bw), by1 + max(0.0, bh)
    intersection_width = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    intersection_height = max(0.0, min(ay2, by2) - max(ay1, by1))
    intersection = intersection_width * intersection_height
    union = max(0.0, aw) * max(0.0, ah) + max(0.0, bw) * max(0.0, bh) - intersection
    return intersection / union if union > 0 else 0.0


__all__ = ["SHADOW_REPORT_VERSION", "build_shadow_comparison_report", "build_shadow_status_report"]
