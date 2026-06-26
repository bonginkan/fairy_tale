#!/usr/bin/env python3
"""Exercise/enforcement check for Spiral Engineering revolution records.

This is deliberately NOT a residency presence check. `fairy_tale_residency_check.py`
verifies that the spiral *spec text* exists in the docs (presence). That is not
enough: a spec can be written and then never used. PR #41 shipped the Spiral
Engineering / double-helix spec with green presence/parity/CI, yet carried no
exercised revolution record and no evidence-pairing enforcement -- a
false-negative surfaced under Jun's no-blocking critical-thinking challenge
(fairy_tale #43/#44).

This script exercises the spec: it requires at least one well-formed spiral
revolution record whose evidence-bearing fields carry CONCRETE references
(URLs, commit shas, #issue/PR, run-/trace-/sha256 ids). A record with empty,
missing, or placeholder evidence fails -- so the gate cannot be satisfied by
presence alone.

Usage:
  spiral_revolution_check.py [--records DIR] [--json]

Exit code 0 = at least one record present and all records pass; 1 = otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS_DIR = ROOT / "spiral-revolutions"

# A concrete, *verifiable* reference. Each evidence entry must BE one of these
# (hostile-review hardened, fairy_tale #44 / PR #45): a bare short hex token
# (`deadbee`), a bare `#44`, or freeform prose ("trust me, reviewed") are NOT
# concrete refs and are rejected. Accepted forms:
#   - URL with host+path:        https://github.com/owner/repo/pull/41
#   - full 40-hex commit sha:    98341e43fce99a1157fbebec713537b406ef8e81
#   - sha256 digest (>=32 hex):  sha256:9e5e7b60...
#   - run-/trace- id (length):   run-20260626T0011Z-cc-...
#   - an existing repo file path: scripts/spiral_revolution_check.py
_URL = r"https?://[^\s/]+\.[^\s/]+/\S+"
_FULL_SHA = r"\b[0-9a-f]{40}\b"
_SHA256 = r"\bsha256:[0-9a-f]{32,}\b"
_RUNTRACE = r"\b(?:run|trace)-[0-9A-Za-z][0-9A-Za-z._-]{7,}\b"
CONCRETE_REF = re.compile("|".join((_URL, _FULL_SHA, _SHA256, _RUNTRACE)), re.IGNORECASE)
REPO_PATH_RE = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.(?:py|json|md|ts|tsx|js|mjs|cjs|yml|yaml|sh|toml|txt)")

# Short label words allowed to accompany a ref (e.g. "merge commit <sha>") without
# the entry counting as freeform prose.
_LABEL_WORDS = re.compile(r"(?i)\b(?:commit|merge|pr|issue|sha|ref|run|trace|id|see|at|in|on|the|comment)\b")

# Residue (entry minus refs/labels/punctuation) longer than this means the entry
# is prose with a ref smuggled in, not a clean reference.
_MAX_RESIDUE = 12

# Tokens that look like evidence but are not.
PLACEHOLDERS = {
    "", "todo", "tbd", "n/a", "na", "none", "null", "-", "--", "...",
    "placeholder", "xxx", "fixme", "pending", "wip", "?",
}

# Fields whose entries must each be concrete evidence references.
EVIDENCE_PATHS = (
    ("strand_pairing_evidence",),
    ("execution_strand", "validation_reviews"),
    ("risk", "burn_down_evidence"),
    ("ledger_receipt",),
)

REQUIRED_TOP = (
    "schema_version", "revolution_id", "altitude", "execution_strand",
    "learning_governance_strand", "strand_pairing_evidence", "risk",
    "mismatch_repair", "validated_governance_template", "win_condition",
    "budget_radius", "safety_floor", "ledger_receipt",
)
REQUIRED_ALTITUDE = ("current", "target", "axis")
ALTITUDE_AXES = {"autonomy", "abstraction", "scope", "delegation", "capability", "risk_burn_down"}
REQUIRED_EXEC = ("objective", "engineer_target", "validation_reviews")
REQUIRED_LEARN = ("double_loop_evaluation", "governing_variable_change", "next_altitude", "stop_or_descend")
REQUIRED_RISK = ("highest_uncertainty", "spike", "burn_down_evidence")


def _get(record: dict, path: tuple[str, ...]):
    node = record
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _entry_problem(entry) -> str | None:
    """Return why `entry` is not a clean, verifiable concrete ref, else None."""
    if not isinstance(entry, str) or not entry.strip():
        return "empty/non-string"
    if entry.strip().strip(".").lower() in PLACEHOLDERS:
        return "placeholder"
    residue = entry
    matched = False
    for match in CONCRETE_REF.finditer(entry):
        residue = residue.replace(match.group(0), " ", 1)
        matched = True
    for match in REPO_PATH_RE.finditer(entry):
        token = match.group(0)
        if (ROOT / token).exists():
            residue = residue.replace(token, " ", 1)
            matched = True
        else:
            return f"repo path does not exist: {token}"
    if not matched:
        return "not a concrete ref (need URL / 40-hex sha / sha256: / run-trace id / existing repo path)"
    # Reject prose smuggled in alongside a ref: strip label words + non-alphanumerics
    # and require the leftover to be short.
    residue = _LABEL_WORDS.sub(" ", residue)
    residue = re.sub(r"[^0-9A-Za-z]", "", residue)
    if len(residue) > _MAX_RESIDUE:
        return "freeform prose mixed with ref (keep evidence entries ref-only)"
    return None


def _check_evidence_array(value, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: must be a non-empty array (unpaired evidence)")
        return
    for index, entry in enumerate(value):
        problem = _entry_problem(entry)
        if problem:
            errors.append(f"{label}[{index}]: {problem}: {entry!r}")


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record is not a JSON object"]

    for key in REQUIRED_TOP:
        if key not in record:
            errors.append(f"missing required field: {key}")

    if record.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")

    altitude = record.get("altitude")
    if isinstance(altitude, dict):
        for key in REQUIRED_ALTITUDE:
            if not altitude.get(key):
                errors.append(f"altitude.{key}: required and non-empty")
        if altitude.get("axis") not in ALTITUDE_AXES:
            errors.append(f"altitude.axis must be one of {sorted(ALTITUDE_AXES)}")
    else:
        errors.append("altitude: required object")

    exec_strand = record.get("execution_strand")
    if isinstance(exec_strand, dict):
        for key in ("objective", "engineer_target"):
            if not exec_strand.get(key):
                errors.append(f"execution_strand.{key}: required and non-empty")
    else:
        errors.append("execution_strand: required object")

    learn = record.get("learning_governance_strand")
    if isinstance(learn, dict):
        for key in REQUIRED_LEARN:
            if not learn.get(key):
                errors.append(f"learning_governance_strand.{key}: required and non-empty")
    else:
        errors.append("learning_governance_strand: required object")

    risk = record.get("risk")
    if isinstance(risk, dict):
        for key in ("highest_uncertainty", "spike"):
            if not risk.get(key):
                errors.append(f"risk.{key}: required and non-empty")
    else:
        errors.append("risk: required object")

    mismatch = record.get("mismatch_repair")
    if not isinstance(mismatch, dict) or "mismatches" not in mismatch or not mismatch.get("repair_action"):
        errors.append("mismatch_repair: requires 'mismatches' array and non-empty 'repair_action'")

    for key in ("validated_governance_template", "win_condition", "budget_radius", "safety_floor"):
        if not record.get(key):
            errors.append(f"{key}: required and non-empty")

    # The teeth: evidence-bearing fields must carry concrete, non-placeholder refs.
    for path in EVIDENCE_PATHS:
        _check_evidence_array(_get(record, path), ".".join(path), errors)

    return errors


def _good_record() -> dict:
    return {
        "schema_version": "1.0",
        "revolution_id": "selftest",
        "altitude": {"current": "flat loop", "target": "spiral", "axis": "abstraction"},
        "execution_strand": {
            "objective": "o",
            "engineer_target": "t",
            "validation_reviews": ["https://github.com/bonginkan/fairy_tale/pull/45"],
        },
        "learning_governance_strand": {
            "double_loop_evaluation": "e",
            "governing_variable_change": "g",
            "next_altitude": "n",
            "stop_or_descend": "s",
        },
        "strand_pairing_evidence": ["https://github.com/bonginkan/fairy_tale/issues/44"],
        "risk": {
            "highest_uncertainty": "u",
            "spike": "s",
            "burn_down_evidence": ["98341e43fce99a1157fbebec713537b406ef8e81"],
        },
        "mismatch_repair": {"mismatches": ["m"], "repair_action": "r"},
        "validated_governance_template": "tpl",
        "win_condition": "w",
        "budget_radius": "b",
        "safety_floor": "f",
        "ledger_receipt": ["run-20260626T0011Z-cc-selftest-evidence"],
    }


def _selftest() -> int:
    """Lock the red->green and hostile-bypass controls (fairy_tale #44 / PR #45)."""
    failures: list[str] = []

    good = _good_record()
    if validate_record(good) != []:
        failures.append(f"good record should pass but got: {validate_record(good)}")

    # Each hostile evidence value must be rejected (it slipped through pre-fix).
    hostile = {
        "empty": [],
        "placeholder": ["TODO"],
        "bare-7hex": ["deadbee"],
        "bare-issue": ["#1"],
        "prose+ref": ["trust me, reviewed carefully", "#44"],
        "abbrev-sha": ["98341e4"],
    }
    for name, value in hostile.items():
        record = _good_record()
        record["strand_pairing_evidence"] = value
        if validate_record(record) == []:
            failures.append(f"hostile case '{name}' should be rejected but passed: {value!r}")

    # No-records dir must fail with exit 1 (suppress its report so selftest output stays clean).
    import contextlib
    import io
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            empty_rc = main(["--records", tmp])
        if empty_rc == 0:
            failures.append("empty records dir should exit 1 but exited 0")

    if failures:
        for line in failures:
            print(f"SELFTEST FAIL: {line}")
        print("Spiral revolution selftest failed.")
        return 1
    print("Spiral revolution selftest passed (good->pass; empty/placeholder/bare-hex/bare-#N/prose+ref/abbrev-sha->reject).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exercise check for spiral revolution records")
    parser.add_argument("--records", default=str(DEFAULT_RECORDS_DIR), help="records directory")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--selftest", action="store_true", help="run built-in red/green/hostile controls")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    records_dir = Path(args.records)
    files = sorted(records_dir.glob("*.json")) if records_dir.is_dir() else []

    report: dict[str, object] = {"records_dir": str(records_dir), "records": [], "passed": False}

    if not files:
        report["error"] = "no spiral revolution records found (presence-only spec is not exercised)"
        _emit(report, args.json)
        return 1

    all_ok = True
    for path in files:
        entry: dict[str, object] = {"file": str(path.relative_to(records_dir.parent) if records_dir.parent in path.parents else path)}
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entry["errors"] = [f"unreadable/invalid JSON: {exc}"]
            all_ok = False
            report["records"].append(entry)  # type: ignore[union-attr]
            continue
        errors = validate_record(record)
        entry["revolution_id"] = record.get("revolution_id") if isinstance(record, dict) else None
        entry["errors"] = errors
        if errors:
            all_ok = False
        report["records"].append(entry)  # type: ignore[union-attr]

    report["passed"] = all_ok
    _emit(report, args.json)
    return 0 if all_ok else 1


def _emit(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    if report.get("error"):
        print(f"FAIL {report['records_dir']}: {report['error']}")
        return
    for entry in report.get("records", []):
        errors = entry.get("errors") or []
        if errors:
            print(f"FAIL {entry.get('file')} ({entry.get('revolution_id')})")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK   {entry.get('file')} ({entry.get('revolution_id')})")
    print("Spiral revolution check passed." if report.get("passed") else "Spiral revolution check failed.")


if __name__ == "__main__":
    raise SystemExit(main())
