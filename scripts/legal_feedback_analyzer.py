#!/usr/bin/env python3
"""Analyze LAB-style legal benchmark results and build retry task manifests."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_results(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        n_criteria = int(row.get("n_criteria", 0) or 0)
        n_passed = int(row.get("n_passed", 0) or 0)
        row["misses"] = n_criteria - n_passed
        row["criteria_rate"] = n_passed / n_criteria if n_criteria else 0.0
        row["domain"] = str(row.get("task", "")).split("/", 1)[0]
    return rows


def classify_failure(row: dict[str, Any]) -> str:
    task = str(row.get("task", ""))
    rate = float(row.get("criteria_rate", 0.0))
    misses = int(row.get("misses", 0))
    n_criteria = int(row.get("n_criteria", 0) or 0)
    if misses == 1:
        return "near_miss_final_criterion"
    if rate < 0.70 and "draft-" in task and n_criteria >= 80:
        return "large_draft_collapse"
    if rate < 0.70 and any(term in task for term in ["worksheet", "financial-covenants", "certificate"]):
        return "calculation_or_form_collapse"
    if rate < 0.70 and any(term in task for term in ["discovery", "counterparty", "issues"]):
        return "issue_spotting_coverage_collapse"
    if rate < 0.80:
        return "domain_scaffold_gap"
    if misses <= 3:
        return "small_coverage_gap"
    return "moderate_coverage_gap"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row for row in rows if not row.get("all_pass")]
    labels = Counter(classify_failure(row) for row in failed)
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_domain[row["domain"]].append(row)
    return {
        "total": len(rows),
        "all_pass": sum(1 for row in rows if row.get("all_pass")),
        "failed": len(failed),
        "one_miss": sum(1 for row in rows if row["misses"] == 1),
        "two_or_less_miss": sum(1 for row in rows if 0 < row["misses"] <= 2),
        "large_collapse_lt70": sum(1 for row in rows if row["criteria_rate"] < 0.70),
        "failure_taxonomy": dict(sorted(labels.items())),
        "domains": {
            domain: {
                "n": len(items),
                "all_pass": sum(1 for row in items if row.get("all_pass")),
                "one_miss": sum(1 for row in items if row["misses"] == 1),
                "large_collapse_lt70": sum(1 for row in items if row["criteria_rate"] < 0.70),
                "avg_criteria_rate": sum(row["criteria_rate"] for row in items) / len(items),
            }
            for domain, items in sorted(by_domain.items())
        },
    }


def select_retry(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    failed = [row for row in rows if not row.get("all_pass")]
    big = sorted([row for row in failed if row["criteria_rate"] < 0.70], key=lambda row: row["criteria_rate"])
    one_miss = sorted(
        [row for row in failed if row["misses"] == 1],
        key=lambda row: (-int(row.get("n_criteria", 0) or 0), str(row.get("task", ""))),
    )
    moderate = sorted(
        [row for row in failed if row not in big and row not in one_miss],
        key=lambda row: (row["misses"], -int(row.get("n_criteria", 0) or 0)),
    )
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bucket in (big, one_miss, moderate):
        for row in bucket:
            task = str(row["task"])
            if task in seen:
                continue
            selected.append(row)
            seen.add(task)
            if len(selected) >= limit:
                return selected
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retry-output", type=Path)
    parser.add_argument("--retry-limit", type=int, default=15)
    args = parser.parse_args()

    rows = load_results(args.results)
    analysis = summarize(rows)
    analysis["worst"] = [
        {
            "task": row["task"],
            "n_passed": row["n_passed"],
            "n_criteria": row["n_criteria"],
            "criteria_rate": row["criteria_rate"],
            "failure_class": classify_failure(row),
        }
        for row in sorted(rows, key=lambda row: row["criteria_rate"])[:20]
    ]
    analysis["one_miss_tasks"] = [
        {
            "task": row["task"],
            "n_passed": row["n_passed"],
            "n_criteria": row["n_criteria"],
            "failure_class": classify_failure(row),
        }
        for row in sorted([row for row in rows if row["misses"] == 1], key=lambda row: row["task"])
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.retry_output:
        selected = select_retry(rows, args.retry_limit)
        retry = {
            "source_results": str(args.results),
            "retry_limit": args.retry_limit,
            "tasks": [row["task"] for row in selected],
            "selection": [
                {
                    "task": row["task"],
                    "n_passed": row["n_passed"],
                    "n_criteria": row["n_criteria"],
                    "criteria_rate": row["criteria_rate"],
                    "failure_class": classify_failure(row),
                }
                for row in selected
            ],
        }
        args.retry_output.parent.mkdir(parents=True, exist_ok=True)
        args.retry_output.write_text(json.dumps(retry, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(analysis, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
