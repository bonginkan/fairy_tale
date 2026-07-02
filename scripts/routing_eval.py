"""Routing-precision eval for the post-#57 Fairy Tale router (issue #59).

Measures whether the slimmed router SKILL.md still routes requests to the
right mode-pattern card(s) — the "lighter but not broken" parity evidence for
issue #57 and scoreboard data for #13.

Three modes:
  --validate   schema/distribution/leakage checks on the fixture file (CI-safe)
  --selftest   red-lock tests for the validator, response parser, and judge
               (CI-safe; no LLM calls)
  --run        manual LLM run: one isolated `claude -p` call per case with the
               CURRENT repo router SKILL.md injected; writes a ledger JSON.

Judgement is exact set comparison. Partial multi-card matches are never green.
`expected_cards: []` (negative control) with any card in the output = overfire.
Missing expected cards = underfire. The runner prompt contains ONLY the case
prompt and the router instruction — never expected_cards, rationale, category,
or risk_tag (leakage is validated as RED).

The LLM run is intentionally NOT wired into CI: it is nondeterministic and
requires credentials. CI pins --validate and --selftest only.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "fairy-tale"
SKILL_MD = SKILL_DIR / "SKILL.md"
CASES_PATH = REPO_ROOT / "fixtures" / "routing-eval" / "cases.jsonl"

CARD_PATH_RE = re.compile(r"^references/cards/[a-z0-9][a-z0-9-]*\.md$")
REQUIRED_FIELDS = {
    "id": str,
    "category": str,
    "prompt": str,
    "expected_cards": list,
    "rationale": str,
    "risk_tag": str,
    "negative_control": bool,
}
REQUIRED_CATEGORIES = (
    "divergent_generation",
    "plain_conversation",
    "review_contrast",
    "review_refactor",
    "loop_spiral",
    "e2e_gui",
    "legal_closed",
    "wwcd_relay",
)
MIN_CASES = 24
MIN_NEGATIVE_CONTROLS = 6
MIN_CONTRAST_PAIRS = 2
MIN_SINGLE_CARD = 8
MIN_MULTI_CARD = 1

# Substrings that must never appear in a case prompt (answer leakage).
# All schema field names are markers: a prompt carrying "category:" or
# "rationale:" style labels would hand the solver judge-side metadata.
LEAK_MARKERS = (
    "expected_cards",
    "references/cards/",
    "risk_tag",
    "negative_control",
    "category",
    "rationale",
)

ROUTER_INSTRUCTION = (
    "You are the routing layer for the Fairy Tale skill. The full skill text "
    "(router) follows between <fairy_tale_router> tags. Given the user "
    "request, decide which mode-pattern card file(s) the router would load "
    "for it, or none if no card should fire (e.g. plain conversation or a "
    "workflow-less simple divergent-generation request under the scope "
    "gate).\n"
    "Respond with ONLY a JSON object, no prose, no code fence:\n"
    '{"cards": ["references/cards/<slug>.md", ...]}\n'
    "Use an empty array when no card should fire. Card paths must be copied "
    "exactly from the router text.\n"
    "<fairy_tale_router>\n{skill}\n</fairy_tale_router>"
)

STRIP_ENV = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_CHILD_SESSION",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_EXECPATH",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_cases(raw_lines: list[str], skill_dir: Path) -> tuple[list[dict], list[str]]:
    """Return (cases, errors). Any error means RED."""
    errors: list[str] = []
    cases: list[dict] = []
    seen_ids: set[str] = set()
    for lineno, line in enumerate(raw_lines, start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON ({exc})")
            continue
        if not isinstance(case, dict):
            errors.append(f"line {lineno}: not an object")
            continue
        missing = [k for k in REQUIRED_FIELDS if k not in case]
        extra = [k for k in case if k not in REQUIRED_FIELDS]
        if missing:
            errors.append(f"line {lineno}: missing field(s) {missing}")
            continue
        if extra:
            errors.append(f"line {lineno}: unknown field(s) {extra}")
            continue
        bad_type = [
            k for k, t in REQUIRED_FIELDS.items() if not isinstance(case[k], t)
        ]
        if bad_type:
            errors.append(f"line {lineno}: wrong type for {bad_type}")
            continue
        cid = case["id"]
        if cid in seen_ids:
            errors.append(f"line {lineno}: duplicate id {cid!r}")
            continue
        seen_ids.add(cid)
        for field in ("id", "category", "prompt", "rationale", "risk_tag"):
            if not case[field].strip():
                errors.append(f"case {cid}: empty {field}")
        expected = case["expected_cards"]
        if len(expected) != len(set(expected)):
            errors.append(f"case {cid}: duplicate entries in expected_cards")
        for card in expected:
            if not isinstance(card, str):
                errors.append(f"case {cid}: non-string card entry")
                continue
            if not CARD_PATH_RE.match(card):
                errors.append(
                    f"case {cid}: invalid card path {card!r} (must be "
                    "repo-relative references/cards/<slug>.md)"
                )
                continue
            if not (skill_dir / card).is_file():
                errors.append(f"case {cid}: card path does not exist: {card}")
        if case["negative_control"] != (len(expected) == 0):
            errors.append(
                f"case {cid}: negative_control must be true iff expected_cards is empty"
            )
        prompt = case["prompt"]
        for marker in LEAK_MARKERS:
            if marker in prompt:
                errors.append(f"case {cid}: answer leakage — prompt contains {marker!r}")
        if case["rationale"].strip() and case["rationale"].strip() in prompt:
            errors.append(f"case {cid}: answer leakage — prompt contains the rationale")
        cases.append(case)
    return cases, errors


def validate_distribution(cases: list[dict]) -> list[str]:
    errors: list[str] = []
    if len(cases) < MIN_CASES:
        errors.append(f"only {len(cases)} cases; minimum is {MIN_CASES}")
    negatives = [c for c in cases if c["negative_control"]]
    if len(negatives) < MIN_NEGATIVE_CONTROLS:
        errors.append(
            f"only {len(negatives)} negative controls; minimum is {MIN_NEGATIVE_CONTROLS}"
        )
    categories = {c["category"] for c in cases}
    for cat in REQUIRED_CATEGORIES:
        if cat not in categories:
            errors.append(f"required category missing: {cat}")
    singles = [c for c in cases if len(c["expected_cards"]) == 1]
    multis = [c for c in cases if len(c["expected_cards"]) > 1]
    if len(singles) < MIN_SINGLE_CARD:
        errors.append(f"only {len(singles)} single-card cases; minimum is {MIN_SINGLE_CARD}")
    if len(multis) < MIN_MULTI_CARD:
        errors.append(f"only {len(multis)} multi-card cases; minimum is {MIN_MULTI_CARD}")
    by_id = {c["id"]: c for c in cases}
    contrasts = [c for c in cases if c["category"] == "review_contrast"]
    if len(contrasts) < MIN_CONTRAST_PAIRS:
        errors.append(
            f"only {len(contrasts)} review_contrast cases; minimum is {MIN_CONTRAST_PAIRS}"
        )
    for c in contrasts:
        base_id = c["id"].removesuffix("-review")
        base = by_id.get(base_id)
        if c["id"] == base_id or base is None:
            errors.append(
                f"contrast case {c['id']}: no paired base case {base_id!r} "
                "(contrast ids must be <base-id>-review)"
            )
        elif not base["negative_control"]:
            errors.append(
                f"contrast case {c['id']}: paired base {base_id} must be a negative control"
            )
        if not c["expected_cards"]:
            errors.append(f"contrast case {c['id']}: must expect at least one card")
    return errors


# ---------------------------------------------------------------------------
# Response parsing and judging
# ---------------------------------------------------------------------------

def parse_routing_response(text: str) -> tuple[list[str] | None, str | None]:
    """Return (cards, error). Strict JSON; a stray code fence is tolerated."""
    body = text.strip()
    if body.startswith("```"):
        body = re.sub(r"^```[a-zA-Z]*\n", "", body)
        body = re.sub(r"\n```$", "", body.strip())
    try:
        obj = json.loads(body)
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc}"
    if not isinstance(obj, dict) or "cards" not in obj:
        return None, "schema violation: top-level object with 'cards' required"
    cards = obj["cards"]
    if not isinstance(cards, list) or not all(isinstance(c, str) for c in cards):
        return None, "schema violation: 'cards' must be a list of strings"
    return cards, None


def judge_case(expected: list[str], cards: list[str] | None, parse_error: str | None) -> dict:
    """Exact set comparison; partial matches never pass."""
    if parse_error is not None:
        return {
            "pass": False,
            "classification": "invalid_output",
            "overfire": False,
            "underfire": False,
            "invalid_paths": [],
            "parse_error": parse_error,
        }
    assert cards is not None
    got = set(cards)
    want = set(expected)
    invalid_paths = sorted(c for c in got if not CARD_PATH_RE.match(c))
    extra = sorted(got - want)
    missing = sorted(want - got)
    passed = not extra and not missing and not invalid_paths
    if passed:
        classification = "pass"
    elif extra and missing:
        classification = "overfire+underfire"
    elif extra:
        classification = "overfire"
    elif missing:
        classification = "underfire"
    else:
        classification = "invalid_output"
    return {
        "pass": passed,
        "classification": classification,
        "overfire": bool(extra),
        "underfire": bool(missing),
        "extra_cards": extra,
        "missing_cards": missing,
        "invalid_paths": invalid_paths,
        "parse_error": None,
    }


# ---------------------------------------------------------------------------
# LLM run
# ---------------------------------------------------------------------------

def run_one_case(case: dict, system_prompt_file: Path, model: str, timeout: float) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    cmd = [
        "claude",
        "-p",
        "--model",
        model,
        "--setting-sources",
        "",
        "--tools",
        "",
        "--output-format",
        "json",
        "--append-system-prompt-file",
        str(system_prompt_file),
    ]
    completed = subprocess.run(
        cmd,
        input=case["prompt"],
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    row: dict = {
        "id": case["id"],
        "category": case["category"],
        "expected_cards": case["expected_cards"],
        "exit_code": completed.returncode,
        "tokens": "unavailable",
        "cost_usd": "unavailable",
    }
    if completed.returncode != 0:
        row.update(judge_case(case["expected_cards"], None, f"claude exit {completed.returncode}: {completed.stderr[-300:]}"))
        row["got_cards"] = None
        return row
    try:
        payload = json.loads(completed.stdout)
        result_text = payload.get("result", "")
        usage = payload.get("usage") or {}
        if usage:
            row["tokens"] = {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
                "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
            }
        if payload.get("total_cost_usd") is not None:
            row["cost_usd"] = payload["total_cost_usd"]
    except json.JSONDecodeError:
        result_text = completed.stdout
    cards, parse_error = parse_routing_response(result_text)
    row.update(judge_case(case["expected_cards"], cards, parse_error))
    row["got_cards"] = cards
    return row


def summarize(results: list[dict], cases: list[dict]) -> dict:
    by_cat: dict[str, dict] = {}
    for row in results:
        slot = by_cat.setdefault(row["category"], {"total": 0, "passed": 0})
        slot["total"] += 1
        slot["passed"] += 1 if row["pass"] else 0
    for slot in by_cat.values():
        slot["accuracy"] = round(slot["passed"] / slot["total"], 4) if slot["total"] else None
    utilization: dict[str, int] = {}
    for row in results:
        for card in row.get("got_cards") or []:
            utilization[card] = utilization.get(card, 0) + 1
    negatives = [r for r in results if not r["expected_cards"]]
    contrast_ids = {c["id"] for c in cases if c["category"] == "review_contrast"}
    scope_gate = {
        "negative_controls_total": len(negatives),
        "negative_controls_clean": sum(1 for r in negatives if r["pass"]),
        "contrast_cases_total": len(contrast_ids),
        "contrast_cases_passed": sum(1 for r in results if r["id"] in contrast_ids and r["pass"]),
    }
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["pass"]),
        "accuracy": round(sum(1 for r in results if r["pass"]) / len(results), 4) if results else None,
        "overfire": sum(1 for r in results if r["overfire"]),
        "underfire": sum(1 for r in results if r["underfire"]),
        "invalid_output": sum(1 for r in results if r["classification"] == "invalid_output"),
        "per_category": by_cat,
        "per_card_utilization": dict(sorted(utilization.items())),
        "scope_gate_54_regression": scope_gate,
    }


def cli_version() -> str:
    completed = subprocess.run(
        ["claude", "--version"], text=True, capture_output=True, check=False, timeout=30
    )
    return completed.stdout.strip() or "unavailable"


def git_head(path: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def eval_inputs_dirty() -> list[str]:
    """Uncommitted changes to eval-relevant files; ledger provenance would lie."""
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(REPO_ROOT),
            "status",
            "--porcelain",
            "--",
            "fixtures/routing-eval",
            "scripts/routing_eval.py",
            "skills/fairy-tale/SKILL.md",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def run_eval(args: argparse.Namespace) -> int:
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip():
        print("RED: CLAUDE_CODE_OAUTH_TOKEN is required for --run", file=sys.stderr)
        return 1
    dirty = eval_inputs_dirty()
    if dirty:
        print(
            "RED: eval inputs have uncommitted changes; the ledger's repo_commit "
            "would not contain what actually ran. Commit first:",
            file=sys.stderr,
        )
        for line in dirty:
            print(f"  {line}", file=sys.stderr)
        return 1
    raw = CASES_PATH.read_text(encoding="utf-8")
    cases, errors = validate_cases(raw.splitlines(), SKILL_DIR)
    errors += validate_distribution(cases)
    if errors:
        for err in errors:
            print(f"RED: {err}", file=sys.stderr)
        return 1
    skill_bytes = SKILL_MD.read_bytes()
    system_prompt = ROUTER_INSTRUCTION.replace("{skill}", skill_bytes.decode("utf-8"))
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(system_prompt)
        system_prompt_file = Path(handle.name)
    try:
        results: list[dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(
                    run_one_case, case, system_prompt_file, args.model, args.timeout_seconds
                ): case["id"]
                for case in cases
            }
            for future in concurrent.futures.as_completed(futures):
                row = future.result()
                results.append(row)
                print(
                    f"{row['id']}: {row['classification']}"
                    + (f" got={row.get('got_cards')}" if not row["pass"] else "")
                )
        results.sort(key=lambda r: [c["id"] for c in cases].index(r["id"]))
        ledger = {
            "schema_version": 1,
            "issue": "#59 routing-precision eval (parity evidence for #57)",
            "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds"
            ),
            "model": args.model,
            "claude_cli_version": cli_version(),
            "command": (
                "claude -p --model {model} --setting-sources '' --tools '' "
                "--output-format json --append-system-prompt-file <router-prompt>"
            ).format(model=args.model),
            "system_prompt_sha256": sha256_bytes(system_prompt.encode("utf-8")),
            "skill_md_sha256": sha256_bytes(skill_bytes),
            "cases_sha256": sha256_bytes(raw.encode("utf-8")),
            "repo_commit": git_head(REPO_ROOT),
            "eval_inputs_committed_at_repo_commit": True,
            "isolation": {
                "setting_sources": "",
                "tools": "",
                "stripped_env": list(STRIP_ENV),
                "skill_source": "current repo skills/fairy-tale/SKILL.md injected "
                "verbatim into the appended system prompt; the runner never "
                "reads installed skills",
                "leakage": "user prompt = case prompt only; expected_cards/"
                "rationale/category/risk_tag never leave the judge",
            },
            "run_policy": {
                "runs_per_case": 1,
                "retry": "none",
                "temperature": "claude -p default (not configurable via CLI)",
                "limitation": "single-run point estimate; individual case flips "
                "on rerun are possible — compare suites, not single cases",
            },
            "token_note": "tokens/cost are primary values from the CLI JSON "
            "payload; 'unavailable' is recorded when the CLI did not return "
            "them (never estimated)",
            "results": results,
            "summary": summarize(results, cases),
        }
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(ledger["summary"], indent=2, ensure_ascii=False))
        print(f"ledger written: {out_path}")
        return 0
    finally:
        system_prompt_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Selftest (red-locks)
# ---------------------------------------------------------------------------

def selftest() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool) -> None:
        status = "ok" if condition else "FAIL"
        print(f"  [{status}] {name}")
        if not condition:
            failures.append(name)

    real_card = "references/cards/implementation-validation-gate.md"
    other_card = "references/cards/legal-reasoning-harness.md"

    def case(**overrides) -> str:
        base = {
            "id": "t-1",
            "category": "review_refactor",
            "prompt": "Review this diff.",
            "expected_cards": [real_card],
            "rationale": "review routes to a card",
            "risk_tag": "underfire",
            "negative_control": False,
        }
        base.update(overrides)
        return json.dumps(base, ensure_ascii=False)

    print("validator red-locks:")
    _, errs = validate_cases([case()], SKILL_DIR)
    check("well-formed case is green", not errs)
    _, errs = validate_cases(["{not json"], SKILL_DIR)
    check("malformed JSON line is RED", bool(errs))
    _, errs = validate_cases([case(risk_tag=None)], SKILL_DIR)
    check("wrong field type is RED", bool(errs))
    line = json.loads(case())
    del line["rationale"]
    _, errs = validate_cases([json.dumps(line)], SKILL_DIR)
    check("missing schema field is RED", bool(errs))
    _, errs = validate_cases([case(), case()], SKILL_DIR)
    check("duplicate id is RED", bool(errs))
    _, errs = validate_cases(
        [case(expected_cards=["references/cards/does-not-exist.md"])], SKILL_DIR
    )
    check("nonexistent card path is RED", bool(errs))
    _, errs = validate_cases(
        [case(expected_cards=["/etc/passwd"])], SKILL_DIR
    )
    check("absolute card path is RED", bool(errs))
    _, errs = validate_cases(
        [case(expected_cards=["references/cards/../../SKILL.md"])], SKILL_DIR
    )
    check("traversal card path is RED", bool(errs))
    _, errs = validate_cases([case(negative_control=True)], SKILL_DIR)
    check("negative_control inconsistency is RED", bool(errs))
    _, errs = validate_cases(
        [case(prompt=f"Review this. Answer: {real_card}")], SKILL_DIR
    )
    check("expected-card leakage in prompt is RED", bool(errs))
    _, errs = validate_cases(
        [case(prompt="Review this. review routes to a card")], SKILL_DIR
    )
    check("rationale leakage in prompt is RED", bool(errs))
    _, errs = validate_cases(
        [case(prompt="Review this diff. category: review_refactor")], SKILL_DIR
    )
    check("category label leakage in prompt is RED", bool(errs))
    _, errs = validate_cases(
        [case(prompt="Review this diff. rationale: it should route somewhere")], SKILL_DIR
    )
    check("rationale label leakage in prompt is RED", bool(errs))
    line = json.loads(case())
    line["hint"] = "extra"
    _, errs = validate_cases([json.dumps(line)], SKILL_DIR)
    check("unknown extra field is RED", bool(errs))

    print("distribution red-locks:")
    raw_lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
    cases, errs = validate_cases(raw_lines, SKILL_DIR)
    errs += validate_distribution(cases)
    check("committed fixture set is green", not errs)
    truncated, terrs = validate_cases(raw_lines[:10], SKILL_DIR)
    check("truncated fixture set is RED", bool(validate_distribution(truncated) or terrs))
    no_neg = [c for c in cases if not c["negative_control"]]
    check("fixture without negative controls is RED", bool(validate_distribution(no_neg)))

    print("parser/judge red-locks:")
    cards, err = parse_routing_response(f'{{"cards": ["{real_card}"]}}')
    check("valid JSON output parses", err is None and cards == [real_card])
    cards, err = parse_routing_response(f'```json\n{{"cards": ["{real_card}"]}}\n```')
    check("fenced JSON output parses", err is None and cards == [real_card])
    _, err = parse_routing_response("I would load the validation gate card.")
    check("free-form prose is invalid_output (never green)", err is not None)
    _, err = parse_routing_response('{"card": "x"}')
    check("schema-violating output is invalid_output", err is not None)

    v = judge_case([real_card], [real_card], None)
    check("exact match passes", v["pass"])
    v = judge_case([real_card], [], None)
    check("expected miss = underfire, not pass", not v["pass"] and v["underfire"])
    v = judge_case([real_card], [real_card, other_card], None)
    check("extra card = overfire, not pass", not v["pass"] and v["overfire"])
    v = judge_case([], [other_card], None)
    check("none-case overfire is RED", not v["pass"] and v["overfire"])
    v = judge_case([], [], None)
    check("clean none-case passes", v["pass"])
    v = judge_case([real_card, other_card], [real_card], None)
    check("multi-card partial match is NOT green", not v["pass"] and v["underfire"])
    v = judge_case(
        [real_card, other_card], [other_card, real_card], None
    )
    check("multi-card order-insensitive exact match passes", v["pass"])
    v = judge_case([real_card], ["/etc/passwd"], None)
    check("invalid card path in output is flagged, not pass", not v["pass"] and v["invalid_paths"])
    v = judge_case([real_card], None, "malformed JSON: x")
    check("malformed output judged invalid_output", not v["pass"] and v["classification"] == "invalid_output")

    if failures:
        print(f"SELFTEST RED: {len(failures)} failure(s)")
        return 1
    print("SELFTEST GREEN")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--validate", action="store_true", help="validate the fixture file")
    parser.add_argument("--selftest", action="store_true", help="run judge/validator red-locks")
    parser.add_argument("--run", action="store_true", help="manual LLM eval run")
    parser.add_argument("--model", default="claude-fable-5")
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", default=str(REPO_ROOT / "docs" / "skill-budget" / "routing-eval-ledger.json"))
    args = parser.parse_args()

    if args.selftest:
        return selftest()
    if args.validate:
        raw_lines = CASES_PATH.read_text(encoding="utf-8").splitlines()
        cases, errors = validate_cases(raw_lines, SKILL_DIR)
        errors += validate_distribution(cases)
        if errors:
            for err in errors:
                print(f"RED: {err}", file=sys.stderr)
            return 1
        print(f"GREEN: {len(cases)} cases valid")
        return 0
    if args.run:
        return run_eval(args)
    parser.error("choose one of --validate / --selftest / --run")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
