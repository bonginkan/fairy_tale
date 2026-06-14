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

HLE_SUCCESS_PRACTICES = {
    "answer_contract_reproducibility": "For HLE-style closed-ended tasks, preserve a strict answer contract: exact final answer field, confidence, model, judge model, dataset, seed, and item-level judged artifact.",
    "compact_closed_form_before_explanation": "On successful HLE-style items, keep the final answer parseable and avoid burying it under optional explanation; use only the derivation needed to justify the closed-ended answer.",
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
    correct_count = sample_size - len(failed)
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
    success_practices = []
    if correct_count > 0:
        for practice_class, practice in HLE_SUCCESS_PRACTICES.items():
            success_practices.append(
                {
                    "id": f"hle-success-{practice_class}-v1",
                    "scope": "hle",
                    "failure_class": f"success:{practice_class}",
                    "rule": practice,
                    "status": "observed_success",
                    "evidence": [evidence_id("hle", args.judged), evidence_id("hle-metrics", args.metrics)],
                    "sample_size": sample_size,
                    "metrics": {
                        "before_all_pass_rate": accuracy,
                        "after_all_pass_rate": accuracy,
                        "success_count": correct_count,
                        "success_rate": accuracy,
                    },
                    "regression_count": 0,
                    "created_at": date.today().isoformat(),
                    "notes": "Observed success practice from correct HLE judged outputs. Keep only while future retry slices remain neutral or positive.",
                }
            )
    payload = {
        "source": "hle",
        "metrics": metrics,
        "failure_count": len(failed),
        "failure_classes": dict(sorted(counts.items())),
        "success_practices": success_practices,
        "rules": rules + success_practices,
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


EXPLOIT_RULES = {
    "coverage_only_plateau": "For ExploitBench V8 sandbox tasks, after basic coverage is reached, explicitly search for the shortest missing step from coverage to diff, sanitizer/crash signal, and controlled PC/ACE progression without using real-world exploit guidance.",
    "no_signal_timeout": "For ExploitBench V8 sandbox tasks with no capability signal by the turn budget midpoint, pivot from broad exploration to harness-visible instrumentation and minimal reproducible trigger discovery.",
}

EXPLOIT_SUCCESS_PRACTICES = {
    "sandbox_reproducibility": "For ExploitBench, preserve reproducibility through official sandbox IDs, seed, model, turn budget, cost cap, manifest, score artifact, and aggregate artifact before comparing runs.",
    "harness_visible_signal": "When an ExploitBench run makes progress, keep actions tied to official harness-visible capability signals rather than speculative exploit narratives.",
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
    success_practices = [
        {
            "id": "exploitbench-v8-success-sandbox_reproducibility-v1",
            "scope": "exploitbench-v8",
            "failure_class": "success:sandbox_reproducibility",
            "rule": EXPLOIT_SUCCESS_PRACTICES["sandbox_reproducibility"],
            "status": "observed_success",
            "evidence": args.evidence,
            "sample_size": len(scores),
            "metrics": {
                "before_all_pass_rate": 0.0,
                "after_all_pass_rate": 0.0,
                "mean_score": round(sum(scores) / len(scores), 4),
                "max_score": max(scores),
            },
            "regression_count": 0,
            "created_at": date.today().isoformat(),
            "notes": "Observed run-practice success. This is reproducibility feedback, not an ExploitBench capability claim.",
        }
    ]
    if any(value > 0 for value in scores):
        success_practices.append(
            {
                "id": "exploitbench-v8-success-harness_visible_signal-v1",
                "scope": "exploitbench-v8",
                "failure_class": "success:harness_visible_signal",
                "rule": EXPLOIT_SUCCESS_PRACTICES["harness_visible_signal"],
                "status": "observed_success",
                "evidence": args.evidence,
                "sample_size": len(scores),
                "metrics": {
                    "before_all_pass_rate": 0.0,
                    "after_all_pass_rate": 0.0,
                    "mean_score": round(sum(scores) / len(scores), 4),
                    "positive_signal_count": sum(1 for value in scores if value > 0),
                },
                "regression_count": 0,
                "created_at": date.today().isoformat(),
                "notes": "Observed success practice from positive official sandbox score. Keep defensive-only and sandbox-bound.",
            }
        )
    payload = {
        "source": "exploitbench-v8",
        "scores": scores,
        "failure_classes": dict(sorted(counts.items())),
        "success_practices": success_practices,
        "rules": rules + success_practices,
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


SWE_RULES = {
    "existing_behavior_regression": "For SWE-style patches, preserve existing visible behavior unless the requirement explicitly deprecates it. Before finalizing, inspect and run adjacent existing tests that encode old behavior; if a new priority rule appears to conflict, implement it narrowly instead of replacing the old invariant.",
    "missing_public_interface": "When a SWE task names a new function, type, method, or helper path, verify the exact symbol is exported or otherwise importable from that path, and run at least one targeted check that imports or calls the public interface exactly as specified.",
    "self_selected_validation_gap": "For SWE-style patches, do not rely only on self-selected focused tests. After editing, run or inspect the benchmark-selected adjacent tests for every touched helper/API surface, plus one compatibility test that covers prior behavior when available.",
    "scorer_failure_general": "For SWE-style patches, convert each scorer failure into a concrete interface, behavior, or validation-gap hypothesis before retrying; avoid broad rewrites that are not tied to the failing assertion.",
}

SWE_SUCCESS_PRACTICES = {
    "local_invariant_mapping": "For SWE-style patches, first map existing helpers, types, call sites, and adjacent tests, then reuse local abstractions instead of introducing a parallel mechanism.",
    "targeted_container_validation": "For SWE-style patches, validate inside the benchmark container with focused tests that exercise the touched surface and record exact commands and outputs.",
    "named_interface_completion": "When a SWE patch succeeds with named new interfaces, preserve the practice of implementing the exact requested symbol at the requested path while keeping backward-compatible wrappers when existing callers rely on them.",
}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def classify_swe_failure(instance_id: str, output_payload: dict[str, Any], stdout: str, stderr: str) -> str:
    text = "\n".join([instance_id, json.dumps(output_payload, sort_keys=True), stdout, stderr]).lower()
    if "is not a function" in text or "undefined is not a function" in text or "not exported" in text:
        return "missing_public_interface"
    if "expected" in text and "to equal" in text:
        return "existing_behavior_regression"
    if "passed" in text and "failed" in text:
        return "self_selected_validation_gap"
    return "scorer_failure_general"


def swe_bench_pro(args: argparse.Namespace) -> int:
    eval_results = load_json(args.eval_results)
    if not isinstance(eval_results, dict):
        raise SystemExit("--eval-results must be a JSON object mapping instance_id to boolean")

    sample_size = len(eval_results)
    passed = sum(1 for value in eval_results.values() if value is True)
    accuracy = passed / sample_size if sample_size else 0.0
    failed_ids = [str(instance_id) for instance_id, ok in eval_results.items() if ok is not True]
    passed_ids = [str(instance_id) for instance_id, ok in eval_results.items() if ok is True]

    counts = Counter()
    evidence_by_class: dict[str, list[str]] = {}
    for instance_id in failed_ids:
        instance_dir = args.eval_dir / instance_id
        output_path = instance_dir / f"{args.prefix}_output.json"
        stdout_path = instance_dir / f"{args.prefix}_stdout.log"
        stderr_path = instance_dir / f"{args.prefix}_stderr.log"
        try:
            output_payload = load_json(output_path)
        except (FileNotFoundError, json.JSONDecodeError):
            output_payload = {}
        failure_class = classify_swe_failure(
            instance_id=instance_id,
            output_payload=output_payload if isinstance(output_payload, dict) else {},
            stdout=read_text(stdout_path),
            stderr=read_text(stderr_path),
        )
        counts[failure_class] += 1
        evidence_by_class.setdefault(failure_class, []).extend(
            [
                evidence_id("swe-output", output_path),
                evidence_id("swe-stdout", stdout_path),
                evidence_id("swe-stderr", stderr_path),
            ]
        )

    rules = []
    for failure_class, count in sorted(counts.items()):
        rules.append(
            {
                "id": f"swe-bench-pro-{failure_class}-v1",
                "scope": "swe-bench-pro",
                "failure_class": failure_class,
                "rule": SWE_RULES[failure_class],
                "status": "candidate",
                "evidence": evidence_by_class.get(failure_class, []),
                "sample_size": sample_size,
                "metrics": {
                    "before_all_pass_rate": accuracy,
                    "after_all_pass_rate": accuracy,
                    "failure_count": count,
                    "failure_rate": round(count / sample_size, 4) if sample_size else 0.0,
                },
                "regression_count": 0,
                "created_at": date.today().isoformat(),
                "notes": "Candidate generated from SWE-Bench Pro scorer artifacts. Promote only after a held-out retry improves pass rate without benchmark-specific hardcoding.",
            }
        )
    success_evidence = []
    for instance_id in passed_ids:
        instance_dir = args.eval_dir / instance_id
        success_evidence.extend(
            [
                evidence_id("swe-output", instance_dir / f"{args.prefix}_output.json"),
                evidence_id("swe-stdout", instance_dir / f"{args.prefix}_stdout.log"),
                evidence_id("swe-stderr", instance_dir / f"{args.prefix}_stderr.log"),
                evidence_id("swe-patch", instance_dir / f"{args.prefix}_patch.diff"),
            ]
        )
    success_practices = []
    if passed_ids:
        for practice_class, practice in SWE_SUCCESS_PRACTICES.items():
            success_practices.append(
                {
                    "id": f"swe-bench-pro-success-{practice_class}-v1",
                    "scope": "swe-bench-pro",
                    "failure_class": f"success:{practice_class}",
                    "rule": practice,
                    "status": "observed_success",
                    "evidence": success_evidence,
                    "sample_size": sample_size,
                    "metrics": {
                        "before_all_pass_rate": accuracy,
                        "after_all_pass_rate": accuracy,
                        "success_count": len(passed_ids),
                        "success_rate": round(len(passed_ids) / sample_size, 4) if sample_size else 0.0,
                    },
                    "regression_count": 0,
                    "created_at": date.today().isoformat(),
                    "notes": "Observed success practice from SWE-Bench Pro passed instances. Keep only while held-out retry slices remain neutral or positive.",
                }
            )

    payload = {
        "source": "swe-bench-pro",
        "eval_results": eval_results,
        "sample_size": sample_size,
        "passed": passed,
        "failed": len(failed_ids),
        "accuracy": accuracy,
        "failure_classes": dict(sorted(counts.items())),
        "success_practices": success_practices,
        "rules": rules + success_practices,
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

    swe_parser = subparsers.add_parser("swe-bench-pro")
    swe_parser.add_argument("--eval-results", type=Path, required=True)
    swe_parser.add_argument("--eval-dir", type=Path, required=True)
    swe_parser.add_argument("--prefix", default="gpt-5.5-fairy-tale-codex")
    swe_parser.add_argument("--output", type=Path, required=True)
    swe_parser.set_defaults(func=swe_bench_pro)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
