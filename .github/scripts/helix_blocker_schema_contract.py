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

from scripts.helix_blocker_triage import (  # noqa: E402
    legacy_sample_record,
    migrate_record,
    validate_record,
)


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
    # A retained fix-now finding holds the ship, so the decision moves with it
    # and this control keeps testing only the report-ref rule it is named for.
    unreported_with_ref["final_readback"]["ship_decision"] = {
        "decision": "hold",
        "rationale": "A retained fix-now finding holds this increment.",
    }
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

    stage_basis_mismatch = copy.deepcopy(sample)
    stage_basis_mismatch["loop"]["ship_stage"]["basis"] = "production_promotion"
    expect_schema(
        stage_basis_mismatch,
        valid=False,
        label="a dev ship cannot claim the production promotion basis",
    )

    unverified_with_check = copy.deepcopy(sample)
    unverified_with_check["loop"]["ship_stage"]["happy_path"]["verified"] = False
    expect_schema(
        unverified_with_check,
        valid=False,
        label="an unverified normal path cannot carry a check ref",
    )

    floor_without_basis = copy.deepcopy(sample)
    floor_without_basis["blockers"][2]["floor_basis"] = "not_applicable"
    expect_schema(
        floor_without_basis,
        valid=False,
        label="a safety-floor finding needs a demonstrated/precautionary basis",
    )

    basis_off_floor = copy.deepcopy(sample)
    basis_off_floor["blockers"][0]["floor_basis"] = "precautionary"
    expect_schema(
        basis_off_floor,
        valid=False,
        label="a finding off the floor must record not_applicable",
    )

    demonstrated_security_defer = copy.deepcopy(sample)
    demonstrated_security_defer["blockers"][2]["floor_basis"] = "demonstrated"
    expect_schema(
        demonstrated_security_defer,
        valid=False,
        label="a demonstrated security defect cannot be deferred",
    )

    for escaping_class in ("abnormal_path", "other"):
        security_class_escape = copy.deepcopy(sample)
        security_class_escape["blockers"][2]["finding_class"] = escaping_class
        expect_schema(
            security_class_escape,
            valid=False,
            label=f"a {escaping_class} security finding cannot be deferred",
        )

    missing_attestation = copy.deepcopy(sample)
    missing_attestation["loop"]["ship_stage"]["evidence_attestation"] = None
    expect_schema(
        missing_attestation,
        valid=False,
        label="a verified dev ship needs a reviewer evidence attestation",
    )

    production_attestation = copy.deepcopy(sample)
    production_attestation["loop"]["ship_stage"]["stage"] = "production"
    production_attestation["loop"]["ship_stage"]["basis"] = "production_promotion"
    expect_schema(
        production_attestation,
        valid=False,
        label="a production stage cannot carry a ship evidence attestation",
    )

    happy_path_defer = copy.deepcopy(sample)
    happy_path_defer["blockers"][0]["finding_class"] = "happy_path"
    expect_schema(
        happy_path_defer,
        valid=False,
        label="a normal-path finding cannot be deferred",
    )

    go_with_retained = copy.deepcopy(sample)
    go_with_retained["final_readback"]["retained_blocker_ids"] = [
        "false-positive-finding"
    ]
    expect_schema(
        go_with_retained,
        valid=False,
        label="a go decision cannot carry retained fix-now findings",
    )

    # Cross-array identities, risk arithmetic, freshness, and exact final
    # readback sets are authoritative in the runtime validator.
    production_precautionary_defer = copy.deepcopy(sample)
    production_precautionary_defer["loop"]["ship_stage"] = {
        "stage": "production",
        "basis": "production_promotion",
        "basis_ref": "source:release-promotion",
        "happy_path": copy.deepcopy(sample["loop"]["ship_stage"]["happy_path"]),
        "evidence_attestation": None,
    }
    expect_schema(
        production_precautionary_defer,
        valid=True,
        label="stage-conditioned floor deferral is runtime-bound",
    )
    if not validate_record(production_precautionary_defer):
        raise AssertionError(
            "runtime must reject a precautionary floor deferral at production stage"
        )
    controls += 1

    green_hold = copy.deepcopy(sample)
    green_hold["final_readback"]["ship_decision"] = {
        "decision": "hold",
        "rationale": "The reviewer would prefer one more hardening round first.",
    }
    expect_schema(green_hold, valid=True, label="green-hold rejection is runtime-bound")
    if not validate_record(green_hold):
        raise AssertionError("runtime must reject holding a green dev increment")
    controls += 1

    same_role = copy.deepcopy(sample)
    same_role["loop"]["roles"]["reviewer_ids"][0] = "misa-3"
    expect_schema(same_role, valid=True, label="role separation is runtime-bound")
    if not validate_record(same_role):
        raise AssertionError("runtime must reject implementer/reviewer overlap")
    controls += 1

    finding_reviewer_only = copy.deepcopy(sample)
    finding_reviewer_only["blockers"][0]["resolution"]["concurred_by"] = [
        "codex-misa"
    ]
    expect_schema(
        finding_reviewer_only,
        valid=True,
        label="independent concurrence identity is runtime-bound",
    )
    if not validate_record(finding_reviewer_only):
        raise AssertionError(
            "runtime must reject concurrence only from the finding reviewer"
        )
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

    self_attested = copy.deepcopy(sample)
    self_attested["loop"]["ship_stage"]["evidence_attestation"]["reviewer_id"] = "misa-3"
    expect_schema(
        self_attested,
        valid=True,
        label="attesting-reviewer identity is runtime-bound",
    )
    if not validate_record(self_attested):
        raise AssertionError(
            "runtime must reject a ship attestation written by the implementer"
        )
    controls += 1

    single_floor_concurrence = copy.deepcopy(sample)
    single_floor_concurrence["blockers"][2]["resolution"]["concurred_by"] = [
        "codex-misa"
    ]
    expect_schema(
        single_floor_concurrence,
        valid=True,
        label="floor-deferral panel size is runtime-bound",
    )
    if not validate_record(single_floor_concurrence):
        raise AssertionError(
            "runtime must reject a floor deferral without the full reviewer panel"
        )
    controls += 1

    # The persisted 1.0 contract keeps a tested upgrade path into this schema.
    legacy = legacy_sample_record()
    expect_schema(legacy, valid=False, label="schema 1.0 is not the current contract")
    migrated = migrate_record(legacy)
    expect_schema(migrated, valid=True, label="a migrated 1.0 record satisfies the schema")
    if validate_record(migrated):
        raise AssertionError("runtime must accept the migrated 1.0 record")
    controls += 1

    print(f"Helix blocker schema contract OK: {controls} controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
