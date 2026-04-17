from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.scripts.build_training_data import (
    _read_jsonl as _read_learning_jsonl,
    _write_jsonl as _write_training_jsonl,
    _training_examples,
    _interaction_examples,
    _synthesize_examples,
)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def run_chat_learning_pipeline(
    *,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    max_examples: int = 500,
    max_synthetic: int = 60,
    max_unrated: int = 300,
    exclude_unrated: bool = False,
) -> Dict[str, Any]:
    events = _read_learning_jsonl(input_path)
    examples = _training_examples(events, max_examples)
    positives = [ex for ex in examples if ex.get("feedback") == "up"]
    synthetic = _synthesize_examples(positives, max_synthetic)
    interaction_examples: List[Dict[str, Any]] = []
    if not exclude_unrated:
        exclude_message_ids = {
            ex.get("message_id") for ex in examples if ex.get("message_id")
        }
        interaction_examples = _interaction_examples(
            events,
            max_unrated,
            exclude_message_ids=exclude_message_ids,
        )
    training_rows = examples + interaction_examples + synthetic
    _write_training_jsonl(output_path, training_rows)

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
            "count": len(training_rows),
            "synthetic": sum(1 for t in training_rows if t.get("source") == "synthetic"),
            "feedback_based": sum(1 for t in training_rows if t.get("source") == "feedback"),
            "interaction": sum(1 for t in training_rows if t.get("source") == "interaction"),
        },
    }
    _write_json(report_path, report)
    return {
        "events": len(events),
        "training_rows": len(training_rows),
        "report_path": str(report_path),
        "output_path": str(output_path),
    }
