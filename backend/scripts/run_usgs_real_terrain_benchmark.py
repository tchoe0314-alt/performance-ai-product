from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.application.usgs_real_terrain_benchmark import run_usgs_real_terrain_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the rights-cleared USGS real-terrain benchmark.")
    parser.add_argument("--input", type=Path, required=True, help="Downloaded USGS 3DEP GeoTIFF.")
    parser.add_argument("--output", type=Path, default=Path("reports/validation/usgs-real-terrain-001.json"))
    parser.add_argument("--expected-sha256", default="")
    args = parser.parse_args()
    report = run_usgs_real_terrain_benchmark(
        args.input,
        expected_sha256=args.expected_sha256 or None,
        output_path=args.output,
    )
    print(json.dumps({"status": report["status"], "output": str(args.output)}, indent=2))
    return 0 if report["automated_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
