#!/usr/bin/env python3
"""Score trace-only Agentic Loop evaluation artifacts.

This Phase 1 harness does not run models or hidden validators. It joins
controller traces with separate ground-truth verdicts, derives mechanism
effects from pre/post state diffs, and reports headroom-only recovery metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "agentic_loop_eval.v1"
ARMS = ("control", "static_ledger", "placebo_loop", "agentic_loop")
POLARITIES = {"positive", "negative"}
REQUIRED_BUDGET_FIELDS = (
    "max_iterations",
    "max_prompt_tokens",
    "max_completion_tokens",
    "max_elapsed_seconds",
    "max_cost_estimate",
)
BUDGET_PARITY_FIELDS = REQUIRED_BUDGET_FIELDS + ("allowed_actions",)
EXTERNAL_OBSERVATION_SOURCES = {
    "command",
    "command_output",
    "diff",
    "file",
    "file_hit",
    "grep",
    "grep_hit",
    "log",
    "replay",
    "runtime",
    "runtime_error",
    "screenshot",
    "search",
    "test",
    "test_failure",
    "validator",
    "validator_output",
}
FORBIDDEN_TRACE_FIELDS = {
    "changed_belief",
    "changed_strategy_after_observation",
    "decisive_for_recovery",
    "ground_truth_verified_pass",
    "quality_score",
    "scored_observation_effects",
    "state_diff_changed_answer_or_action",
    "verified_pass",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise SystemExit(f"missing file: {path}") from None
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL {path}:{line_number}: {exc}") from None
        if not isinstance(row, dict):
            raise SystemExit(f"JSONL row must be an object: {path}:{line_number}")
        rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "passed", "pass"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any, default: float = 0.0) -> float:
    parsed = as_optional_float(value)
    return default if parsed is None else parsed


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_id(seed: int, task_id: str, arm: str) -> str:
    digest = hashlib.sha256(f"{seed}:{task_id}:{arm}".encode("utf-8")).hexdigest()
    return f"al-{digest[:16]}"


def require_text(row: dict[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return value


def load_key(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise SystemExit(f"invalid key file: {path}")
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SystemExit(f"key row must be an object: {index}")
        blind_id = require_text(row, "blind_id", f"key[{index}]")
        task_id = require_text(row, "task_id", f"key[{index}]")
        arm = require_text(row, "arm", f"key[{index}]")
        if arm not in ARMS:
            raise SystemExit(f"key[{index}].arm must be one of {ARMS}")
        polarity = require_text(row, "polarity", f"key[{index}]")
        if polarity not in POLARITIES:
            raise SystemExit(f"key[{index}].polarity must be one of {sorted(POLARITIES)}")
        budgets = row.get("budgets", {})
        if budgets is None:
            budgets = {}
        if not isinstance(budgets, dict):
            raise SystemExit(f"key[{index}].budgets must be an object")
        result[blind_id] = {**row, "budgets": budgets, "task_id": task_id, "arm": arm, "polarity": polarity}
    return result


def load_verdicts(path: Path) -> dict[str, dict[str, Any]]:
    verdicts: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(read_jsonl(path), start=1):
        blind_id = require_text(row, "blind_id", f"verdict[{index}]")
        if "verified_pass" not in row:
            raise SystemExit(f"verdict[{index}].verified_pass is required")
        if blind_id in verdicts:
            raise SystemExit(f"duplicate verdict blind_id: {blind_id}")
        verdicts[blind_id] = row
    return verdicts


def forbidden_paths(value: Any, path: str = "$") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_TRACE_FIELDS:
                paths.append(child_path)
            paths.extend(forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(forbidden_paths(child, f"{path}[{index}]"))
    return paths


def has_required_budget(budgets: dict[str, Any]) -> bool:
    return all(as_optional_float(budgets.get(field)) is not None for field in REQUIRED_BUDGET_FIELDS)


def within_optional_budget(value: float, limit: Any) -> bool:
    parsed = as_optional_float(limit)
    return parsed is None or value <= parsed


def first_numeric(*values: Any) -> float | None:
    for value in values:
        parsed = as_optional_float(value)
        if parsed is not None:
            return parsed
    return None


def iteration_state_diff(iteration: dict[str, Any]) -> bool:
    pre_state = iteration.get("pre_state")
    post_state = iteration.get("post_state")
    if pre_state is not None or post_state is not None:
        return canonical(pre_state) != canonical(post_state)
    comparisons = (
        ("pre_observation_answer", "post_observation_answer"),
        ("pre_observation_action", "post_observation_action"),
        ("pre_action", "post_action"),
        ("pre_answer", "post_answer"),
    )
    for before_field, after_field in comparisons:
        if before_field in iteration or after_field in iteration:
            if canonical(iteration.get(before_field)) != canonical(iteration.get(after_field)):
                return True
    return False


def source_is_external(source: Any) -> bool:
    if not isinstance(source, str):
        return False
    return source.strip().lower() in EXTERNAL_OBSERVATION_SOURCES


def derive_observation_effects(iterations: list[Any]) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    for index, raw_iteration in enumerate(iterations, start=1):
        if not isinstance(raw_iteration, dict):
            continue
        observation = raw_iteration.get("observation")
        if not isinstance(observation, dict):
            observation = {}
        effects.append(
            {
                "iteration_index": int(raw_iteration.get("index") or index),
                "observation_source": observation.get("source"),
                "external_observation": source_is_external(observation.get("source")),
                "state_diff_changed_answer_or_action": iteration_state_diff(raw_iteration),
                "decisive_for_recovery": False,
            }
        )
    return effects


def trace_final(trace: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    final = trace.get("final")
    if isinstance(final, dict):
        return final
    row_final = row.get("final")
    return row_final if isinstance(row_final, dict) else {}


def normalize_trace(row: dict[str, Any], verdict: dict[str, Any], key: dict[str, Any]) -> dict[str, Any]:
    forbidden = forbidden_paths(row)
    if forbidden:
        raise ValueError(
            "trace rows must not contain model-scored mechanism or GT fields: "
            + ", ".join(forbidden[:8])
        )
    trace = row.get("trace") if isinstance(row.get("trace"), dict) else row
    iterations = trace.get("iterations") if isinstance(trace.get("iterations"), list) else []
    usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
    final = trace_final(trace, row)
    prompt_tokens_raw = first_numeric(row.get("prompt_tokens"), usage.get("prompt_tokens"))
    completion_tokens_raw = first_numeric(row.get("completion_tokens"), usage.get("completion_tokens"))
    prompt_tokens = int(prompt_tokens_raw) if prompt_tokens_raw is not None else None
    completion_tokens = int(completion_tokens_raw) if completion_tokens_raw is not None else None
    elapsed_seconds = first_numeric(row.get("elapsed_seconds"), usage.get("elapsed_seconds"))
    cost_estimate = first_numeric(
        row.get("cost_estimate"),
        row.get("cost_estimate_usd"),
        row.get("cost_usd"),
        usage.get("cost_estimate"),
        usage.get("cost_estimate_usd"),
        usage.get("cost_usd"),
    )
    budgets = key.get("budgets") if isinstance(key.get("budgets"), dict) else {}
    budget_complete = has_required_budget(budgets)
    usage_complete = (
        prompt_tokens is not None
        and completion_tokens is not None
        and elapsed_seconds is not None
        and cost_estimate is not None
    )
    within_budget = budget_complete and (
        len(iterations) <= int(as_float(budgets.get("max_iterations"), 0.0))
        and usage_complete
        and within_optional_budget(float(prompt_tokens), budgets.get("max_prompt_tokens"))
        and within_optional_budget(float(completion_tokens), budgets.get("max_completion_tokens"))
        and within_optional_budget(float(elapsed_seconds), budgets.get("max_elapsed_seconds"))
        and within_optional_budget(cost_estimate, budgets.get("max_cost_estimate"))
    )
    effects = derive_observation_effects(iterations)
    has_external_state_diff = any(
        effect["external_observation"] and effect["state_diff_changed_answer_or_action"]
        for effect in effects
    )
    verified_pass = as_bool(verdict.get("verified_pass"))
    claimed_success = as_bool(final.get("claimed_success", row.get("claimed_success")))
    total_tokens = prompt_tokens + completion_tokens if usage_complete else None
    quality_score = as_float(verdict.get("quality_score"), 1.0 if verified_pass else 0.0)
    return {
        **key,
        "claimed_success": claimed_success,
        "verified_pass": verified_pass,
        "false_success": claimed_success and not verified_pass,
        "budget_complete": budget_complete,
        "usage_complete": usage_complete,
        "budgeted_verified_pass": verified_pass and within_budget,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "elapsed_seconds": elapsed_seconds,
        "cost_estimate": cost_estimate,
        "cost_estimate_present": cost_estimate is not None,
        "usage_fields_present": usage_complete,
        "quality_score": quality_score,
        "quality_per_token": quality_score / total_tokens if total_tokens is not None and total_tokens > 0 else None,
        "iterations_used": len(iterations),
        "stop_reason": str(final.get("stop_reason", "")),
        "repeated_failure_stop": final.get("stop_reason") == "repeated_failure",
        "scored_observation_effects": effects,
        "has_external_state_diff": has_external_state_diff,
        "changed_strategy_after_observation": has_external_state_diff,
        "validator": verdict.get("validator", ""),
    }


def rate(rows: list[dict[str, Any]], field: str) -> float | None:
    if not rows:
        return None
    return sum(1 for row in rows if row.get(field)) / len(rows)


def mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [row.get(field) for row in rows if isinstance(row.get(field), (int, float))]
    if not values:
        return None
    return sum(float(value) for value in values) / len(values)


def exact_mcnemar_p(win_a: int, win_b: int) -> float | None:
    discordant = win_a + win_b
    if discordant == 0:
        return None
    tail = sum(math.comb(discordant, k) for k in range(0, min(win_a, win_b) + 1)) / (2**discordant)
    return min(1.0, 2 * tail)


def bootstrap_ci(deltas: list[float], seed: int, samples: int = 2000) -> dict[str, float] | None:
    if not deltas:
        return None
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(samples):
        draw = [rng.choice(deltas) for _ in deltas]
        values.append(sum(draw) / len(draw))
    values.sort()
    low = values[int(0.025 * (samples - 1))]
    high = values[int(0.975 * (samples - 1))]
    return {"low": low, "high": high}


def group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['polarity']}:{row['arm']}"].append(row)
    return grouped


def grouped_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, group in sorted(group_rows(rows).items()):
        summary[key] = {
            "n": len(group),
            "verified_pass_rate": rate(group, "verified_pass"),
            "budgeted_verified_pass_rate": rate(group, "budgeted_verified_pass"),
            "false_success_claim_rate": rate(group, "false_success"),
            "changed_strategy_after_observation_rate": rate(group, "changed_strategy_after_observation"),
            "repeated_failure_stop_rate": rate(group, "repeated_failure_stop"),
            "mean_iterations_used": mean(group, "iterations_used"),
            "mean_total_tokens": mean(group, "total_tokens"),
            "mean_elapsed_seconds": mean(group, "elapsed_seconds"),
            "mean_cost_estimate": mean(group, "cost_estimate"),
            "mean_quality_score": mean(group, "quality_score"),
            "mean_quality_per_token": mean(group, "quality_per_token"),
            "budget_missing_count": sum(1 for row in group if not row.get("budget_complete")),
            "usage_missing_count": sum(1 for row in group if not row.get("usage_complete")),
            "cost_estimate_missing_count": sum(1 for row in group if not row.get("cost_estimate_present")),
        }
    return summary


def tasks_by_arm(rows: list[dict[str, Any]], polarity: str = "positive") -> dict[str, dict[str, dict[str, Any]]]:
    by_task: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row.get("polarity") == polarity:
            by_task[row["task_id"]][row["arm"]] = row
    return {task_id: arms for task_id, arms in by_task.items() if "control" in arms}


def complete_paired_tasks(
    rows: list[dict[str, Any]], task_ids: set[str], polarity: str = "positive"
) -> dict[str, dict[str, dict[str, Any]]]:
    by_task: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row.get("polarity") == polarity and row["task_id"] in task_ids:
            by_task[row["task_id"]][row["arm"]] = row
    return {task_id: arms for task_id, arms in by_task.items() if all(arm in arms for arm in ARMS)}


def headroom_task_ids(rows: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for task_id, arms in tasks_by_arm(rows, "positive").items():
        control = arms["control"]
        if (not control.get("verified_pass")) or control.get("false_success"):
            ids.add(task_id)
    return ids


def paired_contrast(
    tasks: dict[str, dict[str, dict[str, Any]]],
    metric: str,
    arm_a: str,
    arm_b: str,
    seed: int,
) -> dict[str, Any]:
    deltas: list[float] = []
    a_wins = b_wins = 0
    binary_metric = True
    for arms in tasks.values():
        a_value_raw = arms[arm_a].get(metric)
        b_value_raw = arms[arm_b].get(metric)
        binary_metric = binary_metric and isinstance(a_value_raw, bool) and isinstance(b_value_raw, bool)
        a_value = as_float(a_value_raw, 0.0)
        b_value = as_float(b_value_raw, 0.0)
        deltas.append(a_value - b_value)
        if a_value > b_value:
            a_wins += 1
        elif b_value > a_value:
            b_wins += 1
    return {
        "arm_a": arm_a,
        "arm_b": arm_b,
        "metric": metric,
        "n_paired_tasks": len(tasks),
        "mean_delta": sum(deltas) / len(deltas) if deltas else None,
        "bootstrap_ci": bootstrap_ci(deltas, seed),
        "mcnemar_p": exact_mcnemar_p(a_wins, b_wins) if binary_metric else None,
        "discordant": {f"{arm_a}_wins": a_wins, f"{arm_b}_wins": b_wins},
    }


def headroom_summary(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    ids = headroom_task_ids(rows)
    tasks = complete_paired_tasks(rows, ids, "positive")
    headroom_rows = [row for row in rows if row["task_id"] in ids and row["polarity"] == "positive"]
    for row in headroom_rows:
        recovered = bool(row.get("verified_pass"))
        if recovered and row.get("has_external_state_diff"):
            for effect in row["scored_observation_effects"]:
                if effect["external_observation"] and effect["state_diff_changed_answer_or_action"]:
                    effect["decisive_for_recovery"] = True
                    break
    by_arm = {arm: [row for row in headroom_rows if row["arm"] == arm] for arm in ARMS}
    metrics: dict[str, Any] = {}
    for arm, group in by_arm.items():
        decisive_count = sum(
            1
            for row in group
            if row.get("verified_pass")
            and any(effect.get("decisive_for_recovery") for effect in row["scored_observation_effects"])
        )
        metrics[arm] = {
            "n": len(group),
            "headroom_recovery_rate": rate(group, "verified_pass"),
            "false_success_claim_rate": rate(group, "false_success"),
            "budgeted_verified_pass_rate": rate(group, "budgeted_verified_pass"),
            "decisive_external_observation_recovery_count": decisive_count,
        }
    contrasts: dict[str, Any] = {}
    for index, (arm_a, arm_b) in enumerate(
        (
            ("agentic_loop", "control"),
            ("agentic_loop", "placebo_loop"),
            ("agentic_loop", "static_ledger"),
            ("placebo_loop", "control"),
        )
    ):
        contrasts[f"{arm_a}_vs_{arm_b}"] = paired_contrast(
            tasks, "verified_pass", arm_a, arm_b, seed + index
        )
    return {
        "task_ids": sorted(ids),
        "n_headroom_tasks": len(ids),
        "n_complete_paired_headroom_tasks": len(tasks),
        "by_arm": metrics,
        "contrasts": contrasts,
    }


def non_headroom_positive_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    headroom_ids = headroom_task_ids(rows)
    positive_tasks = tasks_by_arm(rows, "positive")
    ids = {task_id for task_id in positive_tasks if task_id not in headroom_ids}
    selected_rows = [row for row in rows if row["task_id"] in ids and row["polarity"] == "positive"]
    by_arm = {arm: [row for row in selected_rows if row["arm"] == arm] for arm in ARMS}
    metrics: dict[str, Any] = {}
    for arm, group in by_arm.items():
        metrics[arm] = {
            "n": len(group),
            "verified_pass_rate": rate(group, "verified_pass"),
            "budgeted_verified_pass_rate": rate(group, "budgeted_verified_pass"),
            "false_success_claim_rate": rate(group, "false_success"),
            "mean_iterations_used": mean(group, "iterations_used"),
            "mean_cost_estimate": mean(group, "cost_estimate"),
        }
    return {
        "task_ids": sorted(ids),
        "n_non_headroom_positive_tasks": len(ids),
        "by_arm": metrics,
    }


def budget_parity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    by_task: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_task[row["task_id"]][row["arm"]] = row
    for task_id, arms in sorted(by_task.items()):
        if "placebo_loop" not in arms or "agentic_loop" not in arms:
            continue
        placebo_budget = arms["placebo_loop"].get("budgets", {})
        agentic_budget = arms["agentic_loop"].get("budgets", {})
        for field in BUDGET_PARITY_FIELDS:
            if canonical(placebo_budget.get(field)) != canonical(agentic_budget.get(field)):
                issues.append(
                    {
                        "task_id": task_id,
                        "field": field,
                        "placebo_loop": placebo_budget.get(field),
                        "agentic_loop": agentic_budget.get(field),
                    }
                )
    return {"passed": not issues, "issues": issues}


def missing_total(summary: dict[str, Any], field: str, prefix: str | None = None) -> int | None:
    grouped = summary.get("grouped") if isinstance(summary.get("grouped"), dict) else {}
    total = 0
    matched = False
    for group_key, group in grouped.items():
        if prefix is not None and not str(group_key).startswith(prefix):
            continue
        if not isinstance(group, dict) or not isinstance(group.get(field), int):
            return None
        total += group[field]
        matched = True
    return total if matched else None


def score(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    verdicts = load_verdicts(args.verdicts)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for trace in read_jsonl(args.traces):
        blind_id = str(trace.get("blind_id", ""))
        if blind_id not in key:
            missing.append(blind_id or "<missing>")
            continue
        if blind_id not in verdicts:
            missing.append(f"{blind_id}:verdict")
            continue
        try:
            rows.append(normalize_trace(trace, verdicts[blind_id], key[blind_id]))
        except ValueError as exc:
            raise SystemExit(f"{blind_id}: {exc}") from None
    if missing:
        raise SystemExit(f"missing or unknown blind_id values: {', '.join(missing[:5])}")

    grouped = grouped_summary(rows)
    headroom = headroom_summary(rows, args.seed)
    non_headroom = non_headroom_positive_summary(rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "n_results": len(rows),
        "arms": list(ARMS),
        "grouped": grouped,
        "headroom": headroom,
        "non_headroom_positive": non_headroom,
        "budget_parity": budget_parity(rows),
        "cost_estimates_complete": missing_total({"grouped": grouped}, "cost_estimate_missing_count") == 0,
        "usage_fields_complete": missing_total({"grouped": grouped}, "usage_missing_count") == 0,
        "budget_fields_complete": missing_total({"grouped": grouped}, "budget_missing_count") == 0,
        "scored_rows": rows if args.include_rows else None,
        "interpretation_guard": (
            "Primary evidence is headroom recovery on control-failed positive tasks. "
            "Mechanism fields are scorer-derived from external observations and pre/post state diffs."
        ),
    }
    if not args.include_rows:
        del summary["scored_rows"]
    write_json(args.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def binomial_pmf(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def positive_exact_power(n_tasks: int, discordant_rate: float, win_rate: float, alpha: float) -> float:
    if n_tasks <= 0 or discordant_rate <= 0 or win_rate <= 0.5:
        return 0.0
    power = 0.0
    for discordant in range(1, n_tasks + 1):
        p_discordant = binomial_pmf(n_tasks, discordant, discordant_rate)
        reject_given_discordant = 0.0
        for arm_a_wins in range(0, discordant + 1):
            arm_b_wins = discordant - arm_a_wins
            p_value = exact_mcnemar_p(arm_a_wins, arm_b_wins)
            if arm_a_wins > arm_b_wins and p_value is not None and p_value <= alpha:
                reject_given_discordant += binomial_pmf(discordant, arm_a_wins, win_rate)
        power += p_discordant * reject_given_discordant
    return power


def power(args: argparse.Namespace) -> int:
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    headroom = summary.get("headroom") if isinstance(summary.get("headroom"), dict) else {}
    contrast = (headroom.get("contrasts") or {}).get(args.contrast)
    if not isinstance(contrast, dict):
        raise SystemExit(f"missing headroom contrast in summary: {args.contrast}")
    discordant = contrast.get("discordant") if isinstance(contrast.get("discordant"), dict) else {}
    arm_a = contrast.get("arm_a")
    arm_b = contrast.get("arm_b")
    arm_a_wins = int(discordant.get(f"{arm_a}_wins") or 0)
    arm_b_wins = int(discordant.get(f"{arm_b}_wins") or 0)
    n_paired = int(contrast.get("n_paired_tasks") or 0)
    total_discordant = arm_a_wins + arm_b_wins
    if n_paired <= 0 or total_discordant <= 0:
        payload = {
            "ok": False,
            "reason": "smoke summary has no paired discordant headroom outcomes",
            "contrast": args.contrast,
            "headroom_n": n_paired,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    discordant_rate = total_discordant / n_paired
    win_rate = arm_a_wins / total_discordant
    required_n = None
    achieved_power = 0.0
    for n_tasks in range(args.min_n, args.max_n + 1):
        achieved_power = positive_exact_power(n_tasks, discordant_rate, win_rate, args.alpha)
        if achieved_power >= args.target_power:
            required_n = n_tasks
            break
    payload = {
        "ok": required_n is not None,
        "contrast": args.contrast,
        "smoke_headroom_n_paired": n_paired,
        "smoke_headroom_discordant": total_discordant,
        "estimated_headroom_discordant_rate": discordant_rate,
        "estimated_agentic_win_rate_given_discordance": win_rate,
        "alpha": args.alpha,
        "target_power": args.target_power,
        "required_n_headroom_tasks": required_n,
        "achieved_power_at_required_n": achieved_power if required_n is not None else None,
        "max_n": args.max_n,
        "interpretation_guard": "Power is estimated on headroom tasks only; it is planning evidence, not effectiveness evidence.",
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if required_n is not None else 1


def check_payload(name: str, passed: bool, observed: Any, threshold: Any, note: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "observed": observed,
        "threshold": threshold,
        "note": note,
    }


def arm_metric(container: dict[str, Any], arm: str, metric: str) -> float | None:
    by_arm = container.get("by_arm") if isinstance(container.get("by_arm"), dict) else {}
    arm_data = by_arm.get(arm)
    if not isinstance(arm_data, dict):
        return None
    value = arm_data.get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def grouped_arm_metric(grouped: dict[str, Any], polarity: str, arm: str, metric: str) -> float | None:
    group = grouped.get(f"{polarity}:{arm}")
    if not isinstance(group, dict):
        return None
    value = group.get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def delta_at_least(value: float | None, baseline: float | None, minimum: float) -> tuple[bool, Any]:
    if value is None or baseline is None:
        return False, {"value": value, "baseline": baseline}
    return value - baseline >= minimum, value - baseline


def increase_at_most(value: float | None, baseline: float | None, maximum: float) -> tuple[bool, Any]:
    if value is None or baseline is None:
        return False, {"value": value, "baseline": baseline}
    return value - baseline <= maximum, value - baseline


def promotion_check(args: argparse.Namespace) -> int:
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    headroom = summary.get("headroom") if isinstance(summary.get("headroom"), dict) else {}
    contrasts = headroom.get("contrasts") if isinstance(headroom.get("contrasts"), dict) else {}
    agentic_vs_placebo = contrasts.get("agentic_loop_vs_placebo_loop")
    agentic_vs_control = contrasts.get("agentic_loop_vs_control")
    grouped = summary.get("grouped") if isinstance(summary.get("grouped"), dict) else {}
    non_headroom = (
        summary.get("non_headroom_positive")
        if isinstance(summary.get("non_headroom_positive"), dict)
        else {}
    )
    checks: list[dict[str, Any]] = []
    stage_allows_promotion = args.stage in {"confirmatory", "heldout"}
    checks.append(
        check_payload(
            "stage_allows_promotion",
            stage_allows_promotion,
            args.stage,
            "confirmatory|heldout",
            "smoke and demo runs are planning evidence only",
        )
    )
    headroom_n = int(headroom.get("n_complete_paired_headroom_tasks") or 0)
    checks.append(check_payload("headroom_nonzero", headroom_n > 0, headroom_n, "> 0"))
    checks.append(
        check_payload(
            "headroom_minimum_n",
            headroom_n >= args.min_headroom_n,
            headroom_n,
            f">= {args.min_headroom_n}",
            "confirmatory promotion must be powered on the control-failed headroom subset",
        )
    )

    placebo_delta = agentic_vs_placebo.get("mean_delta") if isinstance(agentic_vs_placebo, dict) else None
    placebo_ci = agentic_vs_placebo.get("bootstrap_ci") if isinstance(agentic_vs_placebo, dict) else None
    placebo_ci_low = placebo_ci.get("low") if isinstance(placebo_ci, dict) else None
    checks.append(
        check_payload(
            "agentic_beats_placebo_loop",
            isinstance(placebo_delta, (int, float)) and placebo_delta >= args.min_headroom_delta,
            placebo_delta,
            f">= {args.min_headroom_delta}",
        )
    )
    checks.append(
        check_payload(
            "agentic_vs_placebo_ci_low_nonnegative",
            isinstance(placebo_ci_low, (int, float)) and placebo_ci_low >= args.min_ci_low,
            placebo_ci_low,
            f">= {args.min_ci_low}",
        )
    )
    control_delta = agentic_vs_control.get("mean_delta") if isinstance(agentic_vs_control, dict) else None
    checks.append(
        check_payload(
            "agentic_beats_control",
            isinstance(control_delta, (int, float)) and control_delta >= args.min_control_delta,
            control_delta,
            f">= {args.min_control_delta}",
        )
    )

    agentic_headroom = (headroom.get("by_arm") or {}).get("agentic_loop", {})
    decisive_recoveries = agentic_headroom.get("decisive_external_observation_recovery_count")
    checks.append(
        check_payload(
            "external_observation_recovery_present",
            isinstance(decisive_recoveries, int) and decisive_recoveries >= args.min_decisive_recoveries,
            decisive_recoveries,
            f">= {args.min_decisive_recoveries}",
            "requires scorer-derived pre/post state diff after allowlisted external observation",
        )
    )

    for baseline_arm in ("control", "placebo_loop"):
        for metric in ("verified_pass_rate", "budgeted_verified_pass_rate"):
            passed, observed = delta_at_least(
                grouped_arm_metric(grouped, "negative", "agentic_loop", metric),
                grouped_arm_metric(grouped, "negative", baseline_arm, metric),
                args.regression_margin,
            )
            checks.append(
                check_payload(
                    f"negative_{metric}_noninferior_vs_{baseline_arm}",
                    passed,
                    observed,
                    f">= {args.regression_margin}",
                )
            )
            passed, observed = delta_at_least(
                arm_metric(non_headroom, "agentic_loop", metric),
                arm_metric(non_headroom, baseline_arm, metric),
                args.regression_margin,
            )
            checks.append(
                check_payload(
                    f"non_headroom_positive_{metric}_noninferior_vs_{baseline_arm}",
                    passed,
                    observed,
                    f">= {args.regression_margin}",
                )
            )
        passed, observed = increase_at_most(
            grouped_arm_metric(grouped, "negative", "agentic_loop", "false_success_claim_rate"),
            grouped_arm_metric(grouped, "negative", baseline_arm, "false_success_claim_rate"),
            args.max_false_success_increase,
        )
        checks.append(
            check_payload(
                f"negative_false_success_not_increased_vs_{baseline_arm}",
                passed,
                observed,
                f"<= {args.max_false_success_increase}",
            )
        )
        passed, observed = increase_at_most(
            arm_metric(non_headroom, "agentic_loop", "false_success_claim_rate"),
            arm_metric(non_headroom, baseline_arm, "false_success_claim_rate"),
            args.max_false_success_increase,
        )
        checks.append(
            check_payload(
                f"non_headroom_positive_false_success_not_increased_vs_{baseline_arm}",
                passed,
                observed,
                f"<= {args.max_false_success_increase}",
            )
        )

    budget_missing = missing_total({"grouped": grouped}, "budget_missing_count")
    usage_missing = missing_total({"grouped": grouped}, "usage_missing_count")
    cost_missing = missing_total({"grouped": grouped}, "cost_estimate_missing_count")
    checks.append(check_payload("budget_fields_complete", budget_missing == 0, budget_missing, "0 missing budget rows"))
    checks.append(check_payload("usage_fields_complete", usage_missing == 0, usage_missing, "0 missing usage rows"))
    checks.append(check_payload("cost_estimates_complete", cost_missing == 0, cost_missing, "0 missing cost rows"))
    parity = summary.get("budget_parity") if isinstance(summary.get("budget_parity"), dict) else {}
    checks.append(
        check_payload(
            "placebo_agentic_loop_budget_parity",
            bool(parity.get("passed")),
            parity.get("issues", []),
            "no placebo_loop/agentic_loop budget mismatches",
        )
    )
    candidate_eligible = all(check["passed"] for check in checks)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "stage": args.stage,
        "candidate_eligible": candidate_eligible,
        "default_promotion_allowed": False,
        "recommendation": "candidate" if candidate_eligible else "review_only",
        "checks": checks,
        "interpretation_guard": "This gate only supports candidate/review status for measured agentic-loop behavior. It never authorizes default promotion.",
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if candidate_eligible else 1


def demo_key(args: argparse.Namespace) -> int:
    tasks = [
        ("positive-headroom-001", "positive"),
        ("positive-ceiling-002", "positive"),
        ("negative-simple-001", "negative"),
    ]
    rows: list[dict[str, Any]] = []
    for task_id, polarity in tasks:
        for arm in ARMS:
            rows.append(
                {
                    "blind_id": stable_id(args.seed, task_id, arm),
                    "task_id": task_id,
                    "arm": arm,
                    "polarity": polarity,
                    "family": "agentic_coding" if polarity == "positive" else "low_risk_chat",
                    "budgets": {
                        "max_iterations": 3,
                        "max_prompt_tokens": 5000,
                        "max_completion_tokens": 2000,
                        "max_elapsed_seconds": 120,
                        "max_cost_estimate": 0.05,
                        "allowed_actions": ["inspect_file", "search", "run_public_test", "write_answer"],
                    },
                    "demo_note": "synthetic key for harness testing; not eval evidence",
                }
            )
    write_json(args.output, {"rows": rows})
    print(f"wrote demo key: {args.output}")
    return 0


def demo_traces(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    rows: list[dict[str, Any]] = []
    for item in key.values():
        task_id = item["task_id"]
        arm = item["arm"]
        changed = task_id == "positive-headroom-001" and arm == "agentic_loop"
        rows.append(
            {
                "blind_id": item["blind_id"],
                "prompt_tokens": 1200,
                "completion_tokens": 400,
                "elapsed_seconds": 30,
                "cost_estimate": 0.012,
                "iterations": [
                    {
                        "index": 1,
                        "pre_state": {"answer": "claim complete from visible check"},
                        "post_state": {"answer": "rerun missing validator"} if changed else {"answer": "claim complete from visible check"},
                        "observation": {
                            "source": "test" if changed else "none",
                            "summary": "public targeted test exposed skipped validator" if changed else "no external probe",
                            "artifact_path": "demo",
                        },
                        "failure_class": "missing_validator" if changed else "none",
                        "next_decision": "continue" if changed else "finalize",
                    }
                ],
                "final": {"claimed_success": arm == "agentic_loop" or task_id != "positive-headroom-001", "stop_reason": "verified"},
                "demo_note": "synthetic trace for harness testing; not eval evidence",
            }
        )
    write_jsonl(args.output, rows)
    print(f"wrote demo traces: {args.output}")
    return 0


def demo_verdicts(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    rows: list[dict[str, Any]] = []
    for item in key.values():
        task_id = item["task_id"]
        arm = item["arm"]
        if task_id == "positive-headroom-001":
            verified = arm == "agentic_loop"
        else:
            verified = True
        rows.append(
            {
                "blind_id": item["blind_id"],
                "verified_pass": verified,
                "quality_score": 1.0 if verified else 0.0,
                "validator": "deterministic_demo_verdict",
                "demo_note": "synthetic verdict for harness testing; not eval evidence",
            }
        )
    write_jsonl(args.output, rows)
    print(f"wrote demo verdicts: {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score Agentic Loop trace-only eval artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_key_parser = subparsers.add_parser("demo-key", help="write a deterministic demo blind key")
    demo_key_parser.add_argument("--output", required=True, type=Path)
    demo_key_parser.add_argument("--seed", type=int, default=20260619)
    demo_key_parser.set_defaults(func=demo_key)

    demo_traces_parser = subparsers.add_parser("demo-traces", help="write deterministic demo traces")
    demo_traces_parser.add_argument("--key", required=True, type=Path)
    demo_traces_parser.add_argument("--output", required=True, type=Path)
    demo_traces_parser.set_defaults(func=demo_traces)

    demo_verdicts_parser = subparsers.add_parser("demo-verdicts", help="write deterministic demo GT verdicts")
    demo_verdicts_parser.add_argument("--key", required=True, type=Path)
    demo_verdicts_parser.add_argument("--output", required=True, type=Path)
    demo_verdicts_parser.set_defaults(func=demo_verdicts)

    score_parser = subparsers.add_parser("score", help="score trace JSONL joined to GT verdicts")
    score_parser.add_argument("--key", required=True, type=Path)
    score_parser.add_argument("--traces", required=True, type=Path)
    score_parser.add_argument("--verdicts", required=True, type=Path)
    score_parser.add_argument("--output", required=True, type=Path)
    score_parser.add_argument("--seed", type=int, default=20260619)
    score_parser.add_argument("--include-rows", action="store_true")
    score_parser.set_defaults(func=score)

    power_parser = subparsers.add_parser("power", help="estimate confirmatory n on headroom tasks")
    power_parser.add_argument("--summary", required=True, type=Path)
    power_parser.add_argument("--contrast", default="agentic_loop_vs_placebo_loop")
    power_parser.add_argument("--target-power", type=float, default=0.8)
    power_parser.add_argument("--alpha", type=float, default=0.05)
    power_parser.add_argument("--min-n", type=int, default=8)
    power_parser.add_argument("--max-n", type=int, default=1000)
    power_parser.add_argument("--output", required=True, type=Path)
    power_parser.set_defaults(func=power)

    promotion_parser = subparsers.add_parser("promotion-check", help="apply the Agentic Loop promotion gate")
    promotion_parser.add_argument("--summary", required=True, type=Path)
    promotion_parser.add_argument("--output", required=True, type=Path)
    promotion_parser.add_argument("--stage", choices=["smoke", "confirmatory", "heldout"], default="smoke")
    promotion_parser.add_argument("--min-headroom-delta", type=float, default=0.05)
    promotion_parser.add_argument("--min-control-delta", type=float, default=0.05)
    promotion_parser.add_argument("--min-ci-low", type=float, default=0.0)
    promotion_parser.add_argument("--min-decisive-recoveries", type=int, default=1)
    promotion_parser.add_argument("--min-headroom-n", type=int, default=8)
    promotion_parser.add_argument("--regression-margin", type=float, default=-0.03)
    promotion_parser.add_argument("--max-false-success-increase", type=float, default=0.0)
    promotion_parser.set_defaults(func=promotion_check)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
