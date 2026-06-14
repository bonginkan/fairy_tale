#!/usr/bin/env python3
"""Detect contradictory or low-value feedback rules and propose pruning.

Input is a JSON array, a JSON object with a ``rules`` array, or JSONL. Each
rule should contain at least ``id`` and ``rule`` or ``text``. Optional fields
such as ``scope``, ``failure_class``, ``status``, ``metrics``,
``conflicts_with``, ``supersedes``, and ``superseded_by`` improve decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


OPPOSITION_GROUPS = [
    ({"always", "must", "require", "include", "accept", "broaden", "expand"}, {"never", "avoid", "forbid", "exclude", "reject", "narrow", "limit"}),
    ({"summarize", "compress", "deduplicate", "merge"}, {"enumerate", "exhaustive", "separate", "matrix"}),
    ({"generic", "broad", "universal"}, {"specific", "narrow", "domain"}),
]


@dataclass(frozen=True)
class Rule:
    raw: dict[str, Any]
    index: int
    rule_id: str
    text: str
    scope: str
    failure_class: str
    status: str
    fingerprint: str


def load_rules(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            rules = payload.get("rules", [])
        else:
            rules = payload
        if not isinstance(rules, list):
            raise ValueError("JSON input must be a list or an object with a rules list")
        return [rule for rule in rules if isinstance(rule, dict)]
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        return [row for row in rows if isinstance(row, dict)]


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def stable_id(raw: dict[str, Any], index: int) -> str:
    if raw.get("id"):
        return str(raw["id"])
    if raw.get("name"):
        return str(raw["name"])
    text = str(raw.get("rule") or raw.get("text") or raw)
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"rule-{index + 1}-{digest}"


def rule_from_raw(raw: dict[str, Any], index: int) -> Rule:
    text = str(raw.get("rule") or raw.get("text") or raw.get("description") or "")
    scope = str(raw.get("scope") or raw.get("domain") or "global")
    failure_class = str(raw.get("failure_class") or raw.get("class") or "general")
    status = str(raw.get("status") or "candidate").lower()
    fingerprint_source = "\n".join([scope, failure_class, normalize_text(text)])
    fingerprint = hashlib.sha1(fingerprint_source.encode("utf-8")).hexdigest()[:16]
    return Rule(
        raw=raw,
        index=index,
        rule_id=stable_id(raw, index),
        text=text,
        scope=scope,
        failure_class=failure_class,
        status=status,
        fingerprint=fingerprint,
    )


def tokens(value: str) -> set[str]:
    return set(normalize_text(value).split())


def has_opposition(a: str, b: str) -> bool:
    a_tokens = tokens(a)
    b_tokens = tokens(b)
    for left, right in OPPOSITION_GROUPS:
        if (a_tokens & left and b_tokens & right) or (a_tokens & right and b_tokens & left):
            return True
    return False


def same_scope(a: Rule, b: Rule) -> bool:
    return (a.scope, a.failure_class) == (b.scope, b.failure_class)


def explicit_conflicts(rule: Rule) -> set[str]:
    values = rule.raw.get("conflicts_with") or rule.raw.get("conflicts")
    if isinstance(values, str):
        return {values}
    if isinstance(values, list):
        return {str(value) for value in values}
    return set()


def detect_conflicts(rules: list[Rule]) -> list[dict[str, Any]]:
    by_id = {rule.rule_id: rule for rule in rules}
    conflicts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for rule in rules:
        for target_id in explicit_conflicts(rule):
            target = by_id.get(target_id)
            if not target:
                continue
            key = tuple(sorted([rule.rule_id, target.rule_id]) + ["explicit"])
            if key in seen:
                continue
            seen.add(key)
            conflicts.append(
                {
                    "type": "explicit_conflict",
                    "rule_ids": [rule.rule_id, target.rule_id],
                    "reason": "conflicts_with reference",
                }
            )

    for i, left in enumerate(rules):
        for right in rules[i + 1 :]:
            if not same_scope(left, right):
                continue
            if left.fingerprint == right.fingerprint:
                key = tuple(sorted([left.rule_id, right.rule_id]) + ["duplicate"])
                if key not in seen:
                    seen.add(key)
                    conflicts.append(
                        {
                            "type": "duplicate",
                            "rule_ids": [left.rule_id, right.rule_id],
                            "reason": "same normalized scope, failure class, and rule text",
                        }
                    )
                continue
            if has_opposition(left.text, right.text):
                key = tuple(sorted([left.rule_id, right.rule_id]) + ["semantic_opposition"])
                if key not in seen:
                    seen.add(key)
                    conflicts.append(
                        {
                            "type": "semantic_opposition",
                            "rule_ids": [left.rule_id, right.rule_id],
                            "reason": "opposing action words in same scope/failure class",
                        }
                    )
    return conflicts


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def metric_delta(raw: dict[str, Any], key: str) -> float | None:
    metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
    before = metrics.get(f"before_{key}")
    after = metrics.get(f"after_{key}")
    if before is None:
        before = raw.get(f"before_{key}")
    if after is None:
        after = raw.get(f"after_{key}")
    try:
        if before is None or after is None:
            return None
        return float(after) - float(before)
    except (TypeError, ValueError):
        return None


def evidence_count(raw: dict[str, Any]) -> int:
    evidence = raw.get("evidence") or raw.get("artifacts") or raw.get("source_runs") or []
    if isinstance(evidence, list):
        return len(evidence)
    return 1 if evidence else 0


def rule_score(rule: Rule) -> dict[str, Any]:
    all_pass_delta = metric_delta(rule.raw, "all_pass_rate")
    criterion_delta = metric_delta(rule.raw, "criterion_pass_rate")
    regression_count = int(rule.raw.get("regression_count") or rule.raw.get("regressions") or 0)
    retry_n = int(rule.raw.get("retry_n") or rule.raw.get("sample_size") or 0)
    evidence = evidence_count(rule.raw)
    last_seen = parse_date(rule.raw.get("last_seen") or rule.raw.get("updated_at") or rule.raw.get("created_at"))

    positive = any(delta is not None and delta > 0 for delta in [all_pass_delta, criterion_delta])
    negative = any(delta is not None and delta < 0 for delta in [all_pass_delta, criterion_delta])
    weak = evidence == 0 or retry_n == 0
    stale = False
    if last_seen is not None:
        stale = (date.today() - last_seen).days > 90

    return {
        "all_pass_delta": all_pass_delta,
        "criterion_delta": criterion_delta,
        "regression_count": regression_count,
        "retry_n": retry_n,
        "evidence_count": evidence,
        "stale": stale,
        "positive": positive,
        "negative": negative,
        "weak": weak,
    }


def classify_rules(rules: list[Rule], conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conflicts_by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for conflict in conflicts:
        for rule_id in conflict["rule_ids"]:
            conflicts_by_rule[rule_id].append(conflict)

    superseded_rule_ids: set[str] = set()
    for rule in rules:
        if rule.raw.get("superseded_by"):
            superseded_rule_ids.add(rule.rule_id)
        supersedes = rule.raw.get("supersedes")
        if isinstance(supersedes, str):
            superseded_rule_ids.add(supersedes)
        elif isinstance(supersedes, list):
            superseded_rule_ids.update(str(value) for value in supersedes)
    superseded_rule_ids.discard("")

    decisions: list[dict[str, Any]] = []
    for rule in rules:
        score = rule_score(rule)
        reasons: list[str] = []
        decision = "keep"

        if rule.rule_id in superseded_rule_ids:
            decision = "prune"
            reasons.append("superseded")

        if conflicts_by_rule.get(rule.rule_id):
            if decision != "prune":
                decision = "review"
            reasons.append("conflict_or_duplicate")

        if rule.status in {"deprecated", "rejected", "pruned"}:
            decision = "prune"
            reasons.append(f"status:{rule.status}")
        elif rule.status in {"approved", "kept", "locked"} and decision == "keep":
            reasons.append(f"status:{rule.status}")

        if rule.status == "candidate" and not score["positive"] and decision == "keep":
            decision = "review"
            reasons.append("candidate_without_measured_improvement")

        if score["negative"] and score["regression_count"] > 0:
            decision = "prune" if rule.status not in {"approved", "locked"} else "review"
            reasons.append("measured_regression")
        elif score["weak"] and decision == "keep":
            decision = "review"
            reasons.append("insufficient_evidence")
        elif score["stale"] and not score["positive"] and decision == "keep":
            decision = "review"
            reasons.append("stale_without_positive_evidence")

        decisions.append(
            {
                "id": rule.rule_id,
                "decision": decision,
                "scope": rule.scope,
                "failure_class": rule.failure_class,
                "fingerprint": rule.fingerprint,
                "reasons": reasons or ["positive_or_neutral_evidence"],
                "metrics": score,
                "rule": rule.text,
            }
        )
    return decisions


def report(rules: list[Rule], decisions: list[dict[str, Any]], conflicts: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(decision["decision"] for decision in decisions)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rule_count": len(rules),
        "decision_counts": dict(sorted(counts.items())),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "decisions": decisions,
        "kept_rules": [decision["id"] for decision in decisions if decision["decision"] == "keep"],
        "review_rules": [decision["id"] for decision in decisions if decision["decision"] == "review"],
        "pruned_rules": [decision["id"] for decision in decisions if decision["decision"] == "prune"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kept-output", type=Path)
    args = parser.parse_args()

    raw_rules = load_rules(args.ledger)
    rules = [rule_from_raw(raw, index) for index, raw in enumerate(raw_rules)]
    conflicts = detect_conflicts(rules)
    decisions = classify_rules(rules, conflicts)
    payload = report(rules, decisions, conflicts)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.kept_output:
        kept_ids = set(payload["kept_rules"])
        kept = [rule.raw for rule in rules if rule.rule_id in kept_ids]
        args.kept_output.parent.mkdir(parents=True, exist_ok=True)
        args.kept_output.write_text(json.dumps({"rules": kept}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
