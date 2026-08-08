from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.hosted_operational_evidence import build_hosted_operational_evidence


def _revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def _safe_base_url(value: str) -> str:
    base_url = str(value or "").strip().rstrip("/")
    parsed = urlparse(base_url)
    is_local = parsed.hostname in {"localhost", "127.0.0.1"}
    if not parsed.netloc or parsed.scheme not in ({"http", "https"} if is_local else {"https"}):
        raise ValueError("Hosted operational evidence requires an HTTPS backend URL, except for an explicit localhost audit.")
    return base_url


def _json_request(url: str, *, method: str = "GET", payload: Dict[str, Any] | None = None, token: str = "", timeout: float = 30.0) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", "User-Agent": "Civora-RC1-Operational-Evidence/1"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Hosted request failed with HTTP {exc.code} at {urlparse(url).path}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Hosted request could not reach {urlparse(url).netloc}.") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError(f"Hosted request returned an invalid JSON object at {urlparse(url).path}.")
    return decoded


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture redacted, exact-revision Civora hosted operational evidence.")
    parser.add_argument("--base-url", default=os.getenv("CIVORA_HOSTED_API_BASE_URL") or os.getenv("CIVORA_PUBLIC_API_BASE_URL") or "https://api.civoraai.com")
    parser.add_argument("--expected-revision", default=os.getenv("CIVORA_EXPECTED_REVISION") or _revision())
    parser.add_argument("--output", default="reports/release/hosted-operational-evidence.json")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--fail-on-runtime-blocked", action="store_true")
    parser.add_argument("--fail-on-operational-blocked", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    token = ""
    logout_base_url = ""
    try:
        base_url = _safe_base_url(args.base_url)
        logout_base_url = base_url
        email = str(os.getenv("CIVORA_EMAIL") or "").strip()
        password = str(os.getenv("CIVORA_PASSWORD") or "")
        if not email or not password:
            raise RuntimeError("Set CIVORA_EMAIL and CIVORA_PASSWORD in the process environment; credentials are never accepted as command-line arguments or written to the report.")
        health = _json_request(f"{base_url}/api/health", timeout=args.timeout_seconds)
        login = _json_request(
            f"{base_url}/api/auth/login",
            method="POST",
            payload={"email": email, "password": password},
            timeout=args.timeout_seconds,
        )
        token = str(login.get("token") or "")
        if not token:
            raise RuntimeError("Hosted login succeeded without returning an authentication token.")
        runtime = _json_request(f"{base_url}/api/debug/runtime", token=token, timeout=args.timeout_seconds)
        report = build_hosted_operational_evidence(
            health=health,
            runtime=runtime,
            expected_revision=args.expected_revision,
            base_url=base_url,
        )
    except Exception as exc:
        report = {
            "version": "civora_hosted_operational_evidence_v1",
            "success": False,
            "status": "blocked",
            "hosted_runtime_ready": False,
            "operational_configuration_ready": False,
            "runtime_blockers": [{"code": "hosted_evidence_capture_failed", "message": str(exc), "area": "capture"}],
            "operational_blockers": [],
            "construction_ready": False,
            "truth_label": "No credentials or authentication tokens are written to this report.",
        }
    finally:
        if token and logout_base_url:
            try:
                _json_request(f"{logout_base_url}/api/auth/logout", method="POST", payload={}, token=token, timeout=args.timeout_seconds)
            except Exception:
                pass

    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report.get("status"),
        "hosted_runtime_ready": report.get("hosted_runtime_ready"),
        "operational_configuration_ready": report.get("operational_configuration_ready"),
        "runtime_blocker_count": len(report.get("runtime_blockers") or []),
        "operational_blocker_count": len(report.get("operational_blockers") or []),
        "output": str(output),
    }, sort_keys=True))
    if args.fail_on_runtime_blocked and not report.get("hosted_runtime_ready"):
        raise SystemExit(1)
    if args.fail_on_operational_blocked and not report.get("operational_configuration_ready"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
