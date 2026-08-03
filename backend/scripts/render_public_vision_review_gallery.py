from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.planning.vision_review_gallery import build_public_review_gallery_html


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an offline image-by-image reviewer for a verified vision sprint.")
    parser.add_argument("--review-sprint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image-prefix", default="images")
    args = parser.parse_args()
    sprint = json.loads(args.review_sprint.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(sprint, dict):
        raise SystemExit("Review sprint must contain a JSON object.")
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_public_review_gallery_html(sprint, image_prefix=args.image_prefix), encoding="utf-8")
    print(json.dumps({"success": True, "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
