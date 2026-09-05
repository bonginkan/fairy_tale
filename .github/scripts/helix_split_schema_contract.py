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

    # The schema is a structural floor: a banned glitch is a plain string to
    # the schema and only the validator voids the run. This asymmetry is the
    # reason the validator, not the schema, is authoritative.
    banned = copy.deepcopy(sample)
    banned["warps_used"].append("stale_signoff")
    expect_schema(banned, valid=True, label="schema floor admits a banned glitch string")
    expect_validator(banned, valid=False, label="validator rejects a banned glitch without void")

    print(f"helix split schema contract: {controls} controls passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
