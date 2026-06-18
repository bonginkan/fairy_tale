#!/usr/bin/env python3
"""Prepare and summarize Accessible Genius Method evaluation runs.

This harness is intentionally model-provider neutral. It creates paired
control/placebo/treatment prompt bundles and blind grading manifests, then
summarizes externally produced result JSONL files. It does not call model APIs
or execute benchmark scorers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ARMS = ("control", "placebo", "treatment")
POLARITIES = {"positive", "negative"}
SUPPORTED_CARDS = {"empirical_experiment_ledger"}
REQUIRED_BUDGET_FIELDS = ("max_prompt_tokens", "max_completion_tokens", "max_elapsed_seconds")

EMPIRICAL_LEDGER_SCHEMA = """Empirical Experiment Ledger

hypothesis:
observable:
instrument/tool:
control or baseline:
procedure:
result:
confounders:
next experiment:
"""

PLACEBO_GUIDANCE = """Use careful, evidence-aware problem solving.

Before answering, consider whether the visible information is enough, whether a
nearby check or comparison would change the answer, and whether a confident
claim could be premature. Be concise, avoid overclaiming, and mention concrete
evidence when it matters. If the task is simple or preference-only, keep the
answer direct and do not add unnecessary process.
"""

OUTPUT_CONTRACT = """Return JSON only:
{
  "answer": "...",
  "claimed_success": true,
  "evidence_summary": "...",
  "method_trace": {
    "card_used": "none | empirical_experiment_ledger",
    "artifact_completed": false,
    "artifact_changed_decision": false,
    "notes": "..."
  }
}
"""

CARD_SUMMARIES = {
    "empirical_experiment_ledger": {
        "name": "Empirical Experiment Ledger",
        "use_when": "A conclusion can be checked against observations, tests, logs, measurements, screenshots, or user behavior; or a claim risks sounding plausible without evidence.",
        "do_not_use_when": "The task is purely normative, preference-based, low-risk chat, or simple deterministic formatting.",
    }
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


def slug(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return safe.strip("-") or "item"


def blind_id(seed: int, task_id: str, arm: str) -> str:
    digest = hashlib.sha256(f"{seed}:{task_id}:{arm}".encode("utf-8")).hexdigest()
    return f"gm-{digest[:16]}"


def routing_id(seed: int, task_id: str) -> str:
    digest = hashlib.sha256(f"routing:{seed}:{task_id}".encode("utf-8")).hexdigest()
    return f"gr-{digest[:16]}"


def require_text(row: dict[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return value


def validate_tasks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        label = f"task[{index}]"
        task_id = require_text(row, "task_id", label)
        if task_id in seen:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen.add(task_id)
        card = require_text(row, "card", label)
        if card not in SUPPORTED_CARDS:
            raise ValueError(f"{label}.card unsupported: {card}")
        polarity = require_text(row, "polarity", label)
        if polarity not in POLARITIES:
            raise ValueError(f"{label}.polarity must be one of {sorted(POLARITIES)}")
        family = require_text(row, "family", label)
        prompt = require_text(row, "prompt", label)
        ground_truth = row.get("ground_truth")
        if not isinstance(ground_truth, dict):
            raise ValueError(f"{label}.ground_truth must be an object")
        success_criteria = ground_truth.get("success_criteria")
        if not isinstance(success_criteria, list) or not success_criteria:
            raise ValueError(f"{label}.ground_truth.success_criteria must be a non-empty list")
        if not all(isinstance(item, str) and item.strip() for item in success_criteria):
            raise ValueError(f"{label}.ground_truth.success_criteria must contain strings")
        budgets = row.get("budgets", {})
        if budgets is None:
            budgets = {}
        if not isinstance(budgets, dict):
            raise ValueError(f"{label}.budgets must be an object")
        normalized.append(
            {
                "task_id": task_id,
                "card": card,
                "polarity": polarity,
                "family": family,
                "prompt": prompt,
                "ground_truth": ground_truth,
                "budgets": budgets,
            }
        )
    return normalized


def build_prompt(task: dict[str, Any], arm: str) -> str:
    prelude = [
        "# Accessible Genius Method Eval",
        "",
        "You are solving one task under a controlled evaluation. Do not mention the arm name.",
        "If you claim success, tie the claim to evidence available in the task or produced by validation.",
        "",
    ]
    if arm == "control":
        guidance = "Use the normal Fairy Tale process. Do not use Accessible Genius Method cards."
    elif arm == "placebo":
        guidance = PLACEBO_GUIDANCE.strip()
    elif arm == "treatment":
        guidance = (
            "Before claiming success, fill and use this method artifact. "
            "If the task is not measurable, say so and keep the answer direct.\n\n"
            f"{EMPIRICAL_LEDGER_SCHEMA.strip()}"
        )
    else:
        raise ValueError(f"unknown arm: {arm}")

    return "\n".join(
        prelude
        + [
            "## Guidance",
            guidance,
            "",
            "## Task",
            task["prompt"],
            "",
            "## Output Contract",
            OUTPUT_CONTRACT.strip(),
            "",
        ]
    )


def prepare(args: argparse.Namespace) -> int:
    tasks = validate_tasks(read_jsonl(args.tasks))
    jobs: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    judge_rows: list[dict[str, Any]] = []
    prompt_dir = args.output / "prompts"

    for task in tasks:
        for arm in ARMS:
            identifier = blind_id(args.seed, task["task_id"], arm)
            prompt = build_prompt(task, arm)
            prompt_path = prompt_dir / f"{identifier}.md"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")
            key_rows.append(
                {
                    "blind_id": identifier,
                    "task_id": task["task_id"],
                    "arm": arm,
                    "card": task["card"],
                    "polarity": task["polarity"],
                    "family": task["family"],
                    "prompt_path": str(prompt_path.relative_to(args.output)),
                    "budgets": task["budgets"],
                    "ground_truth": task["ground_truth"],
                }
            )
            judge_rows.append(
                {
                    "blind_id": identifier,
                    "prompt_path": str(prompt_path.relative_to(args.output)),
                    "ground_truth": task["ground_truth"],
                    "budgets": task["budgets"],
                }
            )
            jobs.append({"blind_id": identifier, "prompt_path": str(prompt_path)})

    rng = random.Random(args.seed)
    rng.shuffle(jobs)
    manifest = {
        "schema_version": "1.0",
        "eval": "genius-method-forced-injection",
        "tasks": str(args.tasks),
        "seed": args.seed,
        "arms": list(ARMS),
        "primary_comparison": "treatment_vs_placebo",
        "primary_metrics": ["false_success_claim_rate", "verified_pass_rate"],
        "notes": "Run prompts in shuffled job order. Use blind_key.json only after grading.",
        "num_tasks": len(tasks),
        "num_jobs": len(jobs),
    }
    write_json(args.output / "run_manifest.json", manifest)
    write_json(args.output / "blind_key.json", {"rows": key_rows})
    write_jsonl(args.output / "judge_manifest.jsonl", judge_rows)
    write_jsonl(args.output / "jobs.jsonl", jobs)
    write_jsonl(args.output / "tasks.normalized.jsonl", tasks)
    print(f"wrote prompt bundle: {args.output}")
    return 0


def prepare_routing(args: argparse.Namespace) -> int:
    tasks = validate_tasks(read_jsonl(args.tasks))
    rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    prompt_dir = args.output / "routing-prompts"
    for task in tasks:
        identifier = routing_id(args.seed, task["task_id"])
        card = CARD_SUMMARIES["empirical_experiment_ledger"]
        prompt = f"""# Accessible Genius Method Routing Probe

Choose whether the task should use the Empirical Experiment Ledger card.
Return JSON only:
{{"selected_cards":["empirical_experiment_ledger"] | [], "reason":"..."}}

Card:
- name: {card["name"]}
- use_when: {card["use_when"]}
- do_not_use_when: {card["do_not_use_when"]}

Task:
{task["prompt"]}
"""
        prompt_path = prompt_dir / f"{identifier}.md"
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        prompt_path.write_text(prompt, encoding="utf-8")
        rows.append({"blind_id": identifier, "prompt_path": str(prompt_path)})
        key_rows.append(
            {
                "blind_id": identifier,
                "task_id": task["task_id"],
                "expected_select": task["polarity"] == "positive",
                "polarity": task["polarity"],
                "family": task["family"],
                "card": task["card"],
            }
        )

    rng = random.Random(args.seed)
    rng.shuffle(rows)
    write_json(args.output / "routing_key.json", {"rows": key_rows})
    write_jsonl(args.output / "routing_jobs.jsonl", rows)
    print(f"wrote routing probe bundle: {args.output}")
    return 0


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "passed", "pass"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def within_optional_budget(value: float, limit: Any) -> bool:
    parsed = as_optional_float(limit)
    if parsed is None:
        return True
    return value <= parsed


def has_required_budget(budgets: dict[str, Any]) -> bool:
    return all(as_optional_float(budgets.get(field)) is not None for field in REQUIRED_BUDGET_FIELDS)


def first_numeric(*values: Any) -> float | None:
    for value in values:
        parsed = as_optional_float(value)
        if parsed is not None:
            return parsed
    return None


def load_key(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise SystemExit(f"invalid key file: {path}")
    return {str(row["blind_id"]): row for row in rows if isinstance(row, dict) and "blind_id" in row}


def load_verdicts(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    verdicts: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        identifier = str(row.get("blind_id", ""))
        if not identifier:
            raise SystemExit(f"verdict[{index}].blind_id is required")
        if identifier in verdicts:
            raise SystemExit(f"duplicate verdict blind_id: {identifier}")
        if "verified_pass" not in row:
            raise SystemExit(f"verdict[{index}].verified_pass is required")
        verdicts[identifier] = row
    return verdicts


def normalize_answer(row: dict[str, Any], verdict: dict[str, Any], key: dict[str, Any]) -> dict[str, Any]:
    forbidden_answer_fields = sorted({"verified_pass", "quality_score"} & set(row))
    if forbidden_answer_fields:
        raise ValueError(
            "answer rows must not contain GT fields; put them in --verdicts instead: "
            + ", ".join(forbidden_answer_fields)
        )
    usage = row.get("usage") if isinstance(row.get("usage"), dict) else {}
    trace = row.get("method_trace") if isinstance(row.get("method_trace"), dict) else row.get("trace", {})
    if not isinstance(trace, dict):
        trace = {}
    prompt_tokens = int(as_float(row.get("prompt_tokens", usage.get("prompt_tokens")), 0.0))
    completion_tokens = int(as_float(row.get("completion_tokens", usage.get("completion_tokens")), 0.0))
    verified_pass = as_bool(verdict.get("verified_pass"))
    claimed_success = as_bool(row.get("claimed_success"))
    total_tokens = prompt_tokens + completion_tokens
    quality_score = as_float(verdict.get("quality_score"), 1.0 if verified_pass else 0.0)
    artifact_completed = as_bool(trace.get("artifact_completed"))
    elapsed_seconds = as_float(row.get("elapsed_seconds", usage.get("elapsed_seconds")), 0.0)
    budgets = key.get("budgets") if isinstance(key.get("budgets"), dict) else {}
    cost_estimate = first_numeric(
        row.get("cost_estimate"),
        row.get("cost_estimate_usd"),
        row.get("cost_usd"),
        usage.get("cost_estimate"),
        usage.get("cost_estimate_usd"),
        usage.get("cost_usd"),
    )
    budget_complete = has_required_budget(budgets)
    within_budget = budget_complete and (
        within_optional_budget(prompt_tokens, budgets.get("max_prompt_tokens"))
        and within_optional_budget(completion_tokens, budgets.get("max_completion_tokens"))
        and within_optional_budget(elapsed_seconds, budgets.get("max_elapsed_seconds"))
    )
    return {
        **key,
        "claimed_success": claimed_success,
        "verified_pass": verified_pass,
        "budgeted_correct": verified_pass and within_budget,
        "budget_complete": budget_complete,
        "false_success": claimed_success and not verified_pass,
        "quality_score": quality_score,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "quality_per_token": quality_score / total_tokens if total_tokens > 0 else None,
        "elapsed_seconds": elapsed_seconds,
        "cost_estimate": cost_estimate,
        "cost_estimate_present": cost_estimate is not None,
        "artifact_completed": artifact_completed,
        "artifact_changed_decision": as_bool(trace.get("artifact_changed_decision")),
        "no_misapplied_artifact": not artifact_completed,
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


def grouped_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[f"{row['polarity']}:{row['arm']}"].append(row)
    summary: dict[str, Any] = {}
    for key, group in sorted(groups.items()):
        summary[key] = {
            "n": len(group),
            "verified_pass_rate": rate(group, "verified_pass"),
            "budgeted_correct_rate": rate(group, "budgeted_correct"),
            "budget_complete_rate": rate(group, "budget_complete"),
            "budget_missing_count": sum(1 for row in group if not row.get("budget_complete")),
            "false_success_claim_rate": rate(group, "false_success"),
            "artifact_completed_rate": rate(group, "artifact_completed"),
            "artifact_changed_decision_rate": rate(group, "artifact_changed_decision"),
            "no_misapplied_artifact_rate": rate(group, "no_misapplied_artifact"),
            "mean_quality_score": mean(group, "quality_score"),
            "mean_total_tokens": mean(group, "total_tokens"),
            "mean_quality_per_token": mean(group, "quality_per_token"),
            "mean_elapsed_seconds": mean(group, "elapsed_seconds"),
            "mean_cost_estimate": mean(group, "cost_estimate"),
            "cost_estimate_count": sum(1 for row in group if row.get("cost_estimate_present")),
            "cost_estimate_missing_count": sum(1 for row in group if not row.get("cost_estimate_present")),
        }
    return summary


def paired_tasks(rows: list[dict[str, Any]], polarity: str) -> dict[str, dict[str, dict[str, Any]]]:
    by_task: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if row.get("polarity") == polarity:
            by_task[row["task_id"]][row["arm"]] = row
    return {
        task_id: arms
        for task_id, arms in by_task.items()
        if all(arm in arms for arm in ARMS)
    }


def exact_mcnemar_p(win_a: int, win_b: int) -> float | None:
    discordant = win_a + win_b
    if discordant == 0:
        return None
    tail = sum(math.comb(discordant, k) for k in range(0, min(win_a, win_b) + 1)) / (2**discordant)
    return min(1.0, 2 * tail)


def binomial_pmf(n: int, k: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def positive_exact_power(n_tasks: int, discordant_rate: float, win_rate: float, alpha: float) -> float:
    if n_tasks <= 0 or discordant_rate <= 0 or win_rate <= 0.5:
        return 0.0
    power = 0.0
    for discordant in range(1, n_tasks + 1):
        p_discordant = binomial_pmf(n_tasks, discordant, discordant_rate)
        reject_given_discordant = 0.0
        for treatment_wins in range(0, discordant + 1):
            placebo_wins = discordant - treatment_wins
            p_value = exact_mcnemar_p(treatment_wins, placebo_wins)
            if treatment_wins > placebo_wins and p_value is not None and p_value <= alpha:
                reject_given_discordant += binomial_pmf(discordant, treatment_wins, win_rate)
        power += p_discordant * reject_given_discordant
    return power


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


def paired_delta(rows: list[dict[str, Any]], polarity: str, metric: str, seed: int) -> dict[str, Any]:
    tasks = paired_tasks(rows, polarity)
    deltas_tp: list[float] = []
    deltas_pc: list[float] = []
    deltas_tc: list[float] = []
    t_beats_p = p_beats_t = 0
    p_beats_c = c_beats_p = 0
    t_beats_c = c_beats_t = 0
    binary_metric = True
    for arms in tasks.values():
        treatment = arms["treatment"]
        placebo = arms["placebo"]
        control = arms["control"]
        binary_metric = binary_metric and all(
            isinstance(arms[arm].get(metric), bool) for arm in ARMS
        )
        t_value = as_float(treatment.get(metric), 0.0)
        p_value = as_float(placebo.get(metric), 0.0)
        c_value = as_float(control.get(metric), 0.0)
        delta_tp = t_value - p_value
        delta_pc = p_value - c_value
        delta_tc = t_value - c_value
        deltas_tp.append(delta_tp)
        deltas_pc.append(delta_pc)
        deltas_tc.append(delta_tc)
        if t_value > p_value:
            t_beats_p += 1
        elif p_value > t_value:
            p_beats_t += 1
        if p_value > c_value:
            p_beats_c += 1
        elif c_value > p_value:
            c_beats_p += 1
        if t_value > c_value:
            t_beats_c += 1
        elif c_value > t_value:
            c_beats_t += 1
    return {
        "polarity": polarity,
        "metric": metric,
        "n_paired_tasks": len(tasks),
        "treatment_minus_placebo": sum(deltas_tp) / len(deltas_tp) if deltas_tp else None,
        "placebo_minus_control": sum(deltas_pc) / len(deltas_pc) if deltas_pc else None,
        "treatment_minus_control": sum(deltas_tc) / len(deltas_tc) if deltas_tc else None,
        "treatment_vs_placebo_bootstrap_ci": bootstrap_ci(deltas_tp, seed),
        "placebo_vs_control_bootstrap_ci": bootstrap_ci(deltas_pc, seed + 1),
        "treatment_vs_control_bootstrap_ci": bootstrap_ci(deltas_tc, seed + 2),
        "treatment_vs_placebo_mcnemar_p": exact_mcnemar_p(t_beats_p, p_beats_t)
        if binary_metric
        else None,
        "placebo_vs_control_mcnemar_p": exact_mcnemar_p(p_beats_c, c_beats_p)
        if binary_metric
        else None,
        "treatment_vs_control_mcnemar_p": exact_mcnemar_p(t_beats_c, c_beats_t)
        if binary_metric
        else None,
        "discordant": {
            "treatment_beats_placebo": t_beats_p,
            "placebo_beats_treatment": p_beats_t,
            "placebo_beats_control": p_beats_c,
            "control_beats_placebo": c_beats_p,
            "treatment_beats_control": t_beats_c,
            "control_beats_treatment": c_beats_t,
        },
    }


def score(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    answers = read_jsonl(args.answers)
    verdicts = load_verdicts(args.verdicts)
    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for answer in answers:
        identifier = str(answer.get("blind_id", ""))
        if identifier not in key:
            missing.append(identifier or "<missing>")
            continue
        if identifier not in verdicts:
            missing.append(f"{identifier}:verdict")
            continue
        try:
            rows.append(normalize_answer(answer, verdicts[identifier], key[identifier]))
        except ValueError as exc:
            raise SystemExit(f"{identifier}: {exc}") from None
    if missing:
        raise SystemExit(f"missing or unknown blind_id values: {', '.join(missing[:5])}")

    summary = {
        "schema_version": "1.0",
        "n_results": len(rows),
        "positive_primary_metrics": ["false_success_claim_rate", "verified_pass_rate"],
        "budget_metrics": ["budgeted_correct_rate", "mean_cost_estimate"],
        "negative_noninferiority_metrics": [
            "quality_score",
            "quality_per_token",
            "no_misapplied_artifact",
        ],
        "grouped": grouped_summary(rows),
        "paired": {
            "positive_verified_pass": paired_delta(rows, "positive", "verified_pass", args.seed),
            "positive_budgeted_correct": paired_delta(rows, "positive", "budgeted_correct", args.seed + 5),
            "positive_not_false_success": paired_delta(
                [{**row, "not_false_success": not row["false_success"]} for row in rows],
                "positive",
                "not_false_success",
                args.seed + 10,
            ),
            "negative_quality_score": paired_delta(rows, "negative", "quality_score", args.seed + 20),
            "negative_quality_per_token": paired_delta(rows, "negative", "quality_per_token", args.seed + 30),
            "negative_no_misapplied_artifact": paired_delta(
                rows,
                "negative",
                "no_misapplied_artifact",
                args.seed + 40,
            ),
        },
        "interpretation_guard": "Primary conclusion is treatment vs placebo on paired positive tasks using GT verdicts from --verdicts. Ledger completion is mechanism evidence only, not an outcome.",
    }
    write_json(args.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def score_routing(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    rows = read_jsonl(args.routes)
    scored: list[dict[str, Any]] = []
    for row in rows:
        identifier = str(row.get("blind_id", ""))
        if identifier not in key:
            raise SystemExit(f"unknown routing blind_id: {identifier}")
        selected = row.get("selected_cards", [])
        if not isinstance(selected, list):
            selected = []
        selected_card = "empirical_experiment_ledger" in selected
        expected = bool(key[identifier]["expected_select"])
        scored.append({**key[identifier], "selected": selected_card, "correct": selected_card == expected})
    positive = [row for row in scored if row["polarity"] == "positive"]
    negative = [row for row in scored if row["polarity"] == "negative"]
    payload = {
        "schema_version": "1.0",
        "n": len(scored),
        "accuracy": rate(scored, "correct"),
        "positive_selection_rate": rate(positive, "selected"),
        "negative_abstention_rate": rate([{**row, "abstained": not row["selected"]} for row in negative], "abstained"),
        "false_positive_selection_rate": rate(negative, "selected"),
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def power(args: argparse.Namespace) -> int:
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    paired = summary.get("paired") if isinstance(summary.get("paired"), dict) else {}
    metric = paired.get(args.paired_metric)
    if not isinstance(metric, dict):
        raise SystemExit(f"missing paired metric in summary: {args.paired_metric}")
    discordant = metric.get("discordant") if isinstance(metric.get("discordant"), dict) else {}
    treatment_wins = int(discordant.get("treatment_beats_placebo") or 0)
    placebo_wins = int(discordant.get("placebo_beats_treatment") or 0)
    n_paired = int(metric.get("n_paired_tasks") or 0)
    total_discordant = treatment_wins + placebo_wins
    if n_paired <= 0 or total_discordant <= 0:
        payload = {
            "ok": False,
            "reason": "smoke summary has no paired discordant treatment/placebo outcomes",
            "paired_metric": args.paired_metric,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    discordant_rate = total_discordant / n_paired
    win_rate = treatment_wins / total_discordant
    required_n = None
    achieved_power = 0.0
    for n_tasks in range(args.min_n, args.max_n + 1):
        achieved_power = positive_exact_power(n_tasks, discordant_rate, win_rate, args.alpha)
        if achieved_power >= args.target_power:
            required_n = n_tasks
            break
    payload = {
        "ok": required_n is not None,
        "paired_metric": args.paired_metric,
        "smoke_n_paired": n_paired,
        "smoke_discordant": total_discordant,
        "estimated_discordant_rate": discordant_rate,
        "estimated_treatment_win_rate_given_discordance": win_rate,
        "alpha": args.alpha,
        "target_power": args.target_power,
        "required_n_paired_tasks": required_n,
        "achieved_power_at_required_n": achieved_power if required_n is not None else None,
        "max_n": args.max_n,
        "interpretation_guard": "Power is a smoke-based planning estimate, not evidence of method effectiveness.",
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if required_n is not None else 1


def paired_metric(summary: dict[str, Any], name: str) -> dict[str, Any] | None:
    paired = summary.get("paired") if isinstance(summary.get("paired"), dict) else {}
    metric = paired.get(name)
    return metric if isinstance(metric, dict) else None


def weighted_arm_mean(summary: dict[str, Any], arm: str, field: str) -> float | None:
    grouped = summary.get("grouped") if isinstance(summary.get("grouped"), dict) else {}
    total = 0.0
    count = 0
    for group_key, group in grouped.items():
        if not isinstance(group, dict) or not str(group_key).endswith(f":{arm}"):
            continue
        value = group.get(field)
        n = int(group.get("n") or 0)
        if isinstance(value, (int, float)) and n > 0:
            total += float(value) * n
            count += n
    if count == 0:
        return None
    return total / count


def grouped_missing_total(summary: dict[str, Any], field: str, prefix: str | None = None) -> int | None:
    grouped = summary.get("grouped") if isinstance(summary.get("grouped"), dict) else {}
    total = 0
    matched = False
    for group_key, group in grouped.items():
        if prefix is not None and not str(group_key).startswith(prefix):
            continue
        if not isinstance(group, dict):
            return None
        value = group.get(field)
        if not isinstance(value, int):
            return None
        total += value
        matched = True
    return total if matched else None


def check_payload(name: str, passed: bool, observed: Any, threshold: Any, note: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "observed": observed,
        "threshold": threshold,
        "note": note,
    }


def promotion_check(args: argparse.Namespace) -> int:
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    routing_summary = None
    if args.routing_summary:
        routing_summary = json.loads(args.routing_summary.read_text(encoding="utf-8"))

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

    primary = paired_metric(summary, args.primary_metric)
    primary_delta = primary.get("treatment_minus_placebo") if primary else None
    primary_ci = primary.get("treatment_vs_placebo_bootstrap_ci") if primary else None
    primary_ci_low = primary_ci.get("low") if isinstance(primary_ci, dict) else None
    checks.append(
        check_payload(
            "primary_treatment_beats_placebo",
            isinstance(primary_delta, (int, float)) and primary_delta >= args.min_positive_delta,
            primary_delta,
            f">= {args.min_positive_delta}",
        )
    )
    checks.append(
        check_payload(
            "primary_ci_low_nonnegative",
            isinstance(primary_ci_low, (int, float)) and primary_ci_low >= args.min_primary_ci_low,
            primary_ci_low,
            f">= {args.min_primary_ci_low}",
        )
    )

    budgeted = paired_metric(summary, args.budgeted_metric)
    budgeted_delta = budgeted.get("treatment_minus_placebo") if budgeted else None
    positive_budget_missing = grouped_missing_total(summary, "budget_missing_count", "positive:")
    checks.append(
        check_payload(
            "positive_budget_fields_complete",
            positive_budget_missing == 0,
            positive_budget_missing,
            "0 missing budget rows",
            "requires max_prompt_tokens, max_completion_tokens, and max_elapsed_seconds for positive promotion rows",
        )
    )
    checks.append(
        check_payload(
            "budgeted_correct_not_worse",
            isinstance(budgeted_delta, (int, float)) and budgeted_delta >= args.min_budgeted_delta,
            budgeted_delta,
            f">= {args.min_budgeted_delta}",
        )
    )

    negative = paired_metric(summary, args.negative_metric)
    negative_delta = negative.get("treatment_minus_control") if negative else None
    checks.append(
        check_payload(
            "negative_noninferiority_vs_control",
            isinstance(negative_delta, (int, float)) and negative_delta >= args.negative_margin,
            negative_delta,
            f">= {args.negative_margin}",
        )
    )

    cost_missing = grouped_missing_total(summary, "cost_estimate_missing_count")
    treatment_cost = weighted_arm_mean(summary, "treatment", "mean_cost_estimate")
    placebo_cost = weighted_arm_mean(summary, "placebo", "mean_cost_estimate")
    cost_complete = cost_missing == 0
    checks.append(
        check_payload(
            "cost_estimates_complete",
            cost_complete,
            cost_missing,
            "0 missing cost rows",
            "requires numeric cost_estimate for every scored row before cost ratios can promote",
        )
    )
    if cost_complete and treatment_cost is not None and placebo_cost is not None and placebo_cost > 0:
        cost_ratio = treatment_cost / placebo_cost
        cost_passed = cost_ratio <= 1.0 + args.max_cost_increase
        cost_observed: Any = cost_ratio
    else:
        cost_passed = False
        cost_observed = {
            "treatment_mean_cost_estimate": treatment_cost,
            "placebo_mean_cost_estimate": placebo_cost,
            "cost_estimate_missing_count": cost_missing,
        }
    checks.append(
        check_payload(
            "cost_increase_within_limit",
            cost_passed,
            cost_observed,
            f"<= {1.0 + args.max_cost_increase}",
            "requires numeric cost_estimate in answer usage",
        )
    )

    if routing_summary is None:
        checks.append(
            check_payload(
                "routing_summary_present",
                False,
                None,
                "required",
                "run score-routing for Use when / Do not use when promotion",
            )
        )
    else:
        negative_abstention = routing_summary.get("negative_abstention_rate")
        positive_selection = routing_summary.get("positive_selection_rate")
        checks.append(
            check_payload(
                "routing_negative_abstention",
                isinstance(negative_abstention, (int, float))
                and negative_abstention >= args.min_routing_negative_abstention,
                negative_abstention,
                f">= {args.min_routing_negative_abstention}",
            )
        )
        checks.append(
            check_payload(
                "routing_positive_selection",
                isinstance(positive_selection, (int, float))
                and positive_selection >= args.min_routing_positive_selection,
                positive_selection,
                f">= {args.min_routing_positive_selection}",
            )
        )

    candidate_eligible = all(check["passed"] for check in checks)
    payload = {
        "schema_version": "1.0",
        "stage": args.stage,
        "candidate_eligible": candidate_eligible,
        "default_promotion_allowed": False,
        "recommendation": "candidate" if candidate_eligible else "review_only",
        "checks": checks,
        "interpretation_guard": "This gate can only support candidate/review status for the measured card and task family. It never authorizes default promotion.",
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if candidate_eligible else 1


def demo_answers(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    rows: list[dict[str, Any]] = []
    for item in key.values():
        arm = item["arm"]
        polarity = item["polarity"]
        claimed = arm != "control" or polarity == "negative"
        rows.append(
            {
                "blind_id": item["blind_id"],
                "claimed_success": claimed,
                "prompt_tokens": 1000 if arm == "control" else 1200,
                "completion_tokens": 300,
                "cost_estimate": 0.010 if arm != "treatment" else 0.011,
                "elapsed_seconds": 10,
                "method_trace": {
                    "card_used": "empirical_experiment_ledger" if arm == "treatment" else "none",
                    "artifact_completed": arm == "treatment",
                    "artifact_changed_decision": arm == "treatment" and polarity == "positive",
                },
                "demo_note": "synthetic model answer for harness testing; not eval evidence",
            }
        )
    write_jsonl(args.output, rows)
    print(f"wrote demo answers: {args.output}")
    return 0


def demo_verdicts(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    rows: list[dict[str, Any]] = []
    for item in key.values():
        arm = item["arm"]
        polarity = item["polarity"]
        verified = arm == "treatment" if polarity == "positive" else arm != "treatment"
        rows.append(
            {
                "blind_id": item["blind_id"],
                "verified_pass": verified,
                "quality_score": 1.0 if verified else 0.0,
                "validator": "deterministic_demo_verdict",
                "demo_note": "synthetic GT verdict for harness testing; not eval evidence",
            }
        )
    write_jsonl(args.output, rows)
    print(f"wrote demo verdicts: {args.output}")
    return 0


def demo_routes(args: argparse.Namespace) -> int:
    key = load_key(args.key)
    rows: list[dict[str, Any]] = []
    for item in key.values():
        selected = ["empirical_experiment_ledger"] if item["expected_select"] else []
        rows.append(
            {
                "blind_id": item["blind_id"],
                "selected_cards": selected,
                "reason": "deterministic demo route based on the hidden key; do not use as eval evidence",
            }
        )
    write_jsonl(args.output, rows)
    print(f"wrote demo routes: {args.output}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    tasks = validate_tasks(read_jsonl(args.tasks))
    counts: dict[str, int] = defaultdict(int)
    for task in tasks:
        counts[f"{task['polarity']}:{task['family']}"] += 1
    payload = {"ok": True, "n": len(tasks), "counts": dict(sorted(counts.items()))}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and score Accessible Genius Method eval artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-tasks", help="validate task JSONL")
    validate.add_argument("--tasks", required=True, type=Path)
    validate.set_defaults(func=command_validate)

    prep = subparsers.add_parser("prepare", help="write forced-injection prompt bundle")
    prep.add_argument("--tasks", required=True, type=Path)
    prep.add_argument("--output", required=True, type=Path)
    prep.add_argument("--seed", type=int, default=20260618)
    prep.set_defaults(func=prepare)

    routing = subparsers.add_parser("prepare-routing", help="write routing probe prompt bundle")
    routing.add_argument("--tasks", required=True, type=Path)
    routing.add_argument("--output", required=True, type=Path)
    routing.add_argument("--seed", type=int, default=20260618)
    routing.set_defaults(func=prepare_routing)

    demo = subparsers.add_parser("demo-answers", help="write deterministic demo answer JSONL for harness testing")
    demo.add_argument("--key", required=True, type=Path)
    demo.add_argument("--output", required=True, type=Path)
    demo.set_defaults(func=demo_answers)

    demo_verdict = subparsers.add_parser("demo-verdicts", help="write deterministic demo GT verdict JSONL")
    demo_verdict.add_argument("--key", required=True, type=Path)
    demo_verdict.add_argument("--output", required=True, type=Path)
    demo_verdict.set_defaults(func=demo_verdicts)

    demo_route = subparsers.add_parser("demo-routes", help="write deterministic demo routing JSONL")
    demo_route.add_argument("--key", required=True, type=Path)
    demo_route.add_argument("--output", required=True, type=Path)
    demo_route.set_defaults(func=demo_routes)

    score_parser = subparsers.add_parser("score", help="summarize forced-injection answer JSONL")
    score_parser.add_argument("--key", required=True, type=Path)
    score_parser.add_argument("--answers", required=True, type=Path)
    score_parser.add_argument("--verdicts", required=True, type=Path)
    score_parser.add_argument("--output", required=True, type=Path)
    score_parser.add_argument("--seed", type=int, default=20260618)
    score_parser.set_defaults(func=score)

    power_parser = subparsers.add_parser("power", help="estimate confirmatory paired n from a smoke summary")
    power_parser.add_argument("--summary", required=True, type=Path)
    power_parser.add_argument("--paired-metric", default="positive_verified_pass")
    power_parser.add_argument("--target-power", type=float, default=0.8)
    power_parser.add_argument("--alpha", type=float, default=0.05)
    power_parser.add_argument("--min-n", type=int, default=8)
    power_parser.add_argument("--max-n", type=int, default=1000)
    power_parser.add_argument("--output", required=True, type=Path)
    power_parser.set_defaults(func=power)

    promotion = subparsers.add_parser("promotion-check", help="apply the pre-registered promotion gate")
    promotion.add_argument("--summary", required=True, type=Path)
    promotion.add_argument("--routing-summary", type=Path)
    promotion.add_argument("--output", required=True, type=Path)
    promotion.add_argument("--stage", choices=["smoke", "confirmatory", "heldout"], default="smoke")
    promotion.add_argument("--primary-metric", default="positive_verified_pass")
    promotion.add_argument("--budgeted-metric", default="positive_budgeted_correct")
    promotion.add_argument("--negative-metric", default="negative_quality_score")
    promotion.add_argument("--min-positive-delta", type=float, default=0.05)
    promotion.add_argument("--min-primary-ci-low", type=float, default=0.0)
    promotion.add_argument("--min-budgeted-delta", type=float, default=0.0)
    promotion.add_argument("--negative-margin", type=float, default=-0.03)
    promotion.add_argument("--min-routing-negative-abstention", type=float, default=0.8)
    promotion.add_argument("--min-routing-positive-selection", type=float, default=0.8)
    promotion.add_argument("--max-cost-increase", type=float, default=0.2)
    promotion.set_defaults(func=promotion_check)

    route_score = subparsers.add_parser("score-routing", help="summarize routing probe outputs")
    route_score.add_argument("--key", required=True, type=Path)
    route_score.add_argument("--routes", required=True, type=Path)
    route_score.add_argument("--output", required=True, type=Path)
    route_score.set_defaults(func=score_routing)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
