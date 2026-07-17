#!/usr/bin/env python3
"""Validate and summarize measured Fairy Tale workflow impact.

The JSON scoreboard is canonical. Markdown is a derived review view. Example
runs are allowed for documentation but are excluded from measured aggregates
unless explicitly requested.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

try:
    from task_artifacts import (
        ArtifactError,
        canonical_artifact_path,
        has_text,
        load_json as load_json_file,
        repo_relative_path,
        require_distinct_paths,
        valid_id,
        write_text_atomic,
    )
except ImportError:  # pragma: no cover - module import from repository root
    from scripts.task_artifacts import (
        ArtifactError,
        canonical_artifact_path,
        has_text,
        load_json as load_json_file,
        repo_relative_path,
        require_distinct_paths,
        valid_id,
        write_text_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0"
DEFAULT_SCOREBOARD = ROOT / "examples" / "workflow-scoreboard.json"
SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RAW_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")

SCOREBOARD_KEYS = {
    "schema_version",
    "artifact_type",
    "scoreboard_id",
    "generated_at_utc",
    "source_refs",
    "entries",
    "routing_eval_bindings",
}
SOURCE_KEYS = {
    "source_id",
    "url",
    "checked_at",
    "source_type",
    "evidence_kind",
    "artifact_path",
    "artifact_sha256",
    "note",
}
ENTRY_KEYS = {
    "entry_id",
    "task_kind",
    "task_family",
    "task_id",
    "comparison_mode",
    "comparison_contract",
    "runs",
    "comparison_note",
}
CONTRACT_KEYS = {
    "model",
    "effort",
    "prompt_version",
    "scorer_version",
    "sample_ids",
    "max_output_tokens",
    "wall_clock_budget_seconds",
    "tool_budget",
    "budget_unavailable_reason",
    "retry_policy",
    "safety_policy",
}
RUN_KEYS = {
    "run_id",
    "condition",
    "source_kind",
    "isolation",
    "metrics",
    "regression",
    "artifact",
    "card_telemetry",
    "validation_evidence",
}
ISOLATION_KEYS = {"fresh_session", "skill_state", "note"}
METRIC_KEYS = {
    "pass_count",
    "total_count",
    "validation_result",
    "score",
    "score_unit",
    "score_unavailable_reason",
    "elapsed_seconds",
    "elapsed_unavailable_reason",
    "cost_usd",
    "cost_unavailable_reason",
    "tokens",
    "token_unavailable_reason",
}
TOKEN_KEYS = {
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "total_tokens",
}
REGRESSION_KEYS = {"status", "note"}
ARTIFACT_KEYS = {"kind", "source_ref", "path", "visibility", "disclosure", "sha256"}
TELEMETRY_KEYS = {
    "card_path",
    "fired_count",
    "contribution",
    "attributed_tokens",
    "token_unavailable_reason",
    "evidence_refs",
}
BINDING_KEYS = {"entry_id", "condition", "ledger_path", "ledger_sha256"}
ROUTING_LEDGER_IDENTITY_KEYS = {
    "model",
    "skill_md_sha256",
    "system_prompt_sha256",
    "cases_sha256",
    "repo_commit",
}
ROUTING_LEDGER_ARTIFACT_TYPE = "routing_eval_ledger"
ROUTING_LEDGER_CLASS_FIELDS = {"artifact_type"}
ROUTING_RESULT_MARKERS = {
    "expected_cards",
    "extra_cards",
    "got_cards",
    "invalid_paths",
    "missing_cards",
    "overfire",
    "underfire",
}
ROUTING_SUMMARY_MARKERS = {
    "invalid_card_path",
    "invalid_output",
    "invalid_path_outputs",
    "overfire",
    "per_card_utilization",
    "scope_gate_54_regression",
    "underfire",
}
ROUTING_LEDGER_GENERIC_FIELDS = {
    "claude_cli_version",
    "command",
    "eval_inputs_committed_at_repo_commit",
    "generated_at_utc",
    "isolation",
    "issue",
    "model",
    "repo_commit",
    "results",
    "run_policy",
    "schema_version",
    "skill_md_sha256",
    "summary",
    "system_prompt_sha256",
    "cases_sha256",
    "token_note",
}
ROUTING_RESULT_GENERIC_FIELDS = {
    "category",
    "classification",
    "cost_usd",
    "exit_code",
    "id",
    "parse_error",
    "pass",
    "tokens",
}
ROUTING_SUMMARY_GENERIC_FIELDS = {"accuracy", "passed", "per_category", "total"}

COMPARISON_MODES = {"paired_local", "paired_external_baseline", "unpaired"}
TASK_KINDS = {"benchmark", "normal"}
SOURCE_KINDS = {"measured_local", "official_external", "example"}
CONDITIONS = {"baseline", "fairy_tale"}
VALIDATION_RESULTS = {"pass", "fail"}
CONTRIBUTIONS = {"helpful", "neutral", "harmful", "unknown"}
ARTIFACT_KINDS = {"run_output", "example", "routing_eval_ledger"}
SOURCE_EVIDENCE_KINDS = {"context", "example_run", "measured_run", "official_run"}
SOURCE_KIND_TO_EVIDENCE_KIND = {
    "example": "example_run",
    "measured_local": "measured_run",
    "official_external": "official_run",
}


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def enum_member(value: Any, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def valid_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def valid_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or "T" not in value or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def add(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def object_shape(
    value: Any,
    *,
    path: str,
    keys: set[str],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        add(errors, path, "must be an object")
        return None
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing:
        add(errors, path, "missing keys: " + ", ".join(missing))
    if extra:
        add(errors, path, "unknown keys: " + ", ".join(extra))
    return value


def text_list(value: Any, *, path: str, errors: list[str], nonempty: bool = True) -> None:
    if not isinstance(value, list) or (nonempty and not value) or not all(has_text(item) for item in value):
        add(errors, path, "must be a list of non-empty strings" + (" with at least one item" if nonempty else ""))


def validate_source(value: Any, index: int, errors: list[str]) -> None:
    path = f"source_refs[{index}]"
    source = object_shape(value, path=path, keys=SOURCE_KEYS, errors=errors)
    if source is None:
        return
    if not valid_id(source.get("source_id")):
        add(errors, f"{path}.source_id", "must be a portable identifier")
    parsed_url = urlparse(source.get("url") if isinstance(source.get("url"), str) else "")
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        add(errors, f"{path}.url", "must be an HTTPS URL")
    if not valid_date(source.get("checked_at")):
        add(errors, f"{path}.checked_at", "must be an ISO calendar date")
    source_type = source.get("source_type")
    evidence_kind = source.get("evidence_kind")
    if not enum_member(source_type, {"official", "repository", "public_report"}):
        add(errors, f"{path}.source_type", "must be official, repository, or public_report")
    if not enum_member(evidence_kind, SOURCE_EVIDENCE_KINDS):
        add(errors, f"{path}.evidence_kind", "must be context, example_run, measured_run, or official_run")
    artifact_path = source.get("artifact_path")
    artifact_sha256 = source.get("artifact_sha256")
    if evidence_kind == "context":
        if artifact_path is not None or artifact_sha256 is not None:
            add(errors, path, "context sources cannot bind a run artifact")
    elif enum_member(evidence_kind, SOURCE_EVIDENCE_KINDS - {"context"}):
        if not repo_relative_path(artifact_path):
            add(errors, f"{path}.artifact_path", "must be a portable repository-relative path")
        if not isinstance(artifact_sha256, str) or not SHA_RE.fullmatch(artifact_sha256):
            add(errors, f"{path}.artifact_sha256", "must be a lowercase sha256 digest")
    expected_source_type = (
        {
            "example_run": "repository",
            "measured_run": "repository",
            "official_run": "official",
        }.get(evidence_kind)
        if isinstance(evidence_kind, str)
        else None
    )
    if expected_source_type is not None and source_type != expected_source_type:
        add(errors, f"{path}.source_type", f"must be {expected_source_type} for {evidence_kind}")
    if not has_text(source.get("note")):
        add(errors, f"{path}.note", "must be non-empty")


def validate_contract(value: Any, path: str, errors: list[str]) -> None:
    contract = object_shape(value, path=path, keys=CONTRACT_KEYS, errors=errors)
    if contract is None:
        return
    for key in {"model", "effort", "prompt_version", "scorer_version", "retry_policy", "safety_policy"}:
        if not has_text(contract.get(key)):
            add(errors, f"{path}.{key}", "must be non-empty")
    text_list(contract.get("sample_ids"), path=f"{path}.sample_ids", errors=errors)
    sample_ids = contract.get("sample_ids")
    if (
        isinstance(sample_ids, list)
        and all(has_text(item) for item in sample_ids)
        and len(sample_ids) != len(set(sample_ids))
    ):
        add(errors, f"{path}.sample_ids", "must be unique")
    budget_values = [contract.get(key) for key in ("max_output_tokens", "wall_clock_budget_seconds", "tool_budget")]
    for key, value_item in zip(("max_output_tokens", "wall_clock_budget_seconds", "tool_budget"), budget_values):
        minimum = 0 if key == "tool_budget" else 1
        if value_item is not None and (
            not isinstance(value_item, int)
            or isinstance(value_item, bool)
            or value_item < minimum
        ):
            qualifier = "non-negative" if minimum == 0 else "positive"
            add(errors, f"{path}.{key}", f"must be null or a {qualifier} integer")
    if any(item is None for item in budget_values):
        if not has_text(contract.get("budget_unavailable_reason")):
            add(errors, f"{path}.budget_unavailable_reason", "is required when any budget is unavailable")
    elif contract.get("budget_unavailable_reason") is not None:
        add(errors, f"{path}.budget_unavailable_reason", "must be null when all budgets are recorded")


def validate_tokens(value: Any, path: str, unavailable_reason: Any, errors: list[str]) -> None:
    tokens = object_shape(value, path=path, keys=TOKEN_KEYS, errors=errors)
    if tokens is None:
        return
    values = [tokens.get(key) for key in TOKEN_KEYS]
    all_null = all(item is None for item in values)
    all_int = all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in values)
    if not (all_null or all_int):
        add(errors, path, "token fields must be all null or all non-negative integers")
        return
    if all_null:
        if not has_text(unavailable_reason):
            add(errors, path, "requires token_unavailable_reason when token counts are unavailable")
        return
    if unavailable_reason is not None:
        add(errors, path, "token_unavailable_reason must be null when counts are recorded")
    subtotal = sum(tokens[key] for key in TOKEN_KEYS if key != "total_tokens")
    if tokens.get("total_tokens") != subtotal:
        add(errors, f"{path}.total_tokens", f"must equal component sum {subtotal}")


def validate_metrics(value: Any, path: str, errors: list[str]) -> None:
    metrics = object_shape(value, path=path, keys=METRIC_KEYS, errors=errors)
    if metrics is None:
        return
    passes = metrics.get("pass_count")
    total = metrics.get("total_count")
    if not isinstance(total, int) or isinstance(total, bool) or total < 1:
        add(errors, f"{path}.total_count", "must be a positive integer")
    if not isinstance(passes, int) or isinstance(passes, bool) or passes < 0 or (isinstance(total, int) and passes > total):
        add(errors, f"{path}.pass_count", "must be an integer between zero and total_count")
    expected_result = "pass" if isinstance(passes, int) and passes == total else "fail"
    if not enum_member(metrics.get("validation_result"), VALIDATION_RESULTS):
        add(errors, f"{path}.validation_result", "must be pass or fail")
    elif metrics["validation_result"] != expected_result:
        add(errors, f"{path}.validation_result", f"must be {expected_result} for the recorded counts")
    for key, reason_key in (
        ("score", "score_unavailable_reason"),
        ("elapsed_seconds", "elapsed_unavailable_reason"),
        ("cost_usd", "cost_unavailable_reason"),
    ):
        number = metrics.get(key)
        reason = metrics.get(reason_key)
        if number is None:
            if not has_text(reason):
                add(errors, f"{path}.{reason_key}", f"is required when {key} is unavailable")
        elif not finite_number(number) or number < 0:
            add(errors, f"{path}.{key}", "must be null or a non-negative finite number")
        elif reason is not None:
            add(errors, f"{path}.{reason_key}", f"must be null when {key} is recorded")
    if metrics.get("score") is not None and not has_text(metrics.get("score_unit")):
        add(errors, f"{path}.score_unit", "is required when score is recorded")
    if metrics.get("score") is None and metrics.get("score_unit") is not None:
        add(errors, f"{path}.score_unit", "must be null when score is unavailable")
    validate_tokens(metrics.get("tokens"), f"{path}.tokens", metrics.get("token_unavailable_reason"), errors)


def resolve_repository_artifact(value: dict[str, Any], path: str, errors: list[str]) -> Path | None:
    stored_path = value.get("path")
    if not repo_relative_path(stored_path):
        add(errors, f"{path}.path", "must be a portable repository-relative path")
        return None
    try:
        resolved = canonical_artifact_path(ROOT / stored_path, "scoreboard artifact")
    except ArtifactError as exc:
        add(errors, f"{path}.path", str(exc))
        return None
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        add(errors, f"{path}.path", "must remain inside the repository")
        return None
    return resolved


def validate_artifact(value: Any, path: str, errors: list[str]) -> Path | None:
    artifact = object_shape(value, path=path, keys=ARTIFACT_KEYS, errors=errors)
    if artifact is None:
        return None
    if not valid_id(artifact.get("source_ref")):
        add(errors, f"{path}.source_ref", "must be a portable source identifier")
    visibility = artifact.get("visibility")
    disclosure = artifact.get("disclosure")
    if not enum_member(artifact.get("kind"), ARTIFACT_KINDS):
        add(errors, f"{path}.kind", "must be run_output, example, or routing_eval_ledger")
    if not enum_member(visibility, {"repository", "private", "local"}):
        add(errors, f"{path}.visibility", "must be repository, private, or local")
    if not enum_member(disclosure, {"full", "redacted"}):
        add(errors, f"{path}.disclosure", "must be full or redacted")
    digest = artifact.get("sha256")
    if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
        add(errors, f"{path}.sha256", "must be a lowercase sha256 digest")
    if visibility == "repository":
        if disclosure != "full":
            add(errors, f"{path}.disclosure", "repository artifacts must use full disclosure")
        resolved = resolve_repository_artifact(artifact, path, errors)
        if resolved is not None and isinstance(digest, str) and SHA_RE.fullmatch(digest):
            actual = sha256_file(resolved)
            if digest != actual:
                add(errors, f"{path}.sha256", f"does not match {artifact.get('path')}: {actual}")
        return resolved
    elif enum_member(visibility, {"private", "local"}):
        if disclosure != "redacted":
            add(errors, f"{path}.disclosure", "private/local artifacts must be redacted")
        stored_path = artifact.get("path")
        if not has_text(stored_path) or not stored_path.startswith("redacted/") or not repo_relative_path(stored_path):
            add(errors, f"{path}.path", "private/local paths must use a portable redacted/... locator")
    return None


def validate_telemetry(value: Any, path: str, condition: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        add(errors, path, "must be a list")
        return
    if condition == "baseline" and value:
        add(errors, path, "baseline runs cannot claim Fairy Tale card utilization")
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item_path = f"{path}[{index}]"
        item = object_shape(raw, path=item_path, keys=TELEMETRY_KEYS, errors=errors)
        if item is None:
            continue
        card_path = item.get("card_path")
        if not repo_relative_path(card_path) or not str(card_path).startswith("references/cards/"):
            add(errors, f"{item_path}.card_path", "must be relative to skills/fairy-tale and under references/cards")
        elif not (ROOT / "skills" / "fairy-tale" / card_path).is_file():
            add(errors, f"{item_path}.card_path", "does not exist in the canonical skill")
        if isinstance(card_path, str):
            if card_path in seen:
                add(errors, f"{item_path}.card_path", "duplicate card telemetry")
            seen.add(card_path)
        count = item.get("fired_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            add(errors, f"{item_path}.fired_count", "must be a positive integer")
        if not enum_member(item.get("contribution"), CONTRIBUTIONS):
            add(errors, f"{item_path}.contribution", "must be helpful, neutral, harmful, or unknown")
        tokens = item.get("attributed_tokens")
        reason = item.get("token_unavailable_reason")
        if tokens is None:
            if not has_text(reason):
                add(errors, f"{item_path}.token_unavailable_reason", "is required when attributed tokens are unavailable")
        elif not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
            add(errors, f"{item_path}.attributed_tokens", "must be null or a non-negative integer")
        elif reason is not None:
            add(errors, f"{item_path}.token_unavailable_reason", "must be null when attributed tokens are recorded")
        text_list(item.get("evidence_refs"), path=f"{item_path}.evidence_refs", errors=errors)


def is_routing_eval_ledger(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    results = value.get("results")
    summary = value.get("summary")
    if not isinstance(results, list) or not isinstance(summary, dict):
        return False
    top_level_signal = value.get("artifact_type") == ROUTING_LEDGER_ARTIFACT_TYPE
    result_signal = any(
        isinstance(result, dict) and bool(ROUTING_RESULT_MARKERS & set(result))
        for result in results
    )
    summary_signal = bool(ROUTING_SUMMARY_MARKERS & set(summary))
    return sum((top_level_signal, result_signal, summary_signal)) >= 2


def validate_artifact_source(
    artifact: dict[str, Any],
    source_kind: Any,
    sources: dict[str, dict[str, Any]],
    path: str,
    errors: list[str],
) -> None:
    source_ref = artifact.get("source_ref")
    if not valid_id(source_ref):
        return
    source = sources.get(source_ref)
    if source is None:
        add(errors, f"{path}.source_ref", "must reference a declared source")
        return
    expected_evidence_kind = (
        SOURCE_KIND_TO_EVIDENCE_KIND.get(source_kind)
        if isinstance(source_kind, str)
        else None
    )
    if expected_evidence_kind is not None and source.get("evidence_kind") != expected_evidence_kind:
        add(
            errors,
            f"{path}.source_ref",
            f"must reference {expected_evidence_kind} provenance for source_kind {source_kind}",
        )
    if source.get("artifact_path") != artifact.get("path"):
        add(errors, f"{path}.path", "must match the bound source artifact path")
    if source.get("artifact_sha256") != artifact.get("sha256"):
        add(errors, f"{path}.sha256", "must match the bound source artifact hash")


def validate_run(
    value: Any,
    path: str,
    task_kind: Any,
    sources: dict[str, dict[str, Any]],
    errors: list[str],
) -> bool:
    run = object_shape(value, path=path, keys=RUN_KEYS, errors=errors)
    if run is None:
        return False
    if not valid_id(run.get("run_id")):
        add(errors, f"{path}.run_id", "must be a portable identifier")
    condition = run.get("condition")
    condition_valid = enum_member(condition, CONDITIONS)
    if not condition_valid:
        add(errors, f"{path}.condition", "must be baseline or fairy_tale")
    source_kind = run.get("source_kind")
    source_kind_valid = enum_member(source_kind, SOURCE_KINDS)
    if not source_kind_valid:
        add(errors, f"{path}.source_kind", "must be measured_local, official_external, or example")
    isolation = object_shape(run.get("isolation"), path=f"{path}.isolation", keys=ISOLATION_KEYS, errors=errors)
    if isolation is not None:
        if not isinstance(isolation.get("fresh_session"), bool):
            add(errors, f"{path}.isolation.fresh_session", "must be boolean")
        expected_state = "disabled" if condition == "baseline" else "enabled"
        skill_state = isolation.get("skill_state")
        skill_state_valid = enum_member(skill_state, {"disabled", "enabled", "external", "not_applicable"})
        if not skill_state_valid:
            add(errors, f"{path}.isolation.skill_state", "invalid skill state")
        elif condition_valid and source_kind_valid and source_kind != "official_external" and skill_state != expected_state:
            add(errors, f"{path}.isolation.skill_state", f"must be {expected_state} for this condition")
        if not has_text(isolation.get("note")):
            add(errors, f"{path}.isolation.note", "must be non-empty")
    validate_metrics(run.get("metrics"), f"{path}.metrics", errors)
    regression = object_shape(run.get("regression"), path=f"{path}.regression", keys=REGRESSION_KEYS, errors=errors)
    if regression is not None:
        if not enum_member(regression.get("status"), {"none", "observed", "unknown"}):
            add(errors, f"{path}.regression.status", "must be none, observed, or unknown")
        if not has_text(regression.get("note")):
            add(errors, f"{path}.regression.note", "must be non-empty")
    resolved_artifact = validate_artifact(run.get("artifact"), f"{path}.artifact", errors)
    artifact = run.get("artifact") if isinstance(run.get("artifact"), dict) else {}
    validate_artifact_source(artifact, source_kind, sources, f"{path}.artifact", errors)
    validate_telemetry(run.get("card_telemetry"), f"{path}.card_telemetry", condition, errors)
    text_list(run.get("validation_evidence"), path=f"{path}.validation_evidence", errors=errors)
    telemetry = run.get("card_telemetry")
    metrics = run.get("metrics")
    if isinstance(telemetry, list) and isinstance(metrics, dict):
        attributed = [
            item.get("attributed_tokens")
            for item in telemetry
            if (
                isinstance(item, dict)
                and isinstance(item.get("attributed_tokens"), int)
                and not isinstance(item.get("attributed_tokens"), bool)
                and item.get("attributed_tokens") >= 0
            )
        ]
        total_tokens = metrics.get("tokens", {}).get("total_tokens") if isinstance(metrics.get("tokens"), dict) else None
        if (
            attributed
            and isinstance(total_tokens, int)
            and not isinstance(total_tokens, bool)
            and total_tokens >= 0
            and sum(attributed) > total_tokens
        ):
            add(errors, f"{path}.card_telemetry", "attributed tokens cannot exceed total run tokens")
    artifact_kind = artifact.get("kind")
    artifact_payload: Any = None
    if artifact.get("visibility") == "repository" and resolved_artifact is not None:
        try:
            artifact_payload = load_json_file(resolved_artifact)
        except ArtifactError as exc:
            if source_kind == "example":
                add(errors, f"{path}.artifact", str(exc))
    routing_ledger = is_routing_eval_ledger(artifact_payload)
    if artifact_kind == "routing_eval_ledger":
        if artifact.get("visibility") != "repository" or resolved_artifact is None:
            add(errors, f"{path}.artifact.kind", "routing_eval_ledger requires a repository artifact")
        elif not routing_ledger:
            add(errors, f"{path}.artifact.kind", "routing_eval_ledger content contract is missing")
    elif routing_ledger:
        add(errors, f"{path}.artifact.kind", "routing ledger content must use kind routing_eval_ledger")
    if routing_ledger:
        try:
            routing_expected(artifact_payload)
        except ArtifactError as exc:
            add(errors, f"{path}.artifact", str(exc))
    if source_kind == "example":
        if artifact_kind != "example":
            add(errors, f"{path}.artifact.kind", "example runs require artifact kind example")
        if artifact.get("visibility") != "repository" or resolved_artifact is None:
            add(errors, f"{path}.artifact", "example runs require a repository artifact")
        elif artifact_payload is not None:
            expected = {
                "example": True,
                "condition": condition,
                "task_kind": task_kind,
            }
            if not isinstance(artifact_payload, dict) or any(
                artifact_payload.get(key) != item for key, item in expected.items()
            ):
                add(errors, f"{path}.artifact", "example marker, condition, and task kind must match the run")
    elif (
        enum_member(source_kind, SOURCE_KINDS)
        and (
            artifact_kind == "example"
            or (isinstance(artifact_payload, dict) and artifact_payload.get("example") is True)
        )
    ):
        add(errors, f"{path}.source_kind", "artifacts declared or marked as examples must use source_kind example")
    return artifact_kind == "routing_eval_ledger" or routing_ledger


def validate_entry(
    value: Any,
    index: int,
    sources: dict[str, dict[str, Any]],
    errors: list[str],
) -> list[str]:
    path = f"entries[{index}]"
    entry = object_shape(value, path=path, keys=ENTRY_KEYS, errors=errors)
    if entry is None:
        return []
    for key in ("entry_id", "task_id"):
        if not valid_id(entry.get(key)):
            add(errors, f"{path}.{key}", "must be a portable identifier")
    if not enum_member(entry.get("task_kind"), TASK_KINDS):
        add(errors, f"{path}.task_kind", "must be benchmark or normal")
    if not has_text(entry.get("task_family")):
        add(errors, f"{path}.task_family", "must be non-empty")
    mode = entry.get("comparison_mode")
    mode_valid = enum_member(mode, COMPARISON_MODES)
    if not mode_valid:
        add(errors, f"{path}.comparison_mode", "invalid comparison mode")
    if not has_text(entry.get("comparison_note")):
        add(errors, f"{path}.comparison_note", "must be non-empty")
    validate_contract(entry.get("comparison_contract"), f"{path}.comparison_contract", errors)
    runs = entry.get("runs")
    if not isinstance(runs, list) or not runs:
        add(errors, f"{path}.runs", "must be a non-empty list")
        return []
    routing_conditions: list[str] = []
    for run_index, run in enumerate(runs):
        routing_ledger = validate_run(
            run,
            f"{path}.runs[{run_index}]",
            entry.get("task_kind"),
            sources,
            errors,
        )
        if routing_ledger and isinstance(run, dict) and enum_member(run.get("condition"), CONDITIONS):
            routing_conditions.append(run["condition"])
    conditions = [
        run.get("condition")
        for run in runs
        if isinstance(run, dict) and enum_member(run.get("condition"), CONDITIONS)
    ]
    if len(conditions) != len(set(conditions)):
        add(errors, f"{path}.runs", "conditions must be unique")
    if mode == "unpaired" and len(runs) != 1:
        add(errors, f"{path}.runs", "unpaired entries require exactly one run")
    if enum_member(mode, {"paired_local", "paired_external_baseline"}) and set(conditions) != CONDITIONS:
        add(errors, f"{path}.runs", "paired entries require one baseline and one fairy_tale run")
    if mode == "paired_local" and any(run.get("source_kind") == "official_external" for run in runs if isinstance(run, dict)):
        add(errors, f"{path}.runs", "paired_local cannot use an official external run")
    if mode == "paired_local":
        source_kinds = {
            run.get("source_kind")
            for run in runs
            if isinstance(run, dict) and enum_member(run.get("source_kind"), SOURCE_KINDS)
        }
        if source_kinds not in ({"measured_local"}, {"example"}):
            add(errors, f"{path}.runs", "paired_local runs must both be measured_local or both be examples")
    if mode == "paired_external_baseline":
        baseline = next((run for run in runs if isinstance(run, dict) and run.get("condition") == "baseline"), {})
        fairy = next((run for run in runs if isinstance(run, dict) and run.get("condition") == "fairy_tale"), {})
        if baseline.get("source_kind") != "official_external":
            add(errors, f"{path}.runs", "paired_external_baseline requires an official external baseline")
        if fairy.get("source_kind") != "measured_local":
            add(errors, f"{path}.runs", "paired_external_baseline requires a measured_local Fairy Tale run")
    if enum_member(mode, {"paired_local", "paired_external_baseline"}):
        artifact_paths = [
            run.get("artifact", {}).get("path")
            for run in runs
            if isinstance(run, dict) and isinstance(run.get("artifact"), dict)
        ]
        if len(artifact_paths) == 2 and all(repo_relative_path(item) for item in artifact_paths):
            try:
                require_distinct_paths(
                    ROOT / artifact_paths[0],
                    ROOT / artifact_paths[1],
                    "paired runs must use distinct artifacts",
                )
            except ArtifactError as exc:
                add(errors, f"{path}.runs", str(exc))
        for run_index, run in enumerate(runs):
            if (
                isinstance(run, dict)
                and run.get("source_kind") != "official_external"
                and isinstance(run.get("isolation"), dict)
                and run["isolation"].get("fresh_session") is not True
            ):
                add(errors, f"{path}.runs[{run_index}].isolation.fresh_session", "paired local runs require a fresh session")
            if isinstance(run, dict) and run.get("source_kind") == "measured_local":
                metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else None
                tokens = metrics.get("tokens") if isinstance(metrics, dict) else None
                if (
                    not isinstance(metrics, dict)
                    or metrics.get("elapsed_seconds") is None
                    or metrics.get("cost_usd") is None
                    or not isinstance(tokens, dict)
                    or tokens.get("total_tokens") is None
                ):
                    add(errors, f"{path}.runs[{run_index}].metrics", "measured paired runs require elapsed, cost, and token totals")
    return routing_conditions


def routing_expected(ledger: dict[str, Any]) -> dict[str, Any]:
    if ledger.get("artifact_type") != ROUTING_LEDGER_ARTIFACT_TYPE:
        raise ArtifactError("routing ledger artifact_type must be routing_eval_ledger")
    results = ledger.get("results")
    summary = ledger.get("summary")
    if not isinstance(results, list) or not isinstance(summary, dict):
        raise ArtifactError("routing ledger must contain results and summary")
    if not has_text(ledger.get("model")):
        raise ArtifactError("routing ledger model must be non-empty")
    for key in ("skill_md_sha256", "system_prompt_sha256", "cases_sha256"):
        value = ledger.get(key)
        if not isinstance(value, str) or not RAW_SHA256_RE.fullmatch(value):
            raise ArtifactError(f"routing ledger {key} must be a lowercase 64-hex SHA-256")
    repo_commit = ledger.get("repo_commit")
    if not isinstance(repo_commit, str) or not COMMIT_RE.fullmatch(repo_commit):
        raise ArtifactError("routing ledger repo_commit must be a pinned lowercase commit identity")
    token_keys = {
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "cache_creation_input_tokens": "cache_creation_input_tokens",
        "cache_read_input_tokens": "cache_read_input_tokens",
    }
    tokens = {target: 0 for target in token_keys.values()}
    cost = 0.0
    passed = 0
    utilization: dict[str, int] = {}
    sample_ids: list[str] = []
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ArtifactError(f"routing ledger result {index} must be an object")
        sample_id = result.get("id")
        if not has_text(sample_id) or sample_id in sample_ids:
            raise ArtifactError(f"routing ledger result {index} has an invalid or duplicate id")
        sample_ids.append(sample_id)
        if not isinstance(result.get("pass"), bool):
            raise ArtifactError(f"routing ledger result {index} has an invalid pass flag")
        passed += int(result["pass"])
        usage = result.get("tokens")
        if not isinstance(usage, dict) or not finite_number(result.get("cost_usd")):
            raise ArtifactError(f"routing ledger result {index} lacks measured cost/tokens")
        for source, target in token_keys.items():
            value = usage.get(source)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ArtifactError(f"routing ledger result {index} has invalid {source}")
            tokens[target] += value
        cost += float(result["cost_usd"])
        got_cards = result.get("got_cards")
        invalid_paths = result.get("invalid_paths")
        if got_cards is None:
            got_cards = []
        if invalid_paths is None:
            invalid_paths = []
        if not isinstance(got_cards, list) or not all(has_text(card) for card in got_cards):
            raise ArtifactError(f"routing ledger result {index} has invalid got_cards")
        if not isinstance(invalid_paths, list) or not all(has_text(card) for card in invalid_paths):
            raise ArtifactError(f"routing ledger result {index} has invalid invalid_paths")
        invalid = set(invalid_paths)
        for card in got_cards:
            if card not in invalid:
                utilization[card] = utilization.get(card, 0) + 1
    tokens["total_tokens"] = sum(tokens.values())
    utilization = dict(sorted(utilization.items()))
    total = len(results)
    accuracy = round(passed / total, 4) if total else None
    expected_summary = {
        "total": total,
        "passed": passed,
        "accuracy": accuracy,
        "per_card_utilization": utilization,
    }
    for key, expected_value in expected_summary.items():
        if summary.get(key) != expected_value:
            raise ArtifactError(f"routing ledger summary {key} does not match result rows")
    prompt_version = (
        f"skill_sha256:{ledger['skill_md_sha256']};"
        f"system_prompt_sha256:{ledger['system_prompt_sha256']};"
        f"cases_sha256:{ledger['cases_sha256']}"
    )
    return {
        "pass_count": passed,
        "total_count": total,
        "score": accuracy,
        "cost_usd": cost,
        "tokens": tokens,
        "utilization": utilization,
        "sample_ids": sample_ids,
        "model": ledger["model"],
        "prompt_version": prompt_version,
        "scorer_version": f"scripts/routing_eval.py@{repo_commit}",
    }


def validate_routing_binding(
    value: Any,
    index: int,
    entries: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    path = f"routing_eval_bindings[{index}]"
    binding = object_shape(value, path=path, keys=BINDING_KEYS, errors=errors)
    if binding is None:
        return
    condition = binding.get("condition")
    condition_valid = enum_member(condition, CONDITIONS)
    if not condition_valid:
        add(errors, f"{path}.condition", "must be baseline or fairy_tale")
    entry_id = binding.get("entry_id")
    entry_id_valid = valid_id(entry_id)
    if not entry_id_valid:
        add(errors, f"{path}.entry_id", "must be a portable identifier")
    digest = binding.get("ledger_sha256")
    if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
        add(errors, f"{path}.ledger_sha256", "must be a lowercase sha256 digest")
    ledger_path = binding.get("ledger_path")
    if not repo_relative_path(ledger_path):
        add(errors, f"{path}.ledger_path", "must be a portable repository-relative path")
        return
    if not entry_id_valid or not condition_valid:
        return
    entry = entries.get(entry_id)
    if entry is None:
        add(errors, f"{path}.entry_id", "must reference an existing entry")
        return
    run = next(
        (
            item
            for item in entry.get("runs", [])
            if isinstance(item, dict) and item.get("condition") == condition
        ),
        None,
    )
    if run is None:
        add(errors, f"{path}.condition", "must reference a recorded run condition")
        return
    if run.get("source_kind") != "measured_local":
        add(errors, path, "routing bindings require a measured_local run")
    ledger_file = ROOT / ledger_path
    try:
        resolved = canonical_artifact_path(ledger_file, "routing-eval ledger")
        actual_digest = sha256_file(resolved)
        ledger = load_json_file(resolved)
        expected = routing_expected(ledger)
    except ArtifactError as exc:
        add(errors, path, str(exc))
        return
    if digest != actual_digest:
        add(errors, f"{path}.ledger_sha256", f"does not match ledger: {actual_digest}")
    artifact = run.get("artifact") if isinstance(run.get("artifact"), dict) else {}
    if artifact.get("path") != ledger_path or artifact.get("sha256") != actual_digest:
        add(errors, path, "bound run artifact must identify the routing ledger and its exact hash")
    metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
    for key in ("pass_count", "total_count", "score"):
        if metrics.get(key) != expected[key]:
            add(errors, f"{path}.{key}", f"must match routing ledger value {expected[key]!r}")
    if not finite_number(metrics.get("cost_usd")) or not math.isclose(
        float(metrics["cost_usd"]), expected["cost_usd"], rel_tol=0.0, abs_tol=1e-12
    ):
        add(errors, f"{path}.cost_usd", "must match the routing ledger aggregate")
    if metrics.get("tokens") != expected["tokens"]:
        add(errors, f"{path}.tokens", "must match the routing ledger aggregate")
    telemetry = run.get("card_telemetry") if isinstance(run.get("card_telemetry"), list) else []
    observed = {
        item.get("card_path"): item.get("fired_count")
        for item in telemetry
        if (
            isinstance(item, dict)
            and isinstance(item.get("card_path"), str)
            and isinstance(item.get("fired_count"), int)
            and not isinstance(item.get("fired_count"), bool)
        )
    }
    if observed != expected["utilization"]:
        add(errors, f"{path}.card_telemetry", "must exactly match routing ledger utilization")
    contract = entry.get("comparison_contract") if isinstance(entry.get("comparison_contract"), dict) else {}
    for key in ("sample_ids", "model", "prompt_version", "scorer_version"):
        if contract.get(key) != expected[key]:
            add(errors, f"{path}.comparison_contract.{key}", "must match routing ledger identity")


def validate_scoreboard(scoreboard: Any) -> list[str]:
    errors: list[str] = []
    document = object_shape(scoreboard, path="scoreboard", keys=SCOREBOARD_KEYS, errors=errors)
    if document is None:
        return errors
    if document.get("schema_version") != SCHEMA_VERSION:
        add(errors, "scoreboard.schema_version", f"must be {SCHEMA_VERSION}")
    if document.get("artifact_type") != "workflow_impact_scoreboard":
        add(errors, "scoreboard.artifact_type", "must be workflow_impact_scoreboard")
    if not valid_id(document.get("scoreboard_id")):
        add(errors, "scoreboard.scoreboard_id", "must be a portable identifier")
    if not valid_utc_timestamp(document.get("generated_at_utc")):
        add(errors, "scoreboard.generated_at_utc", "must be an explicit UTC timestamp ending in Z")
    sources = document.get("source_refs")
    source_registry: dict[str, dict[str, Any]] = {}
    if not isinstance(sources, list) or not sources:
        add(errors, "scoreboard.source_refs", "must be a non-empty list")
    else:
        for index, source in enumerate(sources):
            validate_source(source, index, errors)
            if isinstance(source, dict) and valid_id(source.get("source_id")):
                source_id = source["source_id"]
                if source_id in source_registry:
                    add(errors, f"source_refs[{index}].source_id", "duplicate source id")
                source_registry[source_id] = source
    entries_raw = document.get("entries")
    entries: dict[str, dict[str, Any]] = {}
    run_ids: set[str] = set()
    routing_runs: set[tuple[str, str]] = set()
    if not isinstance(entries_raw, list) or not entries_raw:
        add(errors, "scoreboard.entries", "must be a non-empty list")
    else:
        for index, entry in enumerate(entries_raw):
            routing_conditions = validate_entry(entry, index, source_registry, errors)
            if isinstance(entry, dict) and valid_id(entry.get("entry_id")):
                if entry["entry_id"] in entries:
                    add(errors, f"entries[{index}].entry_id", "duplicate entry id")
                entries[entry["entry_id"]] = entry
                routing_runs.update((entry["entry_id"], condition) for condition in routing_conditions)
            if isinstance(entry, dict) and isinstance(entry.get("runs"), list):
                for run_index, run in enumerate(entry["runs"]):
                    if not isinstance(run, dict) or not valid_id(run.get("run_id")):
                        continue
                    if run["run_id"] in run_ids:
                        add(errors, f"entries[{index}].runs[{run_index}].run_id", "duplicate run id")
                    run_ids.add(run["run_id"])
    bindings = document.get("routing_eval_bindings")
    if not isinstance(bindings, list):
        add(errors, "scoreboard.routing_eval_bindings", "must be a list")
    else:
        seen_bindings: set[tuple[Any, Any]] = set()
        for index, binding in enumerate(bindings):
            validate_routing_binding(binding, index, entries, errors)
            if isinstance(binding, dict):
                entry_id = binding.get("entry_id")
                condition = binding.get("condition")
                if valid_id(entry_id) and enum_member(condition, CONDITIONS):
                    identity = (entry_id, condition)
                    if identity in seen_bindings:
                        add(errors, f"routing_eval_bindings[{index}]", "duplicate binding")
                    seen_bindings.add(identity)
        for identity in sorted(routing_runs):
            if identity not in seen_bindings:
                add(errors, "scoreboard.routing_eval_bindings", f"missing binding for {identity[0]}:{identity[1]}")
    return errors


def measured_entries(scoreboard: dict[str, Any], *, include_examples: bool) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for entry in scoreboard["entries"]:
        if include_examples or any(run["source_kind"] != "example" for run in entry["runs"]):
            entries.append(entry)
    return entries


def escape_cell(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def render_markdown(scoreboard: dict[str, Any], *, include_examples: bool = False) -> str:
    entries = measured_entries(scoreboard, include_examples=include_examples)
    sources = {source["source_id"]: source for source in scoreboard["source_refs"]}
    lines = [
        f"# Workflow impact scoreboard: {scoreboard['scoreboard_id']}",
        "",
        f"Generated: `{scoreboard['generated_at_utc']}`",
        "",
        "| Entry | Kind | Condition | Source | Provenance | Validation | Pass rate | Elapsed (s) | Cost (USD) | Tokens | Artifact |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for entry in entries:
        for run in entry["runs"]:
            metrics = run["metrics"]
            rate = metrics["pass_count"] / metrics["total_count"]
            source_ref = run["artifact"]["source_ref"]
            provenance = f"{source_ref}: {sources[source_ref]['url']}"
            lines.append(
                "| "
                + " | ".join(
                    escape_cell(value)
                    for value in (
                        entry["entry_id"],
                        entry["task_kind"],
                        run["condition"],
                        run["source_kind"],
                        provenance,
                        metrics["validation_result"],
                        f"{rate:.4f}",
                        metrics["elapsed_seconds"],
                        metrics["cost_usd"],
                        metrics["tokens"]["total_tokens"],
                        run["artifact"]["path"],
                    )
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Run governance evidence",
            "",
            "| Entry | Run | Condition | Regression | Regression note | Validation evidence |",
            "|---|---|---|---|---|---|",
        ]
    )
    for entry in entries:
        for run in entry["runs"]:
            regression = run["regression"]
            lines.append(
                "| "
                + " | ".join(
                    escape_cell(value)
                    for value in (
                        entry["entry_id"],
                        run["run_id"],
                        run["condition"],
                        regression["status"],
                        regression["note"],
                        "; ".join(run["validation_evidence"]),
                    )
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "### Card telemetry",
            "",
            "| Entry | Run | Card | Fires | Contribution | Attributed tokens | Token unavailable reason | Evidence refs |",
            "|---|---|---|---:|---|---:|---|---|",
        ]
    )
    card_rows = 0
    for entry in entries:
        for run in entry["runs"]:
            for item in run["card_telemetry"]:
                lines.append(
                    "| "
                    + " | ".join(
                        escape_cell(value)
                        for value in (
                            entry["entry_id"],
                            run["run_id"],
                            item["card_path"],
                            item["fired_count"],
                            item["contribution"],
                            item["attributed_tokens"],
                            item["token_unavailable_reason"],
                            "; ".join(item["evidence_refs"]),
                        )
                    )
                    + " |"
                )
                card_rows += 1
    if not card_rows:
        lines.append("| n/a | n/a | No card telemetry recorded | n/a | n/a | n/a | n/a | n/a |")
    lines.extend(["", "## Comparison deltas", ""])
    paired = 0
    for entry in entries:
        if entry["comparison_mode"] == "unpaired":
            continue
        runs = {run["condition"]: run for run in entry["runs"]}
        baseline = runs["baseline"]["metrics"]
        fairy = runs["fairy_tale"]["metrics"]
        baseline_rate = baseline["pass_count"] / baseline["total_count"]
        fairy_rate = fairy["pass_count"] / fairy["total_count"]
        elapsed_delta = (
            fairy["elapsed_seconds"] - baseline["elapsed_seconds"]
            if fairy["elapsed_seconds"] is not None and baseline["elapsed_seconds"] is not None
            else None
        )
        token_delta = (
            fairy["tokens"]["total_tokens"] - baseline["tokens"]["total_tokens"]
            if fairy["tokens"]["total_tokens"] is not None and baseline["tokens"]["total_tokens"] is not None
            else None
        )
        cost_delta = (
            fairy["cost_usd"] - baseline["cost_usd"]
            if fairy["cost_usd"] is not None and baseline["cost_usd"] is not None
            else None
        )
        lines.append(
            f"- `{entry['entry_id']}`: pass-rate delta `{fairy_rate - baseline_rate:+.4f}`; "
            f"elapsed delta `{escape_cell(elapsed_delta)}`; cost delta `{escape_cell(cost_delta)}`; "
            f"token delta `{escape_cell(token_delta)}`."
        )
        paired += 1
    if not paired:
        lines.append("- No measured paired comparison is recorded. Unpaired runs do not claim uplift.")
    lines.extend(["", "Example runs are excluded from this view by default.", ""])
    return "\n".join(lines)


def schema_sync_errors() -> list[str]:
    schema = load_json_file(ROOT / "schemas" / "workflow-impact-scoreboard.schema.json")
    errors: list[str] = []
    if set(schema.get("required", [])) != SCOREBOARD_KEYS:
        errors.append("schema root required keys drift from runtime")
    if set(schema.get("properties", {})) != SCOREBOARD_KEYS:
        errors.append("schema root properties drift from runtime")
    definitions = schema.get("$defs", {})
    expected = {
        "source": SOURCE_KEYS,
        "entry": ENTRY_KEYS,
        "comparison_contract": CONTRACT_KEYS,
        "run": RUN_KEYS,
        "isolation": ISOLATION_KEYS,
        "metrics": METRIC_KEYS,
        "tokens": TOKEN_KEYS,
        "regression": REGRESSION_KEYS,
        "artifact": ARTIFACT_KEYS,
        "card_telemetry": TELEMETRY_KEYS,
        "routing_eval_binding": BINDING_KEYS,
    }
    for name, keys in expected.items():
        definition = definitions.get(name, {})
        if set(definition.get("required", [])) != keys or set(definition.get("properties", {})) != keys:
            errors.append(f"schema {name} keys drift from runtime")
    enum_checks = {
        ("source", "source_type"): {"official", "repository", "public_report"},
        ("source", "evidence_kind"): SOURCE_EVIDENCE_KINDS,
        ("entry", "task_kind"): TASK_KINDS,
        ("entry", "comparison_mode"): COMPARISON_MODES,
        ("run", "condition"): CONDITIONS,
        ("run", "source_kind"): SOURCE_KINDS,
        ("isolation", "skill_state"): {"disabled", "enabled", "external", "not_applicable"},
        ("metrics", "validation_result"): VALIDATION_RESULTS,
        ("regression", "status"): {"none", "observed", "unknown"},
        ("artifact", "visibility"): {"repository", "private", "local"},
        ("artifact", "disclosure"): {"full", "redacted"},
        ("artifact", "kind"): ARTIFACT_KINDS,
        ("card_telemetry", "contribution"): CONTRIBUTIONS,
    }
    for (definition_name, property_name), values in enum_checks.items():
        observed = (
            definitions.get(definition_name, {})
            .get("properties", {})
            .get(property_name, {})
            .get("enum")
        )
        if set(observed or []) != values:
            errors.append(f"schema {definition_name}.{property_name} enum drifts from runtime")
    return errors


def selftest(scoreboard_path: Path = DEFAULT_SCOREBOARD) -> int:
    controls = 0

    def check(condition: bool, label: str) -> None:
        nonlocal controls
        controls += 1
        if not condition:
            raise AssertionError(label)

    scoreboard = load_json_file(scoreboard_path)
    check(not validate_scoreboard(scoreboard), "committed sample validates")
    check(not schema_sync_errors(), "schema and runtime key sets match")
    check(len(measured_entries(scoreboard, include_examples=False)) == 1, "examples are excluded from measured aggregate")
    check(len(measured_entries(scoreboard, include_examples=True)) == 3, "examples are included only on request")
    markdown = render_markdown(scoreboard)
    check("No measured paired comparison" in markdown, "unpaired measured data never claims uplift")
    check("routing-eval-20260702.json" in markdown, "measured routing artifact is visible")
    check(
        "No isolated without-skill baseline was recorded" in markdown
        and "references/cards/benchmark-delta-harness.md" in markdown
        and "The routing ledger records aggregate tokens" in markdown,
        "regression and card evidence survive the default review view",
    )
    mutation = copy.deepcopy(scoreboard)
    governed_run = mutation["entries"][0]["runs"][1]
    governed_run["regression"] = {
        "status": "observed",
        "note": "SEVERE-REGRESSION-EVIDENCE",
    }
    governed_run["card_telemetry"][0]["contribution"] = "harmful"
    governed_run["card_telemetry"][0]["evidence_refs"] = ["CARD-HARM-EVIDENCE"]
    governed_markdown = render_markdown(mutation, include_examples=True)
    check(
        all(
            marker in governed_markdown
            for marker in (
                "observed",
                "SEVERE-REGRESSION-EVIDENCE",
                "harmful",
                "CARD-HARM-EVIDENCE",
                "references/cards/benchmark-delta-harness.md",
            )
        ),
        "observed regression and harmful card evidence survive review rendering",
    )

    mutation = copy.deepcopy(scoreboard)
    mutation["surprise"] = True
    check(any("unknown keys" in item for item in validate_scoreboard(mutation)), "unknown root key blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["source_refs"].append(copy.deepcopy(mutation["source_refs"][0]))
    check(any("duplicate source id" in item for item in validate_scoreboard(mutation)), "source ids are unique")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][0]["artifact"]["source_ref"] = "missing-source"
    check(any("declared source" in item for item in validate_scoreboard(mutation)), "artifact source references cannot dangle")
    malformed_fields = [
        (("source_refs", 0, "source_type"), {}, "source_refs[0].source_type"),
        (("source_refs", 0, "evidence_kind"), {}, "source_refs[0].evidence_kind"),
        (("entries", 0, "task_kind"), {}, "entries[0].task_kind"),
        (("entries", 0, "comparison_mode"), {}, "entries[0].comparison_mode"),
        (("entries", 0, "runs", 0, "source_kind"), {}, "entries[0].runs[0].source_kind"),
        (("entries", 0, "runs", 0, "isolation", "skill_state"), {}, "entries[0].runs[0].isolation.skill_state"),
        (("entries", 0, "runs", 0, "metrics", "validation_result"), {}, "entries[0].runs[0].metrics.validation_result"),
        (("entries", 0, "runs", 0, "regression", "status"), {}, "entries[0].runs[0].regression.status"),
        (("entries", 0, "runs", 0, "artifact", "visibility"), {}, "entries[0].runs[0].artifact.visibility"),
        (("entries", 0, "runs", 0, "artifact", "disclosure"), {}, "entries[0].runs[0].artifact.disclosure"),
        (("entries", 0, "runs", 0, "artifact", "kind"), {}, "entries[0].runs[0].artifact.kind"),
        (("entries", 0, "runs", 0, "artifact", "source_ref"), {}, "entries[0].runs[0].artifact.source_ref"),
        (("entries", 0, "runs", 1, "card_telemetry", 0, "contribution"), {}, "entries[0].runs[1].card_telemetry[0].contribution"),
        (("routing_eval_bindings", 0, "condition"), {}, "routing_eval_bindings[0].condition"),
        (("entries", 0, "runs", 1, "card_telemetry", 0, "card_path"), {}, "entries[0].runs[1].card_telemetry[0].card_path"),
        (("entries", 0, "runs", 0, "metrics", "tokens", "total_tokens"), {}, "entries[0].runs[0].metrics.tokens"),
        (("entries", 0, "comparison_contract", "sample_ids", 0), {}, "entries[0].comparison_contract.sample_ids"),
        (("entries", 0, "runs", 0, "condition"), {}, "entries[0].runs[0].condition"),
        (("entries", 0, "runs", 1, "card_telemetry", 0, "attributed_tokens"), "oops", "entries[0].runs[1].card_telemetry[0].attributed_tokens"),
        (("routing_eval_bindings", 0, "entry_id"), {}, "routing_eval_bindings[0].entry_id"),
    ]
    for locator, invalid_value, expected_path in malformed_fields:
        mutation = copy.deepcopy(scoreboard)
        target: Any = mutation
        for segment in locator[:-1]:
            target = target[segment]
        target[locator[-1]] = copy.deepcopy(invalid_value)
        check(
            any(item.startswith(expected_path + ":") for item in validate_scoreboard(mutation)),
            f"malformed nested value is reasoned at {expected_path}",
        )
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"] = mutation["entries"][0]["runs"][:1]
    check(any("paired entries require" in item for item in validate_scoreboard(mutation)), "incomplete pair blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][0]["source_kind"] = "measured_local"
    check(any("must both be" in item for item in validate_scoreboard(mutation)), "mixed example and measured pair blocks")
    mutation = copy.deepcopy(scoreboard)
    for run in mutation["entries"][0]["runs"]:
        run["source_kind"] = "measured_local"
    check(
        any("must use source_kind example" in item for item in validate_scoreboard(mutation)),
        "example artifacts cannot be relabeled as a measured pair",
    )
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"] = [mutation["entries"][0]]
    mutation["routing_eval_bindings"] = []
    external_entry = mutation["entries"][0]
    external_entry["comparison_mode"] = "paired_external_baseline"
    baseline_run, treated_run = external_entry["runs"]
    baseline_path = "adapters/workflow-scoreboard.adapter.json"
    treated_path = "schemas/workflow-impact-scoreboard.schema.json"
    baseline_run["source_kind"] = "official_external"
    baseline_run["artifact"] = {
        "kind": "run_output",
        "source_ref": "claude-skill-eval-guidance",
        "path": baseline_path,
        "visibility": "repository",
        "disclosure": "full",
        "sha256": sha256_file(ROOT / baseline_path),
    }
    treated_run["source_kind"] = "measured_local"
    treated_run["artifact"] = {
        "kind": "run_output",
        "source_ref": "benchmark-validation-plan",
        "path": treated_path,
        "visibility": "repository",
        "disclosure": "full",
        "sha256": sha256_file(ROOT / treated_path),
    }
    check(
        sum("must reference" in item and ".source_ref:" in item for item in validate_scoreboard(mutation)) == 2,
        "arbitrary repository files cannot self-label as official or measured evidence",
    )
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][0]["isolation"]["fresh_session"] = False
    check(any("require a fresh session" in item for item in validate_scoreboard(mutation)), "non-isolated pair blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][1]["artifact"] = copy.deepcopy(mutation["entries"][0]["runs"][0]["artifact"])
    check(any("distinct artifacts" in item for item in validate_scoreboard(mutation)), "paired runs cannot reuse one artifact")
    mutation = copy.deepcopy(scoreboard)
    for run in mutation["entries"][0]["runs"]:
        run["source_kind"] = "measured_local"
    mutation["entries"][0]["runs"][0]["metrics"]["elapsed_seconds"] = None
    mutation["entries"][0]["runs"][0]["metrics"]["elapsed_unavailable_reason"] = "not recorded"
    check(any("measured paired runs" in item for item in validate_scoreboard(mutation)), "measured pairs require elapsed, cost, and tokens")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][0]["card_telemetry"] = copy.deepcopy(
        mutation["entries"][0]["runs"][1]["card_telemetry"]
    )
    check(any("baseline runs cannot" in item for item in validate_scoreboard(mutation)), "baseline card attribution blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["routing_eval_bindings"][0]["ledger_sha256"] = "sha256:" + "0" * 64
    check(any("does not match ledger" in item for item in validate_scoreboard(mutation)), "routing hash drift blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["routing_eval_bindings"] = []
    check(any("missing binding" in item for item in validate_scoreboard(mutation)), "routing ledger cannot bypass binding")
    mutation = copy.deepcopy(scoreboard)
    mutation["routing_eval_bindings"].append(copy.deepcopy(mutation["routing_eval_bindings"][0]))
    check(
        any("duplicate binding" in item for item in validate_scoreboard(mutation)),
        "routing ledger runs require exactly one binding",
    )
    mutation = copy.deepcopy(scoreboard)
    measured = mutation["entries"][2]["runs"][0]
    measured["artifact"]["path"] = "plugins/fairy-tale/docs/skill-budget/routing-eval-20260702.json"
    next(
        source
        for source in mutation["source_refs"]
        if source["source_id"] == measured["artifact"]["source_ref"]
    )["artifact_path"] = measured["artifact"]["path"]
    measured["metrics"].update(pass_count=0, validation_result="fail", score=0, cost_usd=0)
    mutation["routing_eval_bindings"] = []
    check(
        any("missing binding" in item for item in validate_scoreboard(mutation)),
        "routing ledger binding follows content across mirror paths",
    )
    mutation = copy.deepcopy(scoreboard)
    measured = mutation["entries"][2]["runs"][0]
    measured["artifact"]["kind"] = "run_output"
    mutation["routing_eval_bindings"] = []
    errors = validate_scoreboard(mutation)
    check(
        any("routing ledger content must use kind" in item for item in errors)
        and any("missing binding" in item for item in errors),
        "routing content cannot be relabeled as a generic artifact",
    )
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][0]["artifact"]["kind"] = "routing_eval_ledger"
    check(
        any("content contract is missing" in item for item in validate_scoreboard(mutation)),
        "routing artifact kind requires routing ledger content",
    )
    mutation = copy.deepcopy(scoreboard)
    measured = mutation["entries"][2]["runs"][0]
    measured["metrics"]["pass_count"] -= 1
    check(any("must match routing ledger" in item for item in validate_scoreboard(mutation)), "routing aggregate drift blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][2]["comparison_contract"]["model"] = "unbound-model"
    check(any("comparison_contract.model" in item for item in validate_scoreboard(mutation)), "routing model identity drift blocks")
    routing_ledger = load_json_file(ROOT / scoreboard["routing_eval_bindings"][0]["ledger_path"])
    for identity_key in ("skill_md_sha256", "system_prompt_sha256", "cases_sha256", "repo_commit"):
        mutated_ledger = copy.deepcopy(routing_ledger)
        mutated_ledger.pop(identity_key)
        check(
            is_routing_eval_ledger(mutated_ledger),
            f"routing classification survives missing {identity_key}",
        )
        try:
            routing_expected(mutated_ledger)
        except ArtifactError as exc:
            check(identity_key in str(exc), f"missing routing identity {identity_key} blocks")
        else:
            raise AssertionError(f"missing routing identity {identity_key} blocks")
    for identity_key, invalid_value in (
        ("model", " "),
        ("skill_md_sha256", "A" * 64),
        ("system_prompt_sha256", "short"),
        ("cases_sha256", "sha256:" + "0" * 64),
        ("repo_commit", "not-a-commit"),
    ):
        mutated_ledger = copy.deepcopy(routing_ledger)
        mutated_ledger[identity_key] = invalid_value
        try:
            routing_expected(mutated_ledger)
        except ArtifactError as exc:
            check(identity_key in str(exc), f"malformed routing identity {identity_key} blocks")
        else:
            raise AssertionError(f"malformed routing identity {identity_key} blocks")
    mutated_ledger = copy.deepcopy(routing_ledger)
    mutated_ledger.pop("artifact_type")
    check(
        is_routing_eval_ledger(mutated_ledger),
        "routing classification survives missing artifact_type",
    )
    try:
        routing_expected(mutated_ledger)
    except ArtifactError as exc:
        check("artifact_type" in str(exc), "missing routing artifact_type blocks")
    else:
        raise AssertionError("missing routing artifact_type blocks")
    mutated_ledger = copy.deepcopy(routing_ledger)
    mutated_ledger["artifact_type"] = "generic_benchmark"
    try:
        routing_expected(mutated_ledger)
    except ArtifactError as exc:
        check("artifact_type" in str(exc), "wrong routing artifact_type blocks")
    else:
        raise AssertionError("wrong routing artifact_type blocks")
    check(
        not (ROUTING_LEDGER_CLASS_FIELDS & ROUTING_LEDGER_GENERIC_FIELDS)
        and set(routing_ledger)
        == ROUTING_LEDGER_CLASS_FIELDS | ROUTING_LEDGER_GENERIC_FIELDS,
        "routing top-level producer fields have an explicit semantic partition",
    )
    routing_result_fields = {
        key
        for result in routing_ledger["results"]
        for key in result
    }
    check(
        not (ROUTING_RESULT_MARKERS & ROUTING_RESULT_GENERIC_FIELDS)
        and routing_result_fields
        == ROUTING_RESULT_MARKERS | ROUTING_RESULT_GENERIC_FIELDS,
        "routing row producer fields have an explicit semantic partition",
    )
    check(
        not (ROUTING_SUMMARY_MARKERS & ROUTING_SUMMARY_GENERIC_FIELDS)
        and set(routing_ledger["summary"])
        == ROUTING_SUMMARY_MARKERS | ROUTING_SUMMARY_GENERIC_FIELDS,
        "routing summary producer fields have an explicit semantic partition",
    )
    with tempfile.TemporaryDirectory(prefix=".scoreboard-generic-", dir=ROOT) as directory:
        artifact_index = 0

        def validate_as_run_output(
            payload: dict[str, Any],
            *,
            falsify_metrics: bool = False,
        ) -> list[str]:
            nonlocal artifact_index
            artifact_path = Path(directory) / f"run-output-{artifact_index}.json"
            artifact_index += 1
            artifact_path.write_text(
                json.dumps(payload, indent=2) + "\n",
                encoding="utf-8",
            )
            mutated_scoreboard = copy.deepcopy(scoreboard)
            run = mutated_scoreboard["entries"][2]["runs"][0]
            source_ref = run["artifact"]["source_ref"]
            relative_path = artifact_path.relative_to(ROOT).as_posix()
            artifact_hash = sha256_file(artifact_path)
            run["artifact"].update(
                kind="run_output",
                path=relative_path,
                sha256=artifact_hash,
            )
            if falsify_metrics:
                run["metrics"].update(pass_count=0, score=0.0, cost_usd=0.0)
            source = next(
                source
                for source in mutated_scoreboard["source_refs"]
                if source["source_id"] == source_ref
            )
            source.update(
                artifact_path=relative_path,
                artifact_sha256=artifact_hash,
            )
            mutated_scoreboard["routing_eval_bindings"] = []
            return validate_scoreboard(mutated_scoreboard)

        generic_payload_base = {
            "model": "example-model",
            "repo_commit": "0" * 40,
            "results": [{"case_id": "case-a", "outcome": "pass"}],
            "summary": {"passed": 1, "total": 1},
        }
        generic_metadata_variants = (
            {},
            {"run_policy": {"fresh_session": True, "retry_limit": 0}},
            {"token_note": "provider did not expose cache tokens"},
            {
                "run_policy": {"fresh_session": True, "retry_limit": 0},
                "token_note": "provider did not expose cache tokens",
            },
            {
                "skill_md_sha256": "0" * 64,
                "system_prompt_sha256": "1" * 64,
                "cases_sha256": "2" * 64,
            },
            {
                "skill_md_sha256": "0" * 64,
                "system_prompt_sha256": "1" * 64,
                "cases_sha256": "2" * 64,
                "results": [
                    {
                        "case_id": "case-a",
                        "outcome": "pass",
                        "category": "general_benchmark",
                        "classification": "pass",
                    }
                ],
            },
            {
                "skill_md_sha256": "0" * 64,
                "system_prompt_sha256": "1" * 64,
                "cases_sha256": "2" * 64,
                "summary": {
                    "passed": 1,
                    "total": 1,
                    "per_category": {"general_benchmark": {"passed": 1, "total": 1}},
                },
            },
            {
                "results": [
                    {
                        "case_id": "case-a",
                        "outcome": "pass",
                        "category": "general_benchmark",
                        "classification": "pass",
                    }
                ],
                "summary": {
                    "passed": 1,
                    "total": 1,
                    "per_category": {"general_benchmark": {"passed": 1, "total": 1}},
                },
            },
            {
                "results": [
                    {
                        "case_id": "case-a",
                        "outcome": "pass",
                        "expected_cards": [],
                        "got_cards": [],
                        "invalid_paths": [],
                    }
                ]
            },
            {
                "summary": {
                    "passed": 1,
                    "total": 1,
                    "per_card_utilization": {},
                    "invalid_path_outputs": 0,
                }
            },
        )
        for index, metadata in enumerate(generic_metadata_variants):
            generic_payload = {**generic_payload_base, **metadata}
            check(
                not validate_as_run_output(generic_payload),
                f"generic routing-like metadata variant {index} remains run_output",
            )
        partial_routing_ledger = copy.deepcopy(routing_ledger)
        for result in partial_routing_ledger["results"]:
            result.pop("invalid_paths", None)
        partial_routing_ledger["summary"].pop("invalid_path_outputs", None)
        partial_errors = validate_as_run_output(
            partial_routing_ledger,
            falsify_metrics=True,
        )
        check(
            any("routing ledger content must use kind" in error for error in partial_errors)
            and any("missing binding" in error for error in partial_errors),
            "partial routing signatures cannot evade kind and binding validation",
        )
        stripped_routing_ledger = copy.deepcopy(routing_ledger)
        stripped_routing_ledger.pop("artifact_type", None)
        for marker in ("skill_md_sha256", "system_prompt_sha256", "cases_sha256"):
            stripped_routing_ledger.pop(marker, None)
        for result in stripped_routing_ledger["results"]:
            for marker in ("expected_cards", "got_cards", "invalid_paths"):
                result.pop(marker, None)
        for marker in ("per_card_utilization", "invalid_path_outputs"):
            stripped_routing_ledger["summary"].pop(marker, None)
        stripped_errors = validate_as_run_output(
            stripped_routing_ledger,
            falsify_metrics=True,
        )
        check(
            any("routing ledger content must use kind" in error for error in stripped_errors)
            and any("missing binding" in error for error in stripped_errors),
            "remaining producer routing fields cannot evade kind and binding validation",
        )
    mutated_ledger = copy.deepcopy(routing_ledger)
    mutated_ledger["summary"]["passed"] -= 1
    try:
        routing_expected(mutated_ledger)
    except ArtifactError as exc:
        check("does not match result rows" in str(exc), "routing summary is recomputed from rows")
    else:
        raise AssertionError("routing summary drift blocks")
    mutated_ledger = copy.deepcopy(routing_ledger)
    mutated_ledger["results"][0]["got_cards"] = ["references/cards/benchmark-delta-harness.md"]
    try:
        routing_expected(mutated_ledger)
    except ArtifactError as exc:
        check("does not match result rows" in str(exc), "routing utilization is recomputed from rows")
    else:
        raise AssertionError("routing utilization drift blocks")
    mutation = copy.deepcopy(scoreboard)
    measured = mutation["entries"][2]["runs"][0]
    measured["artifact"] = {
        "kind": "run_output",
        "source_ref": "routing-eval-20260702-artifact",
        "path": "/Users/example/private.json",
        "visibility": "local",
        "disclosure": "redacted",
        "sha256": "sha256:" + "1" * 64,
    }
    mutation["routing_eval_bindings"] = []
    check(any("redacted/..." in item for item in validate_scoreboard(mutation)), "absolute private path blocks")
    mutation = copy.deepcopy(scoreboard)
    measured = mutation["entries"][2]["runs"][0]
    measured["metrics"]["tokens"]["total_tokens"] += 1
    check(any("component sum" in item for item in validate_scoreboard(mutation)), "token sum mismatch blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][1]["card_telemetry"][0]["attributed_tokens"] = 9999
    check(any("cannot exceed" in item for item in validate_scoreboard(mutation)), "card attribution cannot exceed run tokens")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][0]["runs"][0]["condition"] = "fairy_tale"
    check(any("example marker" in item for item in validate_scoreboard(mutation)), "example identity is verified from its artifact")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][2]["runs"][0]["source_kind"] = "example"
    check(any("example marker" in item for item in validate_scoreboard(mutation)), "example labels require an example artifact marker")
    mutation = copy.deepcopy(scoreboard)
    mutation["generated_at_utc"] = "2026-99-99T00:00:00Z"
    check(any("UTC timestamp" in item for item in validate_scoreboard(mutation)), "invalid timestamp blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["source_refs"][0]["url"] = "https://"
    check(any("HTTPS URL" in item for item in validate_scoreboard(mutation)), "hostless source URL blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][1]["runs"][0]["run_id"] = mutation["entries"][0]["runs"][0]["run_id"]
    check(any("duplicate run id" in item for item in validate_scoreboard(mutation)), "run ids are globally unique")
    check(escape_cell("a|b\\c") == "a\\|b\\\\c", "Markdown cells escape separators")

    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "summary.md"
        write_text_atomic(output, markdown)
        check(output.read_text(encoding="utf-8") == markdown, "summary write is atomic")
        malformed = Path(directory) / "malformed.json"
        malformed.write_bytes(b"\xff")
        try:
            load_json_file(malformed)
        except ArtifactError as exc:
            check("invalid UTF-8" in str(exc), "malformed encoding is reasoned")
        else:
            raise AssertionError("malformed encoding blocks")
        try:
            require_distinct_paths(scoreboard_path, scoreboard_path, "scoreboard output collides with input")
        except ArtifactError as exc:
            check("collides" in str(exc), "input/output collision is reasoned")
        else:
            raise AssertionError("input/output collision blocks")

    print(f"workflow scoreboard selftest OK: {controls} controls")
    return 0


def require_scoreboard(path: Path) -> dict[str, Any]:
    scoreboard = load_json_file(path)
    errors = validate_scoreboard(scoreboard)
    if errors:
        raise ArtifactError("; ".join(errors))
    return scoreboard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and summarize a Fairy Tale workflow scoreboard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    summarize.add_argument("--output", type=Path)
    summarize.add_argument("--include-examples", action="store_true")
    test = subparsers.add_parser("selftest")
    test.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "selftest":
            return selftest(args.scoreboard)
        scoreboard = require_scoreboard(args.scoreboard)
        if args.command == "validate":
            print(f"workflow scoreboard OK: {len(scoreboard['entries'])} entries")
            return 0
        markdown = render_markdown(scoreboard, include_examples=args.include_examples)
        if args.output is None:
            print(markdown, end="")
        else:
            require_distinct_paths(args.scoreboard, args.output, "scoreboard summary output collides with input")
            write_text_atomic(args.output, markdown)
            print(args.output)
        return 0
    except (ArtifactError, OSError) as exc:
        print(f"workflow scoreboard error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
