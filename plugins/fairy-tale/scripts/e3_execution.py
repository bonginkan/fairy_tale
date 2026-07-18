#!/usr/bin/env python3
"""Create, advance, render, and validate E3 execution-scope ledgers.

This is an independent implementation of the state machine described in
arXiv:2607.13034. It records an initial operating point, executes one scope
level at a time, stops on verified success, and expands monotonically only
after failed verification. JSON is canonical; Markdown is a derived review
view.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

try:
    from task_artifacts import (
        ArtifactError,
        Finding,
        canonical_artifact_path,
        has_text,
        load_json,
        missing_keys,
        require_distinct_paths,
        string_list,
        unknown_keys,
        valid_id,
        write_json,
        write_text_atomic,
    )
except ImportError:  # pragma: no cover - import from repository root
    from scripts.task_artifacts import (
        ArtifactError,
        Finding,
        canonical_artifact_path,
        has_text,
        load_json,
        missing_keys,
        require_distinct_paths,
        string_list,
        unknown_keys,
        valid_id,
        write_json,
        write_text_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0"
DEFAULT_CASES = ROOT / "fixtures" / "e3-execution" / "cases.jsonl"
DEFAULT_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_SAFETY_GATES = (
    "validation_plan",
    "closure_check",
    "tier_a_recall",
    "authority_and_safety",
)

TOP_REQUIRED = {
    "schema_version",
    "artifact_type",
    "task_id",
    "objective",
    "acceptance_checks",
    "estimate",
    "max_expansions",
    "confidence_threshold",
    "low_confidence_expansion_candidate",
    "safety_floor",
    "current_level",
    "cached_evidence",
    "attempts",
    "status",
    "summary",
}
ACCEPTANCE_KEYS = {"id", "description"}
ESTIMATE_KEYS = {
    "difficulty",
    "scope",
    "risk",
    "confidence",
    "rationale",
    "probe",
}
PROBE_KEYS = {"kind", "count", "query", "evidence"}
SAFETY_KEYS = {
    "required_gates",
    "closure_tier_a_preserved",
    "authority_and_safety_preserved",
}
ATTEMPT_KEYS = {
    "index",
    "level",
    "scope",
    "reused_evidence",
    "new_evidence",
    "cost",
    "verification",
}
COST_KEYS = {"latency_ms", "tokens", "tool_calls", "inspected_items"}
VERIFICATION_KEYS = {"tier", "result", "checks", "notes"}
CHECK_KEYS = {"id", "result", "evidence", "notes"}
ATTEMPT_INPUT_KEYS = {"scope_additions", "new_evidence", "cost", "verification"}
SPEC_KEYS = {
    "task_id",
    "objective",
    "acceptance_checks",
    "difficulty",
    "scope",
    "risk",
    "confidence",
    "rationale",
    "probe",
    "max_expansions",
    "confidence_threshold",
    "safety_gates",
}

PROBE_KINDS = {"none", "search", "metadata"}
RISKS = {"low", "medium", "high"}
VERIFICATION_TIERS = {"local", "focused", "full"}
CHECK_RESULTS = {"pass", "fail", "blocked", "not_run"}
VERIFICATION_RESULTS = {"pass", "fail", "blocked"}
STATUSES = {"estimated", "active", "verified", "blocked", "exhausted"}
TIER_RANK = {"local": 1, "focused": 2, "full": 3}
RISK_MIN_TIER = {"low": 1, "medium": 2, "high": 3}
EVIDENCE_REF_RE = re.compile(
    r"^(?:https?://[^\s/]+/\S+|sha256:[0-9a-f]{64}|"
    r"(?:run|trace|search|metadata|test|check|file|artifact|log):"
    r"[A-Za-z0-9][A-Za-z0-9._/@#:+-]{0,255})$"
)


def add(findings: list[Finding], code: str, message: str) -> None:
    findings.append(Finding(code, message))


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def unique_text_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        string_list(value, nonempty=nonempty)
        and len(value) == len(set(value))
    )


def unique_evidence_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        unique_text_list(value, nonempty=nonempty)
        and all(EVIDENCE_REF_RE.fullmatch(item) for item in value)
    )


def ordered_union(left: Sequence[str], right: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in (*left, *right):
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def object_shape(
    value: Any,
    *,
    path: str,
    required: set[str],
    allowed: set[str],
    findings: list[Finding],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        add(findings, path, "must be an object")
        return None
    unknown_keys(value, allowed, f"{path}.unknown_keys", findings)
    missing_keys(value, required, f"{path}.missing", findings)
    return value


def validate_acceptance_checks(value: Any, findings: list[Finding]) -> list[str]:
    identifiers: list[str] = []
    if not isinstance(value, list) or not value:
        add(
            findings,
            "e3.acceptance_checks",
            "acceptance_checks must be a non-empty list",
        )
        return identifiers
    for index, raw in enumerate(value):
        path = f"e3.acceptance_checks[{index}]"
        check = object_shape(
            raw,
            path=path,
            required=ACCEPTANCE_KEYS,
            allowed=ACCEPTANCE_KEYS,
            findings=findings,
        )
        if check is None:
            continue
        identifier = check.get("id")
        if not valid_id(identifier):
            add(findings, f"{path}.id", "id is malformed")
        else:
            identifiers.append(identifier)
        if not has_text(check.get("description")):
            add(findings, f"{path}.description", "description is required")
    if len(identifiers) != len(set(identifiers)):
        add(findings, "e3.acceptance_checks.ids", "check ids must be unique")
    return identifiers


def validate_probe(value: Any, findings: list[Finding]) -> list[str]:
    probe = object_shape(
        value,
        path="e3.estimate.probe",
        required=PROBE_KEYS,
        allowed=PROBE_KEYS,
        findings=findings,
    )
    if probe is None:
        return []
    kind = probe.get("kind")
    if not isinstance(kind, str) or kind not in PROBE_KINDS:
        add(
            findings,
            "e3.estimate.probe.kind",
            f"kind must be one of {sorted(PROBE_KINDS)}",
        )
    count = probe.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count not in {0, 1}:
        add(findings, "e3.estimate.probe.count", "count must be 0 or 1")
    evidence = probe.get("evidence")
    if not unique_evidence_list(evidence):
        add(
            findings,
            "e3.estimate.probe.evidence",
            "evidence must be a unique list of concrete evidence refs",
        )
        evidence = []
    if kind == "none":
        if count != 0:
            add(findings, "e3.estimate.probe.count", "none probe must have count 0")
        if probe.get("query") != "":
            add(findings, "e3.estimate.probe.query", "none probe must have an empty query")
        if evidence:
            add(
                findings,
                "e3.estimate.probe.evidence",
                "none probe cannot claim evidence",
            )
    elif isinstance(kind, str) and kind in {"search", "metadata"}:
        if count != 1:
            add(findings, "e3.estimate.probe.count", "a used probe must have count 1")
        if not has_text(probe.get("query")):
            add(findings, "e3.estimate.probe.query", "a used probe needs a query")
        if not evidence:
            add(
                findings,
                "e3.estimate.probe.evidence",
                "a used probe needs concrete evidence",
            )
    return list(evidence)


def validate_estimate(value: Any, findings: list[Finding]) -> tuple[int | None, str | None, float | None, list[str], list[str]]:
    estimate = object_shape(
        value,
        path="e3.estimate",
        required=ESTIMATE_KEYS,
        allowed=ESTIMATE_KEYS,
        findings=findings,
    )
    if estimate is None:
        return None, None, None, [], []
    difficulty = estimate.get("difficulty")
    if not isinstance(difficulty, int) or isinstance(difficulty, bool) or difficulty not in {1, 2, 3}:
        add(findings, "e3.estimate.difficulty", "difficulty must be 1, 2, or 3")
        difficulty = None
    scope = estimate.get("scope")
    if not unique_text_list(scope, nonempty=True):
        add(
            findings,
            "e3.estimate.scope",
            "scope must be a non-empty unique list of strings",
        )
        scope = []
    risk = estimate.get("risk")
    if not isinstance(risk, str) or risk not in RISKS:
        add(findings, "e3.estimate.risk", f"risk must be one of {sorted(RISKS)}")
        risk = None
    confidence = estimate.get("confidence")
    if not finite_number(confidence) or not 0.0 <= confidence <= 1.0:
        add(findings, "e3.estimate.confidence", "confidence must be finite in [0, 1]")
        confidence = None
    if not has_text(estimate.get("rationale")):
        add(findings, "e3.estimate.rationale", "rationale is required")
    evidence = validate_probe(estimate.get("probe"), findings)
    return difficulty, risk, confidence, list(scope), evidence


def validate_safety_floor(value: Any, findings: list[Finding]) -> None:
    safety = object_shape(
        value,
        path="e3.safety_floor",
        required=SAFETY_KEYS,
        allowed=SAFETY_KEYS,
        findings=findings,
    )
    if safety is None:
        return
    gates = safety.get("required_gates")
    if not unique_text_list(gates, nonempty=True):
        add(
            findings,
            "e3.safety_floor.required_gates",
            "required_gates must be a non-empty unique list",
        )
    else:
        missing = sorted(set(DEFAULT_SAFETY_GATES) - set(gates))
        if missing:
            add(
                findings,
                "e3.safety_floor.required_gates",
                "required_gates cannot suppress defaults: " + ", ".join(missing),
            )
    if safety.get("closure_tier_a_preserved") is not True:
        add(
            findings,
            "e3.safety_floor.closure_tier_a_preserved",
            "Closure Check and Tier A recall are non-suppressible",
        )
    if safety.get("authority_and_safety_preserved") is not True:
        add(
            findings,
            "e3.safety_floor.authority_and_safety_preserved",
            "authority and safety gates are non-suppressible",
        )


def validate_cost(
    value: Any,
    *,
    path: str,
    findings: list[Finding],
) -> None:
    cost = object_shape(
        value,
        path=path,
        required=COST_KEYS,
        allowed=COST_KEYS,
        findings=findings,
    )
    if cost is None:
        return
    latency = cost.get("latency_ms")
    if latency is not None and (not finite_number(latency) or latency < 0):
        add(findings, f"{path}.latency_ms", "latency_ms must be null or finite and non-negative")
    tokens = cost.get("tokens")
    if tokens is not None and (
        not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0
    ):
        add(findings, f"{path}.tokens", "tokens must be null or a non-negative integer")
    for key in ("tool_calls", "inspected_items"):
        raw = cost.get(key)
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            add(findings, f"{path}.{key}", f"{key} must be a non-negative integer")


def validate_verification(
    value: Any,
    *,
    path: str,
    acceptance_ids: list[str],
    known_evidence: set[str],
    risk: str | None,
    level: int | None,
    findings: list[Finding],
) -> str | None:
    verification = object_shape(
        value,
        path=path,
        required=VERIFICATION_KEYS,
        allowed=VERIFICATION_KEYS,
        findings=findings,
    )
    if verification is None:
        return None
    tier = verification.get("tier")
    if not isinstance(tier, str) or tier not in VERIFICATION_TIERS:
        add(findings, f"{path}.tier", f"tier must be one of {sorted(VERIFICATION_TIERS)}")
    elif risk in RISKS and TIER_RANK[tier] < RISK_MIN_TIER[risk]:
        add(findings, f"{path}.tier", f"{risk}-risk execution needs at least {['local', 'focused', 'full'][RISK_MIN_TIER[risk] - 1]} verification")
    if level == 3 and tier != "full":
        add(findings, f"{path}.tier", "scope level 3 requires full verification")

    result = verification.get("result")
    if not isinstance(result, str) or result not in VERIFICATION_RESULTS:
        add(
            findings,
            f"{path}.result",
            f"result must be one of {sorted(VERIFICATION_RESULTS)}",
        )
        result = None
    if not has_text(verification.get("notes")):
        add(findings, f"{path}.notes", "verification notes are required")

    raw_checks = verification.get("checks")
    observed_ids: list[str] = []
    observed_results: list[str] = []
    if not isinstance(raw_checks, list) or not raw_checks:
        add(findings, f"{path}.checks", "checks must be a non-empty list")
        raw_checks = []
    for index, raw in enumerate(raw_checks):
        check_path = f"{path}.checks[{index}]"
        check = object_shape(
            raw,
            path=check_path,
            required=CHECK_KEYS,
            allowed=CHECK_KEYS,
            findings=findings,
        )
        if check is None:
            continue
        identifier = check.get("id")
        if not valid_id(identifier):
            add(findings, f"{check_path}.id", "id is malformed")
        else:
            observed_ids.append(identifier)
        check_result = check.get("result")
        if not isinstance(check_result, str) or check_result not in CHECK_RESULTS:
            add(
                findings,
                f"{check_path}.result",
                f"result must be one of {sorted(CHECK_RESULTS)}",
            )
        else:
            observed_results.append(check_result)
        evidence = check.get("evidence")
        if not unique_evidence_list(evidence):
            add(
                findings,
                f"{check_path}.evidence",
                "evidence must be a unique list of concrete evidence refs",
            )
            evidence = []
        if (
            isinstance(check_result, str)
            and check_result in {"pass", "fail", "blocked"}
            and not evidence
        ):
            add(
                findings,
                f"{check_path}.evidence",
                f"{check_result} needs evidence",
            )
        for ref in evidence:
            if ref not in known_evidence:
                add(
                    findings,
                    f"{check_path}.evidence",
                    f"unregistered evidence: {ref}",
                )
        if check_result == "not_run" and not has_text(check.get("notes")):
            add(findings, f"{check_path}.notes", "not_run needs a reason")
        elif not isinstance(check.get("notes"), str):
            add(findings, f"{check_path}.notes", "notes must be a string")

    if len(observed_ids) != len(set(observed_ids)):
        add(findings, f"{path}.checks.ids", "check ids must be unique")
    if set(observed_ids) != set(acceptance_ids) or len(observed_ids) != len(acceptance_ids):
        add(
            findings,
            f"{path}.checks.coverage",
            "checks must cover every acceptance check exactly once",
        )
    if result == "pass" and observed_results and not all(item == "pass" for item in observed_results):
        add(findings, f"{path}.result", "pass requires every check to pass")
    if result == "fail" and not any(item in {"fail", "not_run"} for item in observed_results):
        add(findings, f"{path}.result", "fail requires a failed or not-run check")
    if result == "blocked" and "blocked" not in observed_results:
        add(findings, f"{path}.result", "blocked requires a blocked check")
    return result


def expected_status(
    *,
    attempts: list[dict[str, Any]],
    difficulty: int,
    max_expansions: int,
) -> str:
    if not attempts:
        return "estimated"
    last = attempts[-1]
    result = last["verification"]["result"]
    if result == "pass":
        return "verified"
    if result == "blocked":
        return "blocked"
    expansions = len(attempts) - 1
    can_expand = last["level"] < 3 and expansions < max_expansions
    return "active" if can_expand else "exhausted"


def validate_attempts(
    value: Any,
    *,
    acceptance_ids: list[str],
    estimate_scope: list[str],
    probe_evidence: list[str],
    difficulty: int | None,
    risk: str | None,
    max_expansions: int | None,
    findings: list[Finding],
) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        add(findings, "e3.attempts", "attempts must be a list")
        return [], probe_evidence
    expected_scope = list(estimate_scope)
    expected_evidence = list(probe_evidence)
    valid_attempts: list[dict[str, Any]] = []
    previous_result: str | None = None
    previous_level: int | None = None

    for index, raw in enumerate(value):
        path = f"e3.attempts[{index}]"
        attempt = object_shape(
            raw,
            path=path,
            required=ATTEMPT_KEYS,
            allowed=ATTEMPT_KEYS,
            findings=findings,
        )
        if attempt is None:
            continue
        valid_attempts.append(attempt)
        if previous_result in {"pass", "blocked"}:
            add(findings, path, f"no attempt is allowed after {previous_result}")

        if attempt.get("index") != index:
            add(findings, f"{path}.index", f"index must be {index}")
        level = attempt.get("level")
        if not isinstance(level, int) or isinstance(level, bool) or level not in {1, 2, 3}:
            add(findings, f"{path}.level", "level must be 1, 2, or 3")
            level = None
        expected_level = difficulty if index == 0 else (
            previous_level + 1 if previous_level is not None else None
        )
        if expected_level is not None and level != expected_level:
            add(
                findings,
                f"{path}.level",
                f"level must expand monotonically to {expected_level}",
            )
        if index == 0 and attempt.get("scope") != estimate_scope:
            add(findings, f"{path}.scope", "first execution scope must equal the estimate")
        elif index > 0:
            scope = attempt.get("scope")
            if not unique_text_list(scope, nonempty=True):
                add(findings, f"{path}.scope", "scope must be a non-empty unique list")
            elif not set(expected_scope) < set(scope):
                add(
                    findings,
                    f"{path}.scope",
                    "expanded scope must be a strict superset of prior scope",
                )
            else:
                expected_scope = list(scope)

        reused = attempt.get("reused_evidence")
        if not unique_evidence_list(reused):
            add(
                findings,
                f"{path}.reused_evidence",
                "reused_evidence must be a unique list of concrete evidence refs",
            )
        elif reused != expected_evidence:
            add(
                findings,
                f"{path}.reused_evidence",
                "each attempt must reuse the complete cached evidence in order",
            )
        new_evidence = attempt.get("new_evidence")
        if not unique_evidence_list(new_evidence, nonempty=True):
            add(
                findings,
                f"{path}.new_evidence",
                "new_evidence must be a non-empty unique list of concrete evidence refs",
            )
            new_evidence = []
        duplicate_evidence = sorted(set(new_evidence) & set(expected_evidence))
        if duplicate_evidence:
            add(
                findings,
                f"{path}.new_evidence",
                "new_evidence repeats cached refs: " + ", ".join(duplicate_evidence),
            )
        known = set(expected_evidence) | set(new_evidence)
        validate_cost(
            attempt.get("cost"),
            path=f"{path}.cost",
            findings=findings,
        )
        result = validate_verification(
            attempt.get("verification"),
            path=f"{path}.verification",
            acceptance_ids=acceptance_ids,
            known_evidence=known,
            risk=risk,
            level=level,
            findings=findings,
        )
        expected_evidence = ordered_union(expected_evidence, new_evidence)
        previous_result = result
        previous_level = level

    if (
        max_expansions is not None
        and len(value) > 0
        and len(value) - 1 > max_expansions
    ):
        add(
            findings,
            "e3.attempts.expansions",
            "attempts exceed max_expansions",
        )
    return valid_attempts, expected_evidence


def validate_ledger(ledger: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(ledger, dict):
        return [Finding("e3.not_object", "E3 ledger must be an object")]
    unknown_keys(ledger, TOP_REQUIRED, "e3.unknown_keys", findings)
    missing_keys(ledger, TOP_REQUIRED, "e3.missing", findings)

    if ledger.get("schema_version") != SCHEMA_VERSION:
        add(findings, "e3.schema_version", f"schema_version must be {SCHEMA_VERSION}")
    if ledger.get("artifact_type") != "e3_execution_ledger":
        add(findings, "e3.artifact_type", "artifact_type must be e3_execution_ledger")
    if not valid_id(ledger.get("task_id")):
        add(findings, "e3.task_id", "task_id is malformed")
    if not has_text(ledger.get("objective")):
        add(findings, "e3.objective", "objective is required")

    acceptance_ids = validate_acceptance_checks(ledger.get("acceptance_checks"), findings)
    difficulty, risk, confidence, estimate_scope, probe_evidence = validate_estimate(
        ledger.get("estimate"), findings
    )
    validate_safety_floor(ledger.get("safety_floor"), findings)

    max_expansions = ledger.get("max_expansions")
    if not isinstance(max_expansions, int) or isinstance(max_expansions, bool) or not 0 <= max_expansions <= 2:
        add(findings, "e3.max_expansions", "max_expansions must be an integer in [0, 2]")
        max_expansions = None
    elif difficulty is not None and max_expansions > 3 - difficulty:
        add(
            findings,
            "e3.max_expansions",
            "max_expansions cannot exceed the remaining scope levels",
        )
    threshold = ledger.get("confidence_threshold")
    if not finite_number(threshold) or not 0.0 <= threshold <= 1.0:
        add(
            findings,
            "e3.confidence_threshold",
            "confidence_threshold must be finite in [0, 1]",
        )
        threshold = None
    expected_low_confidence = (
        confidence < threshold
        if confidence is not None and threshold is not None
        else None
    )
    if not isinstance(ledger.get("low_confidence_expansion_candidate"), bool):
        add(
            findings,
            "e3.low_confidence_expansion_candidate",
            "low-confidence candidate must be boolean",
        )
    elif (
        expected_low_confidence is not None
        and ledger["low_confidence_expansion_candidate"] != expected_low_confidence
    ):
        add(
            findings,
            "e3.low_confidence_expansion_candidate",
            "candidate flag must be derived from initial confidence",
        )

    attempts, expected_cached = validate_attempts(
        ledger.get("attempts"),
        acceptance_ids=acceptance_ids,
        estimate_scope=estimate_scope,
        probe_evidence=probe_evidence,
        difficulty=difficulty,
        risk=risk,
        max_expansions=max_expansions,
        findings=findings,
    )
    cached = ledger.get("cached_evidence")
    if not unique_evidence_list(cached):
        add(
            findings,
            "e3.cached_evidence",
            "cached_evidence must be a unique list of concrete evidence refs",
        )
    elif cached != expected_cached:
        add(
            findings,
            "e3.cached_evidence",
            "cached_evidence must equal the ordered cumulative evidence",
        )

    current_level = ledger.get("current_level")
    expected_level = (
        attempts[-1].get("level")
        if attempts
        else difficulty
    )
    if current_level != expected_level:
        add(
            findings,
            "e3.current_level",
            f"current_level must be {expected_level}",
        )

    status = ledger.get("status")
    if not isinstance(status, str) or status not in STATUSES:
        add(findings, "e3.status", f"status must be one of {sorted(STATUSES)}")
    elif (
        not findings
        and difficulty is not None
        and max_expansions is not None
        and len(attempts) == len(ledger.get("attempts", []))
    ):
        derived = expected_status(
            attempts=attempts,
            difficulty=difficulty,
            max_expansions=max_expansions,
        )
        if status != derived:
            add(findings, "e3.status", f"status must be derived as {derived}")

    summary = ledger.get("summary")
    if isinstance(status, str) and status in {"verified", "blocked", "exhausted"}:
        if not has_text(summary):
            add(findings, "e3.summary", f"{status} status needs a summary")
        elif attempts:
            verification = attempts[-1].get("verification")
            expected_summary = (
                verification.get("notes")
                if isinstance(verification, dict)
                and isinstance(verification.get("notes"), str)
                else None
            )
            if expected_summary is not None and summary != expected_summary:
                add(
                    findings,
                    "e3.summary",
                    "terminal summary must equal the final verification notes",
                )
    elif summary != "":
        add(findings, "e3.summary", "non-terminal status must have an empty summary")
    return findings


def require_valid(ledger: Any) -> dict[str, Any]:
    findings = validate_ledger(ledger)
    if findings:
        detail = "; ".join(f"{item.code}: {item.message}" for item in findings)
        raise ArtifactError(detail)
    assert isinstance(ledger, dict)
    return ledger


def parse_named_text(value: str, label: str) -> dict[str, str]:
    identifier, separator, description = value.partition("=")
    if not separator or not valid_id(identifier) or not has_text(description):
        raise ArtifactError(f"{label} must be ID=TEXT with a valid id")
    return {"id": identifier, "description": description}


def make_ledger(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise ArtifactError("E3 init spec must be an object")
    extra = sorted(set(spec) - SPEC_KEYS)
    missing = sorted(SPEC_KEYS - set(spec))
    if extra:
        raise ArtifactError("E3 init spec unknown keys: " + ", ".join(extra))
    if missing:
        raise ArtifactError("E3 init spec missing keys: " + ", ".join(missing))
    difficulty = spec["difficulty"]
    max_expansions = spec["max_expansions"]
    if max_expansions is None and isinstance(difficulty, int) and not isinstance(difficulty, bool):
        max_expansions = max(0, 3 - difficulty)
    probe = copy.deepcopy(spec["probe"])
    raw_scope = copy.deepcopy(spec["scope"])
    raw_safety_gates = copy.deepcopy(spec["safety_gates"])
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "e3_execution_ledger",
        "task_id": spec["task_id"],
        "objective": spec["objective"],
        "acceptance_checks": copy.deepcopy(spec["acceptance_checks"]),
        "estimate": {
            "difficulty": difficulty,
            "scope": raw_scope,
            "risk": spec["risk"],
            "confidence": spec["confidence"],
            "rationale": spec["rationale"],
            "probe": probe,
        },
        "max_expansions": max_expansions,
        "confidence_threshold": spec["confidence_threshold"],
        "low_confidence_expansion_candidate": (
            spec["confidence"] < spec["confidence_threshold"]
            if finite_number(spec["confidence"])
            and finite_number(spec["confidence_threshold"])
            else False
        ),
        "safety_floor": {
            "required_gates": raw_safety_gates,
            "closure_tier_a_preserved": True,
            "authority_and_safety_preserved": True,
        },
        "current_level": difficulty,
        "cached_evidence": (
            copy.deepcopy(probe.get("evidence", []))
            if isinstance(probe, dict)
            else []
        ),
        "attempts": [],
        "status": "estimated",
        "summary": "",
    }
    return require_valid(ledger)


def validate_attempt_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArtifactError("attempt input must be an object")
    extra = sorted(set(value) - ATTEMPT_INPUT_KEYS)
    missing = sorted(ATTEMPT_INPUT_KEYS - set(value))
    if extra:
        raise ArtifactError("attempt input unknown keys: " + ", ".join(extra))
    if missing:
        raise ArtifactError("attempt input missing keys: " + ", ".join(missing))
    if not unique_text_list(value.get("scope_additions")):
        raise ArtifactError("scope_additions must be a unique list of non-empty strings")
    if not unique_evidence_list(value.get("new_evidence"), nonempty=True):
        raise ArtifactError(
            "new_evidence must be a non-empty unique list of concrete evidence refs"
        )
    cost_findings: list[Finding] = []
    validate_cost(value.get("cost"), path="e3.attempt_input.cost", findings=cost_findings)
    if cost_findings:
        detail = "; ".join(
            f"{item.code}: {item.message}" for item in cost_findings
        )
        raise ArtifactError(detail)
    return value


def append_attempt(ledger: dict[str, Any], attempt_input: dict[str, Any]) -> dict[str, Any]:
    ledger = copy.deepcopy(require_valid(ledger))
    attempt_input = validate_attempt_input(copy.deepcopy(attempt_input))
    if ledger["status"] not in {"estimated", "active"}:
        raise ArtifactError(f"{ledger['status']} E3 run cannot accept another attempt")
    index = len(ledger["attempts"])
    additions = attempt_input["scope_additions"]
    if index == 0 and additions:
        raise ArtifactError("first execution must use the estimated scope without additions")
    if index > 0 and not additions:
        raise ArtifactError("each expansion needs at least one scope addition")
    prior_scope = (
        ledger["attempts"][-1]["scope"]
        if ledger["attempts"]
        else ledger["estimate"]["scope"]
    )
    overlap = sorted(set(additions) & set(prior_scope))
    if overlap:
        raise ArtifactError("scope additions repeat existing scope: " + ", ".join(overlap))
    new_evidence = attempt_input["new_evidence"]
    duplicate_evidence = sorted(set(new_evidence) & set(ledger["cached_evidence"]))
    if duplicate_evidence:
        raise ArtifactError(
            "new evidence repeats cached refs: " + ", ".join(duplicate_evidence)
        )
    level = ledger["estimate"]["difficulty"] + index
    if level > 3 or index > ledger["max_expansions"]:
        raise ArtifactError("E3 expansion budget is exhausted")
    scope = ordered_union(prior_scope, additions)
    verification = copy.deepcopy(attempt_input["verification"])
    verification_findings: list[Finding] = []
    verification_result = validate_verification(
        verification,
        path="e3.attempt_input.verification",
        acceptance_ids=[item["id"] for item in ledger["acceptance_checks"]],
        known_evidence=set(ledger["cached_evidence"]) | set(new_evidence),
        risk=ledger["estimate"]["risk"],
        level=level,
        findings=verification_findings,
    )
    if verification_findings:
        detail = "; ".join(
            f"{item.code}: {item.message}" for item in verification_findings
        )
        raise ArtifactError(detail)
    assert verification_result is not None
    attempt = {
        "index": index,
        "level": level,
        "scope": scope,
        "reused_evidence": list(ledger["cached_evidence"]),
        "new_evidence": list(new_evidence),
        "cost": copy.deepcopy(attempt_input["cost"]),
        "verification": verification,
    }
    ledger["attempts"].append(attempt)
    ledger["cached_evidence"] = ordered_union(
        ledger["cached_evidence"], new_evidence
    )
    ledger["current_level"] = level
    ledger["status"] = expected_status(
        attempts=ledger["attempts"],
        difficulty=ledger["estimate"]["difficulty"],
        max_expansions=ledger["max_expansions"],
    )
    ledger["summary"] = (
        verification["notes"]
        if ledger["status"] in {"verified", "blocked", "exhausted"}
        else ""
    )
    return require_valid(ledger)


def markdown_escape(value: Any) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
    )


def render_markdown(ledger: dict[str, Any]) -> str:
    ledger = require_valid(ledger)
    estimate = ledger["estimate"]
    probe = estimate["probe"]
    lines = [
        f"# E3 Execution Ledger: {markdown_escape(ledger['task_id'])}",
        "",
        f"**Objective:** {markdown_escape(ledger['objective'])}",
        "",
        f"**Status:** `{ledger['status']}`",
        "",
        "## Initial Operating Point",
        "",
        "| Difficulty | Scope | Risk | Confidence | Low-confidence candidate |",
        "|---:|---|---|---:|---|",
        "| "
        + " | ".join(
            (
                str(estimate["difficulty"]),
                markdown_escape(", ".join(estimate["scope"])),
                markdown_escape(estimate["risk"]),
                f"{estimate['confidence']:.3f}",
                str(ledger["low_confidence_expansion_candidate"]).lower(),
            )
        )
        + " |",
        "",
        f"**Rationale:** {markdown_escape(estimate['rationale'])}",
        "",
        f"**Probe:** `{probe['kind']}` ({probe['count']}/1); "
        f"query: {markdown_escape(probe['query'] or '-')}; "
        f"evidence: {markdown_escape(', '.join(probe['evidence']) or '-')}",
        "",
        "## Acceptance And Safety Floor",
        "",
    ]
    for check in ledger["acceptance_checks"]:
        lines.append(
            f"- `{markdown_escape(check['id'])}`: {markdown_escape(check['description'])}"
        )
    lines.extend(
        [
            "",
            "**Non-suppressible gates:** "
            + markdown_escape(", ".join(ledger["safety_floor"]["required_gates"])),
            "",
            "## Attempts",
            "",
            "| # | Level | Scope | Reused evidence | New evidence | Raw cost | Verification | Result |",
            "|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for attempt in ledger["attempts"]:
        verification = attempt["verification"]
        cost = attempt["cost"]
        raw_cost = (
            f"latency_ms={cost['latency_ms'] if cost['latency_ms'] is not None else '-'}; "
            f"tokens={cost['tokens'] if cost['tokens'] is not None else '-'}; "
            f"tool_calls={cost['tool_calls']}; "
            f"inspected_items={cost['inspected_items']}"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    str(attempt["index"]),
                    str(attempt["level"]),
                    markdown_escape(", ".join(attempt["scope"])),
                    markdown_escape(", ".join(attempt["reused_evidence"]) or "-"),
                    markdown_escape(", ".join(attempt["new_evidence"])),
                    markdown_escape(raw_cost),
                    markdown_escape(verification["tier"]),
                    markdown_escape(verification["result"]),
                )
            )
            + " |"
        )
        for check in verification["checks"]:
            lines.append(
                f"  - `{markdown_escape(check['id'])}`: `{check['result']}`; "
                f"evidence={markdown_escape(', '.join(check['evidence']) or '-')}; "
                f"notes={markdown_escape(check['notes'] or '-')}"
            )
        lines.append(f"  - Notes: {markdown_escape(verification['notes'])}")
    if not ledger["attempts"]:
        lines.append("| - | - | - | - | - | - | - | - |")
    lines.extend(
        [
            "",
            "## Cached Evidence",
            "",
        ]
    )
    for ref in ledger["cached_evidence"]:
        lines.append(f"- {markdown_escape(ref)}")
    if not ledger["cached_evidence"]:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Summary",
            "",
            markdown_escape(ledger["summary"] or "Run is not terminal."),
            "",
        ]
    )
    return "\n".join(lines)


def spec_from_args(args: argparse.Namespace) -> dict[str, Any]:
    acceptance = [
        parse_named_text(value, "--acceptance")
        for value in args.acceptance
    ]
    probe = {
        "kind": args.probe_kind,
        "count": 0 if args.probe_kind == "none" else 1,
        "query": args.probe_query,
        "evidence": list(args.probe_evidence),
    }
    return {
        "task_id": args.task_id,
        "objective": args.objective,
        "acceptance_checks": acceptance,
        "difficulty": args.difficulty,
        "scope": list(args.scope),
        "risk": args.risk,
        "confidence": args.confidence,
        "rationale": args.rationale,
        "probe": probe,
        "max_expansions": args.max_expansions,
        "confidence_threshold": args.confidence_threshold,
        "safety_gates": ordered_union(DEFAULT_SAFETY_GATES, args.safety_gate),
    }


def command_init(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if args.markdown_output:
        require_distinct_paths(
            output,
            Path(args.markdown_output),
            "E3 JSON and Markdown output paths must be distinct",
        )
    ledger = make_ledger(spec_from_args(args))
    write_json(output, ledger)
    if args.markdown_output:
        write_text_atomic(Path(args.markdown_output), render_markdown(ledger))
    print(f"wrote E3 ledger: {output}")
    return 0


def command_record(args: argparse.Namespace) -> int:
    ledger_path = canonical_artifact_path(Path(args.ledger), "E3 ledger")
    if args.markdown_output:
        require_distinct_paths(
            ledger_path,
            Path(args.markdown_output),
            "E3 JSON and Markdown output paths must be distinct",
        )
    ledger = load_json(ledger_path)
    attempt_input = load_json(Path(args.attempt))
    updated = append_attempt(ledger, attempt_input)
    write_json(ledger_path, updated)
    if args.markdown_output:
        write_text_atomic(Path(args.markdown_output), render_markdown(updated))
    print(f"recorded E3 attempt {len(updated['attempts']) - 1}: {ledger_path}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    path = canonical_artifact_path(Path(args.ledger), "E3 ledger")
    ledger = load_json(path)
    findings = validate_ledger(ledger)
    if findings:
        for finding in findings:
            print(f"RED {finding.code}: {finding.message}", file=sys.stderr)
        return 2
    print(f"OK valid E3 ledger: {path}")
    return 0


def command_render(args: argparse.Namespace) -> int:
    ledger_path = canonical_artifact_path(Path(args.ledger), "E3 ledger")
    output = Path(args.output)
    require_distinct_paths(
        ledger_path,
        output,
        "E3 render output must not replace the canonical ledger",
    )
    ledger = require_valid(load_json(ledger_path))
    write_text_atomic(output, render_markdown(ledger))
    print(f"rendered E3 ledger: {output}")
    return 0


def default_spec(**overrides: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "task_id": "e3-selftest",
        "objective": "Apply one bounded edit and verify it.",
        "acceptance_checks": [
            {"id": "focused-test", "description": "Focused behavior passes."},
            {"id": "closure-check", "description": "Tier A companions remain covered."},
        ],
        "difficulty": 1,
        "scope": ["src/target.py"],
        "risk": "low",
        "confidence": 0.9,
        "rationale": "Explicit local target and acceptance check.",
        "probe": {"kind": "none", "count": 0, "query": "", "evidence": []},
        "max_expansions": 2,
        "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
        "safety_gates": list(DEFAULT_SAFETY_GATES),
    }
    spec.update(overrides)
    return spec


def attempt_input(
    *,
    scope_additions: Sequence[str] = (),
    new_evidence: Sequence[str],
    cost: dict[str, Any] | None = None,
    tier: str = "local",
    result: str = "pass",
    notes: str = "Verification completed.",
) -> dict[str, Any]:
    check_results = {
        "pass": ("pass", "pass"),
        "fail": ("fail", "not_run"),
        "blocked": ("blocked", "not_run"),
    }
    focused_result, closure_result = check_results[result]
    return {
        "scope_additions": list(scope_additions),
        "new_evidence": list(new_evidence),
        "cost": copy.deepcopy(
            cost
            if cost is not None
            else {
                "latency_ms": 1000.0,
                "tokens": 200,
                "tool_calls": 2,
                "inspected_items": 1,
            }
        ),
        "verification": {
            "tier": tier,
            "result": result,
            "checks": [
                {
                    "id": "focused-test",
                    "result": focused_result,
                    "evidence": [new_evidence[0]] if focused_result != "not_run" else [],
                    "notes": "Focused check.",
                },
                {
                    "id": "closure-check",
                    "result": closure_result,
                    "evidence": [new_evidence[-1]] if closure_result != "not_run" else [],
                    "notes": "Closure check." if closure_result != "not_run" else "Deferred until expansion.",
                },
            ],
            "notes": notes,
        },
    }


def run_selftest() -> int:
    controls = 0

    def check(condition: bool, label: str) -> None:
        nonlocal controls
        controls += 1
        if not condition:
            raise AssertionError(label)

    def blocked(fn, contains: str) -> None:
        nonlocal controls
        controls += 1
        try:
            fn()
        except ArtifactError as exc:
            if contains not in str(exc):
                raise AssertionError(f"wrong reason for {contains}: {exc}") from exc
        else:
            raise AssertionError(f"expected block: {contains}")

    ledger = make_ledger(default_spec())
    check(ledger["status"] == "estimated", "init status")
    check(ledger["current_level"] == 1, "initial level")
    check(not ledger["low_confidence_expansion_candidate"], "high confidence flag")

    low = make_ledger(default_spec(confidence=0.4))
    check(low["low_confidence_expansion_candidate"], "low confidence flag")

    first = append_attempt(
        ledger,
        attempt_input(
            new_evidence=("run:focused-pass", "run:closure-pass"),
            result="pass",
        ),
    )
    check(first["status"] == "verified", "verified status")
    check(first["current_level"] == 1, "verified level")
    check(first["cached_evidence"] == ["run:focused-pass", "run:closure-pass"], "cached evidence")
    check(first["attempts"][0]["cost"]["tool_calls"] == 2, "raw cost is recorded")
    blocked(
        lambda: append_attempt(
            first,
            attempt_input(
                scope_additions=("src/other.py",),
                new_evidence=("run:late", "run:late-closure"),
            ),
        ),
        "verified E3 run cannot accept another attempt",
    )

    failed = append_attempt(
        ledger,
        attempt_input(
            new_evidence=("run:focused-fail", "run:closure-deferred"),
            result="fail",
            notes="Focused verification failed.",
        ),
    )
    check(failed["status"] == "active", "failed verification activates expansion")
    expanded = append_attempt(
        failed,
        attempt_input(
            scope_additions=("src/importer.py",),
            new_evidence=("run:import-trace", "run:expanded-pass"),
            tier="focused",
            result="pass",
        ),
    )
    check(expanded["status"] == "verified", "expanded success")
    check(expanded["current_level"] == 2, "one-level expansion")
    check(
        expanded["attempts"][1]["reused_evidence"]
        == ["run:focused-fail", "run:closure-deferred"],
        "complete evidence reuse",
    )
    check(
        set(expanded["attempts"][0]["scope"]) < set(expanded["attempts"][1]["scope"]),
        "strict scope growth",
    )

    blocked(
        lambda: append_attempt(
            failed,
            attempt_input(
                new_evidence=("run:no-scope", "run:no-scope-closure"),
                tier="focused",
            ),
        ),
        "each expansion needs at least one scope addition",
    )
    blocked(
        lambda: append_attempt(
            failed,
            attempt_input(
                scope_additions=("src/target.py",),
                new_evidence=("run:dup-scope", "run:dup-scope-closure"),
                tier="focused",
            ),
        ),
        "scope additions repeat existing scope",
    )
    blocked(
        lambda: append_attempt(
            failed,
            attempt_input(
                scope_additions=("src/importer.py",),
                new_evidence=("run:focused-fail", "run:other"),
                tier="focused",
            ),
        ),
        "new evidence repeats cached refs",
    )

    high = make_ledger(default_spec(risk="high", difficulty=3, max_expansions=0))
    blocked(
        lambda: append_attempt(
            high,
            attempt_input(
                new_evidence=("run:high", "run:high-closure"),
                tier="local",
            ),
        ),
        "high-risk execution needs at least full verification",
    )

    incomplete = attempt_input(
        new_evidence=("run:incomplete", "run:incomplete-closure"),
    )
    incomplete["verification"]["checks"].pop()
    blocked(
        lambda: append_attempt(ledger, incomplete),
        "checks must cover every acceptance check exactly once",
    )

    unknown_evidence = attempt_input(
        new_evidence=("run:known", "run:known-closure"),
    )
    unknown_evidence["verification"]["checks"][0]["evidence"] = ["run:unknown"]
    blocked(
        lambda: append_attempt(ledger, unknown_evidence),
        "unregistered evidence",
    )
    prose_evidence = attempt_input(
        new_evidence=("run:known", "run:closure"),
    )
    prose_evidence["new_evidence"][0] = "the test passed"
    blocked(
        lambda: append_attempt(ledger, prose_evidence),
        "concrete evidence refs",
    )
    invalid_cost = attempt_input(
        new_evidence=("run:cost", "run:cost-closure"),
        cost={
            "latency_ms": -1,
            "tokens": 10,
            "tool_calls": 1,
            "inspected_items": 1,
        },
    )
    blocked(
        lambda: append_attempt(ledger, invalid_cost),
        "latency_ms must be null or finite and non-negative",
    )

    tampered = copy.deepcopy(expanded)
    tampered["attempts"][1]["level"] = 3
    check(
        any(item.code.endswith(".level") for item in validate_ledger(tampered)),
        "skipped level is detected",
    )
    tampered = copy.deepcopy(expanded)
    tampered["attempts"][1]["reused_evidence"] = []
    check(
        any("reused_evidence" in item.code for item in validate_ledger(tampered)),
        "evidence reset is detected",
    )
    tampered = copy.deepcopy(expanded)
    tampered["attempts"][1]["scope"] = ["src/importer.py"]
    check(
        any(item.code.endswith(".scope") for item in validate_ledger(tampered)),
        "scope shrink is detected",
    )
    tampered = copy.deepcopy(expanded)
    tampered["cached_evidence"] = []
    check(
        any(item.code == "e3.cached_evidence" for item in validate_ledger(tampered)),
        "cached evidence drift is detected",
    )
    tampered = copy.deepcopy(first)
    tampered["attempts"].append(copy.deepcopy(first["attempts"][0]))
    check(
        any("no attempt is allowed after pass" in item.message for item in validate_ledger(tampered)),
        "post-success work is detected",
    )
    tampered = copy.deepcopy(first)
    tampered["safety_floor"]["closure_tier_a_preserved"] = False
    check(
        any("Tier A" in item.message for item in validate_ledger(tampered)),
        "Tier A safety floor is enforced",
    )
    tampered = copy.deepcopy(first)
    tampered["safety_floor"]["required_gates"] = ["custom_gate"]
    check(
        any("cannot suppress defaults" in item.message for item in validate_ledger(tampered)),
        "default safety gates are non-suppressible",
    )
    tampered = copy.deepcopy(first)
    tampered["summary"] = "Unbound terminal claim."
    check(
        any("final verification notes" in item.message for item in validate_ledger(tampered)),
        "terminal summary is bound to verification",
    )
    tampered = copy.deepcopy(first)
    tampered["estimate"]["probe"]["count"] = 2
    check(
        any(item.code == "e3.estimate.probe.count" for item in validate_ledger(tampered)),
        "probe budget is enforced",
    )

    malformed_ledgers: list[tuple[str, dict[str, Any]]] = []
    for label, mutate in (
        ("probe kind", lambda item: item["estimate"]["probe"].update(kind={})),
        ("risk", lambda item: item["estimate"].update(risk={})),
        ("status", lambda item: item.update(status={})),
        (
            "verification tier",
            lambda item: item["attempts"][0]["verification"].update(tier={}),
        ),
        (
            "verification result",
            lambda item: item["attempts"][0]["verification"].update(result={}),
        ),
        (
            "check result",
            lambda item: item["attempts"][0]["verification"]["checks"][0].update(
                result={}
            ),
        ),
        (
            "missing verification",
            lambda item: item["attempts"][0].pop("verification"),
        ),
        (
            "malformed verification",
            lambda item: item["attempts"][0].update(verification={}),
        ),
        ("malformed scope", lambda item: item["attempts"][0].update(scope={})),
        (
            "malformed new evidence",
            lambda item: item["attempts"][0].update(new_evidence={}),
        ),
        (
            "malformed cost",
            lambda item: item["attempts"][0].update(cost={"latency_ms": {}}),
        ),
    ):
        malformed = copy.deepcopy(first)
        mutate(malformed)
        malformed_ledgers.append((label, malformed))
    for label, malformed in malformed_ledgers:
        check(bool(validate_ledger(malformed)), f"{label} is reasoned, not an exception")

    rendered = render_markdown(expanded)
    check("Initial Operating Point" in rendered, "render estimate")
    check("run:focused-fail" in rendered, "render reused evidence")
    check("tier_a_recall" in rendered, "render safety floor")
    check("verified" in rendered, "render terminal status")
    check("tool_calls=2" in rendered, "render raw cost")

    schema = json.loads((ROOT / "schemas" / "e3-execution-ledger.schema.json").read_text(encoding="utf-8"))
    check(set(schema["required"]) == TOP_REQUIRED, "schema top-level required keys")
    check(set(schema["properties"]) - {"$schema", "$id"} == TOP_REQUIRED, "schema top-level properties")
    check(
        set(schema["$defs"]["attempt"]["properties"]) == ATTEMPT_KEYS,
        "schema attempt keys",
    )
    check(
        set(schema["$defs"]["cost"]["properties"]) == COST_KEYS,
        "schema cost keys",
    )
    check(
        set(schema["$defs"]["verification"]["properties"]) == VERIFICATION_KEYS,
        "schema verification keys",
    )
    check(
        set(schema["$defs"]["acceptanceCheck"]["properties"]) == ACCEPTANCE_KEYS,
        "schema acceptance keys",
    )
    check(
        set(schema["$defs"]["estimate"]["properties"]) == ESTIMATE_KEYS,
        "schema estimate keys",
    )
    check(
        set(schema["$defs"]["probe"]["properties"]) == PROBE_KEYS,
        "schema probe keys",
    )
    check(
        set(schema["$defs"]["safetyFloor"]["properties"]) == SAFETY_KEYS,
        "schema safety keys",
    )
    schema_safety_defaults = {
        item["contains"]["const"]
        for item in schema["$defs"]["safetyFloor"]["properties"]["required_gates"][
            "allOf"
        ][1:]
    }
    check(
        schema_safety_defaults == set(DEFAULT_SAFETY_GATES),
        "schema default safety gates",
    )
    check(
        set(schema["$defs"]["check"]["properties"]) == CHECK_KEYS,
        "schema check keys",
    )
    check(
        schema["$defs"]["evidenceRef"]["pattern"] == EVIDENCE_REF_RE.pattern,
        "schema evidence-ref pattern",
    )
    check(
        set(schema["$defs"]["probe"]["properties"]["kind"]["enum"]) == PROBE_KINDS,
        "schema probe kinds",
    )
    check(
        set(schema["$defs"]["estimate"]["properties"]["risk"]["enum"]) == RISKS,
        "schema risk enum",
    )
    check(
        set(schema["$defs"]["verification"]["properties"]["tier"]["enum"])
        == VERIFICATION_TIERS,
        "schema verification tiers",
    )
    check(
        set(schema["$defs"]["verification"]["properties"]["result"]["enum"])
        == VERIFICATION_RESULTS,
        "schema verification results",
    )
    check(
        set(schema["$defs"]["check"]["properties"]["result"]["enum"])
        == CHECK_RESULTS,
        "schema check results",
    )
    check(set(schema["properties"]["status"]["enum"]) == STATUSES, "schema statuses")

    with tempfile.TemporaryDirectory(prefix="e3-selftest-") as raw_tmp:
        tmp = Path(raw_tmp)
        ledger_path = tmp / "ledger.json"
        markdown_path = tmp / "ledger.md"
        write_json(ledger_path, expanded)
        write_text_atomic(markdown_path, render_markdown(expanded))
        check(require_valid(load_json(ledger_path))["status"] == "verified", "JSON round trip")
        check(markdown_path.read_text(encoding="utf-8").startswith("# E3"), "Markdown round trip")
        blocked(
            lambda: require_distinct_paths(
                ledger_path,
                ledger_path,
                "E3 render output must not replace the canonical ledger",
            ),
            "must not replace",
        )

    print(f"E3 execution selftest OK: {controls} controls")
    return 0


def run_cases(path: Path) -> int:
    seen: set[str] = set()
    passed = 0
    total = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        total += 1
        try:
            case = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            print(f"RED line {line_number}: invalid JSON: {exc}", file=sys.stderr)
            continue
        if not isinstance(case, dict) or set(case) != {
            "id",
            "expected",
            "spec",
            "attempts",
            "expected_status",
            "reason_contains",
        }:
            print(f"RED line {line_number}: malformed case shape", file=sys.stderr)
            continue
        case_id = case["id"]
        if not has_text(case_id) or case_id in seen:
            print(f"RED line {line_number}: invalid or duplicate id", file=sys.stderr)
            continue
        seen.add(case_id)
        expected = case["expected"]
        if not isinstance(expected, str) or expected not in {"pass", "block"}:
            print(f"RED {case_id}: expected must be pass or block", file=sys.stderr)
            continue
        try:
            ledger = make_ledger(case["spec"])
            for raw_attempt in case["attempts"]:
                ledger = append_attempt(ledger, raw_attempt)
            require_valid(ledger)
            observed = "pass"
            reason = ""
        except (ArtifactError, TypeError, ValueError) as exc:
            observed = "block"
            reason = str(exc)
        if observed != expected:
            print(f"RED {case_id}: expected {expected}, got {observed}: {reason}", file=sys.stderr)
            continue
        if expected == "pass" and ledger["status"] != case["expected_status"]:
            print(
                f"RED {case_id}: expected status {case['expected_status']}, got {ledger['status']}",
                file=sys.stderr,
            )
            continue
        if expected == "block" and case["reason_contains"] not in reason:
            print(
                f"RED {case_id}: missing reason {case['reason_contains']!r}: {reason}",
                file=sys.stderr,
            )
            continue
        passed += 1
        print(f"PASS {case_id}")
    if passed != total or total == 0:
        print(f"E3 cases FAILED: {passed}/{total}", file=sys.stderr)
        return 1
    print(f"E3 cases OK: {passed}/{total}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="write an estimated E3 ledger")
    init.add_argument("--task-id", required=True)
    init.add_argument("--objective", required=True)
    init.add_argument("--acceptance", action="append", required=True, help="ID=TEXT")
    init.add_argument("--difficulty", type=int, choices=(1, 2, 3), required=True)
    init.add_argument("--scope", action="append", required=True)
    init.add_argument("--risk", choices=sorted(RISKS), required=True)
    init.add_argument("--confidence", type=float, required=True)
    init.add_argument("--rationale", required=True)
    init.add_argument("--probe-kind", choices=sorted(PROBE_KINDS), default="none")
    init.add_argument("--probe-query", default="")
    init.add_argument("--probe-evidence", action="append", default=[])
    init.add_argument("--max-expansions", type=int)
    init.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
    )
    init.add_argument("--safety-gate", action="append", default=[])
    init.add_argument("--output", required=True)
    init.add_argument("--markdown-output")

    record = subparsers.add_parser("record", help="record one Execute or Expand attempt")
    record.add_argument("--ledger", required=True)
    record.add_argument("--attempt", required=True, help="JSON attempt input")
    record.add_argument("--markdown-output")

    validate = subparsers.add_parser("validate", help="validate an E3 ledger")
    validate.add_argument("--ledger", required=True)

    render = subparsers.add_parser("render", help="render an E3 ledger as Markdown")
    render.add_argument("--ledger", required=True)
    render.add_argument("--output", required=True)

    cases = subparsers.add_parser("cases", help="run JSONL lifecycle cases")
    cases.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    subparsers.add_parser("selftest", help="run deterministic E3 self-controls")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return command_init(args)
        if args.command == "record":
            return command_record(args)
        if args.command == "validate":
            return command_validate(args)
        if args.command == "render":
            return command_render(args)
        if args.command == "cases":
            return run_cases(args.cases)
        if args.command == "selftest":
            return run_selftest()
    except (ArtifactError, OSError, json.JSONDecodeError) as exc:
        print(f"E3 error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
