from __future__ import annotations

import argparse
from pathlib import Path

from backend.services.chat_learning_pipeline import run_chat_learning_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run chat learning pipeline.")
    parser.add_argument("--input", default="data/chat_learning.jsonl")
    parser.add_argument("--output", default="data/chat_training.jsonl")
    parser.add_argument("--report", default="data/chat_learning_report.json")
    parser.add_argument("--max-examples", type=int, default=500)
    parser.add_argument("--max-synthetic", type=int, default=60)
    parser.add_argument("--max-unrated", type=int, default=300)
    parser.add_argument("--exclude-unrated", action="store_true")
    args = parser.parse_args()

    run_chat_learning_pipeline(
        input_path=Path(args.input),
        output_path=Path(args.output),
        report_path=Path(args.report),
        max_examples=args.max_examples,
        max_synthetic=args.max_synthetic,
        max_unrated=args.max_unrated,
        exclude_unrated=args.exclude_unrated,
    )


if __name__ == "__main__":
    main()
