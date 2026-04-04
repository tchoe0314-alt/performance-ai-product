from __future__ import annotations

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
