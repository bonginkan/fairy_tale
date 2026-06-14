#!/usr/bin/env python3
"""BioMysteryBench preview runner for Fairy Tale experiments.

The runner keeps answer rubrics out of prompts. Rubrics are loaded only by the
scoring path.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATASET_ID = "Anthropic/BioMysteryBench-preview"
DEFAULT_DATASET_DIR = Path("tmp/biomystery-preview")
DEFAULT_WORK_DIR = Path("tmp/biomystery-runs")
DEFAULT_MODEL = "gpt-5.5"

FAIRY_TALE_GUIDANCE = """Use Fairy Tale's Bio/Health Safety Harness and Evidence Table Harness:
- classify the task as bioinformatics analysis, not clinical advice;
- keep the answer grounded in the supplied data and allowed public domains;
- separate observations, uncertainty, and final answer;
- produce a short final answer in the requested format;
- do not use the benchmark rubric or expected answer unless it is explicitly part of the user prompt.
"""

BASELINE_GUIDANCE = """Solve the task using the supplied problem statement and data summary. Provide the final answer in the requested format."""


@dataclass(frozen=True)
class Problem:
    id: str
    question: str
    answer_rubric: str
    allowed_domains: str
    human_solvable: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_cmd(args: list[str]) -> None:
    subprocess.run(args, check=True)


def ensure_dataset(dataset_dir: Path) -> None:
    required = [dataset_dir / "problems.csv", dataset_dir / "data.zip"]
    if all(path.exists() for path in required):
        return
    dataset_dir.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("hf") is None:
        raise SystemExit("hf CLI is required to download BioMysteryBench preview")
    run_cmd(
        [
            "hf",
            "download",
            DATASET_ID,
            "--repo-type",
            "dataset",
            "--local-dir",
            str(dataset_dir),
            "--max-workers",
            "2",
        ]
    )


def extract_data(dataset_dir: Path) -> Path:
    data_zip = dataset_dir / "data.zip"
    if not data_zip.exists():
        raise SystemExit(f"missing data.zip: {data_zip}")
    extracted = dataset_dir / "data"
    marker = extracted / ".extracted"
    if marker.exists():
        return extracted
    extracted.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(data_zip) as archive:
        archive.extractall(extracted)
    marker.write_text(str(time.time()), encoding="utf-8")
    return extracted


def load_problems(dataset_dir: Path) -> list[Problem]:
    path = dataset_dir / "problems.csv"
    if not path.exists():
        raise SystemExit(f"missing problems.csv: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return [Problem(**row) for row in csv.DictReader(handle)]


def select_problems(problems: list[Problem], ids: list[str]) -> list[Problem]:
    if not ids or ids == ["all"]:
        return problems
    wanted = set(ids)
    selected = [problem for problem in problems if problem.id in wanted]
    missing = wanted - {problem.id for problem in selected}
    if missing:
        raise SystemExit(f"unknown problem ids: {', '.join(sorted(missing))}")
    return selected


def data_files_for(problem_id: str, extracted_dir: Path) -> list[Path]:
    problem_dir = extracted_dir / problem_id
    if not problem_dir.exists():
        return []
    return sorted(path for path in problem_dir.rglob("*") if path.is_file())


def file_summary(path: Path, preview_bytes: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "path": str(path),
        "name": path.name,
        "size_bytes": path.stat().st_size,
    }
    if preview_bytes > 0:
        data = path.read_bytes()[:preview_bytes]
        summary["preview"] = data.decode("utf-8", errors="replace")
        summary["preview_truncated"] = path.stat().st_size > preview_bytes
    return summary


def make_prompt(problem: Problem, files: list[Path], condition: str, preview_bytes: int) -> list[dict[str, Any]]:
    if condition == "fairy_tale":
        guidance = FAIRY_TALE_GUIDANCE
    elif condition == "baseline":
        guidance = BASELINE_GUIDANCE
    else:
        raise SystemExit(f"unsupported condition: {condition}")

    file_summaries = [file_summary(path, preview_bytes) for path in files]
    user_payload = {
        "benchmark": "BioMysteryBench-preview",
        "problem_id": problem.id,
        "question": problem.question,
        "allowed_domains": [item.strip() for item in problem.allowed_domains.split(",") if item.strip()],
        "human_solvable": problem.human_solvable,
        "data_files": file_summaries,
        "output_contract": {
            "final_answer": "Return only the requested biological answer in the final line.",
            "no_rubric": "The answer rubric is intentionally not provided.",
        },
    }
    return [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": guidance}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": json.dumps(user_payload, ensure_ascii=False)}],
        },
    ]


def output_text_from_response(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    parts: list[str] = []
    for item in response.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def call_openai(messages: list[dict[str, Any]], model: str, effort: str, timeout: int) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for non-dry-run execution")
    body = {
        "model": model,
        "input": messages,
        "reasoning": {"effort": effort},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    request_timeout = None if timeout <= 0 else timeout
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI API error {error.code}: {detail}") from error


def parse_expected(rubric: str) -> dict[str, Any]:
    sample_ids = re.findall(r"Sample_\d+", rubric)
    if sample_ids:
        return {"kind": "sample_list", "value": sorted(set(sample_ids))}

    match = re.search(
        r"(?:The answer is|Expected answer is)\s*:?\s*(.+?)\s+Score\s+1\.0",
        rubric,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"could not parse expected answer from rubric: {rubric}")
    value = match.group(1).strip().strip(".").strip()
    return {"kind": "text", "value": value}


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def final_answer_text(answer: str) -> str:
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    candidate = lines[-1] if lines else answer.strip()
    candidate = re.sub(r"^(final\s+answer|answer)\s*:\s*", "", candidate, flags=re.IGNORECASE)
    return candidate.strip()


def score_answer(answer: str, expected: dict[str, Any]) -> dict[str, Any]:
    if expected["kind"] == "sample_list":
        predicted = sorted(set(re.findall(r"Sample_\d+", answer)))
        passed = predicted == expected["value"]
        return {
            "score": 1.0 if passed else 0.0,
            "passed": passed,
            "expected": expected["value"],
            "predicted": predicted,
        }
    expected_norm = normalize_text(str(expected["value"]))
    predicted = final_answer_text(answer)
    predicted_norm = normalize_text(predicted)
    passed = expected_norm == predicted_norm
    return {
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "expected": expected["value"],
        "predicted": predicted,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]], append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def command_prepare(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    problems = load_problems(dataset_dir)
    print(json.dumps({"dataset_dir": str(dataset_dir), "extracted_dir": str(extracted), "problems": len(problems)}))


def command_list(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    rows = []
    for problem in load_problems(dataset_dir):
        files = data_files_for(problem.id, extracted)
        rows.append(
            {
                "id": problem.id,
                "human_solvable": problem.human_solvable,
                "files": [{"path": str(path), "size_bytes": path.stat().st_size} for path in files],
                "question": problem.question,
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def command_prompt(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    problems = select_problems(load_problems(dataset_dir), [args.id])
    problem = problems[0]
    messages = make_prompt(problem, data_files_for(problem.id, extracted), args.condition, args.preview_bytes)
    print(json.dumps({"id": problem.id, "condition": args.condition, "messages": messages}, ensure_ascii=False, indent=2))


def command_run(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    ensure_dataset(dataset_dir)
    extracted = extract_data(dataset_dir)
    problems = select_problems(load_problems(dataset_dir), args.ids)
    rows = []
    for problem in problems:
        messages = make_prompt(problem, data_files_for(problem.id, extracted), args.condition, args.preview_bytes)
        row: dict[str, Any] = {
            "id": problem.id,
            "condition": args.condition,
            "model": args.model,
            "effort": args.effort,
            "preview_bytes": args.preview_bytes,
            "created_at_unix": int(time.time()),
        }
        if args.dry_run:
            row["dry_run"] = True
            row["prompt_messages"] = messages
        else:
            response = call_openai(messages, args.model, args.effort, args.timeout)
            row["response_id"] = response.get("id")
            row["answer"] = output_text_from_response(response)
            row["usage"] = response.get("usage")
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False))
    if args.output:
        write_jsonl(Path(args.output), rows, append=args.append)


def command_score(args: argparse.Namespace) -> None:
    dataset_dir = Path(args.dataset_dir)
    problems = {problem.id: problem for problem in load_problems(dataset_dir)}
    scored = []
    with Path(args.predictions).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            problem = problems.get(row["id"])
            if not problem:
                raise SystemExit(f"prediction contains unknown id: {row['id']}")
            answer = row.get("answer") or row.get("mock_answer") or ""
            expected = parse_expected(problem.answer_rubric)
            scored_row = {
                "id": row["id"],
                "condition": row.get("condition"),
                "model": row.get("model"),
                **score_answer(answer, expected),
            }
            scored.append(scored_row)
    total = sum(item["score"] for item in scored)
    summary = {
        "predictions": args.predictions,
        "n": len(scored),
        "score": total / len(scored) if scored else 0.0,
        "items": scored,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset-dir", default=str(DEFAULT_DATASET_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="BioMysteryBench preview runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    add_common(prepare)
    prepare.set_defaults(func=command_prepare)

    list_parser = subparsers.add_parser("list")
    add_common(list_parser)
    list_parser.set_defaults(func=command_list)

    prompt = subparsers.add_parser("prompt")
    add_common(prompt)
    prompt.add_argument("--id", required=True)
    prompt.add_argument("--condition", choices=["baseline", "fairy_tale"], default="baseline")
    prompt.add_argument("--preview-bytes", type=int, default=0)
    prompt.set_defaults(func=command_prompt)

    run = subparsers.add_parser("run")
    add_common(run)
    run.add_argument("--ids", nargs="+", default=["all"])
    run.add_argument("--condition", choices=["baseline", "fairy_tale"], required=True)
    run.add_argument("--model", default=DEFAULT_MODEL)
    run.add_argument("--effort", choices=["minimal", "low", "medium", "high"], default="medium")
    run.add_argument("--preview-bytes", type=int, default=0)
    run.add_argument("--timeout", type=int, default=0, help="HTTP timeout in seconds; 0 waits until the API returns")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--output")
    run.add_argument("--append", action="store_true")
    run.set_defaults(func=command_run)

    score = subparsers.add_parser("score")
    add_common(score)
    score.add_argument("--predictions", required=True)
    score.add_argument("--output")
    score.set_defaults(func=command_score)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
