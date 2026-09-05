#!/usr/bin/env python3
"""Exercise the shipped Helix run split schema with Draft 2020-12."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(
    os.environ.get(
        "HELIX_SPLIT_SCHEMA_CONTRACT_ROOT",
        Path(__file__).resolve().parents[2],
    )
).resolve()
sys.path.insert(0, str(ROOT))

from scripts.helix_split_check import validate_record  # noqa: E402


def main() -> int:
    schema = json.loads(
        (ROOT / "schemas" / "helix-run-split.schema.json").read_text(encoding="utf-8")
    )
    sample = json.loads(
        (ROOT / "examples" / "helix-run-split.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
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

    def expect_validator(instance: dict[str, Any], *, valid: bool, label: str) -> None:
        nonlocal controls
        findings, _ = validate_record(instance)
        if bool(findings) == valid:
            raise AssertionError(
                f"{label}: expected validator valid={valid}, findings={[str(f) for f in findings][:3]}"
            )
        controls += 1

    expect_schema(sample, valid=True, label="sample positive")
    expect_validator(sample, valid=True, label="sample positive (validator)")

    unknown_key = copy.deepcopy(sample)
    unknown_key["deadline"] = "2026-01-01T10:00:00Z"
    expect_schema(unknown_key, valid=False, label="schema rejects an unknown key")
    expect_validator(unknown_key, valid=False, label="validator rejects an unknown key")

    bad_instant = copy.deepcopy(sample)
    bad_instant["clock"]["finished"] = "yesterday"
    expect_schema(bad_instant, valid=False, label="schema rejects a non-instant split")
    expect_validator(bad_instant, valid=False, label="validator rejects a non-instant split")

    bad_cause = copy.deepcopy(sample)
    bad_cause["time_sinks"][0]["cause"] = "vibes"
    expect_schema(bad_cause, valid=False, label="schema rejects an unlisted cause")
    expect_validator(bad_cause, valid=False, label="validator rejects an unlisted cause")

    # Type contract: the schema types these fields and the validator must not
    # let Python's looser notions (bool is an int, 0 is falsey) admit them.
    transfers_zero = copy.deepcopy(sample)
    transfers_zero["role_transfers"] = 0
    expect_schema(transfers_zero, valid=False, label="schema rejects role_transfers=0")
    expect_validator(transfers_zero, valid=False, label="validator rejects role_transfers=0")

    boolean_minutes = copy.deepcopy(sample)
    boolean_minutes["time_sinks"][0]["minutes"] = True
    expect_schema(boolean_minutes, valid=False, label="schema rejects boolean minutes")
    expect_validator(boolean_minutes, valid=False, label="validator rejects boolean minutes")

    profile_list = copy.deepcopy(sample)
    profile_list["run"]["loop_profile"] = []
    expect_schema(profile_list, valid=False, label="schema rejects a list loop_profile")
    expect_validator(profile_list, valid=False, label="validator rejects a list loop_profile")

    deferral_at_cap = copy.deepcopy(sample)
    deferral_at_cap["round_cap_disposition"] = ["https://github.com/example-org/example-repo/issues/7"]
    expect_schema(deferral_at_cap, valid=True, label="schema admits a deferral at the cap")
    expect_validator(deferral_at_cap, valid=True, label="validator admits a deferral at the cap (W4)")

    third_round_cause_only = copy.deepcopy(sample)
    third_round_cause_only["clock"]["findings_returned"].append(
        {"round": 3, "at": "2026-01-01T09:52:00Z", "finding_count": 0, "kind": "shipping_validation"}
    )
    third_round_cause_only["rounds"] = 3
    third_round_cause_only["third_round_cause"] = "shipping validation reopened the increment; nothing deferred"
    expect_schema(third_round_cause_only, valid=True, label="schema admits a third round with a cause only")
    expect_validator(third_round_cause_only, valid=True, label="validator admits a third round with a cause only")

    bad_kind = copy.deepcopy(sample)
    bad_kind["clock"]["findings_returned"][0]["kind"] = "vibes"
    expect_schema(bad_kind, valid=False, label="schema rejects an unlisted round kind")
    expect_validator(bad_kind, valid=False, label="validator rejects an unlisted round kind")

    # The schema is a structural floor. Two inputs it cannot judge are left to
    # the validator, which is why the validator, not the schema, is
    # authoritative: a banned glitch is a plain string to the schema, and a
    # well-formed instant naming a day that does not exist passes the pattern.
    banned = copy.deepcopy(sample)
    banned["warps_used"].append("stale_signoff")
    expect_schema(banned, valid=True, label="schema floor admits a banned glitch string")
    expect_validator(banned, valid=False, label="validator rejects a banned glitch without void")

    impossible_date = copy.deepcopy(sample)
    impossible_date["clock"]["finished"] = "2026-02-30T09:00:00Z"
    expect_schema(impossible_date, valid=True, label="schema pattern admits an impossible calendar date")
    expect_validator(impossible_date, valid=False, label="validator rejects an impossible calendar date")

    print(f"helix split schema contract: {controls} controls passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
