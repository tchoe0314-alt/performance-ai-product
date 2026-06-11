#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.application.production_env_validator_v1 import validate_production_env_v1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production environment config for Vercel/Railway.")
    parser.add_argument("--target", default="", help="Override deployment target: local, vercel, railway, or split.")
    parser.add_argument("--no-diagnostics", action="store_true", help="Omit redacted env diagnostics.")
    parser.add_argument("--warn-only", action="store_true", help="Always exit zero; useful for exploratory local runs.")
    args = parser.parse_args()

    report = validate_production_env_v1(deployment_target=args.target, include_diagnostics=not args.no_diagnostics)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.warn_only:
        return 0
    return 1 if report["release_blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
