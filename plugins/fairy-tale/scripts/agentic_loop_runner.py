#!/usr/bin/env python3
"""Run controlled Agentic Loop workspaces.

The runner gives solvers only visible task files and public probes. It records
allowlisted actions into trace JSONL, keeps hidden validators out of the solver
workspace/request, and can execute trusted hidden validators after the run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "agentic_loop_runner.v1"
ARMS = ("control", "static_ledger", "placebo_loop", "agentic_loop")
OPTIONAL_BASELINE_ARMS = ("non_loop_control",)
DEFAULT_ALLOWED_ACTIONS = (
    "inspect_file",
    "search",
    "run_public_test",
    "edit",
    "write_answer",
    "abstain",
    "blocked",
)
CONTROL_GUIDANCE = "Use the baseline Fairy Tale process without a forced loop artifact."
STATIC_LEDGER_GUIDANCE = (
    "Use a static empirical ledger if helpful, but the controller will not "
    "force a probe before the final answer."
)
PLACEBO_LOOP_GUIDANCE = (
    "You have the same tool and iteration budget as the agentic loop arm. "
    "Use generic careful retry and verification; no structured loop schema is provided."
)
AGENTIC_LOOP_GUIDANCE = (
    "Use the observe-act-validate loop. Choose one minimal allowed action per "
    "iteration, treat public-test stdout/stderr and file observations as state, "
    "update the target from each external observation, and do not claim success "
    "while any observed requirement remains unresolved."
)
NON_LOOP_CONTROL_GUIDANCE = (
    "One-shot visible-context baseline. Use only the visible task prompt and "
    "provided visible file contents. Do not request probes, searches, or "
    "iterative observations; make at most one edit/final/abstain/block action."
)
ARM_GUIDANCE = {
    "control": CONTROL_GUIDANCE,
    "static_ledger": STATIC_LEDGER_GUIDANCE,
    "placebo_loop": PLACEBO_LOOP_GUIDANCE,
    "agentic_loop": AGENTIC_LOOP_GUIDANCE,
    "non_loop_control": NON_LOOP_CONTROL_GUIDANCE,
}
NON_LOOP_ACTIONS = ("edit", "write_answer", "abstain", "blocked")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise SystemExit(f"missing file: {path}") from None
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL {path}:{line_number}: {exc}") from None
        if not isinstance(row, dict):
            raise SystemExit(f"JSONL row must be an object: {path}:{line_number}")
        rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def stable_id(seed: int, task_id: str, arm: str) -> str:
    digest = hashlib.sha256(f"{seed}:{task_id}:{arm}".encode("utf-8")).hexdigest()
    return f"alr-{digest[:16]}"


def require_text(row: dict[str, Any], field: str, label: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return value


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "passed", "pass"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bounded_text(value: str, max_chars: int = 4000) -> str:
    return value if len(value) <= max_chars else value[:max_chars] + "\n...[truncated]"


def safe_workspace_path(workspace: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("path must be a non-empty string")
    if "\x00" in relative:
        raise ValueError("path must not contain NUL")
    path = (workspace / relative).resolve()
    root = workspace.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"path escapes workspace: {relative}")
    return path


def validate_tasks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        label = f"task[{index}]"
        task_id = require_text(row, "task_id", label)
        if task_id in seen:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen.add(task_id)
        polarity = require_text(row, "polarity", label)
        if polarity not in {"positive", "negative"}:
            raise ValueError(f"{label}.polarity must be positive or negative")
        prompt = require_text(row, "prompt", label)
        family = require_text(row, "family", label)
        files = row.get("visible_files", {})
        if not isinstance(files, dict):
            raise ValueError(f"{label}.visible_files must be an object")
        public_tests = row.get("public_tests", [])
        if not isinstance(public_tests, list):
            raise ValueError(f"{label}.public_tests must be a list")
        hidden_validators = row.get("hidden_validators", [])
        if not isinstance(hidden_validators, list):
            raise ValueError(f"{label}.hidden_validators must be a list")
        budgets = row.get("budgets", {})
        if budgets is None:
            budgets = {}
        if not isinstance(budgets, dict):
            raise ValueError(f"{label}.budgets must be an object")
        allowed_actions = budgets.get("allowed_actions", list(DEFAULT_ALLOWED_ACTIONS))
        if not isinstance(allowed_actions, list) or not all(isinstance(item, str) for item in allowed_actions):
            raise ValueError(f"{label}.budgets.allowed_actions must be a list of strings")
        normalized.append(
            {
                "task_id": task_id,
                "polarity": polarity,
                "family": family,
                "prompt": prompt,
                "visible_files": files,
                "public_tests": public_tests,
                "hidden_validators": hidden_validators,
                "budgets": {**budgets, "allowed_actions": allowed_actions},
            }
        )
    return normalized


def write_workspace(task: dict[str, Any], workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for relative, content in task["visible_files"].items():
        target = safe_workspace_path(workspace, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
    task_md = workspace / "TASK.md"
    task_md.write_text(task["prompt"] + "\n", encoding="utf-8")


def list_visible_files(workspace: Path) -> list[str]:
    files: list[str] = []
    root = workspace.resolve()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(str(path.relative_to(root)))
    return files


def visible_file_contents(workspace: Path, max_chars: int = 4000) -> dict[str, str]:
    contents: dict[str, str] = {}
    root = workspace.resolve()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(root))
            if relative == "TASK.md":
                continue
            try:
                contents[relative] = bounded_text(path.read_text(encoding="utf-8"), max_chars)
            except UnicodeDecodeError:
                contents[relative] = "[binary or non-UTF-8 file omitted]"
    return contents


def public_tests_by_id(task: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tests: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(task.get("public_tests", []), start=1):
        if not isinstance(item, dict):
            continue
        test_id = item.get("id") if isinstance(item.get("id"), str) else f"test-{index}"
        tests[test_id] = item
    return tests


def command_from_spec(spec: Any) -> list[str]:
    if not isinstance(spec, list) or not spec or not all(isinstance(part, str) and part for part in spec):
        raise ValueError("command must be a non-empty argv list")
    return spec


def run_command(command: list[str], cwd: Path, timeout: float) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            input="",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.time() - started
        return {
            "returncode": proc.returncode,
            "stdout": bounded_text(proc.stdout),
            "stderr": bounded_text(proc.stderr),
            "elapsed_seconds": elapsed,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": None,
            "stdout": bounded_text(exc.stdout or ""),
            "stderr": bounded_text(exc.stderr or ""),
            "elapsed_seconds": timeout,
            "timed_out": True,
        }


def action_payload(action: dict[str, Any]) -> dict[str, Any]:
    payload = action.get("input", {})
    if isinstance(payload, dict):
        return payload
    return {}


def execute_action(
    action: dict[str, Any],
    workspace: Path,
    task: dict[str, Any],
    allowed_actions: set[str],
    timeout: float,
) -> tuple[dict[str, Any], bool, dict[str, Any] | None]:
    action_type = action.get("type")
    if not isinstance(action_type, str):
        return {"source": "none", "summary": "invalid action: missing type"}, False, None
    if action_type not in allowed_actions:
        return {"source": "none", "summary": f"action not allowed: {action_type}"}, False, None
    payload = action_payload(action)
    try:
        if action_type == "inspect_file":
            root = workspace.resolve()
            target = safe_workspace_path(workspace, payload.get("path"))
            text = target.read_text(encoding="utf-8")
            return {
                "source": "file",
                "summary": bounded_text(text),
                "artifact_path": str(target.relative_to(root)),
            }, False, None
        if action_type == "search":
            pattern = payload.get("pattern")
            if not isinstance(pattern, str) or not pattern:
                raise ValueError("search.pattern is required")
            root = safe_workspace_path(workspace, payload.get("path", "."))
            workspace_root = workspace.resolve()
            regex = re.compile(pattern)
            matches: list[str] = []
            paths = [root] if root.is_file() else sorted(root.rglob("*"))
            for path in paths:
                if not path.is_file():
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                for line_number, line in enumerate(text.splitlines(), start=1):
                    if regex.search(line):
                        matches.append(f"{path.relative_to(workspace_root)}:{line_number}:{line}")
                        if len(matches) >= 50:
                            break
                if len(matches) >= 50:
                    break
            return {
                "source": "grep_hit" if matches else "grep",
                "summary": bounded_text("\n".join(matches) if matches else "no matches"),
            }, False, None
        if action_type == "run_public_test":
            test_id = payload.get("test_id")
            tests = public_tests_by_id(task)
            if not isinstance(test_id, str) or test_id not in tests:
                raise ValueError(f"unknown public test: {test_id}")
            test = tests[test_id]
            command = command_from_spec(test.get("command"))
            result = run_command(command, workspace, as_float(test.get("timeout_seconds"), timeout))
            passed = result["returncode"] == 0 and not result["timed_out"]
            summary = f"test_id={test_id} passed={passed} returncode={result['returncode']}\n"
            summary += f"stdout:\n{result['stdout']}\nstderr:\n{result['stderr']}"
            return {
                "source": "test" if passed else "test_failure",
                "summary": bounded_text(summary),
                "artifact_path": f"public-test:{test_id}",
            }, False, None
        if action_type == "edit":
            root = workspace.resolve()
            target = safe_workspace_path(workspace, payload.get("path"))
            content = payload.get("content")
            if not isinstance(content, str):
                raise ValueError("edit.content must be a string")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return {
                "source": "diff",
                "summary": f"wrote {target.relative_to(root)} ({len(content)} chars)",
                "artifact_path": str(target.relative_to(root)),
            }, False, None
        if action_type == "write_answer":
            answer = payload.get("answer", "")
            final = {
                "claimed_success": as_bool(payload.get("claimed_success")),
                "answer": str(answer),
                "stop_reason": "verified" if as_bool(payload.get("claimed_success")) else "abstained",
            }
            return {"source": "none", "summary": "final answer recorded"}, True, final
        if action_type == "abstain":
            return {"source": "none", "summary": "solver abstained"}, True, {
                "claimed_success": False,
                "answer": str(payload.get("answer", "INSUFFICIENT_CONTEXT")),
                "stop_reason": "abstained",
            }
        if action_type == "blocked":
            return {"source": "none", "summary": str(payload.get("reason", "blocked"))}, True, {
                "claimed_success": False,
                "answer": str(payload.get("reason", "blocked")),
                "stop_reason": "blocked",
            }
    except Exception as exc:  # noqa: BLE001 - convert action failures into observations.
        return {"source": "runtime_error", "summary": str(exc)}, False, None
    return {"source": "none", "summary": f"unimplemented action: {action_type}"}, False, None


def solver_request(
    task: dict[str, Any],
    blind_id: str,
    arm: str,
    workspace: Path,
    iterations: list[dict[str, Any]],
    remaining_iterations: int,
) -> dict[str, Any]:
    if arm == "non_loop_control":
        allowed = [
            action
            for action in task["budgets"].get("allowed_actions", list(DEFAULT_ALLOWED_ACTIONS))
            if action in NON_LOOP_ACTIONS
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "blind_id": blind_id,
            "arm_guidance": ARM_GUIDANCE[arm],
            "prompt": task["prompt"],
            "workspace_path": str(workspace),
            "visible_files": list_visible_files(workspace),
            "visible_file_contents": visible_file_contents(workspace),
            "public_tests": [],
            "allowed_actions": allowed,
            "remaining_iterations": 1,
            "previous_iterations": [],
            "response_contract": {
                "state": "object or string describing current answer/action state",
                "hypothesis": "string",
                "probe_plan": "string",
                "action": {
                    "type": "edit|write_answer|abstain|blocked",
                    "input": "object",
                },
            },
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "blind_id": blind_id,
        "arm_guidance": ARM_GUIDANCE[arm],
        "prompt": task["prompt"],
        "workspace_path": str(workspace),
        "visible_files": list_visible_files(workspace),
        "public_tests": [
            {
                "id": test_id,
                "description": str(test.get("description", "")),
            }
            for test_id, test in sorted(public_tests_by_id(task).items())
        ],
        "allowed_actions": task["budgets"].get("allowed_actions", list(DEFAULT_ALLOWED_ACTIONS)),
        "remaining_iterations": remaining_iterations,
        "previous_iterations": iterations,
        "response_contract": {
            "state": "object or string describing current answer/action state",
            "hypothesis": "string",
            "probe_plan": "string",
            "action": {
                "type": "inspect_file|search|run_public_test|edit|write_answer|abstain|blocked",
                "input": "object",
            },
        },
    }


def parse_solver_output(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"solver did not return JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("solver output must be a JSON object")
    action = data.get("action")
    if not isinstance(action, dict):
        raise ValueError("solver output.action must be an object")
    return data


def call_solver_command(command: list[str], request: dict[str, Any], workspace: Path, timeout: float) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(workspace),
        input=json.dumps(request, sort_keys=True),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"solver failed exit={proc.returncode}: {bounded_text(proc.stderr, 1000)}")
    return parse_solver_output(proc.stdout)


def demo_solver_response(request: dict[str, Any]) -> dict[str, Any]:
    arm_guidance = str(request.get("arm_guidance", ""))
    previous = request.get("previous_iterations")
    previous_iterations = previous if isinstance(previous, list) else []
    if "observe-act-validate loop" not in arm_guidance:
        return {
            "state": {"answer": "claim visible check is enough"},
            "hypothesis": "Visible context is enough.",
            "probe_plan": "No additional probe.",
            "action": {
                "type": "write_answer",
                "input": {"answer": "The task is complete based on visible checks.", "claimed_success": True},
            },
        }
    if not previous_iterations:
        return {
            "state": {"answer": "need public probe before claiming success"},
            "hypothesis": "The visible file may hide a validator requirement.",
            "probe_plan": "Run the public probe first.",
            "action": {"type": "run_public_test", "input": {"test_id": "visible-check"}},
        }
    first = previous_iterations[0]
    observation = first.get("observation") if isinstance(first, dict) else {}
    failed = isinstance(observation, dict) and observation.get("source") == "test_failure"
    if failed and len(previous_iterations) == 1:
        return {
            "state": {"answer": "public probe exposed missing fix; edit file"},
            "hypothesis": "The file must contain the hidden-ready marker.",
            "probe_plan": "Patch the visible file.",
            "action": {"type": "edit", "input": {"path": "app.txt", "content": "status=fixed\n"}},
        }
    return {
        "state": {"answer": "patched after external probe"},
        "hypothesis": "The public failure has been addressed.",
        "probe_plan": "Finalize with the validator-backed state.",
        "action": {
            "type": "write_answer",
            "input": {"answer": "Patched app.txt after the public test exposed the issue.", "claimed_success": True},
        },
    }


def run_one(
    task: dict[str, Any],
    arm: str,
    blind_id: str,
    workspace: Path,
    request_dir: Path,
    solver_command: list[str] | None,
    use_demo_solver: bool,
    fail_fast: bool,
) -> dict[str, Any]:
    write_workspace(task, workspace)
    max_iterations = as_int(task["budgets"].get("max_iterations"), 1)
    if arm == "non_loop_control":
        max_iterations = 1
    timeout = as_float(task["budgets"].get("max_elapsed_seconds"), 60.0)
    if arm == "non_loop_control":
        allowed_actions = {
            action for action in task["budgets"].get("allowed_actions", list(DEFAULT_ALLOWED_ACTIONS)) if action in NON_LOOP_ACTIONS
        }
    else:
        allowed_actions = set(task["budgets"].get("allowed_actions", list(DEFAULT_ALLOWED_ACTIONS)))
    iterations: list[dict[str, Any]] = []
    final: dict[str, Any] | None = None
    solver_error: str | None = None
    total_prompt_tokens: int | None = 0
    total_completion_tokens: int | None = 0
    total_elapsed_seconds: float | None = 0.0
    total_cost_estimate: float | None = 0.0
    telemetry_observed = False
    telemetry_missing = False
    token_usage_sources: set[str] = set()
    token_usage_split_measured: bool | None = None

    for index in range(1, max_iterations + 1):
        request = solver_request(task, blind_id, arm, workspace, iterations, max_iterations - index + 1)
        write_json(request_dir / f"{blind_id}-{index:02d}.json", request)
        try:
            response = demo_solver_response(request) if use_demo_solver else call_solver_command(
                solver_command or [], request, workspace, timeout
            )
        except Exception as exc:  # noqa: BLE001 - isolate per-run solver failures.
            solver_error = str(exc)
            if fail_fast:
                raise
            telemetry_missing = True
            total_prompt_tokens = None
            total_completion_tokens = None
            total_elapsed_seconds = None
            total_cost_estimate = None
            token_usage_split_measured = None
            final = {"claimed_success": False, "answer": solver_error, "stop_reason": "solver_error"}
            break

        telemetry = response.get("_solver_telemetry") if isinstance(response.get("_solver_telemetry"), dict) else None
        if telemetry is None:
            telemetry_missing = True
            total_prompt_tokens = None
            total_completion_tokens = None
            total_elapsed_seconds = None
            total_cost_estimate = None
            token_usage_split_measured = None
        else:
            telemetry_observed = True
            tokens_used = optional_int(telemetry.get("tokens_used"))
            prompt_tokens = optional_int(telemetry.get("prompt_tokens"))
            completion_tokens = optional_int(telemetry.get("completion_tokens"))
            elapsed_seconds = optional_float(telemetry.get("elapsed_seconds"))
            cost_estimate = optional_float(telemetry.get("cost_estimate"))
            source = telemetry.get("token_usage_source")
            token_source = source if isinstance(source, str) and source.strip() else None
            split_measured = prompt_tokens is not None and completion_tokens is not None
            if prompt_tokens is None and tokens_used is not None:
                prompt_tokens = tokens_used
                token_source = token_source or "total_tokens_as_prompt_proxy"
                split_measured = False
            if completion_tokens is None and tokens_used is not None:
                completion_tokens = 0
                token_source = token_source or "total_tokens_as_prompt_proxy"
                split_measured = False
            if token_source is None and split_measured:
                token_source = "solver_reported_prompt_completion_tokens"
            if token_source is None or prompt_tokens is None or completion_tokens is None or elapsed_seconds is None or cost_estimate is None:
                telemetry_missing = True
            else:
                token_usage_sources.add(token_source)
                if "total_tokens_as_prompt_proxy" in token_source:
                    split_measured = False
                token_usage_split_measured = (
                    split_measured
                    if token_usage_split_measured is None
                    else token_usage_split_measured and split_measured
                )
            total_prompt_tokens = (
                None if total_prompt_tokens is None or prompt_tokens is None else total_prompt_tokens + prompt_tokens
            )
            total_completion_tokens = (
                None
                if total_completion_tokens is None or completion_tokens is None
                else total_completion_tokens + completion_tokens
            )
            total_elapsed_seconds = (
                None
                if total_elapsed_seconds is None or elapsed_seconds is None
                else total_elapsed_seconds + elapsed_seconds
            )
            total_cost_estimate = (
                None
                if total_cost_estimate is None or cost_estimate is None
                else total_cost_estimate + cost_estimate
            )
        if iterations and "post_state" not in iterations[-1]:
            iterations[-1]["post_state"] = response.get("state", response.get("action", {}))
        action = response.get("action") if isinstance(response.get("action"), dict) else {}
        observation, done, action_final = execute_action(action, workspace, task, allowed_actions, timeout)
        record = {
            "index": index,
            "state_summary": response.get("state", ""),
            "hypothesis": str(response.get("hypothesis", "")),
            "probe_plan": str(response.get("probe_plan", "")),
            "pre_state": response.get("state", {}),
            "action": action,
            "observation": observation,
            "failure_class": str(response.get("failure_class", "none")),
            "next_decision": "finalize" if done else "continue",
        }
        iterations.append(record)
        if done:
            final = action_final or {"claimed_success": False, "answer": "", "stop_reason": "blocked"}
            iterations[-1]["post_state"] = {"final": final}
            break
        if arm == "non_loop_control":
            final = {
                "claimed_success": False,
                "answer": "non-loop baseline action executed without controller feedback",
                "stop_reason": "non_loop_action_limit",
            }
            iterations[-1]["post_state"] = {"final": final}
            break
    if final is None:
        final = {"claimed_success": False, "answer": "iteration budget exhausted", "stop_reason": "budget_exhausted"}
    if telemetry_missing or not telemetry_observed:
        total_prompt_tokens = None
        total_completion_tokens = None
        total_elapsed_seconds = None
        total_cost_estimate = None
        token_usage_source = None
        token_usage_split_measured = None
    elif len(token_usage_sources) == 1:
        token_usage_source = next(iter(token_usage_sources))
    else:
        token_usage_source = "mixed:" + ",".join(sorted(token_usage_sources))
    return {
        "schema_version": SCHEMA_VERSION,
        "blind_id": blind_id,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "elapsed_seconds": total_elapsed_seconds,
        "cost_estimate": total_cost_estimate,
        "token_usage_source": token_usage_source,
        "token_usage_split_measured": token_usage_split_measured,
        "iterations": iterations,
        "final": final,
        "solver_error": solver_error,
    }


def run_tasks(args: argparse.Namespace) -> int:
    tasks = validate_tasks(read_jsonl(args.tasks))
    if not args.demo_solver and not args.solver_command:
        raise SystemExit("--solver-command is required unless --demo-solver is set")
    command = args.solver_command
    output = args.output
    traces: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    judge_rows: list[dict[str, Any]] = []

    arms = ARMS + (OPTIONAL_BASELINE_ARMS if args.include_non_loop_baseline else ())
    for task in tasks:
        for arm in arms:
            blind_id = stable_id(args.seed, task["task_id"], arm)
            workspace = output / "workspaces" / blind_id
            key_rows.append(
                {
                    "blind_id": blind_id,
                    "task_id": task["task_id"],
                    "arm": arm,
                    "polarity": task["polarity"],
                    "family": task["family"],
                    "budgets": task["budgets"],
                    "workspace_path": str(workspace.relative_to(output)),
                }
            )
            judge_rows.append(
                {
                    "blind_id": blind_id,
                    "task_id": task["task_id"],
                    "arm": arm,
                    "polarity": task["polarity"],
                    "family": task["family"],
                    "workspace_path": str(workspace.relative_to(output)),
                    "hidden_validators": task["hidden_validators"],
                }
            )
            try:
                traces.append(
                    run_one(
                        task,
                        arm,
                        blind_id,
                        workspace,
                        output / "requests",
                        command,
                        args.demo_solver,
                        args.fail_fast,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - fail-fast path reports the run.
                raise SystemExit(f"{task['task_id']}/{arm} failed: {exc}") from None

    write_json(output / "blind_key.json", {"rows": key_rows})
    write_jsonl(output / "judge_manifest.jsonl", judge_rows)
    write_jsonl(output / "traces.jsonl", traces)
    write_json(
        output / "run_manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "tasks": str(args.tasks),
            "seed": args.seed,
            "arms": list(arms),
            "hidden_validator_isolation": "hidden validator specs are written only to judge_manifest.jsonl, not workspaces or solver requests",
        },
    )
    print(f"wrote agentic loop run: {output}")
    return 0


def run_hidden_validators(args: argparse.Namespace) -> int:
    rows = read_jsonl(args.judge_manifest)
    verdicts: list[dict[str, Any]] = []
    for row in rows:
        blind_id = require_text(row, "blind_id", "judge")
        workspace = args.run_dir / str(row.get("workspace_path", ""))
        validators = row.get("hidden_validators") if isinstance(row.get("hidden_validators"), list) else []
        passed_all = True
        details: list[dict[str, Any]] = []
        for validator in validators:
            if not isinstance(validator, dict):
                continue
            validator_id = str(validator.get("id", "validator"))
            command = command_from_spec(validator.get("command"))
            result = run_command(command, workspace, as_float(validator.get("timeout_seconds"), args.timeout))
            passed = result["returncode"] == 0 and not result["timed_out"]
            passed_all = passed_all and passed
            details.append({"id": validator_id, "passed": passed, "result": result})
        verdicts.append(
            {
                "blind_id": blind_id,
                "verified_pass": passed_all,
                "quality_score": 1.0 if passed_all else 0.0,
                "validator": "agentic_loop_hidden_validator_v1",
                "details": details,
            }
        )
    write_jsonl(args.output, verdicts)
    print(f"wrote hidden verdicts: {args.output}")
    return 0


def demo_tasks(args: argparse.Namespace) -> int:
    row = {
        "task_id": "agentic-demo-hidden-validator-001",
        "polarity": "positive",
        "family": "agentic_coding",
        "prompt": "Fix app.txt. Visible checks are incomplete; do not claim success without a probe.",
        "visible_files": {"app.txt": "status=broken\n"},
        "public_tests": [
            {
                "id": "visible-check",
                "description": "Fails until app.txt is fixed.",
                "command": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; raise SystemExit(0 if 'status=fixed' in Path('app.txt').read_text() else 1)",
                ],
                "timeout_seconds": 5,
            }
        ],
        "hidden_validators": [
            {
                "id": "hidden-final",
                "command": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; raise SystemExit(0 if Path('app.txt').read_text().strip() == 'status=fixed' else 1)",
                ],
                "timeout_seconds": 5,
            }
        ],
        "budgets": {
            "max_iterations": 3,
            "max_prompt_tokens": 5000,
            "max_completion_tokens": 2000,
            "max_elapsed_seconds": 60,
            "max_cost_estimate": 0.05,
            "allowed_actions": list(DEFAULT_ALLOWED_ACTIONS),
        },
    }
    write_jsonl(args.output, [row])
    print(f"wrote demo tasks: {args.output}")
    return 0


def demo_agent(args: argparse.Namespace) -> int:
    request = json.loads(sys.stdin.read())
    response = demo_solver_response(request)
    print(json.dumps(response, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run controlled Agentic Loop workspaces.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_tasks_parser = subparsers.add_parser("demo-tasks", help="write deterministic demo task JSONL")
    demo_tasks_parser.add_argument("--output", required=True, type=Path)
    demo_tasks_parser.set_defaults(func=demo_tasks)

    demo_agent_parser = subparsers.add_parser("demo-agent", help="stdin/stdout deterministic demo solver")
    demo_agent_parser.set_defaults(func=demo_agent)

    run_parser = subparsers.add_parser("run", help="run solver through controlled workspaces")
    run_parser.add_argument("--tasks", required=True, type=Path)
    run_parser.add_argument("--output", required=True, type=Path)
    run_parser.add_argument("--seed", type=int, default=20260619)
    run_parser.add_argument("--solver-command", nargs=argparse.REMAINDER)
    run_parser.add_argument("--demo-solver", action="store_true")
    run_parser.add_argument("--fail-fast", action="store_true")
    run_parser.add_argument(
        "--include-non-loop-baseline",
        action="store_true",
        help="also run the diagnostic one-shot visible-context baseline arm",
    )
    run_parser.set_defaults(func=run_tasks)

    hidden_parser = subparsers.add_parser("run-hidden-validators", help="run trusted hidden validators after solving")
    hidden_parser.add_argument("--run-dir", required=True, type=Path)
    hidden_parser.add_argument("--judge-manifest", required=True, type=Path)
    hidden_parser.add_argument("--output", required=True, type=Path)
    hidden_parser.add_argument("--timeout", type=float, default=30.0)
    hidden_parser.set_defaults(func=run_hidden_validators)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
