#!/usr/bin/env python3
"""Exercise the shipped implementation-contract-closure schema with Draft 2020-12.

The schema owns the static shape; `scripts/implementation_contract_closure.py`
owns closure itself (cross product, hazard-kind admissibility, versioned-diff
re-closure). This contract keeps the two aligned and proves the hostile cases
are rejected by at least one of them.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(
    os.environ.get(
        "CONTRACT_CLOSURE_SCHEMA_CONTRACT_ROOT",
        Path(__file__).resolve().parents[2],
    )
).resolve()
sys.path.insert(0, str(ROOT))

from scripts.implementation_contract_closure import (  # noqa: E402
    validate_record,
    validate_shape,
)


def main() -> int:
    schema = json.loads(
        (ROOT / "schemas" / "implementation-contract-closure.schema.json").read_text(
            encoding="utf-8"
        )
    )
    sample = json.loads(
        (ROOT / "examples" / "implementation-contract-closure.json").read_text(
            encoding="utf-8"
        )
    )
    inventory_path = ROOT / "examples" / "implementation-contract-closure.inventory.txt"
    inventory_raw = inventory_path.read_bytes()
    inventory = [
        line.strip()
        for line in inventory_raw.decode("utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    declared_hash = sample.get("inventory_source", {}).get("sha256")
    actual_hash = hashlib.sha256(inventory_raw).hexdigest()
    if declared_hash != actual_hash:
        print(
            f"[RED    ] shipped example is not bound to the shipped inventory: "
            f"{declared_hash} vs {actual_hash}"
        )
        return 1
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    controls = 1

    errors = sorted(validator.iter_errors(sample), key=lambda e: e.path)
    if errors:
        print(f"[RED    ] shipped example violates the schema: {[e.message for e in errors]}")
        return 1
    controls += 1

    # The dependency-free shape evaluator and jsonschema must agree, or the
    # canonical CLI (which cannot assume jsonschema) would diverge from CI.
    schema_path = ROOT / "schemas" / "implementation-contract-closure.schema.json"
    cross_checks = [
        ("shipped sample", copy.deepcopy(sample), False),
        ("unknown nested key", None, True),
        ("wrong nested type", None, True),
    ]
    nested = copy.deepcopy(sample)
    nested["operations"][0]["unexpected_nested"] = True
    cross_checks[1] = ("unknown nested key", nested, True)
    typed = copy.deepcopy(sample)
    typed["operations"][0]["reads"] = "attachment"
    cross_checks[2] = ("wrong nested type", typed, True)
    for label, candidate, expect_error in cross_checks:
        schema_says = bool(list(validator.iter_errors(candidate)))
        evaluator_says = bool(validate_shape(candidate, schema_path))
        if schema_says != evaluator_says or schema_says != expect_error:
            print(
                f"[RED    ] shape evaluator and jsonschema disagree on {label}: "
                f"jsonschema={schema_says} evaluator={evaluator_says} expected={expect_error}"
            )
            return 1
        controls += 1

    # Provenance is exercised by the CLI step in CI (it needs real Git
    # objects); here the sample is checked for everything else, so the only
    # admissible finding is the missing trusted base.
    findings = validate_record(
        sample, None, inventory, "examples/implementation-contract-closure.inventory.txt", None, ROOT, None
    )
    findings = [f for f in findings if "no trusted base revision" not in str(f)]
    if findings:
        print(f"[RED    ] shipped example fails the runtime gate: {[str(f) for f in findings]}")
        return 1
    controls += 1

    def rejected(record: Any, label: str) -> bool:
        nonlocal controls
        controls += 1
        schema_errors = list(validator.iter_errors(record))
        runtime_findings = validate_record(
            record, None, inventory, "examples/implementation-contract-closure.inventory.txt", None, ROOT, None
        )
        if schema_errors or runtime_findings:
            return True
        print(f"[RED    ] hostile case accepted by both schema and runtime gate: {label}")
        return False

    ok = True

    # A record that declares its own closure.
    declared = copy.deepcopy(sample)
    declared["closure_reached"] = True
    ok &= rejected(declared, "self-declared closure")

    # A hand-listed subset of the cross product.
    subset = copy.deepcopy(sample)
    subset["concurrency_matrix"] = subset["concurrency_matrix"][:2]
    ok &= rejected(subset, "omitted concurrency pair")

    # An impossibility that is really a timing argument.
    timing = copy.deepcopy(sample)
    timing["concurrency_matrix"][1] = {
        "pair": ["remove", "upload"],
        "disposition": "impossible",
        "impossibility": {"kind": "ui_flow", "evidence": "the button is disabled"},
    }
    ok &= rejected(timing, "timing dressed as impossibility")

    # A blank uncertainty cell.
    blank = copy.deepcopy(sample)
    blank["failure_matrix"][0]["unknown"] = ""
    ok &= rejected(blank, "blank UNKNOWN cell")

    # An operation the CODE surface has but the record omits — trimming the
    # record AND its inventory together cannot launder it away.
    omitted = copy.deepcopy(sample)
    omitted["operations"] = [op for op in omitted["operations"] if op["id"] != "list"]
    omitted["concurrency_matrix"] = [
        cell for cell in omitted["concurrency_matrix"] if "list" not in cell["pair"]
    ]
    ok &= rejected(omitted, "operation omission")

    # Re-closure without the base record it must diff against.
    unbased = copy.deepcopy(sample)
    unbased["record_kind"] = "revision"
    unbased["fix_reclosure"] = {
        "fix_id": "fix-1",
        "introduced_at": "2026-07-28T01:00:00+00:00",
        "base_record_ref": "previous",
        "base_record_sha256": "0" * 64,
        "base_exact_base": "0" * 40,
    }
    scoped = copy.deepcopy(sample)
    scoped["inventory_source"]["discovery"] = {"globs": ["x/*.ts"], "pattern": "(?P<operation>x)"}
    ok &= rejected(scoped, "record-declared discovery scope")
    duplicate_identity = copy.deepcopy(sample)
    shadow = copy.deepcopy(duplicate_identity["identities"][0])
    shadow["owner"] = "someone else"
    duplicate_identity["identities"].append(shadow)
    ok &= rejected(duplicate_identity, "duplicate identity definition")
    ok &= rejected(unbased, "re-closure without a base record")

    if not ok:
        return 1
    print(f"implementation contract closure schema contract OK: {controls} controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
