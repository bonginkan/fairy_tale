#!/usr/bin/env python3
"""Run Fairy Fusion independent reviewer passes and synthesize their findings.

This runner is intentionally OpenRouter-free. It implements the repository's
fusion-style contract: bounded independent reviewer prompts, one synthesis
pass, explicit contradictions, blind spots, and closure actions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_ROLES: dict[str, list[dict[str, Any]]] = {
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


def call_openai(messages: list[dict[str, Any]], model: str, effort: str, timeout: int) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required when --execute is set")
    body: dict[str, Any] = {"model": model, "input": messages}
    if effort and effort != "none":
        body["reasoning"] = {"effort": effort}
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    request_timeout = None if timeout <= 0 else timeout
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {error.code}: {detail}") from error


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
            reviewer_outputs.append(future.result())
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
        "synthesis": {
            "raw_text": synthesis_text,
            "parsed": parse_jsonish(synthesis_text),
            "response_id": synthesis_response.get("id"),
            "elapsed_seconds": round(time.time() - started, 3),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
