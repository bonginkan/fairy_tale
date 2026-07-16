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

SCOREBOARD_KEYS = {
    "schema_version",
    "artifact_type",
    "scoreboard_id",
    "generated_at_utc",
    "source_refs",
    "entries",
    "routing_eval_bindings",
}
SOURCE_KEYS = {"url", "checked_at", "source_type", "note"}
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
ARTIFACT_KEYS = {"path", "visibility", "disclosure", "sha256"}
TELEMETRY_KEYS = {
    "card_path",
    "fired_count",
    "contribution",
    "attributed_tokens",
    "token_unavailable_reason",
    "evidence_refs",
}
BINDING_KEYS = {"entry_id", "condition", "ledger_path", "ledger_sha256"}

COMPARISON_MODES = {"paired_local", "paired_external_baseline", "unpaired"}
TASK_KINDS = {"benchmark", "normal"}
SOURCE_KINDS = {"measured_local", "official_external", "example"}
CONDITIONS = {"baseline", "fairy_tale"}
VALIDATION_RESULTS = {"pass", "fail"}
CONTRIBUTIONS = {"helpful", "neutral", "harmful", "unknown"}


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


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
    parsed_url = urlparse(source.get("url") if isinstance(source.get("url"), str) else "")
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        add(errors, f"{path}.url", "must be an HTTPS URL")
    if not valid_date(source.get("checked_at")):
        add(errors, f"{path}.checked_at", "must be an ISO calendar date")
    if source.get("source_type") not in {"official", "repository", "public_report"}:
        add(errors, f"{path}.source_type", "must be official, repository, or public_report")
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
    if isinstance(contract.get("sample_ids"), list) and len(contract["sample_ids"]) != len(set(contract["sample_ids"])):
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
    if metrics.get("validation_result") not in VALIDATION_RESULTS:
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
    visibility = artifact.get("visibility")
    disclosure = artifact.get("disclosure")
    if visibility not in {"repository", "private", "local"}:
        add(errors, f"{path}.visibility", "must be repository, private, or local")
    if disclosure not in {"full", "redacted"}:
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
    elif visibility in {"private", "local"}:
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
        if card_path in seen:
            add(errors, f"{item_path}.card_path", "duplicate card telemetry")
        seen.add(card_path)
        count = item.get("fired_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            add(errors, f"{item_path}.fired_count", "must be a positive integer")
        if item.get("contribution") not in CONTRIBUTIONS:
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


def validate_run(value: Any, path: str, task_kind: Any, errors: list[str]) -> None:
    run = object_shape(value, path=path, keys=RUN_KEYS, errors=errors)
    if run is None:
        return
    if not valid_id(run.get("run_id")):
        add(errors, f"{path}.run_id", "must be a portable identifier")
    condition = run.get("condition")
    if condition not in CONDITIONS:
        add(errors, f"{path}.condition", "must be baseline or fairy_tale")
    if run.get("source_kind") not in SOURCE_KINDS:
        add(errors, f"{path}.source_kind", "must be measured_local, official_external, or example")
    isolation = object_shape(run.get("isolation"), path=f"{path}.isolation", keys=ISOLATION_KEYS, errors=errors)
    if isolation is not None:
        if not isinstance(isolation.get("fresh_session"), bool):
            add(errors, f"{path}.isolation.fresh_session", "must be boolean")
        expected_state = "disabled" if condition == "baseline" else "enabled"
        if isolation.get("skill_state") not in {"disabled", "enabled", "external", "not_applicable"}:
            add(errors, f"{path}.isolation.skill_state", "invalid skill state")
        elif run.get("source_kind") != "official_external" and isolation["skill_state"] != expected_state:
            add(errors, f"{path}.isolation.skill_state", f"must be {expected_state} for this condition")
        if not has_text(isolation.get("note")):
            add(errors, f"{path}.isolation.note", "must be non-empty")
    validate_metrics(run.get("metrics"), f"{path}.metrics", errors)
    regression = object_shape(run.get("regression"), path=f"{path}.regression", keys=REGRESSION_KEYS, errors=errors)
    if regression is not None:
        if regression.get("status") not in {"none", "observed", "unknown"}:
            add(errors, f"{path}.regression.status", "must be none, observed, or unknown")
        if not has_text(regression.get("note")):
            add(errors, f"{path}.regression.note", "must be non-empty")
    resolved_artifact = validate_artifact(run.get("artifact"), f"{path}.artifact", errors)
    validate_telemetry(run.get("card_telemetry"), f"{path}.card_telemetry", condition, errors)
    text_list(run.get("validation_evidence"), path=f"{path}.validation_evidence", errors=errors)
    telemetry = run.get("card_telemetry")
    metrics = run.get("metrics")
    if isinstance(telemetry, list) and isinstance(metrics, dict):
        attributed = [
            item.get("attributed_tokens")
            for item in telemetry
            if isinstance(item, dict) and item.get("attributed_tokens") is not None
        ]
        total_tokens = metrics.get("tokens", {}).get("total_tokens") if isinstance(metrics.get("tokens"), dict) else None
        if attributed and total_tokens is not None and sum(attributed) > total_tokens:
            add(errors, f"{path}.card_telemetry", "attributed tokens cannot exceed total run tokens")
    source_kind = run.get("source_kind")
    artifact = run.get("artifact") if isinstance(run.get("artifact"), dict) else {}
    artifact_payload: Any = None
    if artifact.get("visibility") == "repository" and resolved_artifact is not None:
        try:
            artifact_payload = load_json_file(resolved_artifact)
        except ArtifactError as exc:
            if source_kind == "example":
                add(errors, f"{path}.artifact", str(exc))
    if source_kind == "example":
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
        source_kind in SOURCE_KINDS
        and isinstance(artifact_payload, dict)
        and artifact_payload.get("example") is True
    ):
        add(errors, f"{path}.source_kind", "repository artifacts marked example:true must use source_kind example")


def validate_entry(value: Any, index: int, errors: list[str]) -> None:
    path = f"entries[{index}]"
    entry = object_shape(value, path=path, keys=ENTRY_KEYS, errors=errors)
    if entry is None:
        return
    for key in ("entry_id", "task_id"):
        if not valid_id(entry.get(key)):
            add(errors, f"{path}.{key}", "must be a portable identifier")
    if entry.get("task_kind") not in TASK_KINDS:
        add(errors, f"{path}.task_kind", "must be benchmark or normal")
    if not has_text(entry.get("task_family")):
        add(errors, f"{path}.task_family", "must be non-empty")
    mode = entry.get("comparison_mode")
    if mode not in COMPARISON_MODES:
        add(errors, f"{path}.comparison_mode", "invalid comparison mode")
    if not has_text(entry.get("comparison_note")):
        add(errors, f"{path}.comparison_note", "must be non-empty")
    validate_contract(entry.get("comparison_contract"), f"{path}.comparison_contract", errors)
    runs = entry.get("runs")
    if not isinstance(runs, list) or not runs:
        add(errors, f"{path}.runs", "must be a non-empty list")
        return
    for run_index, run in enumerate(runs):
        validate_run(run, f"{path}.runs[{run_index}]", entry.get("task_kind"), errors)
    conditions = [run.get("condition") for run in runs if isinstance(run, dict)]
    if len(conditions) != len(set(conditions)):
        add(errors, f"{path}.runs", "conditions must be unique")
    if mode == "unpaired" and len(runs) != 1:
        add(errors, f"{path}.runs", "unpaired entries require exactly one run")
    if mode in {"paired_local", "paired_external_baseline"} and set(conditions) != CONDITIONS:
        add(errors, f"{path}.runs", "paired entries require one baseline and one fairy_tale run")
    if mode == "paired_local" and any(run.get("source_kind") == "official_external" for run in runs if isinstance(run, dict)):
        add(errors, f"{path}.runs", "paired_local cannot use an official external run")
    if mode == "paired_local":
        source_kinds = {run.get("source_kind") for run in runs if isinstance(run, dict)}
        if source_kinds not in ({"measured_local"}, {"example"}):
            add(errors, f"{path}.runs", "paired_local runs must both be measured_local or both be examples")
    if mode == "paired_external_baseline":
        baseline = next((run for run in runs if isinstance(run, dict) and run.get("condition") == "baseline"), {})
        fairy = next((run for run in runs if isinstance(run, dict) and run.get("condition") == "fairy_tale"), {})
        if baseline.get("source_kind") != "official_external":
            add(errors, f"{path}.runs", "paired_external_baseline requires an official external baseline")
        if fairy.get("source_kind") != "measured_local":
            add(errors, f"{path}.runs", "paired_external_baseline requires a measured_local Fairy Tale run")
    if mode in {"paired_local", "paired_external_baseline"}:
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


def routing_expected(ledger: dict[str, Any]) -> dict[str, Any]:
    results = ledger.get("results")
    summary = ledger.get("summary")
    if not isinstance(results, list) or not isinstance(summary, dict):
        raise ArtifactError("routing ledger must contain results and summary")
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
        f"skill_sha256:{ledger.get('skill_md_sha256')};"
        f"system_prompt_sha256:{ledger.get('system_prompt_sha256')};"
        f"cases_sha256:{ledger.get('cases_sha256')}"
    )
    return {
        "pass_count": passed,
        "total_count": total,
        "score": accuracy,
        "cost_usd": cost,
        "tokens": tokens,
        "utilization": utilization,
        "sample_ids": sample_ids,
        "model": ledger.get("model"),
        "prompt_version": prompt_version,
        "scorer_version": f"scripts/routing_eval.py@{ledger.get('repo_commit')}",
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
    if binding.get("condition") not in CONDITIONS:
        add(errors, f"{path}.condition", "must be baseline or fairy_tale")
    digest = binding.get("ledger_sha256")
    if not isinstance(digest, str) or not SHA_RE.fullmatch(digest):
        add(errors, f"{path}.ledger_sha256", "must be a lowercase sha256 digest")
    ledger_path = binding.get("ledger_path")
    if not repo_relative_path(ledger_path):
        add(errors, f"{path}.ledger_path", "must be a portable repository-relative path")
        return
    entry = entries.get(binding.get("entry_id"))
    if entry is None:
        add(errors, f"{path}.entry_id", "must reference an existing entry")
        return
    run = next(
        (
            item
            for item in entry.get("runs", [])
            if isinstance(item, dict) and item.get("condition") == binding.get("condition")
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
        if isinstance(item, dict)
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
    if not isinstance(sources, list) or not sources:
        add(errors, "scoreboard.source_refs", "must be a non-empty list")
    else:
        for index, source in enumerate(sources):
            validate_source(source, index, errors)
    entries_raw = document.get("entries")
    entries: dict[str, dict[str, Any]] = {}
    run_ids: set[str] = set()
    if not isinstance(entries_raw, list) or not entries_raw:
        add(errors, "scoreboard.entries", "must be a non-empty list")
    else:
        for index, entry in enumerate(entries_raw):
            validate_entry(entry, index, errors)
            if isinstance(entry, dict) and valid_id(entry.get("entry_id")):
                if entry["entry_id"] in entries:
                    add(errors, f"entries[{index}].entry_id", "duplicate entry id")
                entries[entry["entry_id"]] = entry
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
                identity = (binding.get("entry_id"), binding.get("condition"))
                if identity in seen_bindings:
                    add(errors, f"routing_eval_bindings[{index}]", "duplicate binding")
                seen_bindings.add(identity)
        for entry in entries.values():
            for run in entry.get("runs", []):
                if not isinstance(run, dict) or not isinstance(run.get("artifact"), dict):
                    continue
                artifact_path = run["artifact"].get("path")
                identity = (entry.get("entry_id"), run.get("condition"))
                if (
                    isinstance(artifact_path, str)
                    and artifact_path.startswith("docs/skill-budget/routing-eval-")
                    and identity not in seen_bindings
                ):
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
    lines = [
        f"# Workflow impact scoreboard: {scoreboard['scoreboard_id']}",
        "",
        f"Generated: `{scoreboard['generated_at_utc']}`",
        "",
        "| Entry | Kind | Condition | Source | Validation | Pass rate | Elapsed (s) | Cost (USD) | Tokens | Artifact |",
        "|---|---|---|---|---|---:|---:|---:|---:|---|",
    ]
    for entry in entries:
        for run in entry["runs"]:
            metrics = run["metrics"]
            rate = metrics["pass_count"] / metrics["total_count"]
            lines.append(
                "| "
                + " | ".join(
                    escape_cell(value)
                    for value in (
                        entry["entry_id"],
                        entry["task_kind"],
                        run["condition"],
                        run["source_kind"],
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
        ("entry", "task_kind"): TASK_KINDS,
        ("entry", "comparison_mode"): COMPARISON_MODES,
        ("run", "condition"): CONDITIONS,
        ("run", "source_kind"): SOURCE_KINDS,
        ("isolation", "skill_state"): {"disabled", "enabled", "external", "not_applicable"},
        ("metrics", "validation_result"): VALIDATION_RESULTS,
        ("regression", "status"): {"none", "observed", "unknown"},
        ("artifact", "visibility"): {"repository", "private", "local"},
        ("artifact", "disclosure"): {"full", "redacted"},
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

    mutation = copy.deepcopy(scoreboard)
    mutation["surprise"] = True
    check(any("unknown keys" in item for item in validate_scoreboard(mutation)), "unknown root key blocks")
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
        any("marked example:true" in item for item in validate_scoreboard(mutation)),
        "example artifacts cannot be relabeled as a measured pair",
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
    measured = mutation["entries"][2]["runs"][0]
    measured["metrics"]["pass_count"] -= 1
    check(any("must match routing ledger" in item for item in validate_scoreboard(mutation)), "routing aggregate drift blocks")
    mutation = copy.deepcopy(scoreboard)
    mutation["entries"][2]["comparison_contract"]["model"] = "unbound-model"
    check(any("comparison_contract.model" in item for item in validate_scoreboard(mutation)), "routing model identity drift blocks")
    routing_ledger = load_json_file(ROOT / scoreboard["routing_eval_bindings"][0]["ledger_path"])
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
