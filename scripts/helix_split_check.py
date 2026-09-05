#!/usr/bin/env python3
"""Validate Helix run split records: pace, ordering, sanctioned warps, and attribution.

The record is the clock of one Helix increment, from the directive to the merge
or handover. This validator is authoritative for the semantics the card states:
splits cannot run backwards, only the sanctioned warps validate, a banned
glitch voids the run, a round count past the cap needs a disposition, and an
over-pace run needs its excess attributed. It grants no authority of any kind.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0"
DEFAULT_SAMPLE = ROOT / "examples" / "helix-run-split.json"

TOP_REQUIRED = {
    "schema_version", "run", "clock", "pace", "warps_used", "rounds", "round_cap", "time_sinks", "void",
}
TOP_OPTIONAL = {"round_cap_disposition", "third_round_cause", "role_transfers"}
RUN_REQUIRED = {
    "run_id", "repo", "effort_ref", "category", "size_class", "loop_profile", "implementer", "reviewers",
}
CLOCK_ORDER = (
    "directive_received", "target_located", "contract_closed", "impl_pushed", "review_requested",
)
CLOCK_TAIL = ("signoffs_complete", "validation_read", "finished")
CATEGORIES = ("any_percent_dev", "full_percent_prod", "deliverable")
SIZES = ("small", "medium", "large")
PROFILES = {"two_party": (1, 1), "three_party": (2, None)}
SANCTIONED_WARPS = tuple(f"W{i}" for i in range(1, 11))
BANNED_GLITCHES = (
    "unread_evidence", "stale_signoff", "self_signoff", "skip_ship_validation", "floor_bypass",
    "silence_closure", "scope_shrink",
)
PHASES = (
    "locate", "contract", "implement", "review_wait", "review", "fix", "signoff_wait", "validation",
    "merge", "owner_wait",
)
CAUSES = (
    "reviewer_wait", "owner_wait", "re_verification", "re_derivation", "round_spiral", "ceremony",
    "tool_latency", "scope_growth", "other",
)
TARGET_SOURCES = ("owner", "default", "sum_of_best")
# Defaults the card states; the owner's own target or a recorded sum of best replaces them.
DEFAULT_TARGETS: dict[str, dict[str, int]] = {
    "any_percent_dev": {"small": 60, "medium": 180, "large": 360},
    "deliverable": {"small": 45, "medium": 45, "large": 45},
}
INSTANT_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$"
)
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Finding:
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code, self.path, self.message = code, path, message

    def __str__(self) -> str:
        return f"{self.code} {self.path}: {self.message}"


def parse_instant(value: Any) -> datetime | None:
    """Return the instant, or None when the value is not a real, readable one."""
    if not isinstance(value, str) or not INSTANT_RE.match(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:  # a well-formed string naming a day that does not exist
        return None


def is_int(value: Any) -> bool:
    """A JSON integer. Python's bool is an int subclass and the schema rejects it."""
    return isinstance(value, int) and not isinstance(value, bool)


def load_record(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_record(record: Any) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    verdict: dict[str, Any] = {"verdict": "invalid", "void": False}
    f = findings.append
    if not isinstance(record, dict):
        f(Finding("shape", "$", "record must be an object"))
        return findings, verdict
    keys = set(record)
    for missing in sorted(TOP_REQUIRED - keys):
        f(Finding("missing_key", "$", f"missing {missing}"))
    for extra in sorted(keys - TOP_REQUIRED - TOP_OPTIONAL):
        f(Finding("unknown_key", "$", f"unknown key {extra}"))
    if findings:
        return findings, verdict
    if record["schema_version"] != SCHEMA_VERSION:
        f(Finding("schema_version", "$.schema_version", f"expected {SCHEMA_VERSION}"))

    # run
    run = record["run"]
    if not isinstance(run, dict) or set(run) != RUN_REQUIRED:
        f(Finding("shape", "$.run", f"run must carry exactly {sorted(RUN_REQUIRED)}"))
        return findings, verdict
    if not isinstance(run["run_id"], str) or not run["run_id"].strip():
        f(Finding("shape", "$.run.run_id", "run_id must be non-empty"))
    if not isinstance(run["repo"], str) or not REPO_RE.match(run["repo"]):
        f(Finding("shape", "$.run.repo", "repo must be owner/name"))
    if not isinstance(run["effort_ref"], str) or not run["effort_ref"].startswith("https://"):
        f(Finding("shape", "$.run.effort_ref", "effort_ref must be a canonical https URL"))
    category = run["category"]
    size_class = run["size_class"]
    if not isinstance(category, str) or category not in CATEGORIES:
        f(Finding("enum", "$.run.category", f"must be one of {CATEGORIES}"))
    if not isinstance(size_class, str) or size_class not in SIZES:
        f(Finding("enum", "$.run.size_class", f"must be one of {SIZES}"))
    profile = run["loop_profile"]
    reviewers = run["reviewers"]
    implementer = run["implementer"]
    if not isinstance(profile, str) or profile not in PROFILES:
        f(Finding("enum", "$.run.loop_profile", f"must be one of {tuple(PROFILES)}"))
    if not isinstance(reviewers, list) or not reviewers or not all(
        isinstance(r, str) and r.strip() for r in reviewers
    ):
        f(Finding("shape", "$.run.reviewers", "reviewers must be a non-empty list of names"))
        reviewers = []
    if not isinstance(implementer, str) or not implementer.strip():
        f(Finding("shape", "$.run.implementer", "implementer must be non-empty"))
    if implementer in reviewers:
        f(Finding("self_signoff", "$.run.reviewers", "implementer cannot be a reviewer; the run is void"))
    if len(set(reviewers)) != len(reviewers):
        f(Finding("shape", "$.run.reviewers", "reviewers must be distinct"))
    if isinstance(profile, str) and profile in PROFILES:
        low, high = PROFILES[profile]
        if len(reviewers) < low or (high is not None and len(reviewers) > high):
            f(Finding("profile_reviewers", "$.run.reviewers", f"{profile} expects {low}{'+' if high is None else ''} reviewer(s)"))

    # clock
    clock = record["clock"]
    expected_clock = set(CLOCK_ORDER) | {"findings_returned"} | set(CLOCK_TAIL)
    if not isinstance(clock, dict) or set(clock) != expected_clock:
        f(Finding("shape", "$.clock", f"clock must carry exactly {sorted(expected_clock)}"))
        return findings, verdict
    read: list[tuple[str, datetime]] = []
    for name in CLOCK_ORDER:
        value = clock[name]
        instant = parse_instant(value)
        if instant is not None:
            read.append((name, instant))
        elif value == "not read" and name != "directive_received":
            continue
        elif value == "not applicable" and name == "contract_closed":
            continue
        else:
            f(Finding("instant", f"$.clock.{name}", "must be an ISO instant that was read (or 'not read')"))
    rounds_seen = clock["findings_returned"]
    if not isinstance(rounds_seen, list):
        f(Finding("shape", "$.clock.findings_returned", "must be a list"))
        rounds_seen = []
    for index, entry in enumerate(rounds_seen):
        path = f"$.clock.findings_returned[{index}]"
        if not isinstance(entry, dict) or set(entry) != {"round", "at", "finding_count"}:
            f(Finding("shape", path, "each round carries round, at, finding_count"))
            continue
        if not is_int(entry["round"]) or entry["round"] != index + 1:
            f(Finding("round_order", path, f"round must be the integer {index + 1}"))
        if not is_int(entry["finding_count"]) or entry["finding_count"] < 0:
            f(Finding("shape", f"{path}.finding_count", "must be a non-negative integer"))
        instant = parse_instant(entry["at"])
        if instant is None:
            f(Finding("instant", f"{path}.at", "must be an ISO instant"))
            continue
        read.append((f"findings_returned[{index}]", instant))
    for name in CLOCK_TAIL:
        value = clock[name]
        instant = parse_instant(value)
        if instant is not None:
            read.append((name, instant))
        elif value == "not read" and name != "finished":
            if name == "signoffs_complete":
                f(Finding("signoff_missing", f"$.clock.{name}", "a finished run has its sign-offs read; 'not read' does not finish"))
            continue
        else:
            f(Finding("instant", f"$.clock.{name}", "must be an ISO instant that was read"))
    for (prev_name, prev), (name, current) in zip(read, read[1:]):
        if current < prev:
            f(Finding("split_order", f"$.clock.{name}", f"{name} precedes {prev_name}; splits cannot run backwards"))

    # rounds and cap
    rounds = record["rounds"]
    cap = record["round_cap"]
    if not is_int(rounds) or rounds < 0:
        f(Finding("shape", "$.rounds", "must be a non-negative integer"))
        rounds = len(rounds_seen)
    elif rounds != len(rounds_seen):
        f(Finding("round_count", "$.rounds", f"rounds={rounds} but findings_returned records {len(rounds_seen)}"))
    if not is_int(cap) or cap < 1:
        f(Finding("shape", "$.round_cap", "must be a positive integer"))
        cap = 2
    # W4: a deferral recorded AT the cap is the warp working (the run ends in
    # two rounds with the non-floor findings filed). Only a run that went PAST
    # the cap owes a named cause on top of the disposition refs.
    has_disposition = "round_cap_disposition" in record
    has_cause = "third_round_cause" in record
    disposition = record.get("round_cap_disposition")
    cause = record.get("third_round_cause")
    if has_disposition and (
        not isinstance(disposition, list)
        or not disposition
        or not all(
            isinstance(d, str) and (d.startswith("https://") or d.startswith("tie-break:")) for d in disposition
        )
    ):
        f(Finding("round_cap", "$.round_cap_disposition", "disposition is a non-empty list of issue URLs or tie-break refs"))
    if has_cause and (not isinstance(cause, str) or not cause.strip()):
        f(Finding("round_cap", "$.third_round_cause", "a named cause is non-empty text"))
    if rounds > cap:
        if not has_disposition:
            f(Finding("round_cap", "$.round_cap_disposition", "rounds past the cap need issue URLs or a tie-break ref"))
        if not has_cause:
            f(Finding("round_cap", "$.third_round_cause", "rounds past the cap need a named cause"))
    elif has_cause:
        f(Finding("round_cap", "$.third_round_cause", "a named cause belongs to a run that went past the cap"))

    # warps
    warps = record["warps_used"]
    void_reason: str | None = None
    void_field = record["void"]
    if isinstance(void_field, str) and void_field.strip():
        void_reason = void_field
    elif void_field is not False:
        f(Finding("shape", "$.void", "void is false or a non-empty reason"))
    if not isinstance(warps, list) or not all(isinstance(w, str) for w in warps):
        f(Finding("shape", "$.warps_used", "must be a list of warp ids"))
        warps = []
    if len(set(warps)) != len(warps):
        f(Finding("shape", "$.warps_used", "warp ids must be distinct"))
    for warp in warps:
        if warp in BANNED_GLITCHES:
            if void_reason is None:
                f(Finding("banned_glitch", "$.warps_used", f"{warp} is a banned glitch; the run is void and must say so"))
        elif warp not in SANCTIONED_WARPS:
            f(Finding("unknown_warp", "$.warps_used", f"{warp} is not a sanctioned warp; the owner adds warps, records do not"))
    transfers = record.get("role_transfers")
    if "role_transfers" in record and not isinstance(transfers, list):
        f(Finding("shape", "$.role_transfers", "must be a list of transfers"))
        transfers = []
    if "W5" in warps and not transfers:
        f(Finding("w5_transfer", "$.role_transfers", "W5 names the transfer it made"))
    if transfers and "W5" not in warps:
        f(Finding("w5_transfer", "$.warps_used", "a role transfer is warp W5 and is listed as such"))
    for index, transfer in enumerate(transfers or []):
        path = f"$.role_transfers[{index}]"
        if not isinstance(transfer, dict) or set(transfer) != {"from", "to", "at", "reason"}:
            f(Finding("shape", path, "transfer carries from, to, at, reason"))
        elif parse_instant(transfer["at"]) is None or transfer["from"] == transfer["to"]:
            f(Finding("shape", path, "transfer needs a read instant and distinct parties"))

    # pace
    pace = record["pace"]
    if not isinstance(pace, dict) or not {"target_minutes", "target_source"} <= set(pace) or not set(pace) <= {
        "target_minutes", "target_source", "target_source_ref",
    }:
        f(Finding("shape", "$.pace", "pace carries target_minutes, target_source, optional target_source_ref"))
        return findings, verdict
    target = pace["target_minutes"]
    source = pace["target_source"]
    if not is_int(target) or target < 1:
        f(Finding("shape", "$.pace.target_minutes", "must be a positive integer"))
        target = None
    if source not in TARGET_SOURCES:
        f(Finding("enum", "$.pace.target_source", f"must be one of {TARGET_SOURCES}"))
    elif source == "default":
        expected = (
            DEFAULT_TARGETS.get(category, {}).get(size_class)
            if isinstance(category, str) and isinstance(size_class, str)
            else None
        )
        if expected is None:
            f(Finding("target_source", "$.pace.target_source", f"{category} has no default target; the owner sets it"))
        elif target is not None and target != expected:
            f(Finding("target_source", "$.pace.target_minutes", f"default for {category}/{size_class} is {expected}"))
    elif not isinstance(pace.get("target_source_ref"), str) or not pace["target_source_ref"].strip():
        f(Finding("target_source", "$.pace.target_source_ref", f"{source} target needs its source ref"))

    # time sinks
    sinks = record["time_sinks"]
    attributed = 0
    if not isinstance(sinks, list):
        f(Finding("shape", "$.time_sinks", "must be a list"))
        sinks = []
    for index, sink in enumerate(sinks):
        path = f"$.time_sinks[{index}]"
        if not isinstance(sink, dict) or not {"phase", "cause", "minutes"} <= set(sink) or not set(sink) <= {
            "phase", "cause", "minutes", "note",
        }:
            f(Finding("shape", path, "sink carries phase, cause, minutes, optional note"))
            continue
        if sink["phase"] not in PHASES:
            f(Finding("enum", f"{path}.phase", f"must be one of {PHASES}"))
        if sink["cause"] not in CAUSES:
            f(Finding("enum", f"{path}.cause", f"must be one of {CAUSES}"))
        if not is_int(sink["minutes"]) or sink["minutes"] < 1:
            f(Finding("shape", f"{path}.minutes", "must be a positive integer"))
        else:
            attributed += sink["minutes"]

    start = parse_instant(clock.get("directive_received"))
    end = parse_instant(clock.get("finished"))
    if start is None or end is None or target is None:
        return findings, verdict
    elapsed = int((end - start).total_seconds() // 60)
    excess = max(0, elapsed - target)
    if attributed > elapsed:
        f(Finding("attribution", "$.time_sinks", f"attributed {attributed} minutes exceeds elapsed {elapsed}"))
    if excess > 0 and attributed < excess:
        f(Finding("attribution", "$.time_sinks", f"over pace by {excess} minutes but only {attributed} attributed; name where the time went"))
    verdict = {
        "verdict": "void" if void_reason else ("over_pace" if excess > 0 else "on_pace"),
        "elapsed_minutes": elapsed,
        "target_minutes": target,
        "excess_minutes": excess,
        "attributed_minutes": attributed,
        "rounds": rounds,
        "warps_used": warps,
        "void": void_reason or False,
    }
    return findings, verdict


def command_validate(args: argparse.Namespace) -> int:
    findings, verdict = validate_record(load_record(args.record))
    for finding in findings:
        print(f"FINDING {finding}")
    print("VERDICT " + json.dumps(verdict, sort_keys=True))
    return 1 if findings else 0


def _mutate(record: dict[str, Any], mutate: Any) -> dict[str, Any]:
    clone = copy.deepcopy(record)
    mutate(clone)
    return clone


def selftest() -> int:
    base = load_record(DEFAULT_SAMPLE)
    failures: list[str] = []

    def expect_pass(name: str, record: dict[str, Any], verdict_value: str) -> None:
        findings, verdict = validate_record(record)
        if findings or verdict.get("verdict") != verdict_value:
            failures.append(f"{name}: expected clean {verdict_value}, got {[str(x) for x in findings]} {verdict}")

    def expect_code(name: str, record: dict[str, Any], code: str) -> None:
        findings, _ = validate_record(record)
        if not any(x.code == code for x in findings):
            failures.append(f"{name}: expected finding {code}, got {[str(x) for x in findings]}")

    expect_pass("sample on pace", base, "on_pace")

    def over_pace_attributed(r: dict[str, Any]) -> None:
        r["clock"]["finished"] = "2026-01-01T11:30:00Z"
        r["time_sinks"] = [
            {"phase": "review_wait", "cause": "reviewer_wait", "minutes": 70},
            {"phase": "validation", "cause": "tool_latency", "minutes": 25},
        ]
    expect_pass("over pace with attribution", _mutate(base, over_pace_attributed), "over_pace")

    def three_party_round_three(r: dict[str, Any]) -> None:
        r["run"]["loop_profile"] = "three_party"
        r["run"]["reviewers"] = ["agent-review", "agent-review-2"]
        r["clock"]["findings_returned"].append({"round": 3, "at": "2026-01-01T09:52:00Z", "finding_count": 0})
        r["rounds"] = 3
        r["round_cap_disposition"] = ["https://github.com/example-org/example-repo/issues/9"]
        r["third_round_cause"] = "floor finding on the auth path could not be deferred"
    expect_pass("third round with disposition", _mutate(base, three_party_round_three), "on_pace")

    def w5_with_transfer(r: dict[str, Any]) -> None:
        r["warps_used"].append("W5")
        r["role_transfers"] = [
            {"from": "agent-review", "to": "agent-review-b", "at": "2026-01-01T09:45:00Z", "reason": "hard stall"}
        ]
        r["run"]["reviewers"] = ["agent-review-b"]
    expect_pass("W5 with named transfer", _mutate(base, w5_with_transfer), "on_pace")

    def deferral_at_cap(r: dict[str, Any]) -> None:
        r["clock"]["findings_returned"][1]["finding_count"] = 1
        r["round_cap_disposition"] = ["https://github.com/example-org/example-repo/issues/7"]
    expect_pass("W4 deferral recorded at the cap", _mutate(base, deferral_at_cap), "on_pace")

    def voided(r: dict[str, Any]) -> None:
        r["warps_used"].append("skip_ship_validation")
        r["void"] = "validation on the shipping head was skipped"
    expect_pass("void run says so", _mutate(base, voided), "void")

    def backwards(r: dict[str, Any]) -> None:
        r["clock"]["impl_pushed"] = "2026-01-01T09:02:00Z"
    expect_code("backwards split", _mutate(base, backwards), "split_order")

    def finish_before_signoff(r: dict[str, Any]) -> None:
        r["clock"]["finished"] = "2026-01-01T09:50:00Z"
    expect_code("finish before sign-off", _mutate(base, finish_before_signoff), "split_order")

    def unread_signoff(r: dict[str, Any]) -> None:
        r["clock"]["signoffs_complete"] = "not read"
    expect_code("finished without sign-off read", _mutate(base, unread_signoff), "signoff_missing")

    def banned_not_void(r: dict[str, Any]) -> None:
        r["warps_used"].append("stale_signoff")
    expect_code("banned glitch without void", _mutate(base, banned_not_void), "banned_glitch")

    def unknown_warp(r: dict[str, Any]) -> None:
        r["warps_used"].append("W11")
    expect_code("unknown warp", _mutate(base, unknown_warp), "unknown_warp")

    def over_pace_unattributed(r: dict[str, Any]) -> None:
        r["clock"]["finished"] = "2026-01-01T11:30:00Z"
    expect_code("over pace without attribution", _mutate(base, over_pace_unattributed), "attribution")

    def over_attributed(r: dict[str, Any]) -> None:
        r["time_sinks"] = [{"phase": "review", "cause": "other", "minutes": 500}]
    expect_code("attribution exceeds elapsed", _mutate(base, over_attributed), "attribution")

    def third_round_no_disposition(r: dict[str, Any]) -> None:
        r["clock"]["findings_returned"].append({"round": 3, "at": "2026-01-01T09:52:00Z", "finding_count": 0})
        r["rounds"] = 3
    expect_code("third round without disposition", _mutate(base, third_round_no_disposition), "round_cap")

    def round_count_drift(r: dict[str, Any]) -> None:
        r["rounds"] = 1
    expect_code("round count drift", _mutate(base, round_count_drift), "round_count")

    def self_signoff(r: dict[str, Any]) -> None:
        r["run"]["reviewers"] = ["agent-impl"]
    expect_code("self sign-off", _mutate(base, self_signoff), "self_signoff")

    def profile_mismatch(r: dict[str, Any]) -> None:
        r["run"]["reviewers"] = ["a", "b"]
    expect_code("two-party with two reviewers", _mutate(base, profile_mismatch), "profile_reviewers")

    def prod_default(r: dict[str, Any]) -> None:
        r["run"]["category"] = "full_percent_prod"
    expect_code("prod has no default target", _mutate(base, prod_default), "target_source")

    def wrong_default(r: dict[str, Any]) -> None:
        r["pace"]["target_minutes"] = 600
    expect_code("default target drift", _mutate(base, wrong_default), "target_source")

    def owner_without_ref(r: dict[str, Any]) -> None:
        r["pace"]["target_source"] = "owner"
    expect_code("owner target without ref", _mutate(base, owner_without_ref), "target_source")

    def w5_without_transfer(r: dict[str, Any]) -> None:
        r["warps_used"].append("W5")
    expect_code("W5 without transfer", _mutate(base, w5_without_transfer), "w5_transfer")

    def cause_without_excess(r: dict[str, Any]) -> None:
        r["third_round_cause"] = "none"
    expect_code("cause without a third round", _mutate(base, cause_without_excess), "round_cap")

    def transfers_not_a_list(r: dict[str, Any]) -> None:
        r["role_transfers"] = 0
    expect_code("role_transfers is not a list", _mutate(base, transfers_not_a_list), "shape")

    def boolean_minutes(r: dict[str, Any]) -> None:
        r["time_sinks"][0]["minutes"] = True
    expect_code("boolean minutes", _mutate(base, boolean_minutes), "shape")

    def impossible_date(r: dict[str, Any]) -> None:
        r["clock"]["finished"] = "2026-02-30T09:00:00Z"
    expect_code("well-formed impossible date", _mutate(base, impossible_date), "instant")

    def profile_not_a_string(r: dict[str, Any]) -> None:
        r["run"]["loop_profile"] = []
    expect_code("loop_profile is not a string", _mutate(base, profile_not_a_string), "enum")

    def category_not_a_string(r: dict[str, Any]) -> None:
        r["run"]["category"] = []
    expect_code("category is not a string", _mutate(base, category_not_a_string), "enum")

    def unknown_key(r: dict[str, Any]) -> None:
        r["deadline"] = "2026-01-01T10:00:00Z"
    expect_code("unknown key", _mutate(base, unknown_key), "unknown_key")

    for failure in failures:
        print(f"SELFTEST FAIL {failure}")
    total = 28
    print(f"helix split self-controls: {total - len(failures)}/{total} passed")
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run the hostile self-controls")
    sub = parser.add_subparsers(dest="command")
    validate = sub.add_parser("validate", help="validate one Helix run split record")
    validate.add_argument("--record", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.command == "validate":
        return command_validate(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
