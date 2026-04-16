from __future__ import annotations

import csv
import math
import mimetypes
import shutil
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse


class AuthStoreProtocol(Protocol):
    def authenticate_token(self, token: str) -> Optional[Dict[str, Any]]:
        ...


def upload_image_file(
    *,
    upload_dir: Path,
    file: UploadFile,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    filename = file.filename or "uploaded_image"
    safe_prefix = str(current_user["user_id"]).replace("/", "_")
    safe_name = Path(filename).name
    stored_name = f"{safe_prefix}_{safe_name}"
    target = upload_dir / stored_name

    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "success": True,
        "message": "Image uploaded.",
        "image_path": str(target),
        "filename": safe_name,
        "stored_filename": stored_name,
        "image_url": f"/api/uploads/{stored_name}",
    }


def upload_survey_file(
    *,
    upload_dir: Path,
    file: UploadFile,
    current_user: Dict[str, Any],
) -> Dict[str, Any]:
    filename = file.filename or "survey.csv"
    safe_prefix = str(current_user["user_id"]).replace("/", "_")
    safe_name = Path(filename).name
    stored_name = f"{safe_prefix}_{safe_name}"
    target = upload_dir / stored_name

    with target.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "success": True,
        "message": "Survey uploaded.",
        "filename": safe_name,
        "stored_filename": stored_name,
        "survey_url": f"/api/uploads/{stored_name}",
    }


def estimate_slope_from_survey(
    *,
    upload_dir: Path,
    current_user: Dict[str, Any],
    filename: str,
) -> Dict[str, Any]:
    safe_name = Path(filename).name
    expected_prefix = f"{current_user['user_id']}_"
    if not safe_name.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="That survey file does not belong to this user.")

    target = upload_dir / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Survey file not found.")

    points: list[tuple[float, float, float]] = []
    with target.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = {str(name or "").strip().lower() for name in (reader.fieldnames or [])}
        if not {"x", "y", "z"}.issubset(fields):
            raise HTTPException(
                status_code=400,
                detail="Survey CSV must include x, y, z columns.",
            )
        for row in reader:
            try:
                x = float(row.get("x", ""))
                y = float(row.get("y", ""))
                z = float(row.get("z", ""))
            except Exception:
                continue
            points.append((x, y, z))

    if len(points) < 3:
        raise HTTPException(status_code=400, detail="Survey file needs at least 3 valid points.")

    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_z = sum(p[2] for p in points)
    sum_xx = sum(p[0] * p[0] for p in points)
    sum_yy = sum(p[1] * p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_xz = sum(p[0] * p[2] for p in points)
    sum_yz = sum(p[1] * p[2] for p in points)
    n = float(len(points))

    det = (
        sum_xx * (sum_yy * n - sum_y * sum_y)
        - sum_xy * (sum_xy * n - sum_x * sum_y)
        + sum_x * (sum_xy * sum_y - sum_yy * sum_x)
    )
    if abs(det) < 1e-9:
        raise HTTPException(status_code=400, detail="Survey points are too collinear to estimate slope.")

    det_a = (
        sum_xz * (sum_yy * n - sum_y * sum_y)
        - sum_xy * (sum_yz * n - sum_y * sum_z)
        + sum_x * (sum_yz * sum_y - sum_yy * sum_z)
    )
    det_b = (
        sum_xx * (sum_yz * n - sum_y * sum_z)
        - sum_xz * (sum_xy * n - sum_x * sum_y)
        + sum_x * (sum_xy * sum_z - sum_xz * sum_y)
    )
    det_c = (
        sum_xx * (sum_yy * sum_z - sum_y * sum_yz)
        - sum_xy * (sum_xy * sum_z - sum_x * sum_yz)
        + sum_xz * (sum_xy * sum_y - sum_yy * sum_x)
    )

    a = det_a / det
    b = det_b / det
    c = det_c / det
    slope_ratio = math.hypot(a, b)
    slope_pct = slope_ratio * 100.0

    downhill_dx = -a
    downhill_dy = -b
    mag = math.hypot(downhill_dx, downhill_dy) or 1e-9
    ux = downhill_dx / mag
    uy = downhill_dy / mag
    angle = (math.degrees(math.atan2(uy, ux)) + 360) % 360
    directions = [
        (0, "E"),
        (45, "NE"),
        (90, "N"),
        (135, "NW"),
        (180, "W"),
        (225, "SW"),
        (270, "S"),
        (315, "SE"),
    ]
    closest = min(directions, key=lambda item: abs((angle - item[0] + 180) % 360 - 180))
    direction_label = closest[1]

    return {
        "success": True,
        "message": "Slope estimated.",
        "slope_ratio": round(slope_ratio, 6),
        "slope_percent": round(slope_pct, 3),
        "downhill_dx": round(ux, 6),
        "downhill_dy": round(uy, 6),
        "direction": direction_label,
        "plane_coefficients": {"a": round(a, 6), "b": round(b, 6), "c": round(c, 6)},
        "point_count": len(points),
    }


def get_uploaded_image_response(
    *,
    upload_dir: Path,
    auth_store: AuthStoreProtocol,
    filename: str,
    token: str,
) -> FileResponse:
    current_user = auth_store.authenticate_token(token)
    if current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    safe_name = Path(filename).name
    expected_prefix = f"{current_user['user_id']}_"
    if not safe_name.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="That image does not belong to this user.")

    target = upload_dir / safe_name
    if not target.exists():
        raise HTTPException(status_code=404, detail="Uploaded image not found.")

    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target, media_type=media_type or "application/octet-stream")


def download_artifact_response(
    *,
    artifact_dir: Path,
    current_user: Dict[str, Any],
    filename: str,
) -> FileResponse:
    path = artifact_dir / current_user["user_id"] / Path(filename).name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found.")
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        filename=path.name,
    )
