#!/usr/bin/env python3
"""Create, update, render, and validate Fairy Tale task artifacts.

JSON is the canonical representation. Markdown is a rendered view for handoff
and completion reports. The future unified ``fairy`` CLI can delegate to this
module without duplicating the artifact contract.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
ROOT = Path(__file__).resolve().parents[1]
MODES = ("benchmark", "coding", "research", "security")
RESULTS = ("blocked", "fail", "not_run", "pass")
LEDGER_STATUSES = ("active", "blocked", "complete")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
PORTABLE_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}

TASK_CARD_KEYS = {
    "schema_version",
    "artifact_type",
    "task_id",
    "mode",
    "objective",
    "success_criteria",
    "allowed_targets",
    "constraints",
    "budget",
    "stop_conditions",
    "validation_plan",
    "ledger_path",
}
BUDGET_KEYS = {
    "max_elapsed_minutes",
    "max_tool_calls",
    "max_subagents",
    "max_searches",
    "token_or_cost_limit",
}
LEDGER_KEYS = {
    "schema_version",
    "artifact_type",
    "task_id",
    "task_card_path",
    "status",
    "checks",
    "blockers",
    "remaining_risks",
    "summary",
}
CHECK_KEYS = {
    "id",
    "plan_item",
    "command",
    "result",
    "artifact_paths",
    "notes",
}


class ArtifactError(ValueError):
    """A reasoned, user-facing artifact failure."""


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def valid_id(value: Any) -> bool:
    return isinstance(value, str) and bool(TASK_ID_RE.fullmatch(value))


def string_list(value: Any, *, nonempty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (bool(value) or not nonempty)
        and all(has_text(item) for item in value)
    )


def portable_filename(value: Any) -> bool:
    if not isinstance(value, str) or not PORTABLE_FILENAME_RE.fullmatch(value):
        return False
    stem = value.split(".", 1)[0].upper()
    return stem not in WINDOWS_RESERVED_NAMES and not value.endswith(".")


def add(findings: list[Finding], code: str, message: str) -> None:
    findings.append(Finding(code, message))


def unknown_keys(
    value: dict[str, Any], allowed: set[str], code: str, findings: list[Finding]
) -> None:
    extra = sorted(set(value) - allowed)
    if extra:
        add(findings, code, "unknown keys: " + ", ".join(extra))


def missing_keys(
    value: dict[str, Any], required: set[str], code: str, findings: list[Finding]
) -> None:
    missing = sorted(required - set(value))
    if missing:
        add(findings, code, "missing keys: " + ", ".join(missing))


def validate_task_card(card: Any) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(card, dict):
        return [Finding("task_card.not_object", "task card must be an object")]

    unknown_keys(card, TASK_CARD_KEYS, "task_card.unknown_keys", findings)
    missing_keys(card, TASK_CARD_KEYS, "task_card.missing", findings)
    if card.get("schema_version") != SCHEMA_VERSION:
        add(findings, "task_card.schema_version", "schema_version must be 1.0")
    if card.get("artifact_type") != "task_card":
        add(findings, "task_card.artifact_type", "artifact_type must be task_card")
    if not valid_id(card.get("task_id")):
        add(findings, "task_card.task_id", "task_id is malformed")
    if card.get("mode") not in MODES:
        add(findings, "task_card.mode", "mode must be coding, research, security, or benchmark")
    if not has_text(card.get("objective")):
        add(findings, "task_card.objective", "objective is required")

    for field in (
        "success_criteria",
        "allowed_targets",
        "constraints",
        "stop_conditions",
        "validation_plan",
    ):
        if not string_list(card.get(field)):
            add(findings, f"task_card.{field}", f"{field} must be a non-empty string list")
        elif len(card[field]) != len(set(card[field])):
            add(findings, f"task_card.{field}.duplicate", f"{field} entries must be unique")

    budget = card.get("budget")
    if not isinstance(budget, dict):
        add(findings, "task_card.budget", "budget must be an object")
    else:
        unknown_keys(budget, BUDGET_KEYS, "task_card.budget.unknown_keys", findings)
        missing_keys(budget, BUDGET_KEYS, "task_card.budget.missing", findings)
        for field in ("max_elapsed_minutes", "max_tool_calls"):
            value = budget.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                add(findings, f"task_card.budget.{field}", f"{field} must be a positive integer")
        for field in ("max_subagents", "max_searches"):
            value = budget.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                add(findings, f"task_card.budget.{field}", f"{field} must be a non-negative integer")
        if not has_text(budget.get("token_or_cost_limit")):
            add(
                findings,
                "task_card.budget.token_or_cost_limit",
                "token_or_cost_limit must state a limit or a reasoned not-applicable value",
            )

    if not portable_filename(card.get("ledger_path")):
        add(
            findings,
            "task_card.ledger_path",
            "ledger_path must be a portable filename in the Task Card directory",
        )
    return findings


def validate_check(check: Any, index: int, findings: list[Finding]) -> None:
    prefix = f"validation_ledger.checks[{index}]"
    if not isinstance(check, dict):
        add(findings, prefix, "check must be an object")
        return
    unknown_keys(check, CHECK_KEYS, f"{prefix}.unknown_keys", findings)
    missing_keys(check, CHECK_KEYS, f"{prefix}.missing", findings)
    if not valid_id(check.get("id")):
        add(findings, f"{prefix}.id", "check id is malformed")
    if not has_text(check.get("plan_item")):
        add(findings, f"{prefix}.plan_item", "plan_item is required")
    if not isinstance(check.get("command"), str):
        add(findings, f"{prefix}.command", "command must be a string")
    if check.get("result") not in RESULTS:
        add(findings, f"{prefix}.result", "result must be pass, fail, blocked, or not_run")
    if not string_list(check.get("artifact_paths"), nonempty=False):
        add(findings, f"{prefix}.artifact_paths", "artifact_paths must be a string list")
    if not isinstance(check.get("notes"), str):
        add(findings, f"{prefix}.notes", "notes must be a string")
    if check.get("result") == "pass" and not (
        has_text(check.get("command"))
        or (
            isinstance(check.get("artifact_paths"), list)
            and any(has_text(item) for item in check["artifact_paths"])
        )
        or has_text(check.get("notes"))
    ):
        add(
            findings,
            f"{prefix}.evidence",
            "pass check must record a command, artifact path, or manual observation in notes",
        )


def validate_validation_ledger(
    ledger: Any,
    *,
    ledger_path: Path | None = None,
    verify_link: bool = False,
    allow_missing_ledger: bool = False,
) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(ledger, dict):
        return [Finding("validation_ledger.not_object", "validation ledger must be an object")]

    unknown_keys(ledger, LEDGER_KEYS, "validation_ledger.unknown_keys", findings)
    missing_keys(ledger, LEDGER_KEYS, "validation_ledger.missing", findings)
    if ledger.get("schema_version") != SCHEMA_VERSION:
        add(findings, "validation_ledger.schema_version", "schema_version must be 1.0")
    if ledger.get("artifact_type") != "validation_ledger":
        add(
            findings,
            "validation_ledger.artifact_type",
            "artifact_type must be validation_ledger",
        )
    if not valid_id(ledger.get("task_id")):
        add(findings, "validation_ledger.task_id", "task_id is malformed")
    if not portable_filename(ledger.get("task_card_path")):
        add(
            findings,
            "validation_ledger.task_card_path",
            "task_card_path must be a portable filename in the ledger directory",
        )
    if ledger.get("status") not in LEDGER_STATUSES:
        add(findings, "validation_ledger.status", "status is invalid")

    checks = ledger.get("checks")
    if not isinstance(checks, list):
        add(findings, "validation_ledger.checks", "checks must be a list")
        checks = []
    for index, check in enumerate(checks):
        validate_check(check, index, findings)
    ids = [
        check.get("id")
        for check in checks
        if isinstance(check, dict) and isinstance(check.get("id"), str)
    ]
    duplicates = sorted({identifier for identifier in ids if ids.count(identifier) > 1})
    if duplicates:
        add(
            findings,
            "validation_ledger.checks.duplicate",
            "duplicate check ids: " + ", ".join(str(item) for item in duplicates),
        )

    for field in ("blockers", "remaining_risks"):
        if not string_list(ledger.get(field), nonempty=False):
            add(findings, f"validation_ledger.{field}", f"{field} must be a string list")
    if not isinstance(ledger.get("summary"), str):
        add(findings, "validation_ledger.summary", "summary must be a string")

    card: dict[str, Any] | None = None
    if verify_link:
        if ledger_path is None:
            add(findings, "validation_ledger.link", "ledger path is required for link verification")
        else:
            try:
                resolved_ledger = canonical_artifact_path(
                    ledger_path,
                    "validation ledger",
                    allow_missing=allow_missing_ledger,
                )
            except ArtifactError as exc:
                add(findings, "validation_ledger.link.ledger_path", str(exc))
                resolved_ledger = None

            if portable_filename(ledger.get("task_card_path")):
                stored_card_path = ledger_path.parent / str(ledger["task_card_path"])
                try:
                    card_path = canonical_artifact_path(stored_card_path, "Task Card")
                    loaded = load_json(card_path)
                except (ArtifactError, OSError) as exc:
                    add(findings, "validation_ledger.link.task_card", str(exc))
                else:
                    card_findings = validate_task_card(loaded)
                    findings.extend(
                        Finding(f"validation_ledger.link.{item.code}", item.message)
                        for item in card_findings
                    )
                    if not card_findings:
                        card = loaded
                        if card.get("task_id") != ledger.get("task_id"):
                            add(findings, "validation_ledger.link.task_id", "task ids do not match")
                        if card.get("ledger_path") != ledger_path.name:
                            add(
                                findings,
                                "validation_ledger.link.ledger_path",
                                "Task Card ledger_path must exactly match the validation ledger filename",
                            )
                        try:
                            linked_ledger = canonical_artifact_path(
                                card_path.parent / str(card["ledger_path"]),
                                "validation ledger",
                                allow_missing=allow_missing_ledger,
                            )
                        except ArtifactError as exc:
                            add(
                                findings,
                                "validation_ledger.link.ledger_path",
                                str(exc),
                            )
                        else:
                            if resolved_ledger is not None and linked_ledger != resolved_ledger:
                                add(
                                    findings,
                                    "validation_ledger.link.ledger_path",
                                    "Task Card does not point back to this validation ledger",
                                )

    status = ledger.get("status")
    blockers = ledger.get("blockers") if isinstance(ledger.get("blockers"), list) else []
    if status == "complete":
        if not checks:
            add(findings, "validation_ledger.complete.checks", "complete ledger needs checks")
        non_pass = [
            str(check.get("id") or f"index-{index}")
            if isinstance(check, dict)
            else f"index-{index}"
            for index, check in enumerate(checks)
            if not isinstance(check, dict) or check.get("result") != "pass"
        ]
        if non_pass:
            add(
                findings,
                "validation_ledger.complete.non_pass",
                "complete ledger has non-pass checks: " + ", ".join(non_pass),
            )
        if blockers:
            add(findings, "validation_ledger.complete.blockers", "complete ledger cannot have blockers")
        if not has_text(ledger.get("summary")):
            add(findings, "validation_ledger.complete.summary", "complete ledger needs a summary")
        if card is not None:
            planned = set(card["validation_plan"])
            covered = {check.get("plan_item") for check in checks if isinstance(check, dict)}
            missing = sorted(planned - covered)
            if missing:
                add(
                    findings,
                    "validation_ledger.complete.plan_coverage",
                    "unrecorded validation plan items: " + "; ".join(missing),
                )
    elif status == "blocked":
        if not blockers:
            add(findings, "validation_ledger.blocked.blockers", "blocked ledger needs a blocker")
        if not has_text(ledger.get("summary")):
            add(findings, "validation_ledger.blocked.summary", "blocked ledger needs a summary")
    return findings


def validate_artifact(
    artifact: Any, *, path: Path | None = None, verify_link: bool = False
) -> list[Finding]:
    if not isinstance(artifact, dict):
        return [Finding("artifact.not_object", "artifact must be an object")]
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "task_card":
        return validate_task_card(artifact)
    if artifact_type == "validation_ledger":
        return validate_validation_ledger(artifact, ledger_path=path, verify_link=verify_link)
    return [Finding("artifact.type", "artifact_type must be task_card or validation_ledger")]


def validate_cli_artifact(
    artifact: Any, *, path: Path, verify_link: bool = False
) -> list[Finding]:
    effective_verify_link = (
        verify_link
        or (
            isinstance(artifact, dict)
            and artifact.get("artifact_type") == "validation_ledger"
        )
    )
    return validate_artifact(
        artifact,
        path=path,
        verify_link=effective_verify_link,
    )


def read_utf8(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ArtifactError(f"{label} not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise ArtifactError(f"invalid UTF-8 in {label}: {path}") from exc


def load_json(path: Path) -> Any:
    try:
        return json.loads(read_utf8(path, "artifact"))
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"invalid JSON in {path}: {exc.msg}") from exc


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_json(path: Path, payload: Any) -> None:
    write_text_atomic(
        path,
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )


def resolve_path(path: Path) -> Path:
    try:
        resolved = path.resolve()
        try:
            path.stat()
        except FileNotFoundError:
            # A not-yet-created output path is valid. Other resolution errors,
            # including symlink loops on Python 3.13+, must fail closed.
            pass
        return resolved
    except (OSError, RuntimeError) as exc:
        raise ArtifactError(f"cannot resolve path {path}: {exc}") from exc


def portable_name_identity(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def portable_path_identity(path: Path) -> tuple[str, ...]:
    return tuple(portable_name_identity(part) for part in resolve_path(path).parts)


def canonical_artifact_path(
    path: Path, label: str, *, allow_missing: bool = False
) -> Path:
    try:
        directory_entries = os.listdir(path.parent)
    except OSError as exc:
        raise ArtifactError(f"cannot inspect {label} directory {path.parent}: {exc}") from exc

    if path.name not in directory_entries:
        aliases = [
            name
            for name in directory_entries
            if portable_name_identity(name) == portable_name_identity(path.name)
        ]
        if aliases:
            raise ArtifactError(
                f"{label} filename must match exactly: stored {path.name}, found {aliases[0]}"
            )
        if allow_missing:
            return resolve_path(path)
        raise ArtifactError(f"{label} not found under its exact stored filename: {path.name}")
    if path.is_symlink():
        raise ArtifactError(f"{label} must be a regular file in the artifact directory")
    return resolve_path(path)


def require_distinct_paths(first: Path, second: Path, message: str) -> None:
    if portable_path_identity(first) == portable_path_identity(second):
        raise ArtifactError(message)


def relative_path(target: Path, base: Path) -> str:
    return Path(os.path.relpath(resolve_path(target), resolve_path(base))).as_posix()


def require_valid(findings: list[Finding]) -> None:
    if findings:
        detail = "; ".join(f"{item.code}: {item.message}" for item in findings)
        raise ArtifactError(detail)


def make_task_card(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "task_card",
        "task_id": args.task_id,
        "mode": args.mode,
        "objective": args.objective,
        "success_criteria": args.success,
        "allowed_targets": args.target,
        "constraints": args.constraint,
        "budget": {
            "max_elapsed_minutes": args.max_elapsed_minutes,
            "max_tool_calls": args.max_tool_calls,
            "max_subagents": args.max_subagents,
            "max_searches": args.max_searches,
            "token_or_cost_limit": args.token_or_cost_limit,
        },
        "stop_conditions": args.stop,
        "validation_plan": args.validation,
        "ledger_path": args.ledger_path,
    }


def empty_validation_ledger(card: dict[str, Any], card_path: Path, ledger_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "validation_ledger",
        "task_id": card["task_id"],
        "task_card_path": relative_path(card_path, ledger_path.parent),
        "status": "active",
        "checks": [],
        "blockers": [],
        "remaining_risks": [],
        "summary": "",
    }


def task_card_markdown(card: dict[str, Any]) -> str:
    budget = card["budget"]
    lines = [
        f"# Task Card: {card['task_id']}",
        "",
        f"- Mode: `{card['mode']}`",
        f"- Objective: {card['objective']}",
        f"- Validation ledger: `{card['ledger_path']}`",
        "",
        "## Success Criteria",
        *[f"- {item}" for item in card["success_criteria"]],
        "",
        "## Allowed Targets",
        *[f"- `{item}`" for item in card["allowed_targets"]],
        "",
        "## Constraints",
        *[f"- {item}" for item in card["constraints"]],
        "",
        "## Budget",
        f"- Elapsed minutes: {budget['max_elapsed_minutes']}",
        f"- Tool calls: {budget['max_tool_calls']}",
        f"- Subagents: {budget['max_subagents']}",
        f"- Searches: {budget['max_searches']}",
        f"- Token/cost: {budget['token_or_cost_limit']}",
        "",
        "## Stop Conditions",
        *[f"- {item}" for item in card["stop_conditions"]],
        "",
        "## Validation Plan",
        *[f"- {item}" for item in card["validation_plan"]],
    ]
    return "\n".join(lines) + "\n"


def markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def ledger_markdown(ledger: dict[str, Any]) -> str:
    lines = [
        f"# Validation Ledger: {ledger['task_id']}",
        "",
        f"- Task card: `{ledger['task_card_path']}`",
        f"- Status: `{ledger['status']}`",
        "",
        "## Checks",
        "",
        "| ID | Plan item | Result | Command | Artifacts | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for check in ledger["checks"]:
        artifacts = ", ".join(markdown_cell(item) for item in check["artifact_paths"]) or "-"
        command = markdown_cell(check["command"]) if check["command"] else "manual"
        notes = markdown_cell(check["notes"]) if check["notes"] else "-"
        lines.append(
            f"| {markdown_cell(check['id'])} | {markdown_cell(check['plan_item'])} | "
            f"{check['result']} | {command} | {artifacts} | {notes} |"
        )
    if not ledger["checks"]:
        lines.append("| - | - | not_run | - | - | - |")
    lines.extend(
        [
            "",
            "## Blockers",
            *([f"- {item}" for item in ledger["blockers"]] or ["- None recorded."]),
            "",
            "## Remaining Risks",
            *([f"- {item}" for item in ledger["remaining_risks"]] or ["- None recorded."]),
            "",
            "## Summary",
            "",
            ledger["summary"] or "Not finalized.",
        ]
    )
    return "\n".join(lines) + "\n"


def command_task_card(args: argparse.Namespace) -> int:
    if not portable_filename(args.output.name):
        raise ArtifactError("Task Card output must use a portable filename")
    card = make_task_card(args)
    require_valid(validate_task_card(card))
    linked_ledger = args.output.parent / str(card["ledger_path"])
    require_distinct_paths(
        args.output,
        linked_ledger,
        "Task Card output and linked ledger must be different files",
    )
    if args.markdown_output:
        require_distinct_paths(
            args.output,
            args.markdown_output,
            "Markdown output cannot replace the canonical Task Card JSON",
        )
        require_distinct_paths(
            linked_ledger,
            args.markdown_output,
            "Markdown output cannot replace the linked validation ledger",
        )
    write_json(args.output, card)
    if args.markdown_output:
        write_text_atomic(args.markdown_output, task_card_markdown(card))
    print(f"wrote task card: {args.output}")
    return 0


def command_ledger_init(args: argparse.Namespace) -> int:
    if not portable_filename(args.task_card.name):
        raise ArtifactError("Task Card path must use a portable filename")
    card = load_json(args.task_card)
    require_valid(validate_task_card(card))
    output = args.output or (args.task_card.parent / str(card["ledger_path"]))
    require_distinct_paths(
        args.task_card,
        output,
        "validation ledger cannot replace its linked Task Card",
    )
    expected = resolve_path(args.task_card.parent / str(card["ledger_path"]))
    if resolve_path(output) != expected:
        raise ArtifactError("ledger output must match the task card ledger_path")
    ledger = empty_validation_ledger(card, args.task_card, output)
    require_valid(
        validate_validation_ledger(
            ledger,
            ledger_path=output,
            verify_link=True,
            allow_missing_ledger=True,
        )
    )
    write_json(output, ledger)
    print(f"wrote validation ledger: {output}")
    return 0


def command_ledger_add(args: argparse.Namespace) -> int:
    ledger = load_json(args.ledger)
    require_valid(validate_validation_ledger(ledger, ledger_path=args.ledger, verify_link=True))
    if ledger["status"] != "active":
        raise ArtifactError("only an active ledger can be updated")
    check = {
        "id": args.check_id,
        "plan_item": args.plan_item,
        "command": args.command_text,
        "result": args.result,
        "artifact_paths": args.artifact,
        "notes": args.notes,
    }
    existing = next((item for item in ledger["checks"] if item.get("id") == args.check_id), None)
    if existing is not None and not args.replace:
        raise ArtifactError(f"check id already exists: {args.check_id}; use --replace")
    if existing is not None:
        ledger["checks"][ledger["checks"].index(existing)] = check
    else:
        ledger["checks"].append(check)
    require_valid(validate_validation_ledger(ledger, ledger_path=args.ledger, verify_link=True))
    write_json(args.ledger, ledger)
    print(f"recorded check {args.check_id}: {args.result}")
    return 0


def command_ledger_finalize(args: argparse.Namespace) -> int:
    ledger = load_json(args.ledger)
    require_valid(validate_validation_ledger(ledger, ledger_path=args.ledger, verify_link=True))
    if ledger["status"] != "active":
        raise ArtifactError("only an active ledger can be finalized")
    ledger["status"] = args.status
    ledger["blockers"] = args.blocker
    ledger["remaining_risks"] = args.remaining_risk
    ledger["summary"] = args.summary
    require_valid(validate_validation_ledger(ledger, ledger_path=args.ledger, verify_link=True))
    write_json(args.ledger, ledger)
    print(f"finalized validation ledger as {args.status}: {args.ledger}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    artifact = load_json(args.artifact)
    findings = validate_cli_artifact(
        artifact,
        path=args.artifact,
        verify_link=args.verify_link,
    )
    if args.json:
        print(
            json.dumps(
                {"ok": not findings, "artifact": str(args.artifact), "findings": [item.__dict__ for item in findings]},
                indent=2,
                sort_keys=True,
            )
        )
    elif findings:
        for item in findings:
            print(f"FAIL {item.code}: {item.message}")
    else:
        print(f"OK artifact valid: {args.artifact}")
    return 1 if findings else 0


def command_render(args: argparse.Namespace) -> int:
    artifact = load_json(args.artifact)
    require_valid(
        validate_cli_artifact(
            artifact,
            path=args.artifact,
            verify_link=args.verify_link,
        )
    )
    rendered = (
        task_card_markdown(artifact)
        if artifact["artifact_type"] == "task_card"
        else ledger_markdown(artifact)
    )
    if args.output:
        require_distinct_paths(
            args.artifact,
            args.output,
            "Markdown output cannot replace the canonical JSON artifact",
        )
        linked_filename = (
            artifact["ledger_path"]
            if artifact["artifact_type"] == "task_card"
            else artifact["task_card_path"]
        )
        require_distinct_paths(
            args.artifact.parent / str(linked_filename),
            args.output,
            "Markdown output cannot replace the linked artifact",
        )
        write_text_atomic(args.output, rendered)
        print(f"wrote markdown view: {args.output}")
    else:
        print(rendered, end="")
    return 0


def command_cases(args: argparse.Namespace) -> int:
    total = 0
    failed = 0
    for line_number, raw in enumerate(
        read_utf8(args.cases, "cases file").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        total += 1
        try:
            case = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"FAIL line {line_number}: invalid JSON: {exc.msg}")
            failed += 1
            continue
        if not isinstance(case, dict):
            print(f"FAIL line {line_number}: case must be an object")
            failed += 1
            continue
        findings = validate_artifact(case.get("artifact"))
        actual = "block" if findings else "pass"
        codes = {item.code for item in findings}
        expected_codes = set(case.get("expected_codes", []))
        ok = actual == case.get("expected") and expected_codes <= codes
        print(f"{'PASS' if ok else 'FAIL'} {case.get('id', line_number)}: {actual}")
        if not ok:
            failed += 1
            print(f"  expected={case.get('expected')} expected_codes={sorted(expected_codes)} actual_codes={sorted(codes)}")
    print(f"task artifact cases: {total - failed}/{total} passed")
    return 1 if failed else 0


def _test_card(mode: str = "coding") -> dict[str, Any]:
    args = argparse.Namespace(
        task_id=f"test-{mode}",
        mode=mode,
        objective="Complete a bounded task with recorded evidence.",
        success=["The requested behavior is verified."],
        target=["src/", "tests/"],
        constraint=["Do not change unrelated behavior."],
        max_elapsed_minutes=60,
        max_tool_calls=40,
        max_subagents=1,
        max_searches=8,
        token_or_cost_limit="one bounded agent run",
        stop=["Stop on an authority or safety boundary."],
        validation=["focused test", "adjacent compatibility test"],
        ledger_path="validation-ledger.json",
    )
    return make_task_card(args)


def command_selftest(_args: argparse.Namespace) -> int:
    controls = 0

    def check(condition: bool, label: str) -> None:
        nonlocal controls
        controls += 1
        if not condition:
            raise AssertionError(label)

    for mode in MODES:
        check(not validate_task_card(_test_card(mode)), f"valid {mode} card")

    card = _test_card()
    malformed = dict(card)
    malformed.pop("budget")
    check(any(item.code == "task_card.missing" for item in validate_task_card(malformed)), "missing budget")
    malformed = dict(card, surprise=True)
    check(any(item.code == "task_card.unknown_keys" for item in validate_task_card(malformed)), "unknown card key")
    malformed = json.loads(json.dumps(card))
    malformed["budget"]["max_subagents"] = -1
    check(any(item.code.endswith("max_subagents") for item in validate_task_card(malformed)), "negative subagent budget")
    for unsafe in (
        "../outside.json",
        "nested/outside.json",
        "C:\\outside.json",
        "/outside.json",
        "CON.json",
        "task-card.",
    ):
        malformed = dict(card, ledger_path=unsafe)
        check(
            any(item.code == "task_card.ledger_path" for item in validate_task_card(malformed)),
            f"unsafe ledger path {unsafe}",
        )

    task_schema = load_json(ROOT / "schemas" / "task-card.schema.json")
    ledger_schema = load_json(ROOT / "schemas" / "validation-ledger.schema.json")
    check(set(task_schema["required"]) == TASK_CARD_KEYS, "task schema top-level sync")
    check(set(task_schema["properties"]["budget"]["required"]) == BUDGET_KEYS, "task budget schema sync")
    check(set(ledger_schema["required"]) == LEDGER_KEYS, "ledger schema top-level sync")
    check(set(ledger_schema["$defs"]["check"]["required"]) == CHECK_KEYS, "check schema sync")
    pass_evidence = ledger_schema["$defs"]["check"]["allOf"][0]["then"]["anyOf"]
    check(
        {next(iter(item["properties"])) for item in pass_evidence}
        == {"command", "artifact_paths", "notes"},
        "pass evidence schema sync",
    )
    check(tuple(task_schema["properties"]["mode"]["enum"]) == MODES, "task schema mode sync")
    check(
        tuple(ledger_schema["$defs"]["check"]["properties"]["result"]["enum"]) == RESULTS,
        "ledger schema result sync",
    )
    malformed = dict(card, task_id=123)
    check(any(item.code == "task_card.task_id" for item in validate_task_card(malformed)), "non-string task id")

    with tempfile.TemporaryDirectory() as raw_dir:
        root = Path(raw_dir)
        card_path = root / "task-card.json"
        ledger_path = root / "validation-ledger.json"

        def rejected(operation: Any) -> bool:
            try:
                operation()
            except ArtifactError:
                return True
            return False

        def card_args(
            output: Path, *, ledger_name: str = "validation-ledger.json", markdown: Path | None = None
        ) -> argparse.Namespace:
            return argparse.Namespace(
                task_id=card["task_id"],
                mode=card["mode"],
                objective=card["objective"],
                success=card["success_criteria"],
                target=card["allowed_targets"],
                constraint=card["constraints"],
                max_elapsed_minutes=card["budget"]["max_elapsed_minutes"],
                max_tool_calls=card["budget"]["max_tool_calls"],
                max_subagents=card["budget"]["max_subagents"],
                max_searches=card["budget"]["max_searches"],
                token_or_cost_limit=card["budget"]["token_or_cost_limit"],
                stop=card["stop_conditions"],
                validation=card["validation_plan"],
                ledger_path=ledger_name,
                output=output,
                markdown_output=markdown,
            )

        invalid_utf8 = root / "invalid-utf8.json"
        invalid_utf8.write_bytes(b"\xff\xfe")
        check(
            rejected(lambda: load_json(invalid_utf8)),
            "invalid UTF-8 is a reasoned artifact failure",
        )

        check(
            rejected(
                lambda: require_distinct_paths(
                    root / "Task.json",
                    root / "task.json",
                    "portable path aliases must differ",
                )
            ),
            "case-only path aliases collide across supported filesystems",
        )
        check(
            portable_path_identity(root / "Cafe\u0301" / "task.json")
            == portable_path_identity(root / "Caf\u00e9" / "task.json"),
            "canonically equivalent path names collide",
        )
        check(
            portable_path_identity(root / "\u2460" / "task.json")
            != portable_path_identity(root / "1" / "task.json"),
            "compatibility characters remain distinct path names",
        )

        loop_path = root / "loop.json"
        try:
            loop_path.symlink_to(loop_path.name)
        except (NotImplementedError, OSError):
            pass
        else:
            loop_ledger = empty_validation_ledger(
                card,
                root / "task-card.json",
                root / "loop-ledger.json",
            )
            loop_ledger["task_card_path"] = loop_path.name
            loop_findings = validate_validation_ledger(
                loop_ledger,
                ledger_path=root / "loop-ledger.json",
                verify_link=True,
            )
            check(
                any(
                    item.code == "validation_ledger.link.task_card"
                    for item in loop_findings
                ),
                "symlink loop in a linked artifact is a reasoned finding",
            )
            check(
                rejected(
                    lambda: require_distinct_paths(
                        root / "safe.json",
                        loop_path,
                        "symlink loop must block",
                    )
                ),
                "symlink loop in an output path is a reasoned failure",
            )

        collision_path = root / "collision.json"
        check(
            rejected(
                lambda: command_task_card(
                    card_args(collision_path, ledger_name=collision_path.name)
                )
            ),
            "Task Card cannot replace itself with its linked ledger",
        )
        check(
            rejected(
                lambda: command_task_card(
                    card_args(collision_path, markdown=collision_path)
                )
            ),
            "Task Card Markdown cannot replace canonical JSON",
        )

        self_linked_card = dict(card, ledger_path="self-linked-card.json")
        self_linked_path = root / "self-linked-card.json"
        write_json(self_linked_path, self_linked_card)
        check(
            rejected(
                lambda: command_ledger_init(
                    argparse.Namespace(task_card=self_linked_path, output=None)
                )
            ),
            "ledger init cannot replace its Task Card",
        )
        check(
            load_json(self_linked_path).get("artifact_type") == "task_card",
            "rejected ledger collision preserves the Task Card",
        )

        write_json(card_path, card)
        check(
            rejected(
                lambda: command_render(
                    argparse.Namespace(
                        artifact=card_path,
                        output=card_path,
                        verify_link=False,
                    )
                )
            ),
            "render cannot replace canonical JSON",
        )
        check(
            rejected(
                lambda: command_render(
                    argparse.Namespace(
                        artifact=card_path,
                        output=ledger_path,
                        verify_link=False,
                    )
                )
            ),
            "render cannot replace the linked artifact",
        )
        ledger = empty_validation_ledger(card, card_path, ledger_path)
        write_json(ledger_path, ledger)
        check(not validate_validation_ledger(ledger, ledger_path=ledger_path, verify_link=True), "linked active ledger")

        for index, plan_item in enumerate(card["validation_plan"], start=1):
            ledger["checks"].append(
                {
                    "id": f"check-{index}",
                    "plan_item": plan_item,
                    "command": f"run-check-{index}",
                    "result": "pass",
                    "artifact_paths": [f"artifacts/check-{index}.txt"],
                    "notes": "",
                }
            )
        ledger.update(status="complete", summary="All planned validation passed.")
        check(not validate_validation_ledger(ledger, ledger_path=ledger_path, verify_link=True), "complete linked ledger")
        evidenceless = json.loads(json.dumps(ledger))
        evidenceless["checks"][0].update(command="", artifact_paths=[], notes="")
        check(
            any(
                item.code == "validation_ledger.checks[0].evidence"
                for item in validate_validation_ledger(evidenceless)
            ),
            "pass check needs command or manual evidence",
        )
        manual_evidence = json.loads(json.dumps(ledger))
        manual_evidence["checks"][0].update(
            command="", artifact_paths=[], notes="Observed the expected result in the rendered output."
        )
        check(
            not any(
                item.code == "validation_ledger.checks[0].evidence"
                for item in validate_validation_ledger(manual_evidence)
            ),
            "manual observation can evidence a pass check",
        )
        check(
            "Observed the expected result in the rendered output."
            in ledger_markdown(manual_evidence),
            "manual evidence remains visible in the derived review view",
        )
        artifact_evidence = json.loads(json.dumps(ledger))
        artifact_evidence["checks"][0].update(
            command="", artifact_paths=["artifacts/manual-check.txt"], notes=""
        )
        check(
            not any(
                item.code == "validation_ledger.checks[0].evidence"
                for item in validate_validation_ledger(artifact_evidence)
            ),
            "artifact path can evidence a pass check",
        )

        write_json(ledger_path, ledger)
        orphan_dir = root / "orphan"
        orphan_dir.mkdir()
        orphan_ledger = orphan_dir / ledger_path.name
        write_json(orphan_ledger, ledger)
        check(
            any(
                item.code == "validation_ledger.link.task_card"
                for item in validate_cli_artifact(
                    ledger,
                    path=orphan_ledger,
                )
            ),
            "ledger validation verifies the Task Card link by default",
        )
        orphan_markdown = orphan_dir / "validation-ledger.md"
        check(
            rejected(
                lambda: command_render(
                    argparse.Namespace(
                        artifact=orphan_ledger,
                        output=orphan_markdown,
                        verify_link=False,
                    )
                )
            )
            and not orphan_markdown.exists(),
            "ledger rendering verifies the Task Card link before writing",
        )

        case_dir = root / "case-alias"
        case_dir.mkdir()
        case_card_path = case_dir / "TASK-CARD.JSON"
        case_ledger_path = case_dir / "validation-ledger.json"
        write_json(case_card_path, card)
        case_ledger = empty_validation_ledger(card, case_card_path, case_ledger_path)
        case_ledger["task_card_path"] = "task-card.json"
        write_json(case_ledger_path, case_ledger)
        check(
            any(
                item.code == "validation_ledger.link.task_card"
                for item in validate_validation_ledger(
                    case_ledger,
                    ledger_path=case_ledger_path,
                    verify_link=True,
                )
            ),
            "stored Task Card filename must match its directory entry exactly",
        )

        split_card_dir = root / "split-card"
        split_ledger_dir = root / "split-ledger"
        split_card_dir.mkdir()
        split_ledger_dir.mkdir()
        split_card_path = split_card_dir / "task-card.json"
        split_ledger_path = split_ledger_dir / "validation-ledger.json"
        write_json(split_card_path, card)
        split_ledger = empty_validation_ledger(
            card,
            split_ledger_dir / "task-card.json",
            split_ledger_path,
        )
        write_json(split_ledger_path, split_ledger)
        try:
            (split_card_dir / "validation-ledger.json").symlink_to(split_ledger_path)
            (split_ledger_dir / "task-card.json").symlink_to(split_card_path)
        except (NotImplementedError, OSError):
            pass
        else:
            check(
                any(
                    item.code == "validation_ledger.link.task_card"
                    for item in validate_validation_ledger(
                        split_ledger,
                        ledger_path=split_ledger_path,
                        verify_link=True,
                    )
                ),
                "canonical Task Card and ledger cannot be cross-directory symlink aliases",
            )
        check("# Task Card" in task_card_markdown(card), "task card markdown")
        check("# Validation Ledger" in ledger_markdown(ledger), "ledger markdown")
        escaped = json.loads(json.dumps(ledger))
        escaped["checks"][0]["plan_item"] = "focused | compatibility"
        check("focused \\| compatibility" in ledger_markdown(escaped), "markdown table escaping")

        incomplete = json.loads(json.dumps(ledger))
        incomplete["checks"][0]["result"] = "not_run"
        check(
            any(item.code == "validation_ledger.complete.non_pass" for item in validate_validation_ledger(incomplete)),
            "not-run cannot complete",
        )
        blocked = json.loads(json.dumps(ledger))
        blocked.update(status="blocked", blockers=[], summary="Blocked.")
        check(
            any(item.code == "validation_ledger.blocked.blockers" for item in validate_validation_ledger(blocked)),
            "blocked ledger needs blocker",
        )
        mismatch = json.loads(json.dumps(ledger))
        mismatch["task_id"] = "other-task"
        check(
            any(item.code == "validation_ledger.link.task_id" for item in validate_validation_ledger(mismatch, ledger_path=ledger_path, verify_link=True)),
            "task id mismatch",
        )
        duplicate = json.loads(json.dumps(ledger))
        duplicate["checks"].append(dict(duplicate["checks"][0]))
        check(
            any(item.code == "validation_ledger.checks.duplicate" for item in validate_validation_ledger(duplicate)),
            "duplicate check id",
        )
        uncovered = json.loads(json.dumps(ledger))
        uncovered["checks"] = uncovered["checks"][:1]
        check(
            any(
                item.code == "validation_ledger.complete.plan_coverage"
                for item in validate_validation_ledger(uncovered, ledger_path=ledger_path, verify_link=True)
            ),
            "complete ledger covers task plan",
        )

    print(f"task artifacts selftest OK: {controls} controls")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and validate Fairy Tale task artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    card = subparsers.add_parser("task-card", help="write a canonical JSON Task Card")
    card.add_argument("--task-id", required=True)
    card.add_argument("--mode", required=True, choices=MODES)
    card.add_argument("--objective", required=True)
    card.add_argument("--success", action="append", required=True)
    card.add_argument("--target", action="append", required=True)
    card.add_argument("--constraint", action="append", required=True)
    card.add_argument("--max-elapsed-minutes", type=int, required=True)
    card.add_argument("--max-tool-calls", type=int, required=True)
    card.add_argument("--max-subagents", type=int, required=True)
    card.add_argument("--max-searches", type=int, required=True)
    card.add_argument("--token-or-cost-limit", required=True)
    card.add_argument("--stop", action="append", required=True)
    card.add_argument("--validation", action="append", required=True)
    card.add_argument("--ledger-path", required=True)
    card.add_argument("--output", required=True, type=Path)
    card.add_argument("--markdown-output", type=Path)
    card.set_defaults(func=command_task_card)

    ledger_init = subparsers.add_parser("ledger-init", help="initialize the linked ledger")
    ledger_init.add_argument("--task-card", required=True, type=Path)
    ledger_init.add_argument("--output", type=Path)
    ledger_init.set_defaults(func=command_ledger_init)

    ledger_add = subparsers.add_parser("ledger-add", help="record or replace one check")
    ledger_add.add_argument("--ledger", required=True, type=Path)
    ledger_add.add_argument("--check-id", required=True)
    ledger_add.add_argument("--plan-item", required=True)
    ledger_add.add_argument("--command", dest="command_text", default="")
    ledger_add.add_argument("--result", required=True, choices=RESULTS)
    ledger_add.add_argument("--artifact", action="append", default=[])
    ledger_add.add_argument("--notes", default="")
    ledger_add.add_argument("--replace", action="store_true")
    ledger_add.set_defaults(func=command_ledger_add)

    finalize = subparsers.add_parser("ledger-finalize", help="finalize as complete or blocked")
    finalize.add_argument("--ledger", required=True, type=Path)
    finalize.add_argument("--status", required=True, choices=("blocked", "complete"))
    finalize.add_argument("--summary", required=True)
    finalize.add_argument("--blocker", action="append", default=[])
    finalize.add_argument("--remaining-risk", action="append", default=[])
    finalize.set_defaults(func=command_ledger_finalize)

    validate = subparsers.add_parser("validate", help="validate a Task Card or ledger")
    validate.add_argument("--artifact", required=True, type=Path)
    validate.add_argument("--verify-link", action="store_true")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=command_validate)

    render = subparsers.add_parser("render", help="render canonical JSON as Markdown")
    render.add_argument("--artifact", required=True, type=Path)
    render.add_argument("--output", type=Path)
    render.add_argument("--verify-link", action="store_true")
    render.set_defaults(func=command_render)

    cases = subparsers.add_parser("cases", help="run JSONL acceptance cases")
    cases.add_argument("--cases", required=True, type=Path)
    cases.set_defaults(func=command_cases)

    selftest = subparsers.add_parser("selftest", help="run deterministic self-controls")
    selftest.set_defaults(func=command_selftest)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (ArtifactError, OSError, AssertionError, UnicodeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
