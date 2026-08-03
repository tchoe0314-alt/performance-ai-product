from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re
from statistics import fmean, pvariance
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .common import safe_dict, safe_float, safe_list, safe_str
from .vision_public_bootstrap import now_iso, stable_fingerprint, verify_public_review_sprint


AI_TRIAGE_VERSION = "civora_public_vision_ai_triage_v1"
AI_TRIAGE_OVERRIDE_VERSION = "civora_public_vision_ai_triage_overrides_v1"
AI_RECOMMENDATIONS = {"likely_accept", "likely_reject", "redraw_or_human_review"}
AI_REVIEW_PRIORITIES = {"low", "medium", "high"}
MAX_REGISTERED_IMAGE_DIMENSION = 8192
MAX_REGISTERED_IMAGE_PIXELS = 64 * 1024 * 1024


def build_ai_assisted_vision_triage(
    review_sprint: Dict[str, Any],
    *,
    image_root: Path,
    crop_root: Path,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    sprint_validation = verify_public_review_sprint(review_sprint)
    if not sprint_validation["valid"]:
        raise ValueError("Review sprint failed verification: " + ", ".join(sprint_validation["blockers"]))
    image_root = image_root.expanduser().resolve()
    crop_root = crop_root.expanduser().resolve()
    crop_root.mkdir(parents=True, exist_ok=True)
    meta = safe_dict(review_sprint.get("meta"))
    vision_report = safe_dict(meta.get("civora_vision_detection_report_v2"))
    frames = [safe_dict(item) for item in safe_list(vision_report.get("imagery_frames")) if safe_dict(item)]
    frame_by_id = {safe_str(item.get("frame_id")): item for item in frames if safe_str(item.get("frame_id"))}
    inbox = safe_dict(meta.get("candidate_review_inbox_v1"))
    candidates = [safe_dict(item) for item in safe_list(inbox.get("candidates")) if safe_dict(item)]
    override_by_id = _validate_overrides(overrides or {}, candidates=candidates)
    image_cache: Dict[str, Image.Image] = {}
    recommendations: List[Dict[str, Any]] = []
    try:
        for sequence, candidate in enumerate(candidates, start=1):
            source_record = safe_dict(candidate.get("source_record"))
            properties = safe_dict(source_record.get("properties"))
            candidate_id = safe_str(candidate.get("candidate_id"))
            frame_id = safe_str(properties.get("imagery_frame_id"))
            frame = frame_by_id.get(frame_id)
            if not candidate_id or frame is None:
                raise ValueError(f"Candidate is missing its registered imagery frame: {candidate_id or 'unknown'}")
            image = image_cache.get(frame_id)
            if image is None:
                image = _load_registered_image(frame, image_root=image_root)
                image_cache[frame_id] = image
            points = _polygon_points(safe_dict(properties.get("pixel_geometry")))
            if len(points) < 4:
                raise ValueError(f"Candidate pixel geometry is invalid: {candidate_id}")
            _validate_polygon_points(points, image_size=image.size, candidate_id=candidate_id)
            metrics = _visual_metrics(image, points)
            recommendation = _recommendation(candidate, metrics)
            override = override_by_id.get(candidate_id)
            if override:
                recommendation = _apply_override(recommendation, override)
            crop_name = f"{sequence:04d}-{_safe_file_token(candidate_id)}.png"
            crop_path = crop_root / crop_name
            _render_evidence_crop(
                image,
                points,
                crop_path,
                candidate_id=candidate_id,
                recommendation=safe_str(recommendation.get("recommended_action")),
            )
            recommendations.append(
                {
                    "sequence": sequence,
                    "candidate_id": candidate_id,
                    "imagery_frame_id": frame_id,
                    "geography_id": safe_str(frame.get("geography_id")),
                    "source_capture_date": safe_str(frame.get("captured_at")),
                    "source_season": safe_str(frame.get("season")),
                    "imagery_quality_band": safe_str(frame.get("imagery_quality_band")),
                    "source_confidence": round(safe_float(candidate.get("confidence")), 4),
                    "recommended_action": safe_str(recommendation.get("recommended_action")),
                    "recommendation_confidence": round(safe_float(recommendation.get("confidence")), 4),
                    "review_priority": safe_str(recommendation.get("review_priority")),
                    "reason_codes": list(recommendation.get("reason_codes") or []),
                    "visual_metrics": metrics,
                    "evidence_crop": {
                        "file_name": crop_name,
                        "sha256": _file_sha256(crop_path),
                    },
                    "override_applied": bool(override),
                    "ground_truth_eligible": False,
                    "human_review_required": True,
                }
            )
    finally:
        for image in image_cache.values():
            image.close()
    recommendation_counts = Counter(item["recommended_action"] for item in recommendations)
    priority_counts = Counter(item["review_priority"] for item in recommendations)
    override_count = sum(1 for item in recommendations if item["override_applied"])
    payload: Dict[str, Any] = {
        "version": AI_TRIAGE_VERSION,
        "created_at": now_iso(),
        "source_review_sprint_fingerprint": safe_str(review_sprint.get("review_sprint_fingerprint")),
        "source_dataset_fingerprint": safe_str(review_sprint.get("source_dataset_fingerprint")),
        "assistant_id": "civora_ai_review_assist",
        "reviewer_type": "ai_assisted_non_human",
        "candidate_count": len(recommendations),
        "override_count": override_count,
        "recommendation_counts": dict(sorted(recommendation_counts.items())),
        "review_priority_counts": dict(sorted(priority_counts.items())),
        "recommendations": recommendations,
        "human_attestation_present": False,
        "ground_truth_eligible": False,
        "ledger_append_allowed": False,
        "promotion_eligible": False,
        "truth_label": (
            "This artifact is non-human visual triage. It can prioritize review but cannot accept, reject, correct, "
            "or promote ground-truth labels without an independent human source-frame review."
        ),
    }
    payload["triage_fingerprint"] = ai_triage_fingerprint(payload)
    return payload


def verify_ai_assisted_vision_triage(
    triage: Dict[str, Any],
    *,
    review_sprint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rec = safe_dict(triage)
    blockers: List[str] = []
    if safe_str(rec.get("version")) != AI_TRIAGE_VERSION:
        blockers.append("unsupported_ai_triage_version")
    if safe_str(rec.get("reviewer_type")) != "ai_assisted_non_human":
        blockers.append("ai_triage_reviewer_type_mismatch")
    for key in ("human_attestation_present", "ground_truth_eligible", "ledger_append_allowed", "promotion_eligible"):
        if rec.get(key) is not False:
            blockers.append(f"ai_triage_{key}_must_be_false")
    recommendations = [safe_dict(item) for item in safe_list(rec.get("recommendations")) if safe_dict(item)]
    candidate_ids = [safe_str(item.get("candidate_id")) for item in recommendations]
    if len(recommendations) != int(safe_float(rec.get("candidate_count"))):
        blockers.append("ai_triage_candidate_count_mismatch")
    override_count = sum(1 for item in recommendations if item.get("override_applied") is True)
    if override_count != int(safe_float(rec.get("override_count"))):
        blockers.append("ai_triage_override_count_mismatch")
    if any(not item for item in candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
        blockers.append("ai_triage_candidate_ids_missing_or_duplicate")
    if any(safe_str(item.get("recommended_action")) not in AI_RECOMMENDATIONS for item in recommendations):
        blockers.append("ai_triage_recommendation_invalid")
    if any(safe_str(item.get("review_priority")) not in AI_REVIEW_PRIORITIES for item in recommendations):
        blockers.append("ai_triage_review_priority_invalid")
    if any(not 0.0 <= safe_float(item.get("recommendation_confidence")) <= 1.0 for item in recommendations):
        blockers.append("ai_triage_recommendation_confidence_invalid")
    if any(item.get("ground_truth_eligible") is not False for item in recommendations):
        blockers.append("ai_triage_candidate_ground_truth_must_be_false")
    if any(item.get("human_review_required") is not True for item in recommendations):
        blockers.append("ai_triage_candidate_human_review_must_be_true")
    actual_recommendation_counts = dict(sorted(Counter(
        safe_str(item.get("recommended_action")) for item in recommendations
    ).items()))
    if safe_dict(rec.get("recommendation_counts")) != actual_recommendation_counts:
        blockers.append("ai_triage_recommendation_counts_mismatch")
    actual_priority_counts = dict(sorted(Counter(
        safe_str(item.get("review_priority")) for item in recommendations
    ).items()))
    if safe_dict(rec.get("review_priority_counts")) != actual_priority_counts:
        blockers.append("ai_triage_review_priority_counts_mismatch")
    expected_fingerprint = ai_triage_fingerprint(rec)
    if safe_str(rec.get("triage_fingerprint")) != expected_fingerprint:
        blockers.append("ai_triage_fingerprint_mismatch")
    if review_sprint is not None:
        sprint_validation = verify_public_review_sprint(review_sprint)
        if not sprint_validation["valid"]:
            blockers.append("source_review_sprint_invalid")
        elif safe_str(rec.get("source_review_sprint_fingerprint")) != safe_str(
            review_sprint.get("review_sprint_fingerprint")
        ):
            blockers.append("source_review_sprint_fingerprint_mismatch")
        sprint_meta = safe_dict(review_sprint.get("meta"))
        sprint_inbox = safe_dict(sprint_meta.get("candidate_review_inbox_v1"))
        expected_ids = {
            safe_str(safe_dict(item).get("candidate_id"))
            for item in safe_list(sprint_inbox.get("candidates"))
            if safe_str(safe_dict(item).get("candidate_id"))
        }
        if set(candidate_ids) != expected_ids:
            blockers.append("ai_triage_candidate_coverage_mismatch")
    return {
        "valid": not blockers,
        "blockers": sorted(set(blockers)),
        "triage_fingerprint": expected_fingerprint,
        "candidate_count": len(recommendations),
    }


def ai_triage_fingerprint(triage: Dict[str, Any]) -> str:
    rec = safe_dict(triage)
    return stable_fingerprint(
        {
            "version": safe_str(rec.get("version")),
            "created_at": safe_str(rec.get("created_at")),
            "source_review_sprint_fingerprint": safe_str(rec.get("source_review_sprint_fingerprint")),
            "source_dataset_fingerprint": safe_str(rec.get("source_dataset_fingerprint")),
            "assistant_id": safe_str(rec.get("assistant_id")),
            "reviewer_type": safe_str(rec.get("reviewer_type")),
            "candidate_count": int(safe_float(rec.get("candidate_count"))),
            "override_count": int(safe_float(rec.get("override_count"))),
            "recommendation_counts": safe_dict(rec.get("recommendation_counts")),
            "review_priority_counts": safe_dict(rec.get("review_priority_counts")),
            "recommendations": safe_list(rec.get("recommendations")),
            "human_attestation_present": rec.get("human_attestation_present") is True,
            "ground_truth_eligible": rec.get("ground_truth_eligible") is True,
            "ledger_append_allowed": rec.get("ledger_append_allowed") is True,
            "promotion_eligible": rec.get("promotion_eligible") is True,
            "truth_label": safe_str(rec.get("truth_label")),
        }
    )


def render_ai_triage_contact_sheets(
    triage: Dict[str, Any],
    *,
    crop_root: Path,
    output_root: Path,
    columns: int = 4,
    rows: int = 4,
) -> List[str]:
    validation = verify_ai_assisted_vision_triage(triage)
    if not validation["valid"]:
        raise ValueError("AI triage failed verification: " + ", ".join(validation["blockers"]))
    crop_root = crop_root.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    columns = max(1, int(columns))
    rows = max(1, int(rows))
    recommendations = [safe_dict(item) for item in safe_list(triage.get("recommendations")) if safe_dict(item)]
    page_size = columns * rows
    result = []
    for page_index in range(0, len(recommendations), page_size):
        page = recommendations[page_index : page_index + page_size]
        sheet = Image.new("RGB", (columns * 320, rows * 300), "#eef1f2")
        draw = ImageDraw.Draw(sheet)
        for position, item in enumerate(page):
            column = position % columns
            row = position // columns
            x0 = column * 320
            y0 = row * 300
            crop_path = (crop_root / safe_str(safe_dict(item.get("evidence_crop")).get("file_name"))).resolve()
            if crop_root not in crop_path.parents or not crop_path.is_file():
                raise ValueError(f"AI triage evidence crop is missing: {crop_path}")
            with Image.open(crop_path) as crop:
                thumb = ImageOps.contain(crop.convert("RGB"), (304, 246))
            sheet.paste(thumb, (x0 + 8, y0 + 8))
            action = safe_str(item.get("recommended_action"))
            action_color = {
                "likely_accept": "#147d48",
                "likely_reject": "#b42336",
                "redraw_or_human_review": "#8a5b00",
            }.get(action, "#38444b")
            draw.text(
                (x0 + 8, y0 + 258),
                f"{int(safe_float(item.get('sequence'))):03d} · {safe_str(item.get('geography_id'))}",
                fill="#17202a",
            )
            draw.text((x0 + 8, y0 + 276), action, fill=action_color)
        page_number = page_index // page_size + 1
        output = output_root / f"triage-contact-sheet-{page_number:02d}.jpg"
        sheet.save(output, format="JPEG", quality=92, optimize=True)
        result.append(str(output))
    return result


def _validate_overrides(
    overrides: Dict[str, Any],
    *,
    candidates: Sequence[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    if not overrides:
        return {}
    if safe_str(overrides.get("version")) != AI_TRIAGE_OVERRIDE_VERSION:
        raise ValueError("Unsupported AI triage override version.")
    if safe_str(overrides.get("reviewer_type")) != "ai_assisted_non_human":
        raise ValueError("AI triage overrides cannot claim human review.")
    if overrides.get("human_attestation_present") is True or overrides.get("ground_truth_eligible") is True:
        raise ValueError("AI triage overrides cannot include human attestation or ground-truth eligibility.")
    candidate_ids = {safe_str(item.get("candidate_id")) for item in candidates if safe_str(item.get("candidate_id"))}
    rows = [safe_dict(item) for item in safe_list(overrides.get("overrides")) if safe_dict(item)]
    result: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        candidate_id = safe_str(row.get("candidate_id"))
        action = safe_str(row.get("recommended_action"))
        if candidate_id not in candidate_ids:
            raise ValueError(f"AI triage override candidate is outside this sprint: {candidate_id}")
        if candidate_id in result:
            raise ValueError(f"AI triage override candidate is duplicated: {candidate_id}")
        if action not in AI_RECOMMENDATIONS:
            raise ValueError(f"AI triage override recommendation is invalid: {action}")
        priority = safe_str(row.get("review_priority"), "high")
        if priority not in AI_REVIEW_PRIORITIES:
            raise ValueError(f"AI triage override review priority is invalid: {priority}")
        result[candidate_id] = row
    return result


def _apply_override(recommendation: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(recommendation)
    result["recommended_action"] = safe_str(override.get("recommended_action"))
    result["confidence"] = min(max(safe_float(override.get("confidence"), result.get("confidence")), 0.0), 0.95)
    result["review_priority"] = safe_str(override.get("review_priority"), "high")
    reasons = [safe_str(item) for item in safe_list(override.get("reason_codes")) if safe_str(item)]
    result["reason_codes"] = reasons or ["ai_visual_inspection_override"]
    return result


def _recommendation(candidate: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    source_confidence = safe_float(candidate.get("confidence"))
    area = safe_float(metrics.get("polygon_area_pixels"))
    minimum_dimension = min(safe_float(metrics.get("bbox_width_pixels")), safe_float(metrics.get("bbox_height_pixels")))
    contrast = safe_float(metrics.get("inside_context_contrast"))
    edge_density = safe_float(metrics.get("inside_edge_density"))
    rectangularity = safe_float(metrics.get("rectangularity"))
    aspect_ratio = safe_float(metrics.get("aspect_ratio"), 1.0)
    if metrics.get("touches_frame_edge") is True:
        return {
            "recommended_action": "redraw_or_human_review",
            "confidence": 0.86,
            "review_priority": "high",
            "reason_codes": ["proposal_touches_frame_edge", "possible_clipped_building_outline"],
        }
    if area < 16 or minimum_dimension < 3:
        return {
            "recommended_action": "redraw_or_human_review",
            "confidence": 0.82,
            "review_priority": "high",
            "reason_codes": ["proposal_too_small_for_reliable_visual_triage"],
        }
    if area < 90 or aspect_ratio >= 4.5:
        return {
            "recommended_action": "redraw_or_human_review",
            "confidence": 0.8,
            "review_priority": "high",
            "reason_codes": ["proposal_scale_or_shape_requires_source_frame_review"],
        }
    visual_signal = min(1.0, contrast * 9.0 + edge_density * 2.2 + rectangularity * 0.25)
    if source_confidence >= 0.6 and visual_signal >= 0.32 and minimum_dimension >= 5:
        return {
            "recommended_action": "likely_accept",
            "confidence": round(min(0.93, 0.58 + visual_signal * 0.28), 4),
            "review_priority": "low" if visual_signal >= 0.55 else "medium",
            "reason_codes": ["source_proposal_confident", "visible_roof_or_structure_signal_present"],
        }
    if source_confidence <= 0.1 and visual_signal < 0.15:
        return {
            "recommended_action": "likely_reject",
            "confidence": round(min(0.72, 0.52 + (0.15 - visual_signal)), 4),
            "review_priority": "high",
            "reason_codes": ["source_proposal_low_confidence", "weak_visible_structure_signal"],
        }
    return {
        "recommended_action": "redraw_or_human_review",
        "confidence": 0.68,
        "review_priority": "high" if source_confidence < 0.5 else "medium",
        "reason_codes": ["visual_match_ambiguous", "human_source_frame_review_required"],
    }


def _load_registered_image(frame: Dict[str, Any], *, image_root: Path) -> Image.Image:
    asset = safe_dict(frame.get("source_asset"))
    relative_name = safe_str(asset.get("file_name"))
    image_path = (image_root / relative_name).resolve()
    if image_root not in image_path.parents or not image_path.is_file():
        raise ValueError(f"Registered AI triage image is missing or escaped its root: {image_path}")
    if _file_sha256(image_path) != safe_str(asset.get("sha256")):
        raise ValueError(f"Registered AI triage image fingerprint mismatch: {relative_name}")
    with Image.open(image_path) as image:
        width, height = image.size
        if (
            width <= 0
            or height <= 0
            or width > MAX_REGISTERED_IMAGE_DIMENSION
            or height > MAX_REGISTERED_IMAGE_DIMENSION
            or width * height > MAX_REGISTERED_IMAGE_PIXELS
        ):
            raise ValueError(f"Registered AI triage image dimensions are unsupported: {relative_name}")
        return image.convert("RGB")


def _visual_metrics(image: Image.Image, points: Sequence[Tuple[float, float]]) -> Dict[str, Any]:
    width, height = image.size
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    west = max(0, int(min(xs)))
    north = max(0, int(min(ys)))
    east = min(width, int(max(xs) + 1))
    south = min(height, int(max(ys) + 1))
    bbox_width = max(1, east - west)
    bbox_height = max(1, south - north)
    polygon_area = abs(_signed_area(points))
    rectangularity = min(1.0, polygon_area / max(1.0, bbox_width * bbox_height))
    context_margin = max(8, int(max(bbox_width, bbox_height) * 0.65))
    context_box = (
        max(0, west - context_margin),
        max(0, north - context_margin),
        min(width, east + context_margin),
        min(height, south + context_margin),
    )
    context_image = image.crop(context_box)
    context_width, context_height = context_image.size
    local_points = [(point[0] - context_box[0], point[1] - context_box[1]) for point in points]
    mask = Image.new("L", context_image.size, 0)
    ImageDraw.Draw(mask).polygon(local_points, fill=255)
    grayscale = ImageOps.grayscale(context_image)
    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    gray_values = list(grayscale.getdata())
    edge_values = list(edges.getdata())
    mask_values = list(mask.getdata())
    inside_indexes = [index for index, value in enumerate(mask_values) if value > 0]
    context_indexes = [index for index, value in enumerate(mask_values) if value == 0]
    inside_gray = [gray_values[index] for index in inside_indexes]
    context_gray = [gray_values[index] for index in context_indexes]
    inside_edges = [edge_values[index] for index in inside_indexes]
    inside_mean = fmean(inside_gray) if inside_gray else 0.0
    context_mean = fmean(context_gray) if context_gray else inside_mean
    return {
        "polygon_area_pixels": round(polygon_area, 4),
        "bbox_width_pixels": bbox_width,
        "bbox_height_pixels": bbox_height,
        "rectangularity": round(rectangularity, 4),
        "aspect_ratio": round(max(bbox_width, bbox_height) / max(1, min(bbox_width, bbox_height)), 4),
        "inside_context_contrast": round(abs(inside_mean - context_mean) / 255.0, 4),
        "inside_intensity_variance": round(pvariance(inside_gray) / (255.0 * 255.0), 4) if len(inside_gray) > 1 else 0.0,
        "inside_edge_density": round(
            sum(value >= 35 for value in inside_edges) / max(1, len(inside_edges)),
            4,
        ),
        "touches_frame_edge": west <= 2 or north <= 2 or east >= width - 2 or south >= height - 2,
        "frame_width_pixels": width,
        "frame_height_pixels": height,
        "context_width_pixels": context_width,
        "context_height_pixels": context_height,
    }


def _render_evidence_crop(
    image: Image.Image,
    points: Sequence[Tuple[float, float]],
    output: Path,
    *,
    candidate_id: str,
    recommendation: str,
) -> None:
    width, height = image.size
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    bbox_width = max(1.0, max(xs) - min(xs))
    bbox_height = max(1.0, max(ys) - min(ys))
    margin = max(28, int(max(bbox_width, bbox_height) * 1.25))
    crop_box = (
        max(0, int(min(xs)) - margin),
        max(0, int(min(ys)) - margin),
        min(width, int(max(xs)) + margin + 1),
        min(height, int(max(ys)) + margin + 1),
    )
    crop = image.crop(crop_box).convert("RGBA")
    overlay = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    local_points = [(point[0] - crop_box[0], point[1] - crop_box[1]) for point in points]
    draw = ImageDraw.Draw(overlay)
    draw.polygon(local_points, fill=(0, 163, 255, 34), outline=(0, 163, 255, 255), width=3)
    draw.line(local_points, fill=(0, 163, 255, 255), width=3, joint="curve")
    crop = Image.alpha_composite(crop, overlay).convert("RGB")
    header = Image.new("RGB", (crop.width, 34), "#17202a")
    ImageDraw.Draw(header).text((8, 9), f"{candidate_id} · {recommendation}", fill="white")
    result = Image.new("RGB", (crop.width, crop.height + header.height), "white")
    result.paste(header, (0, 0))
    result.paste(crop, (0, header.height))
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, format="PNG", optimize=True)


def _polygon_points(geometry: Dict[str, Any]) -> List[Tuple[float, float]]:
    if safe_str(geometry.get("type")) != "Polygon":
        return []
    rings = safe_list(geometry.get("coordinates"))
    ring = safe_list(rings[0]) if rings else []
    result = []
    for point in ring:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            result.append((safe_float(point[0]), safe_float(point[1])))
    return result


def _validate_polygon_points(
    points: Sequence[Tuple[float, float]],
    *,
    image_size: Tuple[int, int],
    candidate_id: str,
) -> None:
    if any(not math.isfinite(value) for point in points for value in point):
        raise ValueError(f"Candidate pixel geometry contains non-finite coordinates: {candidate_id}")
    width, height = image_size
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    if max(xs) < 0 or max(ys) < 0 or min(xs) >= width or min(ys) >= height:
        raise ValueError(f"Candidate pixel geometry does not intersect its registered image: {candidate_id}")


def _safe_file_token(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_str(value)).strip("._-")
    short = normalized[:72] or "candidate"
    digest = hashlib.sha256(safe_str(value).encode("utf-8")).hexdigest()[:10]
    return f"{short}-{digest}"


def _signed_area(points: Sequence[Tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    return sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    ) / 2.0


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "AI_RECOMMENDATIONS",
    "AI_TRIAGE_OVERRIDE_VERSION",
    "AI_TRIAGE_VERSION",
    "ai_triage_fingerprint",
    "build_ai_assisted_vision_triage",
    "render_ai_triage_contact_sheets",
    "verify_ai_assisted_vision_triage",
]
