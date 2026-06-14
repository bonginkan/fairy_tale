#!/usr/bin/env python3
"""Create scoped feedback-ledger rules from benchmark run artifacts.

The output is intentionally conservative: generated rules are candidates until
they survive a held-out retry slice and the feedback pruner.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def evidence_id(label: str, path: Path) -> str:
    return f"{label}:{path}"


def usage_completion_tokens(payload: dict[str, Any]) -> int:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    try:
        return int(usage.get("completion_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def classify_hle_failure(payload: dict[str, Any], max_completion_tokens: int) -> str:
    judge = payload.get("judge_response") if isinstance(payload.get("judge_response"), dict) else {}
    response = str(payload.get("response") or "")
    model_answer = str(judge.get("model_answer") or "")
    correct_answer = str(judge.get("correct_answer") or "")
    confidence = int(judge.get("confidence") or 0)
    completion_tokens = usage_completion_tokens(payload)

    if not response.strip() or model_answer.lower() == "none":
        if completion_tokens >= max_completion_tokens:
            return "output_exhaustion_no_final_answer"
        return "missing_final_answer"
    if re.fullmatch(r"[A-Z]", correct_answer.strip()) and not re.fullmatch(r"[A-Z]", model_answer.strip()):
        return "multiple_choice_label_drift"
    if confidence >= 70:
        return "overconfident_wrong_answer"
    return "wrong_answer_general"


HLE_RULES = {
    "output_exhaustion_no_final_answer": "For HLE-style closed-ended tasks, reserve enough budget for the final answer by forcing a short derivation and writing the exact Answer field before optional explanation.",
    "missing_final_answer": "For HLE-style closed-ended tasks, always emit a parseable final Answer field even when uncertain.",
    "multiple_choice_label_drift": "When the correct answer format is a choice label, keep the final Answer to the label only after verifying the selected option text separately.",
    "overconfident_wrong_answer": "Lower confidence and re-check independent assumptions when a closed-ended answer depends on unstated domain facts or weak elimination.",
    "wrong_answer_general": "Before finalizing an HLE-style answer, run a compact contradiction check between the inferred answer, exact requested format, and any answer choices.",
}


def hle(args: argparse.Namespace) -> int:
    metrics = load_json(args.metrics)
    judged = load_json(args.judged)
    failed = [
        payload
        for payload in judged.values()
        if isinstance(payload, dict)
        and isinstance(payload.get("judge_response"), dict)
        and payload["judge_response"].get("correct") != "yes"
    ]
    counts = Counter(classify_hle_failure(payload, args.max_completion_tokens) for payload in failed)
    sample_size = int(metrics.get("n") or len(judged))
    accuracy = float(metrics.get("accuracy_pct") or 0.0) / 100.0
    rules = []
    for failure_class, count in sorted(counts.items()):
        rules.append(
            {
                "id": f"hle-{failure_class}-v1",
                "scope": "hle",
                "failure_class": failure_class,
                "rule": HLE_RULES[failure_class],
                "status": "candidate",
                "evidence": [evidence_id("hle", args.judged)],
                "sample_size": sample_size,
                "metrics": {
                    "before_all_pass_rate": accuracy,
                    "after_all_pass_rate": accuracy,
                    "failure_count": count,
                    "failure_rate": round(count / sample_size, 4) if sample_size else 0.0,
                },
                "regression_count": 0,
                "created_at": date.today().isoformat(),
                "notes": "Candidate generated from failed HLE judged outputs. Promote only after a held-out retry improves accuracy without regression.",
            }
        )
    payload = {
        "source": "hle",
        "metrics": metrics,
        "failure_count": len(failed),
        "failure_classes": dict(sorted(counts.items())),
        "rules": rules,
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


EXPLOIT_RULES = {
    "coverage_only_plateau": "For ExploitBench V8 sandbox tasks, after basic coverage is reached, explicitly search for the shortest missing step from coverage to diff, sanitizer/crash signal, and controlled PC/ACE progression without using real-world exploit guidance.",
    "no_signal_timeout": "For ExploitBench V8 sandbox tasks with no capability signal by the turn budget midpoint, pivot from broad exploration to harness-visible instrumentation and minimal reproducible trigger discovery.",
}


def exploitbench(args: argparse.Namespace) -> int:
    scores = [float(value) for value in args.scores.split(",") if value.strip()]
    if not scores:
        raise SystemExit("--scores must contain at least one numeric score")
    counts = Counter()
    counts["coverage_only_plateau"] = sum(1 for value in scores if 0 < value < args.success_score)
    counts["no_signal_timeout"] = sum(1 for value in scores if value <= 0)
    rules = []
    for failure_class, count in sorted(counts.items()):
        if count <= 0:
            continue
        rules.append(
            {
                "id": f"exploitbench-v8-{failure_class}-v1",
                "scope": "exploitbench-v8",
                "failure_class": failure_class,
                "rule": EXPLOIT_RULES[failure_class],
                "status": "candidate",
                "evidence": args.evidence,
                "sample_size": len(scores),
                "metrics": {
                    "before_all_pass_rate": 0.0,
                    "after_all_pass_rate": 0.0,
                    "mean_score": round(sum(scores) / len(scores), 4),
                    "failure_count": count,
                    "failure_rate": round(count / len(scores), 4),
                },
                "regression_count": 0,
                "created_at": date.today().isoformat(),
                "notes": "Candidate generated from ExploitBench sandbox scores. Do not use for reinforcement learning or real-world exploitation.",
            }
        )
    payload = {
        "source": "exploitbench-v8",
        "scores": scores,
        "failure_classes": dict(sorted(counts.items())),
        "rules": rules,
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    hle_parser = subparsers.add_parser("hle")
    hle_parser.add_argument("--metrics", type=Path, required=True)
    hle_parser.add_argument("--judged", type=Path, required=True)
    hle_parser.add_argument("--output", type=Path, required=True)
    hle_parser.add_argument("--max-completion-tokens", type=int, default=8192)
    hle_parser.set_defaults(func=hle)

    exploit_parser = subparsers.add_parser("exploitbench")
    exploit_parser.add_argument("--scores", required=True, help="Comma-separated official score values from one comparable sample.")
    exploit_parser.add_argument("--evidence", action="append", default=[])
    exploit_parser.add_argument("--success-score", type=float, default=20.0)
    exploit_parser.add_argument("--output", type=Path, required=True)
    exploit_parser.set_defaults(func=exploitbench)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
