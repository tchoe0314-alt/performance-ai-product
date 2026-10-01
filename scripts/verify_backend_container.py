"""Run inside a disposable backend container; never uses live credentials."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import sys
import time

import requests
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--phase", choices=("fresh", "restored"), required=True)
    args = parser.parse_args()
    assert os.getuid() == 10001 and os.getgid() == 10001, "Container must run as restricted user"
    assert not os.access("/app", os.W_OK), "Application code must not be writable"
    for directory in (Path("/data"), Path(os.environ["MPLCONFIGDIR"])):
        probe = directory / "container-permission-probe"
        probe.write_text("writable", encoding="utf-8")
        probe.unlink()
    base = f"http://127.0.0.1:{args.port}"
    for attempt in range(60):
        try:
            if requests.get(base + "/api/health", timeout=2).ok:
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    else:
        raise RuntimeError("Backend did not become healthy")

    def call(method: str, path: str, **kwargs):
        response = requests.request(method, base + path, timeout=30, **kwargs)
        assert response.ok, f"{method} {path}: HTTP {response.status_code}"
        return response

    credentials = {"email": "container-proof@example.test", "password": "disposable-container-proof-123"}
    marker = Path("/data/container-runtime-evidence.json")
    if args.phase == "fresh":
        call("POST", "/api/auth/register", json={**credentials, "name": "Container Proof"})
    login = call("POST", "/api/auth/login", json=credentials).json()
    headers = {"Authorization": "Bearer " + login["token"]}
    user_id = login["user"]["user_id"]
    if args.phase == "fresh":
        project = call("POST", "/api/projects", headers=headers,
                       json={"name": "Container persistence proof", "project_input": {"units": "ft"}}).json()["project"]
        image = io.BytesIO()
        Image.new("RGB", (8, 8), "white").save(image, format="PNG")
        uploaded = call("POST", "/api/upload-image", headers=headers,
                        files={"file": ("proof.png", image.getvalue(), "image/png")}).json()
        path = uploaded.get("image_url") or uploaded.get("url")
        assert path and path.startswith("/api/uploads/"), "Upload must return private file path"
        artifact_dir = Path("/data/artifacts") / user_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "permission-proof.txt").write_text("artifact file access proven", encoding="utf-8")
        marker.write_text(json.dumps({"project_id": project["project_id"], "upload_path": path}), encoding="utf-8")
    evidence = json.loads(marker.read_text(encoding="utf-8"))
    project = call("GET", "/api/projects/" + evidence["project_id"], headers=headers).json()["project"]
    assert project["name"] == "Container persistence proof"
    private_file = call("GET", evidence["upload_path"], headers=headers)
    assert private_file.headers.get("Cache-Control") == "no-store"
    assert requests.get(base + evidence["upload_path"], timeout=10).status_code == 401
    artifact = call("GET", "/api/artifacts/permission-proof.txt", headers=headers)
    assert artifact.text == "artifact file access proven"
    sys.path.insert(0, "/app")
    from backend.services.database import Database
    from backend.services.job_queue import JobQueueService
    queue = JobQueueService(Database(Path("/data/permission-worker.db")), worker_count=1)
    try:
        queue.register_handler("permission_probe", lambda job: {"success": True})
        job = queue.submit_job(user_id=user_id, project_id=None, job_type="permission_probe", payload={})
        for attempt in range(60):
            result = queue.get_job(user_id=user_id, job_id=job["job_id"])
            if result and result["status"] == "completed":
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Restricted-user worker did not complete persisted job")
    finally:
        queue.shutdown()
    print(json.dumps({"phase": args.phase, "uid": os.getuid(), "status": "passed",
                      "checks": ["health", "permissions", "auth", "projects", "uploads", "artifact_access", "worker"]}))


if __name__ == "__main__":
    main()
