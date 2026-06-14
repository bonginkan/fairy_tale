#!/usr/bin/env python3
"""Run a random HLE sample through Codex CLI with Fairy Tale enabled."""

from __future__ import annotations

import argparse
import asyncio
import base64
import copy
import json
import math
import os
import random
import re
import subprocess
from pathlib import Path
from typing import Any, Literal

import numpy as np
from datasets import load_dataset
from openai import AsyncOpenAI
from pydantic import BaseModel
from tqdm import tqdm
from tqdm.asyncio import tqdm_asyncio


JUDGE_PROMPT = """Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

[question]: {question}

[response]: {response}

Your judgement must be in the format and criteria specified below:

extracted_final_answer: The final exact answer extracted from the [response]. Put the extracted answer as 'None' if there is no exact, final answer to extract from the response.

[correct_answer]: {correct_answer}

reasoning: Explain why the extracted_final_answer is correct or incorrect based on [correct_answer], focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

correct: Answer 'yes' if extracted_final_answer matches the [correct_answer] given below, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect.

confidence: The extracted confidence score between 0% and 100% from [response]. Put 100 if there is no confidence score available."""


class ExtractedAnswer(BaseModel):
    extracted_final_answer: str
    reasoning: str
    correct: Literal["yes", "no"]
    confidence: int
    strict: Literal[True]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def dataset_rows(dataset_name: str) -> list[dict[str, Any]]:
    dataset = load_dataset(dataset_name, split="test").to_dict()
    return [dict(zip(dataset.keys(), values)) for values in zip(*dataset.values())]


def sample_rows(rows: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    indices = list(range(len(rows)))
    rng.shuffle(indices)
    selected = sorted(indices[:sample_size])
    return [rows[index] for index in selected]


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-") or "item"


def output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "Explanation": {"type": "string"},
            "Answer": {"type": "string"},
            "Confidence": {"type": "integer", "minimum": 0, "maximum": 100},
            "ToolUseSummary": {"type": "string"},
        },
        "required": ["Explanation", "Answer", "Confidence", "ToolUseSummary"],
    }


def decode_image(question: dict[str, Any], item_dir: Path) -> Path | None:
    image = question.get("image")
    if not image:
        return None
    if not isinstance(image, str) or not image.startswith("data:image/"):
        path = item_dir / "image-reference.txt"
        path.write_text(str(image), encoding="utf-8")
        return None
    header, encoded = image.split(",", 1)
    mime = header.split(";", 1)[0].removeprefix("data:")
    ext = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime, ".img")
    path = item_dir / f"image{ext}"
    path.write_bytes(base64.b64decode(encoded))
    return path


def write_prompt(question: dict[str, Any], item_dir: Path, has_image: bool) -> Path:
    prompt_path = item_dir / "prompt.md"
    hle_python = Path.cwd() / "tmp/hle-venv/bin/python"
    prompt_path.write_text(
        f"""Use the installed fairy-tale plugin and the fairy-tale-benchmark-feedback skill.
This is an HLE-style closed-ended benchmark item. You may use Codex tools for
calculation, local scratch work, and consistency checks when they materially
reduce uncertainty. Do not inspect hidden answers, dataset answer fields,
judge outputs, or benchmark scorer internals.

Return only the JSON object required by the output schema.

Answer contract:
- Explanation: concise derivation or evidence check.
- Answer: exact final answer, compact and grader-friendly.
- Confidence: integer 0-100.
- ToolUseSummary: short generic summary of tools/checks used, or "none".

Fairy Tale gates:
1. Classify subject, answer type, and exactness.
2. Isolate independent assumptions, variables, definitions, and answer choices.
3. Use the minimum derivation needed to justify the final closed-ended answer.
4. If confidence is high, run one compact contradiction check before finalizing.
5. Put the exact final answer in Answer; do not bury it in Explanation.

Tool budget:
- Use Codex tools when they materially reduce uncertainty, but keep them compact.
- Prefer direct calculation, symbolic checks, small scripts, and targeted web or
  file inspection over broad search.
- Do not run exhaustive parameter sweeps, long simulations, or many alternative
  reconstructions unless the problem explicitly requires them.
- Use non-interactive one-shot commands. Do not start commands that require
  later stdin writes or an interactive TTY.
- If tool evidence remains ambiguous after a compact check, state the best
  supported answer with calibrated confidence instead of escalating the search.
- If a Python calculation benefits from installed packages, use
  `{hle_python}` when that executable exists.

{"An image is attached to the initial prompt; inspect it when relevant." if has_image else "No image is attached."}

Question:
{question["question"]}
""",
        encoding="utf-8",
    )
    return prompt_path


def prediction_to_response(payload: dict[str, Any]) -> str:
    if "response" in payload:
        return str(payload["response"])
    if "raw_response" in payload:
        return str(payload["raw_response"])
    return str(payload.get("error", ""))


def codex_command(args: argparse.Namespace, item_dir: Path, schema_path: Path, output_path: Path, image_path: Path | None) -> list[str]:
    command = [
        *args.codex_cmd,
        "exec",
        "--ephemeral",
        "--sandbox",
        args.sandbox,
        "-m",
        args.model,
        "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"',
        "-c",
        'approval_policy="never"',
        "-c",
        "shell_environment_policy.inherit=all",
        "--cd",
        str(item_dir),
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
    ]
    if image_path is not None:
        command.extend(["--image", str(image_path)])
    command.append("-")
    return command


def build_prediction_payload(args: argparse.Namespace, output_path: Path, stdout_path: Path, stderr_path: Path, returncode: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": args.model,
        "condition": "fairy_tale_codex_tools",
        "returncode": returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "output_path": str(output_path),
    }
    if output_path.exists():
        raw = output_path.read_text(encoding="utf-8").strip()
        payload["raw_response"] = raw
        try:
            parsed = json.loads(raw)
            payload["parsed"] = parsed
            payload["response"] = (
                f"Explanation: {parsed.get('Explanation', '')}\n"
                f"Answer: {parsed.get('Answer', '')}\n"
                f"Confidence: {parsed.get('Confidence', 0)}%"
            )
            payload["tool_use_summary"] = parsed.get("ToolUseSummary", "")
        except json.JSONDecodeError:
            payload["error"] = "codex output was not valid JSON"
    else:
        payload["error"] = "missing codex output"
    if returncode != 0 and "error" not in payload:
        payload["error"] = f"codex exited with {returncode}"
    return payload


async def answer_one(question: dict[str, Any], args: argparse.Namespace, predictions: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    item_id = str(question["id"])
    if item_id in predictions:
        return None
    item_dir = args.run_dir / "items" / safe_name(item_id)
    item_dir.mkdir(parents=True, exist_ok=True)
    schema_path = item_dir / "answer.schema.json"
    output_path = item_dir / "answer.json"
    stdout_path = item_dir / "codex.stdout.log"
    stderr_path = item_dir / "codex.stderr.log"
    if output_path.exists():
        return item_id, build_prediction_payload(args, output_path, stdout_path, stderr_path, 0)
    write_json(schema_path, output_schema())
    image_path = decode_image(question, item_dir)
    prompt_path = write_prompt(question, item_dir, image_path is not None)
    prompt_text = prompt_path.read_text(encoding="utf-8")
    command = codex_command(args, item_dir, schema_path, output_path, image_path)
    env = os.environ.copy()
    if env.get("OPENAI_API_KEY") and not env.get("CODEX_API_KEY"):
        env["CODEX_API_KEY"] = env["OPENAI_API_KEY"]
    venv_bin = (Path("tmp/hle-venv/bin").resolve())
    if venv_bin.exists():
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
        env.setdefault("VIRTUAL_ENV", str(venv_bin.parent))
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            check=False,
            input=prompt_text,
            stdout=stdout,
            stderr=stderr,
            text=True,
            env=env,
        )
    return item_id, build_prediction_payload(args, output_path, stdout_path, stderr_path, result.returncode)


async def answer_all(rows: list[dict[str, Any]], args: argparse.Namespace, predictions: dict[str, Any]) -> dict[str, Any]:
    pending = [row for row in rows if row["id"] not in predictions]
    semaphore = asyncio.Semaphore(args.num_workers)

    async def bound(row: dict[str, Any]):
        async with semaphore:
            return await answer_one(row, args, predictions)

    tasks = [asyncio.create_task(bound(row)) for row in pending]
    for task in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
        result = await task
        if result is None:
            continue
        unique_id, payload = result
        predictions[unique_id] = payload
        write_json(args.predictions_path, predictions)
    return predictions


async def judge_one(client: AsyncOpenAI, question: dict[str, Any], prediction: dict[str, Any], args: argparse.Namespace) -> tuple[str, dict[str, Any]] | None:
    if "response" not in prediction:
        judged = copy.deepcopy(prediction)
        judged["judge_response"] = {
            "correct_answer": question["answer"],
            "model_answer": None,
            "reasoning": prediction.get("error", "missing response"),
            "correct": "no",
            "confidence": 0,
        }
        return question["id"], judged
    prompt = JUDGE_PROMPT.format(
        question=question["question"],
        correct_answer=question["answer"],
        response=prediction_to_response(prediction),
    )
    try:
        response = await client.beta.chat.completions.parse(
            model=args.judge_model,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            response_format=ExtractedAnswer,
        )
    except Exception as exc:
        judged = copy.deepcopy(prediction)
        judged["judge_error"] = repr(exc)
        return question["id"], judged
    content = response.choices[0].message.parsed
    judged = copy.deepcopy(prediction)
    judged["judge_response"] = {
        "correct_answer": question["answer"],
        "model_answer": content.extracted_final_answer,
        "reasoning": content.reasoning,
        "correct": content.correct,
        "confidence": content.confidence,
    }
    return question["id"], judged


async def judge_all(rows: list[dict[str, Any]], args: argparse.Namespace, predictions: dict[str, Any], judged: dict[str, Any]) -> dict[str, Any]:
    client = AsyncOpenAI(timeout=300.0, max_retries=1)
    by_id = {row["id"]: row for row in rows}
    pending_ids = [unique_id for unique_id in predictions if unique_id not in judged and unique_id in by_id]
    semaphore = asyncio.Semaphore(args.judge_workers)

    async def bound(unique_id: str):
        async with semaphore:
            return await judge_one(client, by_id[unique_id], predictions[unique_id], args)

    results = await tqdm_asyncio.gather(*[bound(unique_id) for unique_id in pending_ids])
    for result in results:
        if result is None:
            continue
        unique_id, payload = result
        judged[unique_id] = payload
        write_json(args.judged_path, judged)
    return judged


def metrics(judged: dict[str, Any]) -> dict[str, Any]:
    rows = [payload for payload in judged.values() if "judge_response" in payload]
    n = len(rows)
    correct = np.array(["yes" in row["judge_response"]["correct"] for row in rows], dtype=bool)
    confidence = np.array([row["judge_response"]["confidence"] for row in rows], dtype=float) / 100 if rows else np.array([])
    accuracy = float(correct.mean()) if n else 0.0
    half_width = 1.96 * math.sqrt(accuracy * (1.0 - accuracy) / n) if n else 0.0
    calibration_error = float(np.sqrt(np.mean((confidence - correct.astype(float)) ** 2))) if n else 0.0
    return {
        "n": n,
        "accuracy_pct": round(100 * accuracy, 2),
        "ci95_half_width_pct": round(100 * half_width, 2),
        "calibration_error_pct": round(100 * calibration_error, 2),
        "correct": int(correct.sum()) if n else 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="cais/hle")
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--judge-model", default="o3-mini-2025-01-31")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260618)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--judge-workers", type=int, default=4)
    parser.add_argument("--reasoning-effort", default="xhigh")
    parser.add_argument("--sandbox", default="danger-full-access")
    parser.add_argument("--codex-cmd", nargs="+", default=["npx", "--yes", "@openai/codex@latest"])
    parser.add_argument("--run-dir", type=Path, default=Path("tmp/hle-runs/gpt55-fairy-codex-tools-random-n100-20260618"))
    parser.add_argument("--answers-only", action="store_true")
    parser.add_argument("--judge-only", action="store_true")
    return parser


def run_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = dataset_rows(args.dataset)
    if args.sample_path.exists():
        sample_ids = [str(row["id"]) for row in json.loads(args.sample_path.read_text(encoding="utf-8"))]
        by_id = {str(row["id"]): row for row in rows}
        missing = [sample_id for sample_id in sample_ids if sample_id not in by_id]
        if missing:
            raise SystemExit(f"sample IDs not found in dataset: {missing[:5]}")
        return [by_id[sample_id] for sample_id in sample_ids]
    sampled = sample_rows(rows, args.sample_size, args.seed)
    write_json(args.sample_path, [{"id": row["id"]} for row in sampled])
    return sampled


def main() -> int:
    args = build_parser().parse_args()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    args.predictions_path = args.run_dir / "predictions.json"
    args.judged_path = args.run_dir / "judged.json"
    args.metrics_path = args.run_dir / "metrics.json"
    args.sample_path = args.run_dir / "sample-ids.json"
    rows = run_rows(args)
    predictions = load_json(args.predictions_path)
    judged = load_json(args.judged_path)
    if not args.judge_only:
        predictions = asyncio.run(answer_all(rows, args, predictions))
    if not args.answers_only:
        judged = asyncio.run(judge_all(rows, args, predictions, judged))
        result = metrics(judged)
        result.update(
            {
                "dataset": args.dataset,
                "model": args.model,
                "judge_model": args.judge_model,
                "sample_size": args.sample_size,
                "seed": args.seed,
                "condition": "fairy_tale_codex_tools",
                "codex_cmd": args.codex_cmd,
                "reasoning_effort": args.reasoning_effort,
            }
        )
        write_json(args.metrics_path, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
