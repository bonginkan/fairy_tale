#!/usr/bin/env python3
"""Generic latent-structure ledger and gate for Fairy Tale workflows.

The harness is intentionally domain-neutral. It does not know SWE-Bench, ARC,
legal tasks, or any benchmark scorer. Its job is to force hidden assumptions,
candidate invariants, negative evidence, probes, and validators into an
auditable ledger before an agent promotes a local pattern into a general rule.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
FAMILIES = {
    "generic",
    "coding",
    "arc",
    "legal",
    "research",
    "document",
    "security",
    "ui",
    "spatial",
    "other",
}
RISKS = {"low", "medium", "high"}
TRIGGERS = {
    "hidden_rule",
    "implicit_contract",
    "black_box_environment",
    "unknown_tool",
    "benchmark_miss",
    "ambiguous_spec",
    "external_contract",
    "generalization_gap",
    "none",
}
PROBE_TRIGGERS = TRIGGERS - {"none"}
OBSERVATION_CONFIDENCE = {"confirmed", "likely", "risky", "refuted", "unknown"}
HYPOTHESIS_STATUS = {"open", "supported", "refuted", "promoted"}
INVARIANT_STATUS = {"confirmed", "likely", "risky", "needs_evidence"}
ASSUMPTION_RESOLUTION = {"resolved", "accepted", "blocked", "open"}
PROBE_STATUS = {"passed", "failed", "inconclusive", "not_run"}
VALIDATOR_STATUS = {"planned", "passed", "failed", "blocked", "not_applicable"}
VALIDATION_RESULT = {"passed", "failed", "blocked", "not_applicable"}
PROMOTION_STATUS = {"none", "candidate", "promoted", "rejected"}


@dataclass
class Finding:
    severity: str
    code: str
    message: str

    @property
    def failed(self) -> bool:
        return self.severity == "FAIL"


def _item(identifier: str, **kwargs: Any) -> dict[str, Any]:
    data = {"id": identifier}
    data.update(kwargs)
    return data


def empty_ledger(
    objective: str,
    family: str,
    risk: str,
    triggers: list[str],
    artifacts: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "objective": objective,
            "family": family,
            "risk": risk,
            "triggers": triggers or ["none"],
            "artifacts": artifacts,
            "notes": "",
        },
        "observations": [],
        "negative_evidence": [],
        "hypotheses": [],
        "inferred_invariants": [],
        "risky_assumptions": [],
        "probes_run": [],
        "compiled_validators": [],
        "actions": [],
        "validation_results": [],
        "promotion_decision": {
            "status": "none",
            "reason": "",
            "evidence_ids": [],
        },
    }


def demo_ledger() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "objective": "Preserve an unstated repository contract while changing a local implementation.",
            "family": "coding",
            "risk": "medium",
            "triggers": ["implicit_contract", "generalization_gap"],
            "artifacts": [
                _item(
                    "artifact_repo_scan",
                    kind="source-scan",
                    path="src/",
                    notes="Adjacent files and tests inspected before editing.",
                )
            ],
            "notes": "Demo ledger for the latent-structure harness.",
        },
        "observations": [
            _item(
                "obs_legacy_shape",
                claim="Existing callers pass a mapping with id and value keys.",
                source="src/consumer.py and tests/test_consumer.py",
                confidence="confirmed",
                notes="Observed in both production path and mock fixture.",
            ),
            _item(
                "obs_new_path",
                claim="The requested change only mentions the producer implementation.",
                source="user task prompt",
                confidence="confirmed",
                notes="The prompt omits consumer compatibility.",
            ),
        ],
        "negative_evidence": [
            _item(
                "neg_no_tuple_callers",
                probe="Search for tuple-style consumer calls.",
                observation="No callers expect positional tuple output.",
                implication="Changing the producer to return a tuple would invent a contract.",
                notes="Negative evidence prevents a false analogy to another module.",
            )
        ],
        "hypotheses": [
            _item(
                "hyp_mapping_contract",
                statement="The hidden contract is the mapping shape, not only the visible producer API.",
                status="promoted",
                evidence_ids=["obs_legacy_shape", "neg_no_tuple_callers"],
                notes="Supported by caller and fixture evidence.",
            )
        ],
        "inferred_invariants": [
            _item(
                "inv_mapping_shape",
                statement="Producer output must remain a mapping containing id and value.",
                scope="Current repository callers and tests.",
                status="confirmed",
                evidence_ids=["obs_legacy_shape", "neg_no_tuple_callers"],
                notes="Action must preserve this shape.",
            )
        ],
        "risky_assumptions": [
            _item(
                "assume_no_external_callers",
                assumption="No unscanned external package consumes the producer directly.",
                risk="medium",
                resolution="accepted",
                mitigation="Preserve the existing public output shape, so external callers remain compatible.",
                notes="Risk accepted because the invariant is backward-compatible.",
            )
        ],
        "probes_run": [
            _item(
                "probe_callers",
                question="Do adjacent files rely on a more specific output shape?",
                method="Search source and tests for producer consumers.",
                result="Two consumers and one mock fixture require mapping keys.",
                status="passed",
                evidence_ids=["obs_legacy_shape"],
                notes="Probe succeeded before editing.",
            )
        ],
        "compiled_validators": [
            _item(
                "val_unit_tests",
                validator="Run adjacent unit tests that exercise the producer and consumer.",
                command="python3 -m pytest tests/test_consumer.py",
                status="passed",
                covers_invariant_ids=["inv_mapping_shape"],
                notes="Demo command; replace with the real project validator.",
            )
        ],
        "actions": [
            _item(
                "act_preserve_mapping",
                description="Implement the local change while preserving mapping output keys.",
                depends_on_invariant_ids=["inv_mapping_shape"],
                notes="The edit is gated by the inferred invariant.",
            )
        ],
        "validation_results": [
            _item(
                "res_unit_tests",
                validator_id="val_unit_tests",
                result="passed",
                evidence="Adjacent tests passed after the edit.",
                notes="Demo result.",
            )
        ],
        "promotion_decision": {
            "status": "promoted",
            "reason": "The invariant predicts observed callers and is validated by the adjacent test.",
            "evidence_ids": ["obs_legacy_shape", "probe_callers", "res_unit_tests"],
        },
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing ledger: {path}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from None
    if not isinstance(data, dict):
        raise SystemExit(f"ledger root must be an object: {path}")
    return data


def add(findings: list[Finding], severity: str, code: str, message: str) -> None:
    findings.append(Finding(severity, code, message))


def list_field(ledger: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = ledger.get(name)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def ids_for(ledger: dict[str, Any], sections: list[str]) -> set[str]:
    ids: set[str] = set()
    for section in sections:
        for item in list_field(ledger, section):
            identifier = item.get("id")
            if isinstance(identifier, str):
                ids.add(identifier)
    return ids


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_structure(ledger: dict[str, Any], findings: list[Finding]) -> None:
    if ledger.get("schema_version") != SCHEMA_VERSION:
        add(findings, "FAIL", "schema_version", "schema_version must be 1.0")

    task = ledger.get("task")
    if not isinstance(task, dict):
        add(findings, "FAIL", "task", "task must be an object")
        task = {}

    if not has_text(task.get("objective")):
        add(findings, "FAIL", "task.objective", "task objective is required")
    if task.get("family") not in FAMILIES:
        add(findings, "FAIL", "task.family", f"task family must be one of {sorted(FAMILIES)}")
    if task.get("risk") not in RISKS:
        add(findings, "FAIL", "task.risk", "task risk must be low, medium, or high")

    triggers = task.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        add(findings, "FAIL", "task.triggers", "task triggers must be a non-empty list")
    elif unknown := [trigger for trigger in triggers if trigger not in TRIGGERS]:
        add(findings, "FAIL", "task.triggers", f"unknown triggers: {', '.join(unknown)}")

    required_lists = [
        "observations",
        "negative_evidence",
        "hypotheses",
        "inferred_invariants",
        "risky_assumptions",
        "probes_run",
        "compiled_validators",
        "actions",
        "validation_results",
    ]
    for name in required_lists:
        if not isinstance(ledger.get(name), list):
            add(findings, "FAIL", name, "section must be a list")

    promotion = ledger.get("promotion_decision")
    if not isinstance(promotion, dict):
        add(findings, "FAIL", "promotion_decision", "promotion_decision must be an object")
    elif promotion.get("status") not in PROMOTION_STATUS:
        add(findings, "FAIL", "promotion_decision.status", "invalid promotion decision status")


def validate_item_shapes(ledger: dict[str, Any], findings: list[Finding]) -> None:
    section_status = {
        "observations": ("confidence", OBSERVATION_CONFIDENCE),
        "hypotheses": ("status", HYPOTHESIS_STATUS),
        "inferred_invariants": ("status", INVARIANT_STATUS),
        "probes_run": ("status", PROBE_STATUS),
        "compiled_validators": ("status", VALIDATOR_STATUS),
        "validation_results": ("result", VALIDATION_RESULT),
    }
    seen: dict[str, str] = {}
    for section in [
        "observations",
        "negative_evidence",
        "hypotheses",
        "inferred_invariants",
        "risky_assumptions",
        "probes_run",
        "compiled_validators",
        "actions",
        "validation_results",
    ]:
        for index, item in enumerate(list_field(ledger, section), start=1):
            identifier = item.get("id")
            if not has_text(identifier):
                add(findings, "FAIL", f"{section}[{index}].id", "item id is required")
            elif identifier in seen:
                add(findings, "FAIL", f"{section}.{identifier}", f"duplicate id also used in {seen[identifier]}")
            else:
                seen[identifier] = section

    for section, (field, allowed) in section_status.items():
        for item in list_field(ledger, section):
            status = item.get(field)
            if status not in allowed:
                add(findings, "FAIL", f"{section}.{item.get('id', '?')}.{field}", f"invalid value: {status!r}")

    for item in list_field(ledger, "risky_assumptions"):
        if item.get("risk") not in RISKS:
            add(findings, "FAIL", f"risky_assumptions.{item.get('id', '?')}.risk", "invalid risk")
        if item.get("resolution") not in ASSUMPTION_RESOLUTION:
            add(findings, "FAIL", f"risky_assumptions.{item.get('id', '?')}.resolution", "invalid resolution")


def validate_references(ledger: dict[str, Any], findings: list[Finding]) -> None:
    evidence_ids = ids_for(
        ledger,
        [
            "observations",
            "negative_evidence",
            "probes_run",
            "validation_results",
        ],
    )
    invariant_ids = ids_for(ledger, ["inferred_invariants"])
    validator_ids = ids_for(ledger, ["compiled_validators"])

    for section in ["hypotheses", "inferred_invariants", "probes_run"]:
        for item in list_field(ledger, section):
            for evidence_id in item.get("evidence_ids", []):
                if evidence_id not in evidence_ids:
                    add(
                        findings,
                        "WARN",
                        f"{section}.{item.get('id', '?')}.evidence_ids",
                        f"evidence id {evidence_id!r} is not defined in an evidence section",
                    )

    for item in list_field(ledger, "compiled_validators"):
        for invariant_id in item.get("covers_invariant_ids", []):
            if invariant_id not in invariant_ids:
                add(
                    findings,
                    "FAIL",
                    f"compiled_validators.{item.get('id', '?')}.covers_invariant_ids",
                    f"unknown invariant id {invariant_id!r}",
                )

    for item in list_field(ledger, "actions"):
        for invariant_id in item.get("depends_on_invariant_ids", []):
            if invariant_id not in invariant_ids:
                add(
                    findings,
                    "FAIL",
                    f"actions.{item.get('id', '?')}.depends_on_invariant_ids",
                    f"unknown invariant id {invariant_id!r}",
                )

    for item in list_field(ledger, "validation_results"):
        validator_id = item.get("validator_id")
        if validator_id not in validator_ids:
            add(
                findings,
                "FAIL",
                f"validation_results.{item.get('id', '?')}.validator_id",
                f"unknown validator id {validator_id!r}",
            )


def validate_gate(ledger: dict[str, Any], stage: str, findings: list[Finding]) -> None:
    task = ledger.get("task") if isinstance(ledger.get("task"), dict) else {}
    risk = task.get("risk")
    triggers = set(task.get("triggers", [])) if isinstance(task.get("triggers"), list) else set()
    triggered = bool(triggers & PROBE_TRIGGERS)
    needs_probe = triggered or risk in {"medium", "high"}

    observations = list_field(ledger, "observations")
    negative = list_field(ledger, "negative_evidence")
    hypotheses = list_field(ledger, "hypotheses")
    invariants = list_field(ledger, "inferred_invariants")
    assumptions = list_field(ledger, "risky_assumptions")
    probes = list_field(ledger, "probes_run")
    validators = list_field(ledger, "compiled_validators")
    validation_results = list_field(ledger, "validation_results")
    promotion = ledger.get("promotion_decision") if isinstance(ledger.get("promotion_decision"), dict) else {}

    if not observations:
        add(findings, "FAIL", "gate.observations", "record at least one observation before acting")
    if not hypotheses and not invariants:
        add(findings, "FAIL", "gate.rule_candidate", "record at least one hypothesis or inferred invariant")

    if needs_probe and not probes and not validators:
        add(
            findings,
            "FAIL",
            "gate.probe_or_validator",
            "medium/high-risk or latent-structure triggers require a probe or planned validator",
        )
    if triggered and not negative:
        add(
            findings,
            "WARN",
            "gate.negative_evidence",
            "latent-structure work should record negative evidence or no-op observations",
        )

    open_high = [
        item.get("id", "?")
        for item in assumptions
        if item.get("risk") == "high" and item.get("resolution") == "open"
    ]
    if open_high:
        add(findings, "FAIL", "gate.high_risk_assumptions", f"open high-risk assumptions: {', '.join(open_high)}")

    if stage == "pre-act":
        return

    if not invariants:
        add(findings, "FAIL", "final.invariants", "final validation requires at least one inferred invariant")

    unbacked_invariants = [
        item.get("id", "?")
        for item in invariants
        if item.get("status") in {"confirmed", "likely", "risky"} and not item.get("evidence_ids")
    ]
    if unbacked_invariants:
        add(
            findings,
            "FAIL",
            "final.invariant_evidence",
            f"invariants need evidence ids: {', '.join(unbacked_invariants)}",
        )

    resolved_probe = [item for item in probes if item.get("status") in {"passed", "failed", "inconclusive"}]
    if needs_probe and not resolved_probe:
        add(findings, "FAIL", "final.probes", "final validation requires at least one completed probe")

    failed_validators = [item.get("id", "?") for item in validators if item.get("status") == "failed"]
    if failed_validators:
        add(findings, "FAIL", "final.validators_failed", f"failed validators: {', '.join(failed_validators)}")

    passed_validators = [item for item in validators if item.get("status") == "passed"]
    applicable_results = [item for item in validation_results if item.get("result") in {"passed", "failed"}]
    if not passed_validators and not applicable_results:
        add(
            findings,
            "FAIL",
            "final.validation",
            "final validation requires a passed validator or an explicit validation result",
        )

    unresolved = [
        item.get("id", "?")
        for item in assumptions
        if item.get("risk") in {"medium", "high"} and item.get("resolution") in {"open", "blocked"}
    ]
    if unresolved:
        add(findings, "FAIL", "final.assumptions", f"unresolved medium/high-risk assumptions: {', '.join(unresolved)}")

    if promotion.get("status") == "none":
        add(findings, "FAIL", "final.promotion", "set promotion_decision.status before finalizing")
    if promotion.get("status") in {"candidate", "promoted", "rejected"} and not has_text(promotion.get("reason")):
        add(findings, "FAIL", "final.promotion.reason", "promotion_decision.reason is required")
    if promotion.get("status") == "promoted" and not promotion.get("evidence_ids"):
        add(findings, "FAIL", "final.promotion.evidence", "promoted decisions require evidence_ids")


def validate_ledger(ledger: dict[str, Any], stage: str) -> list[Finding]:
    findings: list[Finding] = []
    validate_structure(ledger, findings)
    validate_item_shapes(ledger, findings)
    validate_references(ledger, findings)
    validate_gate(ledger, stage, findings)
    if not findings:
        add(findings, "OK", "ledger", f"{stage} validation passed")
    elif not any(item.failed for item in findings):
        add(findings, "OK", "ledger", f"{stage} validation passed with warnings")
    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        print(f"{finding.severity:4} {finding.code}: {finding.message}")


def command_init(args: argparse.Namespace) -> int:
    artifacts = [
        _item(f"artifact_{index}", kind="reference", path=path, notes="")
        for index, path in enumerate(args.artifact, start=1)
    ]
    ledger = empty_ledger(args.task, args.task_family, args.risk, args.trigger, artifacts)
    write_json(args.output, ledger)
    print(f"wrote latent-structure ledger skeleton: {args.output}")
    return 0


def command_demo(args: argparse.Namespace) -> int:
    write_json(args.output, demo_ledger())
    print(f"wrote latent-structure demo ledger: {args.output}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    ledger = load_json(args.ledger)
    findings = validate_ledger(ledger, args.stage)
    failed = any(item.failed for item in findings)
    if args.json:
        payload = {
            "ok": not failed,
            "stage": args.stage,
            "ledger": str(args.ledger),
            "findings": [item.__dict__ for item in findings],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_findings(findings)
    return 1 if failed else 0


def command_summarize(args: argparse.Namespace) -> int:
    ledger = load_json(args.ledger)
    task = ledger.get("task", {})
    if not isinstance(task, dict):
        task = {}
    summary = {
        "objective": task.get("objective", ""),
        "family": task.get("family", ""),
        "risk": task.get("risk", ""),
        "triggers": task.get("triggers", []),
        "observations": len(list_field(ledger, "observations")),
        "negative_evidence": len(list_field(ledger, "negative_evidence")),
        "hypotheses": len(list_field(ledger, "hypotheses")),
        "invariants": len(list_field(ledger, "inferred_invariants")),
        "probes": len(list_field(ledger, "probes_run")),
        "validators": len(list_field(ledger, "compiled_validators")),
        "promotion": ledger.get("promotion_decision", {}).get("status", "none")
        if isinstance(ledger.get("promotion_decision"), dict)
        else "none",
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and validate a generic Fairy Tale latent-structure ledger."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="write an empty latent-structure ledger")
    init.add_argument("--task", required=True, help="task objective")
    init.add_argument("--task-family", default="generic", choices=sorted(FAMILIES))
    init.add_argument("--risk", default="medium", choices=sorted(RISKS))
    init.add_argument("--trigger", action="append", choices=sorted(TRIGGERS), default=[])
    init.add_argument("--artifact", action="append", default=[], help="path to a supporting artifact")
    init.add_argument("--output", required=True, type=Path)
    init.set_defaults(func=command_init)

    demo = subparsers.add_parser("demo", help="write a complete valid demo ledger")
    demo.add_argument("--output", required=True, type=Path)
    demo.set_defaults(func=command_demo)

    validate = subparsers.add_parser("validate", help="validate a latent-structure ledger")
    validate.add_argument("--ledger", required=True, type=Path)
    validate.add_argument("--stage", choices=("pre-act", "final"), default="pre-act")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)

    summarize = subparsers.add_parser("summarize", help="print a compact ledger summary")
    summarize.add_argument("--ledger", required=True, type=Path)
    summarize.add_argument("--json", action="store_true")
    summarize.set_defaults(func=command_summarize)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
