from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import numpy as np
from PIL import Image


@dataclass
class FeatureDetection:
    kind: str
    bbox: Tuple[float, float, float, float]
    confidence: float
    geometry_type: str
    geometry: List[Tuple[float, float]]


@dataclass
class FeatureDetectionResult:
    success: bool
    message: str
    image_width: int
    image_height: int
    detections: List[FeatureDetection]
    warnings: List[str]
    meta: Dict[str, Any]


class FeatureDetectionEngine:
    """
    First-pass heuristic feature detector for imagery.

    This is intentionally approximate and should be treated as "suggested" only.
    """

    def __init__(self, max_size: int = 512) -> None:
        self.max_size = max(128, int(max_size))

    def detect(self, image_path: str) -> FeatureDetectionResult:
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as exc:
            return FeatureDetectionResult(
                success=False,
                message=f"Unable to open image: {exc}",
                image_width=0,
                image_height=0,
                detections=[],
                warnings=["Image could not be read."],
                meta={},
            )

        width, height = image.size
        scale = min(1.0, float(self.max_size) / max(width, height))
        if scale < 1.0:
            image = image.resize((int(round(width * scale)), int(round(height * scale))), Image.Resampling.BILINEAR)
        resized_width, resized_height = image.size

        arr = np.asarray(image).astype(np.float32)
        if arr.ndim != 3 or arr.shape[2] < 3:
            return FeatureDetectionResult(
                success=False,
                message="Image array format unsupported for detection.",
                image_width=width,
                image_height=height,
                detections=[],
                warnings=["Unsupported image format."],
                meta={},
            )

        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        edge_strength = self._sobel_edges(gray)

        detections: List[FeatureDetection] = []
        warnings: List[str] = [
            "Detected features are approximate and must be confirmed by the user.",
        ]

        total_pixels = gray.size
        min_area = max(40, int(total_pixels * 0.002))
        max_components = 12

        green_mask = (g > r * 1.2) & (g > b * 1.2) & (g > 80)
        blue_mask = (b > r * 1.2) & (b > g * 1.1) & (b > 80)
        light_mask = gray >= 205
        driveway_mask = (gray >= 90) & (gray < 120)

        for kind, mask in (
            ("building", gray < 70),
            ("road", (gray >= 70) & (gray < 130)),
            ("parking", (gray >= 130) & (gray < 205)),
            ("driveway", driveway_mask),
            ("sidewalk", light_mask),
            ("open_space", green_mask),
            ("basin", blue_mask),
            ("pool", blue_mask),
        ):
            # Merge nearby fragments before component extraction so adjacent detections become a single shape.
            if kind in {"road", "parking", "driveway", "sidewalk", "open_space", "building"}:
                mask = self._close_mask(mask, iterations=2 if kind != "building" else 1)
            detections.extend(
                self._components_to_detections(
                    mask=mask,
                    kind=kind,
                    min_area=min_area,
                    max_components=max_components,
                    resized_width=resized_width,
                    resized_height=resized_height,
                    original_width=width,
                    original_height=height,
                    edge_strength=edge_strength,
                )
            )

        detections = self._merge_overlaps(detections)

        if not detections:
            warnings.append("No strong feature regions detected. Try a clearer map or topo image.")

        return FeatureDetectionResult(
            success=True,
            message="Feature detection completed (heuristic).",
            image_width=width,
            image_height=height,
            detections=detections,
            warnings=warnings,
            meta={"scale": scale},
        )

    def _components_to_detections(
        self,
        *,
        mask: np.ndarray,
        kind: str,
        min_area: int,
        max_components: int,
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
        edge_strength: Optional[np.ndarray],
    ) -> List[FeatureDetection]:
        detections: List[FeatureDetection] = []
        visited = np.zeros(mask.shape, dtype=bool)
        height, width = mask.shape
        for y in range(height):
            for x in range(width):
                if not mask[y, x] or visited[y, x]:
                    continue
                stack = [(y, x)]
                visited[y, x] = True
                min_x = max_x = x
                min_y = max_y = y
                count = 0
                component_points: List[Tuple[int, int]] = []
                while stack:
                    cy, cx = stack.pop()
                    count += 1
                    min_x = min(min_x, cx)
                    max_x = max(max_x, cx)
                    min_y = min(min_y, cy)
                    max_y = max(max_y, cy)
                    component_points.append((cx, cy))
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((ny, nx))
                if count < min_area:
                    continue
                component_mask = np.zeros((max_y - min_y + 1, max_x - min_x + 1), dtype=bool)
                for px, py in component_points:
                    component_mask[py - min_y, px - min_x] = True
                bbox = self._scale_bbox(
                    (min_x, min_y, max_x - min_x, max_y - min_y),
                    resized_width,
                    resized_height,
                    original_width,
                    original_height,
                )
                confidence = min(0.6, max(0.2, count / float(mask.size)))
                geometry_type, geometry = self._derive_geometry(
                    kind=kind,
                    points=component_points,
                    component_mask=component_mask,
                    component_offset=(min_x, min_y),
                    resized_width=resized_width,
                    resized_height=resized_height,
                    original_width=original_width,
                    original_height=original_height,
                    edge_strength=edge_strength,
                )
                detections.append(
                    FeatureDetection(
                        kind=kind,
                        bbox=bbox,
                        confidence=confidence,
                        geometry_type=geometry_type,
                        geometry=geometry,
                    )
                )
                if len(detections) >= max_components:
                    return detections
        return detections

    @staticmethod
    def _scale_bbox(
        bbox: Tuple[int, int, int, int],
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
    ) -> Tuple[float, float, float, float]:
        x, y, w, h = bbox
        scale_x = original_width / max(resized_width, 1)
        scale_y = original_height / max(resized_height, 1)
        return (
            round(x * scale_x, 3),
            round(y * scale_y, 3),
            round(w * scale_x, 3),
            round(h * scale_y, 3),
        )

    @staticmethod
    def _scale_points(
        points: List[Tuple[float, float]],
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
    ) -> List[Tuple[float, float]]:
        scale_x = original_width / max(resized_width, 1)
        scale_y = original_height / max(resized_height, 1)
        return [(round(px * scale_x, 3), round(py * scale_y, 3)) for px, py in points]

    @staticmethod
    def _convex_hull(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if len(points) <= 3:
            return points
        pts = sorted(set(points))
        if len(pts) <= 3:
            return pts

        def cross(o: Tuple[int, int], a: Tuple[int, int], b: Tuple[int, int]) -> float:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower: List[Tuple[int, int]] = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        upper: List[Tuple[int, int]] = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        return lower[:-1] + upper[:-1]

    def _derive_geometry(
        self,
        *,
        kind: str,
        points: List[Tuple[int, int]],
        component_mask: Optional[np.ndarray],
        component_offset: Tuple[int, int],
        resized_width: int,
        resized_height: int,
        original_width: int,
        original_height: int,
        edge_strength: Optional[np.ndarray],
    ) -> Tuple[str, List[Tuple[float, float]]]:
        if not points:
            return "rect", []
        line_kinds = {"sidewalk", "path", "road", "driveway"}
        if kind in line_kinds and len(points) >= 2:
            arr = np.asarray(points, dtype=np.float32)
            mean = arr.mean(axis=0)
            centered = arr - mean
            cov = np.cov(centered.T)
            eig_vals, eig_vecs = np.linalg.eig(cov)
            axis = eig_vecs[:, int(np.argmax(eig_vals))]
            projections = centered @ axis
            min_proj = projections.min()
            max_proj = projections.max()
            p1 = mean + min_proj * axis
            p2 = mean + max_proj * axis
            scaled = self._scale_points(
                [(float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))],
                resized_width,
                resized_height,
                original_width,
                original_height,
            )
            return "polyline", scaled

        contour = None
        if component_mask is not None:
            filled = self._fill_holes(component_mask)
            contour = self._trace_contour(filled)
        if contour:
            offset_x, offset_y = component_offset
            shifted = [(pt[0] + offset_x, pt[1] + offset_y) for pt in contour]
            if edge_strength is not None:
                shifted = self._snap_contour_to_edges(
                    shifted,
                    edge_strength,
                    search_radius=2 if kind in {"building"} else 3,
                    min_strength=18.0,
                )
                shifted = self._thin_contour(shifted)
            epsilon = self._adaptive_simplify_epsilon(shifted, kind=kind)
            simplified = self._simplify_path(shifted, epsilon=epsilon)
            if kind == "building":
                simplified = self._orthogonalize_polygon(simplified)
                simplified = self._fit_oriented_rectangle(simplified)
            if len(simplified) >= 3:
                if simplified[0] != simplified[-1]:
                    simplified.append(simplified[0])
                scaled = self._scale_points(simplified, resized_width, resized_height, original_width, original_height)
                return "polygon", scaled

        hull = self._convex_hull(points)
        if len(hull) < 3:
            scaled = self._scale_points(hull, resized_width, resized_height, original_width, original_height)
            return "rect", scaled
        if len(hull) > 64:
            step = max(1, len(hull) // 64)
            hull = hull[::step]
        if hull[0] != hull[-1]:
            hull.append(hull[0])
        scaled = self._scale_points(hull, resized_width, resized_height, original_width, original_height)
        return "polygon", scaled

    @staticmethod
    def _trace_contour(component_mask: np.ndarray) -> List[Tuple[int, int]]:
        height, width = component_mask.shape
        if height == 0 or width == 0:
            return []

        def is_boundary(y: int, x: int) -> bool:
            if not component_mask[y, x]:
                return False
            for ny, nx in (
                (y - 1, x),
                (y + 1, x),
                (y, x - 1),
                (y, x + 1),
            ):
                if ny < 0 or ny >= height or nx < 0 or nx >= width:
                    return True
                if not component_mask[ny, nx]:
                    return True
            return False

        start: Optional[Tuple[int, int]] = None
        for y in range(height):
            for x in range(width):
                if is_boundary(y, x):
                    start = (x, y)
                    break
            if start is not None:
                break
        if start is None:
            return []

        dirs = [
            (1, 0),
            (1, 1),
            (0, 1),
            (-1, 1),
            (-1, 0),
            (-1, -1),
            (0, -1),
            (1, -1),
        ]
        contour: List[Tuple[int, int]] = []
        current = start
        dir_idx = 0
        max_steps = height * width * 4
        steps = 0
        while steps < max_steps:
            contour.append(current)
            found = False
            search_start = (dir_idx + 6) % 8
            for i in range(8):
                idx = (search_start + i) % 8
                dx, dy = dirs[idx]
                nx = current[0] + dx
                ny = current[1] + dy
                if 0 <= ny < height and 0 <= nx < width and component_mask[ny, nx]:
                    current = (nx, ny)
                    dir_idx = idx
                    found = True
                    break
            if not found:
                break
            steps += 1
            if current == start and steps > 3:
                break
        return contour

    @staticmethod
    def _simplify_path(points: List[Tuple[int, int]], epsilon: float) -> List[Tuple[int, int]]:
        if len(points) < 4:
            return points

        def perpendicular_distance(pt: Tuple[int, int], start: Tuple[int, int], end: Tuple[int, int]) -> float:
            if start == end:
                return float(np.hypot(pt[0] - start[0], pt[1] - start[1]))
            sx, sy = start
            ex, ey = end
            px, py = pt
            num = abs((ey - sy) * px - (ex - sx) * py + ex * sy - ey * sx)
            den = np.hypot(ey - sy, ex - sx)
            return float(num / den)

        def rdp(seq: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
            if len(seq) < 3:
                return seq
            start = seq[0]
            end = seq[-1]
            max_dist = 0.0
            index = 0
            for i in range(1, len(seq) - 1):
                dist = perpendicular_distance(seq[i], start, end)
                if dist > max_dist:
                    max_dist = dist
                    index = i
            if max_dist > epsilon:
                left = rdp(seq[: index + 1])
                right = rdp(seq[index:])
                return left[:-1] + right
            return [start, end]

        closed = points[0] == points[-1]
        seq = points[:-1] if closed else points
        simplified = rdp(seq)
        if closed and simplified[0] != simplified[-1]:
            simplified.append(simplified[0])
        return simplified

    @staticmethod
    def _adaptive_simplify_epsilon(points: List[Tuple[int, int]], *, kind: str) -> float:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        # Smaller epsilon for compact shapes (buildings), larger for wide regions.
        base = max(0.8, min(3.5, span * 0.035))
        if kind in {"building"}:
            return max(0.6, min(2.0, base * 0.6))
        if kind in {"road", "driveway", "sidewalk"}:
            return max(0.8, min(3.0, base * 0.8))
        return base

    @staticmethod
    def _orthogonalize_polygon(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if len(points) < 4:
            return points
        closed = points[0] == points[-1]
        seq = points[:-1] if closed else points
        adjusted: List[Tuple[int, int]] = []
        for i, pt in enumerate(seq):
            prev_pt = seq[i - 1]
            next_pt = seq[(i + 1) % len(seq)]
            vx1, vy1 = pt[0] - prev_pt[0], pt[1] - prev_pt[1]
            vx2, vy2 = next_pt[0] - pt[0], next_pt[1] - pt[1]
            is_h1 = abs(vx1) >= abs(vy1)
            is_h2 = abs(vx2) >= abs(vy2)
            if is_h1 and is_h2:
                # Snap y to neighbor average for horizontal emphasis
                new_y = int(round((prev_pt[1] + next_pt[1]) / 2))
                adjusted.append((pt[0], new_y))
            elif not is_h1 and not is_h2:
                # Snap x to neighbor average for vertical emphasis
                new_x = int(round((prev_pt[0] + next_pt[0]) / 2))
                adjusted.append((new_x, pt[1]))
            else:
                adjusted.append(pt)
        if closed and adjusted[0] != adjusted[-1]:
            adjusted.append(adjusted[0])
        return adjusted

    @staticmethod
    def _fit_oriented_rectangle(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if len(points) < 4:
            return points
        closed = points[0] == points[-1]
        seq = points[:-1] if closed else points
        arr = np.asarray(seq, dtype=np.float32)
        if arr.shape[0] < 3:
            return points
        mean = arr.mean(axis=0)
        centered = arr - mean
        cov = np.cov(centered.T)
        eig_vals, eig_vecs = np.linalg.eig(cov)
        axis = eig_vecs[:, int(np.argmax(eig_vals))]
        angle = np.arctan2(axis[1], axis[0])
        cos_a = float(np.cos(-angle))
        sin_a = float(np.sin(-angle))
        rot = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)
        rotated = centered @ rot.T
        min_xy = rotated.min(axis=0)
        max_xy = rotated.max(axis=0)
        width = max_xy[0] - min_xy[0]
        height = max_xy[1] - min_xy[1]
        if width <= 0 or height <= 0:
            return points
        rect = np.array(
            [
                [min_xy[0], min_xy[1]],
                [max_xy[0], min_xy[1]],
                [max_xy[0], max_xy[1]],
                [min_xy[0], max_xy[1]],
                [min_xy[0], min_xy[1]],
            ],
            dtype=np.float32,
        )
        # Rotate back to image space
        inv_cos = float(np.cos(angle))
        inv_sin = float(np.sin(angle))
        inv_rot = np.array([[inv_cos, -inv_sin], [inv_sin, inv_cos]], dtype=np.float32)
        rect_world = rect @ inv_rot.T + mean
        rect_points = [(int(round(x)), int(round(y))) for x, y in rect_world.tolist()]

        # Only accept rectangle if polygon is already roughly rectangular.
        poly_area = abs(FeatureDetectionEngine._polygon_area(seq))
        rect_area = float(width * height)
        if rect_area <= 0:
            return points
        fill_ratio = poly_area / rect_area
        if fill_ratio < 0.7:
            return points
        return rect_points

    @staticmethod
    def _polygon_area(points: List[Tuple[int, int]]) -> float:
        if len(points) < 3:
            return 0.0
        area = 0.0
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            area += x1 * y2 - x2 * y1
        return area / 2.0

    @staticmethod
    def _sobel_edges(gray: np.ndarray) -> np.ndarray:
        padded = np.pad(gray, 1, mode="edge")
        gx = (
            padded[0:-2, 2:]
            + 2 * padded[1:-1, 2:]
            + padded[2:, 2:]
            - padded[0:-2, 0:-2]
            - 2 * padded[1:-1, 0:-2]
            - padded[2:, 0:-2]
        )
        gy = (
            padded[2:, 0:-2]
            + 2 * padded[2:, 1:-1]
            + padded[2:, 2:]
            - padded[0:-2, 0:-2]
            - 2 * padded[0:-2, 1:-1]
            - padded[0:-2, 2:]
        )
        return np.sqrt(gx * gx + gy * gy)

    @staticmethod
    def _snap_contour_to_edges(
        contour: List[Tuple[int, int]],
        edge_strength: np.ndarray,
        *,
        search_radius: int,
        min_strength: float,
    ) -> List[Tuple[int, int]]:
        height, width = edge_strength.shape
        snapped: List[Tuple[int, int]] = []
        for x, y in contour:
            best_x, best_y = x, y
            best_val = 0.0
            for dy in range(-search_radius, search_radius + 1):
                ny = y + dy
                if ny < 0 or ny >= height:
                    continue
                for dx in range(-search_radius, search_radius + 1):
                    nx = x + dx
                    if nx < 0 or nx >= width:
                        continue
                    val = edge_strength[ny, nx]
                    if val > best_val:
                        best_val = val
                        best_x, best_y = nx, ny
            if best_val >= min_strength:
                snapped.append((best_x, best_y))
            else:
                snapped.append((x, y))
        return snapped

    @staticmethod
    def _thin_contour(points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        if len(points) < 5:
            return points
        thinned = [points[0]]
        last = points[0]
        for pt in points[1:]:
            if pt != last:
                if abs(pt[0] - last[0]) + abs(pt[1] - last[1]) >= 1:
                    thinned.append(pt)
                    last = pt
        if thinned[0] != thinned[-1]:
            thinned.append(thinned[0])
        return thinned

    @staticmethod
    def _fill_holes(component_mask: np.ndarray) -> np.ndarray:
        # Flood fill from borders to find background; fill remaining holes.
        height, width = component_mask.shape
        visited = np.zeros_like(component_mask, dtype=bool)
        stack: List[Tuple[int, int]] = []
        for x in range(width):
            if not component_mask[0, x]:
                stack.append((0, x))
            if not component_mask[height - 1, x]:
                stack.append((height - 1, x))
        for y in range(height):
            if not component_mask[y, 0]:
                stack.append((y, 0))
            if not component_mask[y, width - 1]:
                stack.append((y, width - 1))
        while stack:
            cy, cx = stack.pop()
            if cy < 0 or cy >= height or cx < 0 or cx >= width:
                continue
            if visited[cy, cx] or component_mask[cy, cx]:
                continue
            visited[cy, cx] = True
            stack.extend([(cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)])
        filled = component_mask.copy()
        holes = ~component_mask & ~visited
        filled[holes] = True
        return filled

    @staticmethod
    def _merge_overlaps(detections: List[FeatureDetection]) -> List[FeatureDetection]:
        if not detections:
            return detections
        output: List[FeatureDetection] = []
        for det in sorted(detections, key=lambda d: d.confidence, reverse=True):
            should_keep = True
            for kept in output:
                if det.kind != kept.kind:
                    continue
                if FeatureDetectionEngine._iou(det.bbox, kept.bbox) > 0.5:
                    should_keep = False
                    break
            if should_keep:
                output.append(det)
        return output

    @staticmethod
    def _iou(
        a: Tuple[float, float, float, float],
        b: Tuple[float, float, float, float],
    ) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        ax2 = ax + aw
        ay2 = ay + ah
        bx2 = bx + bw
        by2 = by + bh
        inter_x1 = max(ax, bx)
        inter_y1 = max(ay, by)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area_a = aw * ah
        area_b = bw * bh
        return inter_area / max(area_a + area_b - inter_area, 1e-6)

    @staticmethod
    def _close_mask(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        if iterations <= 0:
            return mask
        result = mask.copy()
        for _ in range(iterations):
            # Dilate
            padded = np.pad(result, 1, mode="edge")
            dilated = np.zeros_like(result, dtype=bool)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    dilated |= padded[1 + dy : 1 + dy + result.shape[0], 1 + dx : 1 + dx + result.shape[1]]
            # Erode
            padded = np.pad(dilated, 1, mode="edge")
            eroded = np.ones_like(result, dtype=bool)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    eroded &= padded[1 + dy : 1 + dy + result.shape[0], 1 + dx : 1 + dx + result.shape[1]]
            result = eroded
        return result
