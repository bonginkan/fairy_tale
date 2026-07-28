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

from scripts.implementation_contract_closure import validate_record  # noqa: E402


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

    findings = validate_record(sample, None, inventory)
    if findings:
        print(f"[RED    ] shipped example fails the runtime gate: {[str(f) for f in findings]}")
        return 1
    controls += 1

    def rejected(record: Any, label: str) -> bool:
        nonlocal controls
        controls += 1
        schema_errors = list(validator.iter_errors(record))
        runtime_findings = validate_record(record, None, inventory)
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

    # An operation the EXTERNAL canonical inventory has but the record omits —
    # trimming the record's own tables cannot launder it away.
    omitted = copy.deepcopy(sample)
    omitted["operations"] = [op for op in omitted["operations"] if op["id"] != "list"]
    omitted["concurrency_matrix"] = [
        cell for cell in omitted["concurrency_matrix"] if "list" not in cell["pair"]
    ]
    ok &= rejected(omitted, "operation omission")

    # Re-closure without the base record it must diff against.
    unbased = copy.deepcopy(sample)
    unbased["fix_reclosure"] = {
        "fix_id": "fix-1",
        "introduced_at": "2026-07-28T01:00:00+00:00",
        "base_record_ref": "previous",
        "base_record_sha256": "0" * 64,
    }
    ok &= rejected(unbased, "re-closure without a base record")

    if not ok:
        return 1
    print(f"implementation contract closure schema contract OK: {controls} controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
