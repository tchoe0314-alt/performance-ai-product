from __future__ import annotations

import argparse
import json

from backend.planning.vision_benchmark_dataset import import_spacenet2_building_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import an official SpaceNet 2 building benchmark into Civora's traceable COCO contract."
    )
    parser.add_argument("--root", required=True, help="Extracted SpaceNet 2 sample or training root.")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = import_spacenet2_building_benchmark(args.root, args.output_dir)
    print(
        json.dumps(
            {
                "success": True,
                "package_path": result["package_path"],
                "image_root": result["image_root"],
                "eligible_image_count": result["eligible_image_count"],
                "annotation_count": result["annotation_count"],
                "splits": {key: len(value) for key, value in result["splits"].items()},
                "evaluation_scope": result["evaluation_scope"],
                "dataset_fingerprint": result["dataset_fingerprint"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
