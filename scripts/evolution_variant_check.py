#!/usr/bin/env python3
"""Exercise/enforcement check for evolutionary spiral variant records (fairy_tale #42).

This sits ON TOP of the spiral exercise gate. A spiral revolution raises altitude;
an evolution variant is a *bounded mutation* of process/prompt/harness/validator/
role/delegation that must declare its blast radius, be selected only on concrete
evidence, and be inherited only when validated. Without enforcement, "evolution"
degrades into random self-modification or a rename for ordinary iteration.

The teeth (beyond presence):
  - bounded mutation: mutation_budget needs changeable/immutable/blast_radius, AND
    NO changeable entry may name a safety-floor surface (the safety floor is never
    a mutation target).
  - evidence-driven selection: selection.evidence entries must be concrete refs,
    selection.safety_floor_preserved must be true, outcome in {accepted,rejected,
    quarantined}.
  - validated inheritance: inherited=true requires outcome=accepted plus a concrete
    template_change; unvalidated mutations die locally.
  - lineage / parent: concrete references, so a variant traces to its source.
  - review calibration: the SAME #43 contract as the spiral ledger (>=2 distinct
    registered reviewers; a no_block needs a concrete refute_pass; no self-review),
    reused -- not reimplemented -- from spiral_revolution_check.

Usage:
  evolution_variant_check.py [--records DIR] [--json] [--selftest]

Exit 0 = at least one record present and all records pass; 1 = otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS_DIR = ROOT / "evolution-variants"

# Reuse the spiral exercise gate's verified primitives instead of cloning them
# (concrete-reference validation + #43 review calibration + principal registry).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spiral_revolution_check as spiral  # noqa: E402

MUTATION_OPERATORS = {"process", "prompt", "harness", "validator", "role_assignment", "delegation_policy"}
SELECTION_OUTCOMES = {"accepted", "rejected", "quarantined"}

# Safety-floor / authority / deploy / runtime surfaces a variant may NEVER list as
# changeable. Matched as substrings (case-insensitive) against each `changeable`
# entry. A mutation that names any of these is forbidden, not a variant -- a
# safety gate errs toward rejecting (the author rephrases) rather than allowing.
SAFETY_FLOOR_TERMS = (
    # operating gates
    "dnd", "do not disturb", "approval", "security",
    "meeting-join", "meeting join", "owner-escalation", "owner escalation",
    "escalation", "branch/merge", "branch merge", "merge gate",
    # secrets / credentials / auth / authority
    "credential", "secret", "token", "api key", "apikey",
    "permission", "allowlist", "allow-list", "allow list", "access control",
    "access-control", "rbac", "privilege", "authorization", "authentication",
    "role binding", "rolebinding", "scope grant",
    # deploy / production / runtime
    "deploy", "production", "rollout", "runtime-install", "runtime install",
    "runtime promotion", "runtime-promotion", "self-update", "self update",
    "runtime parity", "runtime-parity", "install companion",
    # external mutation
    "external-mutation", "external mutation",
)

REQUIRED_TOP = (
    "schema_version", "variant_id", "parent_revolution", "mutation_operator",
    "hypothesis", "mutation_budget", "fitness_metric", "selection",
    "inheritance_decision", "rollback_plan", "extinction_quarantine", "lineage",
    "safety_floor", "ledger_receipt", "implementer", "implementer_id", "reviews",
)


def _nonempty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_evidence_array(value, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: must be a non-empty array (unpaired evidence)")
        return
    for index, entry in enumerate(value):
        problem = spiral._entry_problem(entry)
        if problem:
            errors.append(f"{label}[{index}]: {problem}: {entry!r}")


def _contains_concrete_ref(value) -> bool:
    """True if the string CITES a concrete, verifiable mechanism somewhere in it:
    a URL / sha256: / run-trace id (anywhere), or an existing repo path. Unlike
    spiral._entry_problem (which requires the WHOLE entry to be a clean ref), this
    allows descriptive prose AROUND a concrete reference -- so a re-introduction
    guard / rollback / inherited-template claim must point at a real artifact, not
    be pure prose."""
    if not isinstance(value, str) or not value.strip():
        return False
    if spiral.CONCRETE_REF.search(value):
        return True
    for match in spiral.REPO_PATH_RE.finditer(value):
        token = match.group(0)
        if ".." in token.split("/"):
            continue
        try:
            resolved = (ROOT / token).resolve()
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            continue
        if resolved.exists():
            return True
    return False


def _check_mutation_budget(budget, errors: list[str]) -> None:
    if not isinstance(budget, dict):
        errors.append("mutation_budget: required object")
        return
    for key in ("changeable", "immutable"):
        arr = budget.get(key)
        if not isinstance(arr, list) or not arr or not all(_nonempty_str(x) for x in arr):
            errors.append(f"mutation_budget.{key}: required non-empty array of strings")
    if not _nonempty_str(budget.get("blast_radius")):
        errors.append("mutation_budget.blast_radius: required and non-empty")
    # The teeth: the safety floor is never a mutation target.
    changeable = budget.get("changeable")
    if isinstance(changeable, list):
        for entry in changeable:
            if not isinstance(entry, str):
                continue
            lowered = entry.lower()
            hit = next((term for term in SAFETY_FLOOR_TERMS if term in lowered), None)
            if hit:
                errors.append(
                    f"mutation_budget.changeable lists a safety-floor surface "
                    f"('{hit}' in {entry!r}): the safety floor is never mutable"
                )


def _check_selection(selection, errors: list[str]) -> None:
    if not isinstance(selection, dict):
        errors.append("selection: required object")
        return
    if selection.get("outcome") not in SELECTION_OUTCOMES:
        errors.append(f"selection.outcome: must be one of {sorted(SELECTION_OUTCOMES)}")
    if not _nonempty_str(selection.get("baseline_comparison")):
        errors.append("selection.baseline_comparison: required and non-empty")
    if selection.get("safety_floor_preserved") is not True:
        errors.append("selection.safety_floor_preserved: must be true (a variant that weakens the safety floor is not selectable)")
    _check_evidence_array(selection.get("evidence"), "selection.evidence", errors)


def _check_inheritance(record: dict, errors: list[str]) -> None:
    inheritance = record.get("inheritance_decision")
    if not isinstance(inheritance, dict):
        errors.append("inheritance_decision: required object")
        return
    inherited = inheritance.get("inherited")
    if not isinstance(inherited, bool):
        errors.append("inheritance_decision.inherited: required boolean")
    for key in ("template_change", "rationale"):
        if not _nonempty_str(inheritance.get(key)):
            errors.append(f"inheritance_decision.{key}: required and non-empty")
    # Only an accepted, evidence-backed variant may be inherited.
    selection = record.get("selection")
    outcome = selection.get("outcome") if isinstance(selection, dict) else None
    if inherited is True and outcome != "accepted":
        errors.append(
            f"inheritance_decision.inherited is true but selection.outcome is "
            f"{outcome!r}: only an accepted variant may be inherited"
        )
    # An inherited template change must cite the concrete artifact it carries
    # forward, not be a prose claim ("trust me").
    if inherited is True and not _contains_concrete_ref(inheritance.get("template_change")):
        errors.append(
            "inheritance_decision.template_change: an inherited variant must cite a "
            "concrete artifact (repo path / test / URL), not prose"
        )


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record is not a JSON object"]

    for key in REQUIRED_TOP:
        if key not in record:
            errors.append(f"missing required field: {key}")

    if record.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    if not _nonempty_str(record.get("variant_id")):
        errors.append("variant_id: required and non-empty")
    if record.get("mutation_operator") not in MUTATION_OPERATORS:
        errors.append(f"mutation_operator: must be one of {sorted(MUTATION_OPERATORS)}")
    for key in ("hypothesis", "fitness_metric", "rollback_plan", "extinction_quarantine", "safety_floor"):
        if not _nonempty_str(record.get(key)):
            errors.append(f"{key}: required and non-empty")
    # Re-introduction prevention and rollback must cite a concrete mechanism, not
    # prose: a real test / repo path / CI ref, so the guard is evidence-backed.
    for key in ("extinction_quarantine", "rollback_plan"):
        value = record.get(key)
        if _nonempty_str(value) and not _contains_concrete_ref(value):
            errors.append(
                f"{key}: must cite a concrete mechanism (a repo path / test / URL / "
                f"run-trace ref), not prose -- presence is not re-introduction prevention"
            )

    # parent_revolution + lineage anchor the variant to its source.
    parent = record.get("parent_revolution")
    if not _nonempty_str(parent):
        errors.append("parent_revolution: required and non-empty")
    elif spiral._entry_problem(parent) is not None and not _is_known_revolution(parent):
        errors.append(
            f"parent_revolution must be a concrete ref or a known revolution id "
            f"(present in spiral-revolutions/): {parent!r}"
        )

    _check_mutation_budget(record.get("mutation_budget"), errors)
    _check_selection(record.get("selection"), errors)
    _check_inheritance(record, errors)
    _check_evidence_array(record.get("lineage"), "lineage", errors)
    _check_evidence_array(record.get("ledger_receipt"), "ledger_receipt", errors)

    # Review calibration: reuse the spiral ledger's #43 contract verbatim.
    spiral._check_reviews(record, errors)

    return errors


def _is_known_revolution(value: str) -> bool:
    """True if `value` names a revolution id that exists under spiral-revolutions/."""
    revolutions_dir = ROOT / "spiral-revolutions"
    if not revolutions_dir.is_dir():
        return False
    token = value.strip()
    for path in revolutions_dir.glob("*.json"):
        if path.stem == token:
            return True
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("revolution_id") == token:
            return True
    return False


def _good_record() -> dict:
    return {
        "schema_version": "1.0",
        "variant_id": "selftest-variant",
        "parent_revolution": "https://github.com/bonginkan/fairy_tale/issues/42",
        "mutation_operator": "validator",
        "hypothesis": "Adding evidence-driven selection raises acceptance precision.",
        "mutation_budget": {
            "changeable": ["the validator schema", "the selection gate wording"],
            "immutable": ["the spiral safety floor", "the residency fail-closed posture"],
            "blast_radius": "one schema + one checker + one dogfooded record; no runtime/credential/deploy change.",
        },
        "fitness_metric": "Red->green: the gate FAILs on an unbounded mutation and PASSes only on a bounded, evidence-backed one.",
        "selection": {
            "outcome": "accepted",
            "baseline_comparison": "Baseline spiral gate had no mutation-bounding; this adds it with a measurable red->green.",
            "safety_floor_preserved": True,
            "evidence": ["https://github.com/bonginkan/fairy_tale/pull/50"],
        },
        "inheritance_decision": {
            "inherited": True,
            "template_change": "The evolutionary operator layer (scripts/evolution_variant_check.py) becomes part of the validated governance template.",
            "rationale": "It is validated by an objective red->green gate and reviewed with refute-pass.",
        },
        "rollback_plan": "Delete the variant record and revert scripts/evolution_variant_check.py; the spiral gate remains intact.",
        "extinction_quarantine": "Each bypass is red-locked in scripts/evolution_variant_check.py --selftest so a pruned variant cannot silently reappear.",
        "lineage": ["https://github.com/bonginkan/fairy_tale/issues/42"],
        "safety_floor": "Unchanged: DND, approval, security, credential, deploy, external-mutation, meeting-join, owner-escalation, branch/merge, secret, runtime-install gates outrank any mutation.",
        "ledger_receipt": ["run-20260626T0430Z-cc-42-evolution-operators"],
        "implementer": "CC MISA",
        "implementer_id": "1510042936027381821",
        "reviews": [
            {"reviewer": "Codex MISA", "reviewer_id": "1510912873981804627", "verdict": "no_block",
             "refute_pass": "https://github.com/bonginkan/fairy_tale/pull/50#issuecomment-4806259939"},
            {"reviewer": "MISA 3", "reviewer_id": "1516725819517567077", "verdict": "no_block",
             "refute_pass": "https://github.com/bonginkan/fairy_tale/pull/48#issuecomment-4806074854"},
        ],
    }


def _selftest() -> int:
    failures: list[str] = []

    good = _good_record()
    if validate_record(good) != []:
        failures.append(f"good record should pass but got: {validate_record(good)}")

    def mutated(mutator) -> dict:
        record = _good_record()
        mutator(record)
        return record

    hostile = {
        "safety-floor-in-changeable": lambda r: r["mutation_budget"]["changeable"].append("relax the deploy approval gate"),
        "safety-floor-credential": lambda r: r["mutation_budget"]["changeable"].append("store the credential inline"),
        "safety-floor-token": lambda r: r["mutation_budget"]["changeable"].append("token handling policy"),
        "safety-floor-permission-allowlist": lambda r: r["mutation_budget"]["changeable"].append("access permission allowlist"),
        "safety-floor-production-rollout": lambda r: r["mutation_budget"]["changeable"].append("production rollout policy"),
        "safety-floor-runtime-promotion": lambda r: r["mutation_budget"]["changeable"].append("allow runtime promotion without self-update gate"),
        "empty-changeable": lambda r: r["mutation_budget"].__setitem__("changeable", []),
        "no-blast-radius": lambda r: r["mutation_budget"].__setitem__("blast_radius", ""),
        "bad-operator": lambda r: r.__setitem__("mutation_operator", "yolo"),
        "prose-selection-evidence": lambda r: r["selection"].__setitem__("evidence", ["looked solid"]),
        "empty-selection-evidence": lambda r: r["selection"].__setitem__("evidence", []),
        "safety-floor-not-preserved": lambda r: r["selection"].__setitem__("safety_floor_preserved", False),
        "bad-outcome": lambda r: r["selection"].__setitem__("outcome", "vibes"),
        "inherit-without-accept": lambda r: (r["selection"].__setitem__("outcome", "rejected")),
        "prose-lineage": lambda r: r.__setitem__("lineage", ["because reasons"]),
        "bare-issue-parent": lambda r: r.__setitem__("parent_revolution", "#42"),
        "prose-extinction": lambda r: r.__setitem__("extinction_quarantine", "we will remember not to do it again"),
        "prose-rollback": lambda r: r.__setitem__("rollback_plan", "we will figure it out later"),
        "prose-template-change": lambda r: r["inheritance_decision"].__setitem__("template_change", "trust me, it becomes the template"),
    }
    for name, mutator in hostile.items():
        if validate_record(mutated(mutator)) == []:
            failures.append(f"hostile case '{name}' should be rejected but passed")

    # Review calibration is inherited from the spiral gate; spot-check one case.
    dup = _good_record()
    dup["reviews"] = [dup["reviews"][0], dup["reviews"][0]]
    if validate_record(dup) == []:
        failures.append("duplicate-reviewer case should be rejected but passed")

    import contextlib
    import io
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            if main(["--records", tmp]) == 0:
                failures.append("empty records dir should exit 1 but exited 0")

    if failures:
        for line in failures:
            print(f"SELFTEST FAIL: {line}")
        print("Evolution variant selftest failed.")
        return 1
    print(
        "Evolution variant selftest passed (good->pass; reject: safety-floor/authority/deploy/runtime "
        "surfaces in changeable [deploy, credential, token, permission/allowlist, production rollout, "
        "runtime promotion/self-update], empty/!blast budget, bad operator, prose/empty selection "
        "evidence, !safety_floor_preserved, bad outcome, inherit-without-accept, prose lineage, "
        "bare-#N parent, prose extinction/rollback/template_change, duplicate reviewer)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exercise check for evolution variant records")
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
        report["error"] = "no evolution variant records found (presence-only spec is not exercised)"
        _emit(report, args.json)
        return 1

    all_ok = True
    for path in files:
        entry: dict[str, object] = {"file": str(path.name)}
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entry["errors"] = [f"unreadable/invalid JSON: {exc}"]
            all_ok = False
            report["records"].append(entry)  # type: ignore[union-attr]
            continue
        errors = validate_record(record)
        entry["variant_id"] = record.get("variant_id") if isinstance(record, dict) else None
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
            print(f"FAIL {entry.get('file')} ({entry.get('variant_id')})")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK   {entry.get('file')} ({entry.get('variant_id')})")
    print("Evolution variant check passed." if report.get("passed") else "Evolution variant check failed.")


if __name__ == "__main__":
    raise SystemExit(main())
