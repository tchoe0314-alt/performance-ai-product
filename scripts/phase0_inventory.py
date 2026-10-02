"""Read-only Git/source inventory; never records file contents or secret hashes."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".css", ".md", ".json", ".sh", ".toml", ".yml", ".yaml"}
CODE_ROOTS = {"apps", "backend", "frontend", "tests", "scripts", "docs", "core", "performance_ai", "engines", "geometry", "parsers", "review", "vision"}


def git(*args, root=ROOT):
    return subprocess.check_output(["git", *args], cwd=root).decode("utf-8", errors="surrogateescape")


def classify(path):
    parts = Path(path).parts
    name = Path(path).name.lower()
    if name.startswith(".env") or any(token in name for token in ("secret", "credential", "private_key")) or Path(path).suffix.lower() in {".pem", ".key", ".p12"}:
        return "sensitive-name-metadata-only"
    if any(part in {"private", "node_modules", "test-results", "playwright-report"} or part.startswith(".next") for part in parts):
        return "private-or-generated-metadata-only"
    if parts and (parts[0] in CODE_ROOTS or len(parts) == 1) and Path(path).suffix.lower() in CODE_SUFFIXES:
        return "source-or-documentation"
    return "asset-or-experiment-metadata-only"


def parse_status(raw):
    records = raw.split("\0")
    entries = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        entry = {"status": record[:2], "path": record[3:]}
        if "R" in entry["status"] or "C" in entry["status"]:
            entry["original_path"] = records[index]
            index += 1
        entries.append(entry)
    return entries


def inventory(root=ROOT):
    # NUL delimiters preserve filenames containing whitespace/newlines.
    files = sorted(set(filter(None, git("ls-files", "-z", "--cached", "--others", "--exclude-standard", root=root).split("\0"))))
    rows = []
    digest = hashlib.sha256()
    for relative in files:
        path = root / relative
        category = classify(relative)
        row = {"path": relative, "category": category, "exists": path.exists(), "symlink": path.is_symlink()}
        if path.exists() and not path.is_symlink() and path.is_file():
            row["bytes"] = path.stat().st_size
            if category == "source-or-documentation":
                raw = path.read_bytes()
                row["sha256"] = hashlib.sha256(raw).hexdigest()
                row["lines"] = len(raw.splitlines())
                digest.update(json.dumps([relative, row["sha256"]], ensure_ascii=True).encode())
        rows.append(row)
    branches = []
    for line in git("for-each-ref", "--format=%(refname:short)\t%(objectname)\t%(upstream:short)", "refs/heads", root=root).splitlines():
        name, sha, upstream = line.split("\t")
        result = subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=root, capture_output=True)
        if result.returncode not in (0, 1):
            raise RuntimeError("Unable to classify branch ancestry")
        patch_rows = []
        if result.returncode == 1:
            # Cherry compares patch identity, not commit ancestry. Equivalence
            # still does not prove the active runtime preserves the feature.
            for patch_line in git("cherry", "HEAD", sha, root=root).splitlines():
                marker, patch_sha = patch_line.split(" ", 1)
                patch_rows.append({"commit": patch_sha, "equivalent_patch_in_head": marker == "-"})
        branches.append({"name": name, "commit": sha, "upstream": upstream or None, "contained_in_head": result.returncode == 0, "patch_comparison": patch_rows})
    return {
        "schema": "civora_phase0_inventory_v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "head": git("rev-parse", "HEAD", root=root).strip(),
        "branch": git("branch", "--show-current", root=root).strip(),
        "source_fingerprint_sha256": digest.hexdigest(),
        "changes": parse_status(git("status", "--porcelain=v1", "-z", "--untracked-files=all", root=root)),
        "local_branches": branches,
        "worktrees": git("worktree", "list", "--porcelain", root=root),
        "files": rows,
        "limits": ["Ignored files are excluded; secret contents are never included.", "Source-named files must still be reviewed before sharing this inventory externally.", "Branch ancestry is not proof that a feature is authoritative or correct.", "Cached remote references are not proof of current remote state.", "Metadata-only files are not covered by the source fingerprint; no release gate is asserted."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Local evidence file; do not upload automatically")
    args = parser.parse_args()
    report = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    print(json.dumps({"output": str(args.output), "head": report["head"], "source_fingerprint_sha256": report["source_fingerprint_sha256"], "files": len(report["files"]), "changed_paths": len(report["changes"]), "local_branches": len(report["local_branches"])}))


if __name__ == "__main__":
    main()
