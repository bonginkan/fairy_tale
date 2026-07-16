#!/usr/bin/env python3
"""Run Fairy Fusion independent reviewer passes and synthesize their findings.

This runner is intentionally OpenRouter-free. It implements the repository's
fusion-style contract: bounded independent reviewer prompts, one synthesis
pass, explicit contradictions, blind spots, and closure actions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTO_CHECK_INPUT_KEYS = {
    "schema_version",
    "failure_signatures",
    "validation_ledger_status",
    "artifact_status",
    "review_conflict",
    "explicit_request",
    "reviewer_cap",
    "recursion_depth",
    "artifact_path",
}
AUTO_CHECK_DECISION_KEYS = {
    "schema_version",
    "artifact_type",
    "decision",
    "should_trigger",
    "reasons",
    "reviewer_cap",
    "recursion_depth",
    "recursion_cap",
    "artifact_path",
    "automatic_execution",
    "input_sha256",
    "observed",
}
AUTO_CHECK_REASONS = {
    "repeated_failure_signature",
    "validation_ledger_missing",
    "empty_artifact",
    "meaningless_artifact",
    "review_conflict",
    "explicit_request",
    "recursion_cap_reached",
}
AUTO_CHECK_OBSERVED_KEYS = {
    "max_failure_signature_repeat",
    "validation_ledger_status",
    "artifact_status",
    "review_conflict",
    "explicit_request",
}
VALIDATION_LEDGER_STATUSES = {"present", "missing", "not_required"}
ARTIFACT_STATUSES = {"meaningful", "empty", "meaningless", "not_expected"}
AUTO_REVIEWER_CAP = 5
AUTO_RECURSION_CAP = 1


class AutoCheckError(ValueError):
    """A reasoned, user-facing automatic-trigger decision failure."""


DEFAULT_ROLES: dict[str, list[dict[str, Any]]] = {
    "swe": [
        {
            "name": "interface_reviewer",
            "objective": "Find missing or incorrectly exposed public interfaces, imports, exports, call signatures, and named paths.",
            "checklist": [
                "requested symbols",
                "import/export path",
                "constructor and method signature",
                "typing or schema compatibility",
                "backward-compatible wrapper needs",
            ],
        },
        {
            "name": "regression_reviewer",
            "objective": "Find existing behavior, edge cases, and local invariants that the patch could accidentally break.",
            "checklist": [
                "existing callers",
                "adjacent tests",
                "default behavior",
                "error handling",
                "data migration or compatibility",
            ],
        },
        {
            "name": "validation_reviewer",
            "objective": "Find the smallest credible validation commands and identify gaps between self-selected checks and benchmark checks.",
            "checklist": [
                "focused test command",
                "adjacent compatibility command",
                "container execution",
                "unrelated infrastructure blockers",
                "validation ledger completeness",
            ],
        },
        {
            "name": "minimality_reviewer",
            "objective": "Find broad unrelated rewrites, unclosed semantic clone families, parallel maintenance paths, formatting churn, test edits, or patches not tied to the stated requirement.",
            "checklist": [
                "diff scope",
                "bounded pre/post abstraction and clone search",
                "codebase-wide closure of each confirmed family",
                "migration or evidence-backed exclusions",
                "before/after independent maintenance paths",
                "temporary artifacts",
                "test and fixture edits",
                "style-only churn",
            ],
        },
    ],
    "legal": [
        {
            "name": "coverage_reviewer",
            "objective": "Find omitted task requirements, requested deliverables, facts, authority, and output-format elements.",
            "checklist": [
                "instructions",
                "matter facts",
                "jurisdiction and authority",
                "playbook requirements",
                "requested output format",
                "citations and caveats",
            ],
        },
        {
            "name": "draft_architecture_reviewer",
            "objective": "Review clause architecture, defined terms, cross-references, schedules, exhibits, and signature mechanics.",
            "checklist": [
                "section inventory",
                "defined terms",
                "cross-references",
                "thresholds and exceptions",
                "schedules and exhibits",
                "signature blocks",
            ],
        },
        {
            "name": "calculation_form_reviewer",
            "objective": "Review worksheets, numeric fields, dates, thresholds, units, formulas, and form completion logic.",
            "checklist": [
                "input extraction",
                "formula or governing rule",
                "units and periods",
                "field-by-field reconciliation",
                "rounding and threshold treatment",
            ],
        },
        {
            "name": "domain_specialist_reviewer",
            "objective": "Identify domain-specific legal issues that a generic contract or litigation pass may miss.",
            "checklist": [
                "practice area assumptions",
                "industry-specific terms",
                "regulatory hooks",
                "customary drafting conventions",
                "deal or dispute posture",
            ],
        },
        {
            "name": "adversarial_omission_reviewer",
            "objective": "Assume the draft is almost correct but one criterion is missing; find the most likely hidden miss.",
            "checklist": [
                "single omitted requirement",
                "ambiguous instruction",
                "silent exception",
                "missing fallback",
                "overbroad or unsupported statement",
            ],
        },
    ],
    "generic": [
        {
            "name": "coverage_reviewer",
            "objective": "Find omitted requirements, constraints, evidence, and output-format obligations.",
            "checklist": ["instructions", "constraints", "evidence", "format", "validation"],
        },
        {
            "name": "contradiction_reviewer",
            "objective": "Find internal contradictions, unsupported assumptions, and mutually exclusive actions.",
            "checklist": ["claims", "assumptions", "dependencies", "risks", "tradeoffs"],
        },
        {
            "name": "completion_reviewer",
            "objective": "Find what remains before the work can be called complete.",
            "checklist": ["open tasks", "verification", "artifacts", "handoff", "residual risk"],
        },
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_failure_signature(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip()).casefold()
    return re.sub(r"0x[0-9a-f]+|\d+", "<n>", normalized)


def max_failure_signature_repeat(signatures: list[str]) -> int:
    counts: dict[str, int] = {}
    for signature in signatures:
        normalized = normalize_failure_signature(signature)
        counts[normalized] = counts.get(normalized, 0) + 1
    return max(counts.values(), default=0)


def safe_artifact_path(value: Any) -> bool:
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\\" in value
        or ":" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return False
    path = Path(value)
    segments = value.split("/")
    return not path.is_absolute() and all(
        segment not in {"", ".", ".."} for segment in segments
    )


def canonical_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def validate_auto_check_input(state: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(state, dict):
        return ["auto-check state must be an object"]
    unknown = sorted(set(state) - AUTO_CHECK_INPUT_KEYS)
    missing = sorted(AUTO_CHECK_INPUT_KEYS - set(state))
    if unknown:
        errors.append("unknown keys: " + ", ".join(unknown))
    if missing:
        errors.append("missing keys: " + ", ".join(missing))
    if state.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    signatures = state.get("failure_signatures")
    if not isinstance(signatures, list):
        errors.append("failure_signatures must be a list")
    elif len(signatures) > 100:
        errors.append("failure_signatures cannot exceed 100 entries")
    elif not all(
        isinstance(item, str) and bool(item.strip()) and len(item) <= 512
        for item in signatures
    ):
        errors.append("failure_signatures entries must be non-empty strings up to 512 characters")
    if state.get("validation_ledger_status") not in VALIDATION_LEDGER_STATUSES:
        errors.append("validation_ledger_status is invalid")
    if state.get("artifact_status") not in ARTIFACT_STATUSES:
        errors.append("artifact_status is invalid")
    for field in ("review_conflict", "explicit_request"):
        if not isinstance(state.get(field), bool):
            errors.append(f"{field} must be boolean")
    reviewer_cap = state.get("reviewer_cap")
    if (
        not isinstance(reviewer_cap, int)
        or isinstance(reviewer_cap, bool)
        or not 1 <= reviewer_cap <= AUTO_REVIEWER_CAP
    ):
        errors.append(f"reviewer_cap must be an integer from 1 to {AUTO_REVIEWER_CAP}")
    recursion_depth = state.get("recursion_depth")
    if (
        not isinstance(recursion_depth, int)
        or isinstance(recursion_depth, bool)
        or recursion_depth < 0
    ):
        errors.append("recursion_depth must be a non-negative integer")
    if not safe_artifact_path(state.get("artifact_path")):
        errors.append("artifact_path must be a safe repository-relative path")
    return errors


def evaluate_auto_check(state: Any) -> dict[str, Any]:
    errors = validate_auto_check_input(state)
    if errors:
        raise AutoCheckError("; ".join(errors))
    assert isinstance(state, dict)
    signatures = state["failure_signatures"]
    repeat_count = max_failure_signature_repeat(signatures)
    reasons: list[str] = []
    if repeat_count >= 3:
        reasons.append("repeated_failure_signature")
    if state["validation_ledger_status"] == "missing":
        reasons.append("validation_ledger_missing")
    if state["artifact_status"] == "empty":
        reasons.append("empty_artifact")
    if state["artifact_status"] == "meaningless":
        reasons.append("meaningless_artifact")
    if state["review_conflict"]:
        reasons.append("review_conflict")
    if state["explicit_request"]:
        reasons.append("explicit_request")

    if reasons and state["recursion_depth"] >= AUTO_RECURSION_CAP:
        decision = "blocked"
        should_trigger = False
        reasons.append("recursion_cap_reached")
    elif reasons:
        decision = "trigger"
        should_trigger = True
    else:
        decision = "skip"
        should_trigger = False

    return {
        "schema_version": "1.0",
        "artifact_type": "fairy_fusion_trigger_decision",
        "decision": decision,
        "should_trigger": should_trigger,
        "reasons": reasons,
        "reviewer_cap": state["reviewer_cap"],
        "recursion_depth": state["recursion_depth"],
        "recursion_cap": AUTO_RECURSION_CAP,
        "artifact_path": state["artifact_path"],
        "automatic_execution": False,
        "input_sha256": canonical_sha256(state),
        "observed": {
            "max_failure_signature_repeat": repeat_count,
            "validation_ledger_status": state["validation_ledger_status"],
            "artifact_status": state["artifact_status"],
            "review_conflict": state["review_conflict"],
            "explicit_request": state["explicit_request"],
        },
    }


def validate_auto_check_decision(decision: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(decision, dict):
        return ["auto-check decision must be an object"]
    if set(decision) != AUTO_CHECK_DECISION_KEYS:
        errors.append("decision keys do not match the closed contract")
    if decision.get("schema_version") != "1.0":
        errors.append("decision schema_version must be 1.0")
    if decision.get("artifact_type") != "fairy_fusion_trigger_decision":
        errors.append("decision artifact_type is invalid")
    outcome = decision.get("decision")
    if outcome not in {"skip", "trigger", "blocked"}:
        errors.append("decision is invalid")
    reasons = decision.get("reasons")
    if not isinstance(reasons, list) or not all(reason in AUTO_CHECK_REASONS for reason in reasons):
        errors.append("decision reasons are invalid")
    elif len(reasons) != len(set(reasons)):
        errors.append("decision reasons must be unique")
    if outcome == "trigger" and decision.get("should_trigger") is not True:
        errors.append("trigger decisions must set should_trigger=true")
    if outcome != "trigger" and decision.get("should_trigger") is not False:
        errors.append("non-trigger decisions must set should_trigger=false")
    if outcome == "skip" and reasons:
        errors.append("skip decisions cannot carry trigger reasons")
    if outcome == "blocked" and (
        not isinstance(reasons, list)
        or len(reasons) < 2
        or "recursion_cap_reached" not in reasons
    ):
        errors.append("blocked decisions must record a trigger and recursion_cap_reached")
    if outcome != "blocked" and isinstance(reasons, list) and "recursion_cap_reached" in reasons:
        errors.append("only blocked decisions may record recursion_cap_reached")
    reviewer_cap = decision.get("reviewer_cap")
    if (
        not isinstance(reviewer_cap, int)
        or isinstance(reviewer_cap, bool)
        or not 1 <= reviewer_cap <= AUTO_REVIEWER_CAP
    ):
        errors.append("decision reviewer_cap is invalid")
    recursion_depth = decision.get("recursion_depth")
    if (
        not isinstance(recursion_depth, int)
        or isinstance(recursion_depth, bool)
        or recursion_depth < 0
    ):
        errors.append("decision recursion_depth is invalid")
    if (
        not isinstance(decision.get("recursion_cap"), int)
        or isinstance(decision.get("recursion_cap"), bool)
        or decision.get("recursion_cap") != AUTO_RECURSION_CAP
    ):
        errors.append("decision recursion_cap is invalid")
    if outcome == "trigger" and isinstance(recursion_depth, int) and recursion_depth >= AUTO_RECURSION_CAP:
        errors.append("trigger decisions must stay below the recursion cap")
    if (
        outcome == "blocked"
        and isinstance(recursion_depth, int)
        and recursion_depth < AUTO_RECURSION_CAP
    ):
        errors.append("blocked decisions must be at or above the recursion cap")
    if not safe_artifact_path(decision.get("artifact_path")):
        errors.append("decision artifact_path is invalid")
    if decision.get("automatic_execution") is not False:
        errors.append("auto-check cannot execute reviewers")
    if not isinstance(decision.get("input_sha256"), str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", decision["input_sha256"]
    ):
        errors.append("input_sha256 is invalid")
    observed = decision.get("observed")
    if not isinstance(observed, dict) or set(observed) != AUTO_CHECK_OBSERVED_KEYS:
        errors.append("decision observed values do not match the closed contract")
    else:
        repeat_count = observed.get("max_failure_signature_repeat")
        if (
            not isinstance(repeat_count, int)
            or isinstance(repeat_count, bool)
            or repeat_count < 0
        ):
            errors.append("observed max_failure_signature_repeat is invalid")
        if observed.get("validation_ledger_status") not in VALIDATION_LEDGER_STATUSES:
            errors.append("observed validation_ledger_status is invalid")
        if observed.get("artifact_status") not in ARTIFACT_STATUSES:
            errors.append("observed artifact_status is invalid")
        for field in ("review_conflict", "explicit_request"):
            if not isinstance(observed.get(field), bool):
                errors.append(f"observed {field} must be boolean")
    return errors


def load_auto_check_state(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AutoCheckError(f"cannot read auto-check state {path}: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AutoCheckError(f"invalid JSON in auto-check state {path}: {exc.msg}") from exc
    errors = validate_auto_check_input(payload)
    if errors:
        raise AutoCheckError("; ".join(errors))
    return payload


def auto_check_selftest() -> int:
    controls = 0

    def check(condition: bool, label: str) -> None:
        nonlocal controls
        controls += 1
        if not condition:
            raise AssertionError(label)

    base = {
        "schema_version": "1.0",
        "failure_signatures": [],
        "validation_ledger_status": "present",
        "artifact_status": "meaningful",
        "review_conflict": False,
        "explicit_request": False,
        "reviewer_cap": 3,
        "recursion_depth": 0,
        "artifact_path": "artifacts/fairy-fusion/review.json",
    }

    def evaluated(**updates: Any) -> dict[str, Any]:
        state = dict(base)
        state.update(updates)
        return evaluate_auto_check(state)

    clean = evaluated()
    check(clean["decision"] == "skip" and not clean["reasons"], "clean state skips")
    repeated = evaluated(
        failure_signatures=["Error code 41", " error   CODE 42 ", "ERROR code 43"]
    )
    check(
        repeated["decision"] == "trigger"
        and repeated["reasons"] == ["repeated_failure_signature"],
        "three normalized failure signatures trigger",
    )
    check(
        evaluated(failure_signatures=["same error", "same error"])["decision"] == "skip",
        "two repeated failures stay below the threshold",
    )
    check(
        evaluated(validation_ledger_status="missing")["reasons"]
        == ["validation_ledger_missing"],
        "missing validation ledger triggers",
    )
    check(
        evaluated(validation_ledger_status="not_required")["decision"] == "skip",
        "a reasoned not-required ledger does not false-trigger",
    )
    check(evaluated(artifact_status="empty")["reasons"] == ["empty_artifact"], "empty artifact triggers")
    check(
        evaluated(artifact_status="meaningless")["reasons"] == ["meaningless_artifact"],
        "meaningless artifact triggers",
    )
    check(
        evaluated(artifact_status="not_expected")["decision"] == "skip",
        "not-expected artifact does not false-trigger",
    )
    check(evaluated(review_conflict=True)["reasons"] == ["review_conflict"], "review conflict triggers")
    check(evaluated(explicit_request=True)["reasons"] == ["explicit_request"], "explicit request triggers")
    blocked = evaluated(validation_ledger_status="missing", recursion_depth=1)
    check(
        blocked["decision"] == "blocked"
        and not blocked["should_trigger"]
        and blocked["reasons"][-1] == "recursion_cap_reached",
        "one-level recursion cap blocks nested automatic fusion",
    )
    check(blocked["reviewer_cap"] == 3 and blocked["recursion_cap"] == 1, "caps remain explicit")
    check(blocked["artifact_path"] == base["artifact_path"], "artifact path remains explicit")
    check(not validate_auto_check_decision(clean), "generated skip decision is valid")
    check(not validate_auto_check_decision(repeated), "generated trigger decision is valid")
    check(not validate_auto_check_decision(blocked), "generated blocked decision is valid")
    malformed_decision = dict(repeated)
    malformed_decision["automatic_execution"] = True
    check(bool(validate_auto_check_decision(malformed_decision)), "execution claim fails closed")
    malformed_decision = dict(blocked)
    malformed_decision["reasons"] = ["recursion_cap_reached"]
    check(bool(validate_auto_check_decision(malformed_decision)), "blocked decision requires a trigger")

    invalid_states = [
        {**base, "unknown": True},
        {key: value for key, value in base.items() if key != "artifact_path"},
        {**base, "failure_signatures": "error"},
        {**base, "validation_ledger_status": "unknown"},
        {**base, "artifact_status": "unknown"},
        {**base, "review_conflict": 1},
        {**base, "reviewer_cap": 6},
        {**base, "recursion_depth": -1},
        {**base, "artifact_path": "../review.json"},
        {**base, "artifact_path": "artifacts/review\u0000.json"},
    ]
    for index, state in enumerate(invalid_states, start=1):
        try:
            evaluate_auto_check(state)
        except AutoCheckError:
            rejected = True
        else:
            rejected = False
        check(rejected, f"malformed state {index} fails closed")

    input_schema = json.loads(
        (ROOT / "schemas" / "fairy-fusion-auto-check-input.schema.json").read_text(encoding="utf-8")
    )
    decision_schema = json.loads(
        (ROOT / "schemas" / "fairy-fusion-trigger-decision.schema.json").read_text(encoding="utf-8")
    )
    check(set(input_schema["properties"]) == AUTO_CHECK_INPUT_KEYS, "input schema keys match runtime")
    check(set(input_schema["required"]) == AUTO_CHECK_INPUT_KEYS, "input schema requires every runtime key")
    input_properties = input_schema["properties"]
    check(
        set(input_properties["validation_ledger_status"]["enum"])
        == VALIDATION_LEDGER_STATUSES,
        "input ledger enum matches runtime",
    )
    check(
        set(input_properties["artifact_status"]["enum"]) == ARTIFACT_STATUSES,
        "input artifact enum matches runtime",
    )
    check(
        input_properties["reviewer_cap"]["maximum"] == AUTO_REVIEWER_CAP,
        "input reviewer cap matches runtime",
    )
    input_path_pattern = input_properties["artifact_path"]["pattern"]
    for path_value in (
        "artifacts/review.json",
        "",
        ".",
        "../review.json",
        "artifacts/../review.json",
        "artifacts//review.json",
        "artifacts\\review.json",
        "C:/review.json",
        "artifacts/review\u0000.json",
    ):
        check(
            bool(re.fullmatch(input_path_pattern, path_value)) == safe_artifact_path(path_value),
            f"input schema path policy matches runtime for {path_value!r}",
        )
    check(
        set(decision_schema["properties"]) == AUTO_CHECK_DECISION_KEYS,
        "decision schema keys match runtime",
    )
    check(
        set(decision_schema["required"]) == AUTO_CHECK_DECISION_KEYS,
        "decision schema requires every runtime key",
    )
    decision_properties = decision_schema["properties"]
    check(
        set(decision_properties["reasons"]["items"]["enum"]) == AUTO_CHECK_REASONS,
        "decision reason enum matches runtime",
    )
    check(
        decision_properties["reviewer_cap"]["maximum"] == AUTO_REVIEWER_CAP,
        "decision reviewer cap matches runtime",
    )
    check(
        decision_properties["recursion_cap"]["const"] == AUTO_RECURSION_CAP,
        "decision recursion cap matches runtime",
    )
    check(
        decision_properties["automatic_execution"]["const"] is False,
        "decision schema prohibits automatic execution",
    )
    print(f"fairy fusion auto-check selftest OK: {controls} controls")
    return 0


def load_task(args: argparse.Namespace) -> dict[str, Any]:
    if args.task_json:
        payload = json.loads(read_text(args.task_json))
        if not isinstance(payload, dict):
            raise ValueError("--task-json must contain a JSON object")
        return payload
    if args.prompt_file:
        return {"task": read_text(args.prompt_file)}
    if not sys.stdin.isatty():
        return {"task": sys.stdin.read()}
    raise ValueError("provide --task-json, --prompt-file, or stdin")


def load_roles(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.blind_panel:
        return [
            {
                "name": f"panelist_{index}",
                "mode": "blind_panel",
                "objective": "Answer the task directly and independently without a specialized role or lens.",
            }
            for index in range(1, args.max_reviewers + 1)
        ]
    if args.roles_file:
        payload = json.loads(read_text(args.roles_file))
        if isinstance(payload, dict):
            payload = payload.get("roles")
        if not isinstance(payload, list):
            raise ValueError("--roles-file must contain a role list or {'roles': [...]} object")
        roles = payload
    else:
        roles = DEFAULT_ROLES.get(args.domain, DEFAULT_ROLES["generic"])
    if not all(isinstance(role, dict) and isinstance(role.get("name"), str) for role in roles):
        raise ValueError("each role must be an object with a string 'name'")
    return roles[: args.max_reviewers]


def response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"].strip()
    parts: list[str] = []
    for item in response.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def retry_delay_seconds(headers: Any, attempt: int) -> float:
    retry_after = headers.get("Retry-After") if headers else None
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    return min(2.0**attempt, 30.0)


def call_openai(messages: list[dict[str, Any]], model: str, effort: str, timeout: int) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required when --execute is set")
    body: dict[str, Any] = {"model": model, "input": messages}
    if effort and effort != "none":
        body["reasoning"] = {"effort": effort}
    request_timeout = None if timeout <= 0 else timeout
    last_error: Exception | None = None
    for attempt in range(6):
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=request_timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"OpenAI API error {error.code}: {detail}")
            if error.code not in {408, 409, 425, 429} and error.code < 500:
                raise last_error from error
            if attempt == 5:
                raise last_error from error
            time.sleep(retry_delay_seconds(error.headers, attempt))
        except urllib.error.URLError as error:
            last_error = RuntimeError(f"OpenAI API transport error: {error.reason}")
            if attempt == 5:
                raise last_error from error
            time.sleep(retry_delay_seconds(None, attempt))
    if last_error:
        raise last_error
    raise RuntimeError("OpenAI API call failed without a captured error")


def parse_jsonish(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def reviewer_messages(task: dict[str, Any], role: dict[str, Any]) -> list[dict[str, Any]]:
    if role.get("mode") == "blind_panel":
        schema = {
            "role": role["name"],
            "answer": "direct answer or decision",
            "key_evidence": ["specific evidence or checks that support the answer"],
            "uncertainties": ["unknowns that could change the answer"],
            "possible_misses": ["requirements, edge cases, or contradictions to verify"],
            "confidence": "low | medium | high",
        }
        system = (
            "You are an isolated Fairy Fusion panelist. You receive the same task "
            "as every other panelist, but you cannot see their work. Do not adopt "
            "a persona or specialized lens. Solve the task directly, use only the "
            "supplied context, and return compact JSON matching the schema."
        )
        user = {
            "task_context": task,
            "required_output_schema": schema,
        }
        return [
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user, ensure_ascii=False)}]},
        ]

    schema = {
        "role": role["name"],
        "findings": ["specific supported findings"],
        "omissions": ["missing or weak items"],
        "contradictions": ["conflicts or incompatible assumptions"],
        "blind_spots": ["areas not answerable from the provided context"],
        "closure_actions": ["actionable changes before final output"],
        "confidence": "low | medium | high",
    }
    system = (
        "You are an isolated Fairy Fusion reviewer. You do not see any parent "
        "conversation. Review only the supplied task context and your role. "
        "Return compact JSON matching the requested schema."
    )
    user = {
        "reviewer_role": role,
        "task_context": task,
        "required_output_schema": schema,
    }
    return [
        {"role": "system", "content": [{"type": "input_text", "text": system}]},
        {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user, ensure_ascii=False)}]},
    ]


def synthesis_messages(task: dict[str, Any], reviewer_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schema = {
        "consensus": ["points supported by multiple reviewers"],
        "contradictions": ["conflicts that must be resolved"],
        "partial_coverage": ["requirements only partly handled"],
        "unique_insights": ["single-reviewer findings worth keeping"],
        "blind_spots": ["unknowns or unverified assumptions"],
        "final_closure_actions": ["required edits or checks before final"],
        "rejected_items": [{"item": "finding", "reason": "evidence-based rejection"}],
    }
    system = (
        "You are the Fairy Fusion synthesizer. Do not majority-vote away a "
        "minority risk. Compare independent reviewer outputs, preserve "
        "contradictions, identify blind spots, and return compact JSON."
    )
    user = {
        "task_context": task,
        "reviewer_outputs": reviewer_outputs,
        "required_output_schema": schema,
    }
    return [
        {"role": "system", "content": [{"type": "input_text", "text": system}]},
        {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user, ensure_ascii=False)}]},
    ]


def dry_run_payload(task: dict[str, Any], roles: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    return {
        "created_at": utc_now(),
        "mode": "dry_run",
        "domain": args.domain,
        "fusion_mode": "blind_panel" if args.blind_panel else "specialist_review",
        "reviewer_count": len(roles),
        "roles": roles,
        "recursion_cap": 1,
        "openrouter_dependency": False,
        "executor": "OpenAI Responses API only when --execute is set",
        "task_preview_chars": len(json.dumps(task, ensure_ascii=False)),
    }


def run_reviewer(task: dict[str, Any], role: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    started = time.time()
    messages = reviewer_messages(task, role)
    response = call_openai(messages, args.model, args.effort, args.timeout)
    text = response_text(response)
    return {
        "role": role["name"],
        "objective": role.get("objective"),
        "raw_text": text,
        "parsed": parse_jsonish(text),
        "response_id": response.get("id"),
        "elapsed_seconds": round(time.time() - started, 3),
    }


def execute(task: dict[str, Any], roles: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    depth = int(os.environ.get("FAIRY_FUSION_DEPTH", "0") or "0")
    if depth >= 1 and not args.allow_recursive:
        raise SystemExit("Fairy Fusion recursion cap reached")

    reviewer_outputs: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {pool.submit(run_reviewer, task, role, args): role["name"] for role in roles}
        for future in as_completed(future_map):
            role_name = future_map[future]
            try:
                reviewer_outputs.append(future.result())
            except Exception as error:
                reviewer_outputs.append(
                    {
                        "role": role_name,
                        "raw_text": "",
                        "parsed": None,
                        "error": str(error),
                        "elapsed_seconds": None,
                    }
                )
    reviewer_outputs.sort(key=lambda item: item["role"])

    started = time.time()
    synthesis_response = call_openai(
        synthesis_messages(task, reviewer_outputs),
        args.judge_model or args.model,
        args.effort,
        args.timeout,
    )
    synthesis_text = response_text(synthesis_response)
    return {
        "created_at": utc_now(),
        "mode": "executed",
        "domain": args.domain,
        "fusion_mode": "blind_panel" if args.blind_panel else "specialist_review",
        "reviewer_count": len(roles),
        "roles": [role["name"] for role in roles],
        "recursion_cap": 1,
        "openrouter_dependency": False,
        "model": args.model,
        "judge_model": args.judge_model or args.model,
        "reviewer_outputs": reviewer_outputs,
        "reviewer_error_count": sum(1 for output in reviewer_outputs if output.get("error")),
        "synthesis": {
            "raw_text": synthesis_text,
            "parsed": parse_jsonish(synthesis_text),
            "response_id": synthesis_response.get("id"),
            "elapsed_seconds": round(time.time() - started, 3),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auto-check", action="store_true")
    parser.add_argument("--state-json", type=Path)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--domain", default="generic", choices=sorted(DEFAULT_ROLES))
    parser.add_argument("--task-json", type=Path)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--roles-file", type=Path)
    parser.add_argument(
        "--blind-panel",
        action="store_true",
        help="Run identical independent panelists instead of role-specialized reviewers.",
    )
    parser.add_argument("--max-reviewers", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--timeout", type=int, default=0)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-recursive", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.selftest:
        if args.auto_check or args.state_json:
            print("ERROR --selftest cannot be combined with auto-check inputs", file=sys.stderr)
            return 2
        return auto_check_selftest()
    if args.auto_check:
        incompatible = any(
            (
                args.task_json,
                args.prompt_file,
                args.roles_file,
                args.blind_panel,
                args.execute,
                args.dry_run,
                args.allow_recursive,
                args.domain != "generic",
                args.max_reviewers != 5,
                args.workers != 4,
                args.model != "gpt-5.5",
                args.judge_model,
                args.effort != "medium",
                args.timeout != 0,
            )
        )
        if incompatible:
            print("ERROR --auto-check cannot be combined with reviewer execution inputs", file=sys.stderr)
            return 2
        if args.state_json is None:
            print("ERROR --auto-check requires --state-json", file=sys.stderr)
            return 2
        try:
            payload = evaluate_auto_check(load_auto_check_state(args.state_json))
        except AutoCheckError as exc:
            print(f"ERROR {exc}", file=sys.stderr)
            return 2
        decision_errors = validate_auto_check_decision(payload)
        if decision_errors:
            print("ERROR " + "; ".join(decision_errors), file=sys.stderr)
            return 2
        if args.output:
            try:
                write_json(args.output, payload)
            except (OSError, UnicodeError) as exc:
                print(f"ERROR cannot write auto-check decision {args.output}: {exc}", file=sys.stderr)
                return 2
        else:
            print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    if args.state_json is not None:
        print("ERROR --state-json requires --auto-check", file=sys.stderr)
        return 2
    task = load_task(args)
    roles = load_roles(args)
    if args.max_reviewers < 1:
        raise ValueError("--max-reviewers must be positive")
    if args.execute and args.dry_run:
        raise ValueError("choose either --execute or --dry-run")

    payload = execute(task, roles, args) if args.execute else dry_run_payload(task, roles, args)
    if args.output:
        write_json(args.output, payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
