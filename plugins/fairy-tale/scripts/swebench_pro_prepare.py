#!/usr/bin/env python3
"""Prepare SWE-Bench Pro slices without leaking gold patches into prompts."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Iterable


DATASET_ID = "ScaleAI/SWE-bench_Pro"
DEFAULT_OUTPUT_DIR = Path("tmp/swe-bench-pro-runs/prepared")
PROMPT_EXCLUDED_FIELDS = {
    "patch",
    "gold_patch",
    "model_patch",
    "test_patch",
    "fail_to_pass",
    "pass_to_pass",
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "before_repo_set_cmd",
    "selected_test_files_to_run",
    "base_dockerfile",
    "instance_dockerfile",
}


def load_dataset_stream(split: str):
    try:
        from datasets import load_dataset
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "The datasets package is required. Use the local SWE-Bench Pro venv "
            "or install the official SWE-Bench Pro requirements first."
        ) from exc
    return load_dataset(DATASET_ID, split=split, streaming=True)


def clean_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): clean_value(item) for key, item in value.items()}
    return str(value)


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): clean_value(value) for key, value in row.items()}


def create_problem_statement(row: dict[str, Any]) -> str:
    parts = [row.get("problem_statement") or ""]
    requirements = row.get("requirements")
    if requirements:
        parts.extend(["", "Requirements:", str(requirements)])
    interface = row.get("interface")
    if interface:
        parts.extend(["", "New interfaces introduced:", str(interface)])
    return "\n".join(parts).strip()


def task_payload(row: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: row.get(key)
        for key in [
            "instance_id",
            "repo",
            "repo_language",
            "base_commit",
            "dockerhub_tag",
        ]
        if key in row
    }
    return {
        "benchmark": "SWE-Bench Pro",
        "instance_id": row["instance_id"],
        "repo": row.get("repo"),
        "repo_language": row.get("repo_language"),
        "base_commit": row.get("base_commit"),
        "dockerhub_tag": row.get("dockerhub_tag"),
        "prompt": create_problem_statement(row),
        "metadata": metadata,
        "excluded_gold_fields": sorted(PROMPT_EXCLUDED_FIELDS),
    }


def reservoir_sample(rows: Iterable[dict[str, Any]], size: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    sample: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        normalized = normalize_row(row)
        if len(sample) < size:
            sample.append(normalized)
            continue
        slot = rng.randrange(index)
        if slot < size:
            sample[slot] = normalized
    return sample


def select_by_ids(rows: Iterable[dict[str, Any]], ids: list[str]) -> list[dict[str, Any]]:
    wanted = set(ids)
    selected: list[dict[str, Any]] = []
    for row in rows:
        instance_id = str(row.get("instance_id"))
        if instance_id in wanted:
            selected.append(normalize_row(row))
            if {item["instance_id"] for item in selected} == wanted:
                break
    found = {row["instance_id"] for row in selected}
    missing = wanted - found
    if missing:
        raise SystemExit(f"missing instance ids: {', '.join(sorted(missing))}")
    return selected


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def prepare(args: argparse.Namespace) -> None:
    if args.ids:
        selected = select_by_ids(load_dataset_stream(args.split), args.ids)
    else:
        selected = reservoir_sample(load_dataset_stream(args.split), args.sample_size, args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "raw-eval.jsonl"
    tasks_path = args.output_dir / "agent-tasks.jsonl"
    manifest_path = args.output_dir / "manifest.json"

    tasks = [task_payload(row) for row in selected]
    write_jsonl(raw_path, selected)
    write_jsonl(tasks_path, tasks)

    manifest = {
        "benchmark": "SWE-Bench Pro",
        "dataset": DATASET_ID,
        "split": args.split,
        "seed": args.seed if not args.ids else None,
        "sample_size": len(selected),
        "instance_ids": [row["instance_id"] for row in selected],
        "raw_eval_path": str(raw_path),
        "agent_tasks_path": str(tasks_path),
        "prompt_excluded_fields": sorted(PROMPT_EXCLUDED_FIELDS),
        "notes": "raw-eval.jsonl may contain gold patches and scorer fields. agent-tasks.jsonl is the prompt-safe artifact.",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare prompt-safe SWE-Bench Pro slices")
    parser.add_argument("--split", default="test")
    parser.add_argument("--sample-size", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260614)
    parser.add_argument("--ids", nargs="*", default=[])
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.sample_size < 1 and not args.ids:
        parser.error("--sample-size must be positive when --ids is not used")
    prepare(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
