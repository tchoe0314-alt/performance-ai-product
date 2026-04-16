from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List

from parsers.ai_parser import _get_client


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


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _training_examples(events: List[Dict[str, Any]], max_examples: int) -> List[Dict[str, Any]]:
    examples = [
        {
            "source": "feedback",
            "feedback": event.get("feedback"),
            "input": event.get("input"),
            "output": event.get("output"),
            "project_id": event.get("project_id"),
            "message_id": event.get("message_id"),
        }
        for event in events
        if event.get("event_type") == "training_example"
        and event.get("input")
        and event.get("output")
    ]
    if len(examples) > max_examples:
        examples = random.sample(examples, max_examples)
    return examples


def _generate_paraphrases(message: str, limit: int) -> List[str]:
    if not message or limit <= 0:
        return []
    client = _get_client()
    response = client.responses.create(
        model=os.getenv("CIVORA_CHAT_MODEL", "gpt-5"),
        input=[
            {
                "role": "system",
                "content": (
                    "Create concise paraphrases of the user message, preserving intent. "
                    "Return only JSON matching the schema."
                ),
            },
            {"role": "user", "content": message},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "chat_paraphrases",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "paraphrases": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["paraphrases"],
                },
                "strict": True,
            }
        },
    )
    data = json.loads(response.output_text)
    paraphrases = [str(item).strip() for item in data.get("paraphrases") or [] if str(item).strip()]
    return paraphrases[:limit]


def _synthesize_examples(
    positives: List[Dict[str, Any]],
    max_synthetic: int,
) -> List[Dict[str, Any]]:
    synthetic: List[Dict[str, Any]] = []
    if max_synthetic <= 0 or not positives:
        return synthetic
    per_example = max(1, min(2, max_synthetic // max(len(positives), 1)))
    for example in positives:
        message = str(example.get("input") or "")
        output = str(example.get("output") or "")
        for paraphrase in _generate_paraphrases(message, per_example):
            synthetic.append(
                {
                    "source": "synthetic",
                    "feedback": "up",
                    "input": paraphrase,
                    "output": output,
                    "project_id": example.get("project_id"),
                    "message_id": example.get("message_id"),
                }
            )
            if len(synthetic) >= max_synthetic:
                return synthetic
    return synthetic


def main() -> None:
    parser = argparse.ArgumentParser(description="Build chat training examples from learning log.")
    parser.add_argument("--input", default="data/chat_learning.jsonl")
    parser.add_argument("--output", default="data/chat_training.jsonl")
    parser.add_argument("--max-examples", type=int, default=500)
    parser.add_argument("--max-synthetic", type=int, default=60)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    events = _read_jsonl(input_path)
    examples = _training_examples(events, args.max_examples)
    positives = [ex for ex in examples if ex.get("feedback") == "up"]
    synthetic = _synthesize_examples(positives, args.max_synthetic)
    all_rows = examples + synthetic
    _write_jsonl(output_path, all_rows)


if __name__ == "__main__":
    main()
