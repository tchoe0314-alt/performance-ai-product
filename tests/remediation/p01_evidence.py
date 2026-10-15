"""P01-only evidence tools. No application startup, activation or repair.

Use -I -B. Inventory reads tracked source, never effective environment values.
Bundles are create-only; verification requires an independently retained manifest hash.
Local files/hashes are tamper-evident, NOT WORM storage or third-party attestation.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
_guard_active = False


def _audit(event, args):
    if not _guard_active:
        return
    if event == "open":
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        ):
            raise PermissionError("P01 read-only assertion guard: file write denied")
        if isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"} or path.name == ".env" or any(
                part in {"uploads", "artifacts", "node_modules", ".git", "data"} for part in path.parts
            ):
                raise PermissionError("P01 assertion guard: storage/config read denied")
    if event.startswith(("socket.", "subprocess.", "sqlite3.", "ctypes.")) or event in {
        "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.system", "os.putenv", "os.unsetenv",
        "os.link", "os.symlink", "os.truncate", "os.chmod", "os.chown", "os.fork", "os.exec",
    }:
        raise PermissionError("P01 assertion guard: side effect denied: " + event)


sys.addaudithook(_audit)


@contextmanager
def readonly_assertions():
    global _guard_active
    previous = _guard_active
    _guard_active = True
    try:
        yield
    finally:
        _guard_active = previous


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def safe_relative(name: str) -> Path:
    p = PurePosixPath(name)
    if not name or p.is_absolute() or ".." in p.parts or "\\" in name or str(p) != name:
        raise ValueError("Unsafe evidence path")
    return Path(*p.parts)


def publish_bundle(root: Path, run_id: str, artifacts: dict[str, bytes], metadata: dict) -> str:
    """Create-only run namespace. Failure never overwrites or removes earlier evidence."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", run_id):
        raise ValueError("Invalid run ID")
    for name in artifacts:
        safe_relative(name)
        if name in {"manifest.json", "manifest.sha256"}:
            raise ValueError("Reserved evidence path")
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError("Symlink evidence root")
    root.mkdir(parents=True, exist_ok=True)
    target = root / run_id
    target.mkdir(exist_ok=False)
    for name, content in artifacts.items():
        path = target / safe_relative(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
    manifest = encoded({"format": "p01_evidence_v1", "run_id": run_id, "metadata": metadata,
                        "files": {k: {"sha256": sha(v), "bytes": len(v)} for k, v in sorted(artifacts.items())}})
    with (target / "manifest.json").open("xb") as stream:
        stream.write(manifest)
    digest = sha(manifest)
    with (target / "manifest.sha256").open("x") as stream:
        stream.write(digest + "\n")
    return digest


def verify_bundle(target: Path, *, expected_source_sha: str, expected_manifest_sha: str):
    if target.is_symlink() or any(p.is_symlink() for p in target.parents):
        raise ValueError("Symlink bundle")
    raw = (target / "manifest.json").read_bytes()
    if sha(raw) != expected_manifest_sha:
        raise ValueError("Manifest anchor mismatch")
    manifest = json.loads(raw)
    if manifest["metadata"]["application_revision"] != expected_source_sha:
        raise ValueError("Source revision mismatch")
    if manifest["run_id"] != target.name or manifest["format"] != "p01_evidence_v1":
        raise ValueError("Manifest identity mismatch")
    actual = set()
    for path in target.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink artifact")
        if path.is_file():
            actual.add(path.relative_to(target).as_posix())
    if actual != {*manifest["files"], "manifest.json", "manifest.sha256"}:
        raise ValueError("Missing or extra evidence")
    if (target / "manifest.sha256").read_text().strip() != expected_manifest_sha:
        raise ValueError("Local anchor mismatch")
    for name, record in manifest["files"].items():
        data = (target / safe_relative(name)).read_bytes()
        if sha(data) != record["sha256"] or len(data) != record["bytes"]:
            raise ValueError("Artifact hash mismatch: " + name)
    return manifest


def extracted(relative: str, names: list[str], namespace: dict):
    """Execute original AST bodies only; skip startup/import side effects.

    Annotations are deferred, decorators are forbidden. Report records source hashes.
    Callers supply original pure helpers and synthetic external dependencies explicitly.
    """
    path = ROOT / relative
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    if {n.name for n in nodes} != set(names) or any(n.decorator_list for n in nodes):
        raise ValueError("Requested undecorated functions not found")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


def tracked_source_paths() -> list[str]:
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    prefixes = ("backend/", "core/", "engines/", "geometry/", "output/", "parsers/", "review/",
                "apps/web/", "scripts/", "vision/")
    return sorted(p for p in files if p and Path(p).suffix in {".py", ".ts", ".tsx", ".js", ".mjs"}
                  and (p.startswith(prefixes) or "/" not in p)
                  and not any(x in Path(p).parts for x in ("fixtures", "tests", "data", "artifacts", "uploads", "__pycache__")))


ENV_PATTERN = re.compile(r"\b(?:CIVORA_|PERFORMANCE_AI_|NEXT_PUBLIC_|OPENAI_|MAPBOX_|STRIPE_)[A-Z0-9_]+\b|\bDATABASE_URL\b")
CONTROL_PATTERN = re.compile(r"<(button|Button|input|select|textarea|[A-Z][A-Za-z]*(?:Button|Slider|Switch|Control))\b")


def inventory(paths: list[str]) -> dict:
    records, files, errors = [], [], []
    def add(kind, path, line, name, **extra):
        records.append({"id": f"{kind}:{path}:{line}:{name}", "kind": kind, "source": path, "line": line,
                        "name": name, "implementation_status": "SOURCE_PRESENT_RUNTIME_UNVERIFIED",
                        "verification_status": "NOT TESTED", "observed": "Static source construct only; not activated",
                        "expected": "Disposition in feature inventory, not release acceptance",
                        "enablement_conditions": "See referenced source and linked feature family; effective configuration UNKNOWN",
                        "permissions": "UNKNOWN; inspect handler and authorization dependencies before execution",
                        "units_and_sources": "UNKNOWN unless family record specifies; no inference from label",
                        "side_effects": "Potential writes/network/storage/charges UNKNOWN; do not execute by default",
                        "safe_test_mode": "Static inspection now; isolated synthetic fixtures and fake transports in later authorized package",
                        "issues": ["TEST-08", "TEST-07"], **extra})
    for relative in paths:
        data = (ROOT / relative).read_bytes()
        # Python accepts UTF-8 BOMs; hash the original bytes, decode as Python does.
        text = data.decode("utf-8-sig")
        files.append({"path": relative, "sha256": sha(data), "bytes": len(data)})
        environment_keys = set()
        if relative.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError as exc:
                errors.append({"path": relative, "error": str(exc)})
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    call = ast.unparse(node.func)
                    if call.endswith("getenv") or call.endswith("environ.get"):
                        key = node.args[0] if node.args else None
                        name = key.value if isinstance(key, ast.Constant) and isinstance(key.value, str) else "DYNAMIC_ENVIRONMENT_KEY"
                        environment_keys.add(name)
                        add("environment_lookup", relative, node.lineno, name,
                            discovery="Actual environment lookup, values NOT read; dynamic names require later characterization",
                            static_default_present=len(node.args) > 1 or bool(node.keywords))
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {
                        "get", "post", "put", "patch", "delete", "options", "head", "websocket", "api_route"
                    }:
                        receiver = ast.unparse(dec.func.value)
                        # Restrict to likely route decorators, not arbitrary object's get().
                        if any(x in receiver.lower() for x in ("app", "router", "api")):
                            route = ast.literal_eval(dec.args[0]) if dec.args and isinstance(dec.args[0], ast.Constant) else "DYNAMIC_ROUTE"
                            add("api_route", relative, node.lineno, f"{receiver}.{dec.func.attr} {route}",
                                handler=node.name, declaration=ast.unparse(dec),
                                permissions="Declaration only: " + ast.unparse(node.args))
            if relative.startswith("engines/"):
                names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
                add("engine_module", relative, 1, Path(relative).stem, public_symbols=names,
                    issues=["ENG-06", "TEST-08"], units_and_sources="Engine-specific; see engineering validation plan; accuracy NOT VERIFIED")
        if relative.endswith((".tsx", ".ts", ".js", ".mjs")):
            for match in re.finditer(r"process\.env(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\])", text):
                name = match.group(1) or match.group(2)
                environment_keys.add(name)
                add("environment_lookup", relative, text.count("\n", 0, match.start()) + 1, name,
                    discovery="Literal process.env source lookup; effective value NOT read")
            for match in CONTROL_PATTERN.finditer(text):
                add("ui_control", relative, text.count("\n", 0, match.start()) + 1, match.group(1),
                    discovery="Lexical JSX locator, not a rendered control count")
            if re.search(r"/(page|route)\.(?:tsx?|jsx?)$", relative):
                add("frontend_entry", relative, 1, Path(relative).name,
                    http_methods=re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\b", text))
        seen = set()
        for match in ENV_PATTERN.finditer(text):
            name = match.group(0)
            if name not in seen and name not in environment_keys:
                seen.add(name)
                add("configuration_reference", relative, text.count("\n", 0, match.start()) + 1, name,
                    discovery="Literal/name reference (including comments); values NOT read; dynamic names may be missed")
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        # Same-name JSX controls on one source line need independent locators.
        counts = {}
        for row in records:
            base = row["id"]
            counts[base] = counts.get(base, 0) + 1
            row["id"] = base + ":" + str(counts[base])
    counts = {kind: sum(r["kind"] == kind for r in records) for kind in sorted({r["kind"] for r in records})}
    return {"scope": "Tracked source scan; all discovered constructs have dispositions; NOT all-feature runtime verification",
            "coverage_limits": ["Literal/AST discovery cannot enumerate dynamically generated routes, controls or configuration names",
                                "No feature is enabled; runtime provider configuration and installed optional dependencies UNKNOWN",
                                "Tests, fixtures, customer storage, .env values, generated files and production excluded",
                                "Custom interactive JSX without listed tag suffixes may be missed; curated family map complements scan"],
            "files": files, "parse_errors": errors, "counts": counts, "records": records}
