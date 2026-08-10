from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Mapping, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.hosted_canary import build_hosted_canary_report


def _revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def _safe_origin(value: str, *, label: str) -> str:
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    is_local = parsed.hostname in {"localhost", "127.0.0.1"}
    allowed_schemes = {"http", "https"} if is_local else {"https"}
    if parsed.scheme not in allowed_schemes or not parsed.netloc or parsed.username or parsed.password or parsed.path not in {"", "/"}:
        raise ValueError(f"{label} must be an approved origin without embedded credentials or a path.")
    return normalized


def _request(
    url: str,
    *,
    method: str = "GET",
    payload: Optional[Mapping[str, Any]] = None,
    headers: Optional[Mapping[str, str]] = None,
    timeout: float,
) -> Tuple[int, Dict[str, str], bytes, float]:
    parsed = urlparse(url)
    is_local = parsed.hostname in {"localhost", "127.0.0.1"}
    allowed_schemes = {"http", "https"} if is_local else {"https"}
    if parsed.scheme not in allowed_schemes or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Canary requests require an approved HTTP(S) URL without embedded credentials.")
    body = json.dumps(dict(payload)).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json", "User-Agent": "Civora-Hosted-Canary/1", **dict(headers or {})}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, method=method, headers=request_headers)
    started = time.monotonic()
    try:
        # URL scheme and credential form are validated before opening the request.
        with urlopen(request, timeout=timeout) as response:  # nosec B310
            return int(response.status), {key.lower(): value for key, value in response.headers.items()}, response.read(), round((time.monotonic() - started) * 1000.0, 1)
    except HTTPError as exc:
        return int(exc.code), {key.lower(): value for key, value in exc.headers.items()}, exc.read(), round((time.monotonic() - started) * 1000.0, 1)
    except URLError as exc:
        raise RuntimeError(f"Canary could not reach {parsed.netloc}.") from exc


def _json(body: bytes, *, endpoint: str) -> Dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Canary received invalid JSON from {endpoint}.") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Canary received a non-object JSON response from {endpoint}.")
    return value


def _capture(
    *,
    frontend_url: str,
    api_base_url: str,
    expected_revision: str,
    expected_product_mode: str,
    timeout: float,
    require_authenticated: bool,
) -> Dict[str, Any]:
    timings: Dict[str, float] = {}
    frontend_status, _frontend_headers, frontend_body, timings["frontend"] = _request(frontend_url, timeout=timeout)
    frontend = {
        "status": frontend_status,
        "body_has_civora": b"civora" in frontend_body.lower(),
    }
    health_status, _health_headers, health_body, timings["health"] = _request(f"{api_base_url}/api/health", timeout=timeout)
    if health_status != 200:
        raise RuntimeError(f"Hosted health returned HTTP {health_status}.")
    health = _json(health_body, endpoint="/api/health")
    auth_status_code, _auth_headers, auth_body, timings["auth_status"] = _request(f"{api_base_url}/api/auth/status", timeout=timeout)
    if auth_status_code != 200:
        raise RuntimeError(f"Hosted auth status returned HTTP {auth_status_code}.")
    auth_status = _json(auth_body, endpoint="/api/auth/status")
    runtime_guard_status, _runtime_headers, _runtime_body, timings["runtime_auth_guard"] = _request(f"{api_base_url}/api/debug/runtime", timeout=timeout)
    production_env_guard_status, _production_headers, _production_body, timings["production_env_auth_guard"] = _request(f"{api_base_url}/api/debug/production-env", timeout=timeout)
    frontend_origin = f"{urlparse(frontend_url).scheme}://{urlparse(frontend_url).netloc}"
    cors_status, cors_headers, _cors_body, timings["cors_preflight"] = _request(
        f"{api_base_url}/api/health",
        method="OPTIONS",
        headers={"Origin": frontend_origin, "Access-Control-Request-Method": "GET"},
        timeout=timeout,
    )

    email = str(os.getenv("CIVORA_CANARY_EMAIL") or "").strip()
    password = str(os.getenv("CIVORA_CANARY_PASSWORD") or "")
    authenticated_runtime = None
    token = ""
    try:
        if email and password:
            login_status, _login_headers, login_body, timings["login"] = _request(
                f"{api_base_url}/api/auth/login",
                method="POST",
                payload={"email": email, "password": password},
                timeout=timeout,
            )
            if login_status != 200:
                raise RuntimeError(f"Hosted canary login returned HTTP {login_status}.")
            login = _json(login_body, endpoint="/api/auth/login")
            token = str(login.get("token") or "")
            if not token:
                raise RuntimeError("Hosted canary login did not return a token.")
            runtime_status, _headers, runtime_body, timings["authenticated_runtime"] = _request(
                f"{api_base_url}/api/debug/runtime",
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
            )
            if runtime_status != 200:
                raise RuntimeError(f"Authenticated runtime returned HTTP {runtime_status}.")
            authenticated_runtime = _json(runtime_body, endpoint="/api/debug/runtime")
        elif email or password:
            raise RuntimeError("Configure both CIVORA_CANARY_EMAIL and CIVORA_CANARY_PASSWORD or neither.")

        report = build_hosted_canary_report(
            frontend_url=frontend_url,
            api_base_url=api_base_url,
            expected_revision=expected_revision,
            expected_product_mode=expected_product_mode,
            frontend=frontend,
            health=health,
            auth_status=auth_status,
            cors={"status": cors_status, "allow_origin": cors_headers.get("access-control-allow-origin", "")},
            unauthenticated_runtime_status=runtime_guard_status,
            unauthenticated_production_env_status=production_env_guard_status,
            authenticated_runtime=authenticated_runtime,
            require_authenticated=require_authenticated,
        )
        report["request_timings_ms"] = timings
        return report
    finally:
        if token:
            try:
                _request(
                    f"{api_base_url}/api/auth/logout",
                    method="POST",
                    payload={},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=timeout,
                )
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a low-impact Civora hosted availability and release-truth canary.")
    parser.add_argument("--frontend-url", default=os.getenv("CIVORA_CANARY_FRONTEND_URL") or "https://civoraai.com")
    parser.add_argument("--api-base-url", default=os.getenv("CIVORA_CANARY_API_BASE_URL") or "https://api.civoraai.com")
    parser.add_argument("--expected-revision", default=os.getenv("CIVORA_EXPECTED_REVISION") or _revision())
    parser.add_argument("--expected-product-mode", default=os.getenv("CIVORA_EXPECTED_PRODUCT_MODE") or "private_alpha")
    parser.add_argument("--output", default="reports/release/hosted-canary.json")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--retry-delay-seconds", type=float, default=15.0)
    parser.add_argument("--required-consecutive-successes", type=int, default=1)
    parser.add_argument("--require-authenticated", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {}
    try:
        frontend_url = _safe_origin(args.frontend_url, label="Frontend URL")
        api_base_url = _safe_origin(args.api_base_url, label="API base URL")
        attempts = max(1, min(int(args.attempts), 60))
        required_consecutive = max(1, min(int(args.required_consecutive_successes), 5))
        consecutive_successes = 0
        attempt_history = []
        for attempt in range(1, attempts + 1):
            attempt_started = time.monotonic()
            try:
                report = _capture(
                    frontend_url=frontend_url,
                    api_base_url=api_base_url,
                    expected_revision=args.expected_revision,
                    expected_product_mode=args.expected_product_mode,
                    timeout=max(1.0, args.timeout_seconds),
                    require_authenticated=args.require_authenticated,
                )
            except Exception as exc:
                report = {
                    "version": "civora_hosted_canary_v1",
                    "success": False,
                    "status": "blocked",
                    "public_checks_ready": False,
                    "authenticated_checks_status": "blocked" if args.require_authenticated else "not_captured",
                    "public_blockers": [{"code": "canary_capture_failed", "message": str(exc), "area": "capture"}],
                    "authenticated_blockers": [],
                    "construction_ready": False,
                    "public_beta_allowed": False,
                    "truth_label": "No credentials or authentication tokens are written to this report.",
                }
            report["attempt"] = attempt
            report["attempts_allowed"] = attempts
            consecutive_successes = consecutive_successes + 1 if report.get("success") else 0
            attempt_history.append({
                "attempt": attempt,
                "success": bool(report.get("success")),
                "duration_ms": round((time.monotonic() - attempt_started) * 1000.0, 1),
                "public_blocker_codes": [str(item.get("code") or "") for item in report.get("public_blockers") or []],
                "authenticated_blocker_codes": [str(item.get("code") or "") for item in report.get("authenticated_blockers") or []],
                "checks": dict(report.get("checks") or {}),
                "request_timings_ms": dict(report.get("request_timings_ms") or {}),
            })
            if consecutive_successes >= required_consecutive:
                break
            if attempt < attempts:
                time.sleep(max(0.0, args.retry_delay_seconds))
        report["attempt_history"] = attempt_history
        report["required_consecutive_successes"] = required_consecutive
        report["consecutive_successes"] = consecutive_successes
        if consecutive_successes < required_consecutive:
            report["success"] = False
            report["status"] = "blocked"
            report["public_checks_ready"] = False
            report.setdefault("public_blockers", []).append({
                "code": "insufficient_consecutive_healthy_samples",
                "message": f"The canary did not record {required_consecutive} consecutive healthy samples.",
                "area": "stability",
            })
    except Exception as exc:
        report = {
            "version": "civora_hosted_canary_v1",
            "success": False,
            "status": "blocked",
            "public_checks_ready": False,
            "authenticated_checks_status": "not_captured",
            "public_blockers": [{"code": "canary_configuration_invalid", "message": str(exc), "area": "configuration"}],
            "authenticated_blockers": [],
            "construction_ready": False,
            "public_beta_allowed": False,
            "truth_label": "No credentials or authentication tokens are written to this report.",
        }

    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "status": report.get("status"),
        "success": report.get("success"),
        "public_checks_ready": report.get("public_checks_ready"),
        "authenticated_checks_status": report.get("authenticated_checks_status"),
        "public_blocker_count": len(report.get("public_blockers") or []),
        "authenticated_blocker_count": len(report.get("authenticated_blockers") or []),
        "hosted_revision": report.get("hosted_revision"),
        "output": str(output),
    }, sort_keys=True))
    if not report.get("success"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
