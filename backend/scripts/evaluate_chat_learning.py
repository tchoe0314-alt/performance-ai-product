from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize chat learning signals.")
    parser.add_argument("--input", default="data/chat_learning.jsonl")
    parser.add_argument("--training", default="data/chat_training.jsonl")
    parser.add_argument("--output", default="data/chat_learning_report.json")
    args = parser.parse_args()

    events = _read_jsonl(Path(args.input))
    training = _read_jsonl(Path(args.training))

    feedback_events = [e for e in events if e.get("event_type") == "feedback"]
    up = sum(1 for e in feedback_events if e.get("feedback") == "up")
    down = sum(1 for e in feedback_events if e.get("feedback") == "down")
    total = up + down
    score = round((up / total) * 100, 1) if total else 0.0

    report = {
        "feedback": {
            "up": up,
            "down": down,
            "total": total,
            "score_percent": score,
        },
        "training_examples": {
            "count": len(training),
            "synthetic": sum(1 for t in training if t.get("source") == "synthetic"),
            "feedback_based": sum(1 for t in training if t.get("source") == "feedback"),
        },
    }
    _write_json(Path(args.output), report)


if __name__ == "__main__":
    main()
