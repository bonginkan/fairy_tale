#!/usr/bin/env python3
"""Exercise the shipped E3 schema with a Draft 2020-12 validator."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(
    os.environ.get("E3_SCHEMA_CONTRACT_ROOT", Path(__file__).resolve().parents[2])
).resolve()
sys.path.insert(0, str(ROOT))

from scripts.e3_execution import append_attempt, make_ledger, validate_ledger  # noqa: E402


def load_case(index: int) -> dict[str, Any]:
    lines = (
        ROOT / "fixtures" / "e3-execution" / "cases.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    return json.loads(lines[index])


def build_ledger(case: dict[str, Any], attempts: int) -> dict[str, Any]:
    ledger = make_ledger(copy.deepcopy(case["spec"]))
    for attempt in case["attempts"][:attempts]:
        ledger = append_attempt(ledger, copy.deepcopy(attempt))
    return ledger


def main() -> int:
    schema = json.loads(
        (ROOT / "schemas" / "e3-execution-ledger.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    controls = 1

    def expect_schema(instance: dict[str, Any], *, valid: bool, label: str) -> None:
        nonlocal controls
        errors = list(validator.iter_errors(instance))
        if bool(errors) == valid:
            detail = "; ".join(error.message for error in errors[:3])
            raise AssertionError(
                f"{label}: expected schema valid={valid}, errors={detail or 'none'}"
            )
        controls += 1

    verified = build_ledger(load_case(0), 1)
    failed = build_ledger(load_case(1), 1)
    blocked_case = copy.deepcopy(load_case(0))
    blocked_verification = blocked_case["attempts"][0]["verification"]
    blocked_verification["result"] = "blocked"
    blocked_verification["checks"][0]["result"] = "blocked"
    blocked_verification["checks"][0]["notes"] = "The acceptance check was blocked."
    for gate in blocked_verification["checks"][1:]:
        gate["result"] = "not_run"
        gate["evidence"] = []
        gate["notes"] = "Deferred because the acceptance check was blocked."
    blocked_verification["notes"] = "Execution was blocked."
    blocked = build_ledger(blocked_case, 1)
    expect_schema(verified, valid=True, label="verified positive control")
    expect_schema(failed, valid=True, label="failed positive control")
    expect_schema(blocked, valid=True, label="blocked positive control")

    for result in ("pass", "fail", "blocked"):
        mutant = copy.deepcopy(verified)
        verification = mutant["attempts"][0]["verification"]
        verification["result"] = result
        verification["checks"][0]["result"] = result
        verification["checks"][0]["evidence"] = []
        expect_schema(
            mutant,
            valid=False,
            label=f"{result} check needs evidence",
        )

    all_not_run = copy.deepcopy(verified)
    verification = all_not_run["attempts"][0]["verification"]
    verification["result"] = "fail"
    for check in verification["checks"]:
        check["result"] = "not_run"
        check["evidence"] = []
    expect_schema(
        all_not_run,
        valid=False,
        label="aggregate fail needs a failed check",
    )

    no_blocked_check = copy.deepcopy(all_not_run)
    no_blocked_check["attempts"][0]["verification"]["result"] = "blocked"
    expect_schema(
        no_blocked_check,
        valid=False,
        label="aggregate blocked needs a blocked check",
    )

    behavior_only = copy.deepcopy(verified)
    behavior_only["attempts"][0]["verification"]["checks"] = behavior_only[
        "attempts"
    ][0]["verification"]["checks"][:1]
    expect_schema(
        behavior_only,
        valid=False,
        label="aggregate pass needs default safety gates",
    )

    nonpassing_gate = copy.deepcopy(verified)
    gate = nonpassing_gate["attempts"][0]["verification"]["checks"][1]
    gate["result"] = "not_run"
    gate["evidence"] = []
    expect_schema(
        nonpassing_gate,
        valid=False,
        label="aggregate pass needs every check to pass",
    )

    custom_case = copy.deepcopy(load_case(0))
    custom_case["spec"]["safety_gates"].append("repository_policy")
    custom_case["attempts"][0]["verification"]["checks"].append(
        {
            "id": "repository_policy",
            "result": "pass",
            "evidence": ["run:target-pass"],
            "notes": "Repository policy passed.",
        }
    )
    custom = build_ledger(custom_case, 1)
    expect_schema(custom, valid=True, label="custom gate positive control")

    missing_custom = copy.deepcopy(custom)
    missing_custom["attempts"][0]["verification"]["checks"] = [
        check
        for check in missing_custom["attempts"][0]["verification"]["checks"]
        if check["id"] != "repository_policy"
    ]
    expect_schema(
        missing_custom,
        valid=True,
        label="dynamic custom coverage remains outside schema",
    )
    if not validate_ledger(missing_custom):
        raise AssertionError(
            "authoritative runtime must reject missing dynamic custom-gate coverage"
        )
    controls += 1

    missing_acceptance = copy.deepcopy(verified)
    missing_acceptance["attempts"][0]["verification"]["checks"] = [
        check
        for check in missing_acceptance["attempts"][0]["verification"]["checks"]
        if check["id"] != "target-check"
    ]
    expect_schema(
        missing_acceptance,
        valid=True,
        label="dynamic acceptance coverage remains outside schema",
    )
    if not validate_ledger(missing_acceptance):
        raise AssertionError(
            "authoritative runtime must reject missing dynamic acceptance coverage"
        )
    controls += 1

    print(f"E3 schema contract OK: {controls} controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
