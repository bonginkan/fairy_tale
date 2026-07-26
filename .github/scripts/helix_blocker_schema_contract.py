#!/usr/bin/env python3
"""Exercise the shipped Helix blocker schema with Draft 2020-12."""

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
        "HELIX_BLOCKER_SCHEMA_CONTRACT_ROOT",
        Path(__file__).resolve().parents[2],
    )
).resolve()
sys.path.insert(0, str(ROOT))

from scripts.helix_blocker_triage import validate_record  # noqa: E402


def main() -> int:
    schema = json.loads(
        (ROOT / "schemas" / "helix-blocker-triage.schema.json").read_text(
            encoding="utf-8"
        )
    )
    sample = json.loads(
        (ROOT / "examples" / "helix-blocker-triage.json").read_text(
            encoding="utf-8"
        )
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

    expect_schema(sample, valid=True, label="sample positive")

    protected_defer = copy.deepcopy(sample)
    protected_defer["blockers"][0]["protected_floor"] = "production"
    protected_defer["blockers"][0]["resolution"]["priority"] = "P0"
    expect_schema(protected_defer, valid=False, label="protected floor cannot defer")

    missing_issue = copy.deepcopy(sample)
    missing_issue["blockers"][0]["resolution"]["issue_url"] = None
    expect_schema(missing_issue, valid=False, label="defer needs issue")

    missing_report = copy.deepcopy(sample)
    missing_report["blockers"][0]["resolution"]["human_report"] = None
    expect_schema(missing_report, valid=False, label="defer needs report")

    severity_bargain = copy.deepcopy(sample)
    severity_bargain["blockers"][1]["objection"]["refuted_claim"] = "severity"
    expect_schema(
        severity_bargain,
        valid=False,
        label="objection must refute failure sequence",
    )

    extra_round = copy.deepcopy(sample)
    extra_round["blockers"][1]["objection"]["tie_break"] = {
        "reviewer_id": "cc-misa-hime",
        "outcome": "sustain_blocker",
        "rationale": "An extra discussion round is not allowed after acceptance.",
        "evidence_refs": ["test:extra-round"],
    }
    expect_schema(extra_round, valid=False, label="accepted objection ends discussion")

    fabricated_deadline = copy.deepcopy(sample)
    fabricated_deadline["loop"]["deadline"]["source"] = "none"
    expect_schema(fabricated_deadline, valid=False, label="absent deadline shape")

    untrusted_fresh_usage = copy.deepcopy(sample)
    untrusted_fresh_usage["loop"]["usage"]["source"] = "self_report"
    expect_schema(
        untrusted_fresh_usage,
        valid=False,
        label="fresh usage needs trusted source",
    )

    unknown_key = copy.deepcopy(sample)
    unknown_key["blockers"][0]["resolution"]["extra"] = True
    expect_schema(unknown_key, valid=False, label="unknown key")

    unreported_with_ref = copy.deepcopy(sample)
    unreported_with_ref["blockers"][0]["resolution"]["disposition"] = "fix_now"
    unreported_with_ref["blockers"][0]["resolution"]["priority"] = "P3"
    unreported_with_ref["blockers"][0]["resolution"]["concurred_by"] = []
    unreported_with_ref["blockers"][0]["resolution"]["issue_url"] = None
    unreported_with_ref["blockers"][0]["resolution"]["human_report"] = None
    unreported_with_ref["final_readback"]["deferred_blocker_ids"] = []
    unreported_with_ref["final_readback"]["retained_blocker_ids"] = [
        "low-probability-capacity-eviction"
    ]
    unreported_with_ref["final_readback"]["reported_to_human"] = False
    unreported_with_ref["final_readback"]["report_ref"] = "source:unexpected-report"
    expect_schema(
        unreported_with_ref,
        valid=False,
        label="unreported readback cannot carry a report ref",
    )

    reported_without_ref = copy.deepcopy(unreported_with_ref)
    reported_without_ref["final_readback"]["reported_to_human"] = True
    reported_without_ref["final_readback"]["report_ref"] = ""
    expect_schema(
        reported_without_ref,
        valid=False,
        label="reported readback needs an evidence ref",
    )

    # Cross-array identities, risk arithmetic, freshness, and exact final
    # readback sets are authoritative in the runtime validator.
    same_role = copy.deepcopy(sample)
    same_role["loop"]["roles"]["reviewer_ids"][0] = "misa-3"
    expect_schema(same_role, valid=True, label="role separation is runtime-bound")
    if not validate_record(same_role):
        raise AssertionError("runtime must reject implementer/reviewer overlap")
    controls += 1

    hidden_defer = copy.deepcopy(sample)
    hidden_defer["final_readback"]["deferred_blocker_ids"] = []
    expect_schema(hidden_defer, valid=True, label="readback set is runtime-bound")
    if not validate_record(hidden_defer):
        raise AssertionError("runtime must reject hidden deferred finding")
    controls += 1

    stale_usage = copy.deepcopy(sample)
    stale_usage["loop"]["usage"]["observed_at"] = "2026-07-26T10:00:00+09:00"
    expect_schema(stale_usage, valid=True, label="freshness arithmetic is runtime-bound")
    if not validate_record(stale_usage):
        raise AssertionError("runtime must reject stale fresh-usage claim")
    controls += 1

    excessive_risk = copy.deepcopy(sample)
    excessive_risk["blockers"][0]["impact"] = "critical"
    excessive_risk["blockers"][0]["probability_percent"] = 20
    excessive_risk["blockers"][0]["resolution"]["priority"] = "P2"
    expect_schema(excessive_risk, valid=True, label="risk arithmetic is runtime-bound")
    if not validate_record(excessive_risk):
        raise AssertionError("runtime must reject excessive defer risk")
    controls += 1

    print(f"Helix blocker schema contract OK: {controls} controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
