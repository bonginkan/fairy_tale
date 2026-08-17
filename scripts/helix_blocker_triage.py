#!/usr/bin/env python3
"""Validate and render risk-aware Helix blocker triage records."""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import math
import re
import sys
import tempfile
from datetime import datetime, timezone
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
        unknown_keys,
        valid_id,
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
        unknown_keys,
        valid_id,
        write_text_atomic,
    )


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.2"
# The persisted contract records already written against the previous version.
# They stay readable through `migrate`, which upgrades them without inventing
# evidence the original record never carried.
MIGRATABLE_SCHEMA_VERSION = "1.1"
# 1.0 records still upgrade, chained 1.0 -> 1.1 -> 1.2, because the previous
# release promised persisted records upgrade rather than expire.
MIGRATABLE_SCHEMA_VERSIONS = ("1.0", "1.1")
DEFAULT_SAMPLE = ROOT / "examples" / "helix-blocker-triage.json"
MAX_DEFERRABLE_RISK_SCORE = 60
# Edison Ship Gate: a dev-stage increment with a verified normal path buys a
# wider defer envelope, never a weaker floor. The cap still exists so a
# dev deploy cannot absorb an arbitrarily probable severe failure.
DEV_MAX_DEFERRABLE_RISK_SCORE = 200
FRESH_USAGE_MINUTES = 60
DEADLINE_RESERVE_MINUTES = 24 * 60

TOP_KEYS = {
    "schema_version",
    "artifact_type",
    "loop",
    "blockers",
    "final_readback",
}
LOOP_KEYS = {
    "loop_id",
    "repo",
    "artifact_ref",
    "exact_head",
    "evaluated_at",
    "roles",
    "deadline",
    "usage",
    "ship_stage",
    "target",
    "claim_envelope",
    "working_branch",
    "priority_authority",
}
SHIP_STAGE_KEYS = {"stage", "basis", "basis_ref", "happy_path", "evidence_attestation"}
HAPPY_PATH_KEYS = {"verified", "check_ref", "summary"}
SHIP_ATTESTATION_KEYS = {"reviewer_id", "evidence_refs"}
SHIP_DECISION_KEYS = {"decision", "rationale"}
ROLE_KEYS = {"implementer_id", "reviewer_ids", "priority_reviewer_id"}
DEADLINE_KEYS = {
    "at",
    "source",
    "source_ref",
    "clock_readings",
    "minimum_shape",
    "source_pin",
}
USAGE_KEYS = {
    "primary_5h_remaining",
    "secondary_weekly_remaining",
    "status",
    "source",
    "source_ref",
    "observed_at",
}
BLOCKER_KEYS = {
    "id",
    "summary",
    "failure_sequence",
    "preconditions",
    "probability_percent",
    "impact",
    "risk_rationale",
    "finding_class",
    "protected_floor",
    "floor_basis",
    "estimated_fix_minutes",
    "evidence_refs",
    "finding_reviewer",
    "objection",
    "resolution",
}
FINDING_REVIEWER_KEYS = {"reviewer_id", "finding_ref"}
OBJECTION_KEYS = {
    "implementer_id",
    "refuted_claim",
    "rationale",
    "evidence_refs",
    "rebuttal",
    "tie_break",
}
REBUTTAL_KEYS = {"reviewer_id", "outcome", "rationale", "evidence_refs"}
TIE_BREAK_KEYS = {"reviewer_id", "outcome", "rationale", "evidence_refs"}
RESOLUTION_KEYS = {
    "disposition",
    "priority",
    "rationale",
    "concurred_by",
    "issue_url",
    "human_report",
}
HUMAN_REPORT_KEYS = {
    "audience",
    "reported",
    "summary",
    "report_ref",
}
READBACK_KEYS = {
    "deferred_blocker_ids",
    "retained_blocker_ids",
    "not_blocker_ids",
    "reported_to_human",
    "report_ref",
    "ship_decision",
}

IMPACTS = {"negligible", "low", "medium", "high", "critical"}
IMPACT_WEIGHTS = {
    "negligible": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}
PROTECTED_FLOORS = {
    "none",
    "secret_credential",
    "data_loss",
    "production",
    "authority_permission",
    "security",
    "required_acceptance",
    "unapproved_branch_change",
}
FLOOR_BASES = {"not_applicable", "demonstrated", "precautionary"}
FINDING_CLASSES = {"happy_path", "abnormal_path", "hardening", "other"}
SHIP_STAGES = {"production", "dev_deploy"}
SHIP_BASES = {
    "production_promotion",
    "owner_directive",
    "non_production_target",
    "early_development",
}
DEV_SHIP_BASES = SHIP_BASES - {"production_promotion"}
SHIP_DECISIONS = {"go", "hold"}
# The only floor a dev-stage ship may defer, and only when no reachable
# failure sequence has been demonstrated against the deployed surface.
DEV_DEFERRABLE_FLOORS = {"security"}
# Unconditional floor values: no demonstrated reach is required to raise them and
# no level of concurrence defers them. Their only exits are a cited owner
# approval or returning to the recorded branch and consolidating.
NON_DEFERRABLE_FLOORS = {"unapproved_branch_change"}
DEADLINE_SOURCES = {"none", "explicit_owner", "explicit_policy"}
USAGE_STATUSES = {"fresh", "stale", "unknown"}
USAGE_SOURCES = {
    "primary_check",
    "session_owner_observation",
    "self_report",
    "unknown",
}
TRUSTED_USAGE_SOURCES = {"primary_check", "session_owner_observation"}
DISPOSITIONS = {"fix_now", "defer_issue", "not_blocker"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
REBUTTAL_OUTCOMES = {"accept", "reject"}
TIE_BREAK_OUTCOMES = {"sustain_blocker", "accept_objection"}

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ISSUE_RE = re.compile(
    r"^https://github\.com/(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/"
    r"issues/(?P<number>[1-9][0-9]*)$"
)
EVIDENCE_RE = re.compile(
    r"^(?:https://[^\s]+|sha256:[0-9a-f]{64}|"
    r"(?:artifact|check|file|issue|log|receipt|run|source|test|trace|usage):"
    r"[A-Za-z0-9][A-Za-z0-9._/@#:+-]{0,255})$"
)


def add(findings: list[Finding], code: str, message: str) -> None:
    findings.append(Finding(code, message))


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


def unique_text_list(value: Any, *, nonempty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (bool(value) or not nonempty)
        and all(has_text(item) for item in value)
        and len(value) == len(set(value))
    )


def evidence_list(value: Any, *, nonempty: bool = False) -> bool:
    return unique_text_list(value, nonempty=nonempty) and all(
        EVIDENCE_RE.fullmatch(item) for item in value
    )


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def parse_timestamp(value: Any, path: str, findings: list[Finding]) -> datetime | None:
    if not has_text(value):
        add(findings, path, "must be a timezone-qualified timestamp")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        add(findings, path, "must be an ISO 8601 timestamp")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        add(findings, path, "must include a timezone offset")
        return None
    return parsed.astimezone(timezone.utc)


def validate_roles(value: Any, findings: list[Finding]) -> tuple[str | None, list[str]]:
    roles = object_shape(
        value,
        path="helix.loop.roles",
        required=ROLE_KEYS,
        allowed=ROLE_KEYS,
        findings=findings,
    )
    if roles is None:
        return None, []
    implementer = roles.get("implementer_id")
    reviewers = roles.get("reviewer_ids")
    if not valid_id(implementer):
        add(findings, "helix.loop.roles.implementer_id", "implementer_id is malformed")
        implementer = None
    if not unique_text_list(reviewers, nonempty=True) or len(reviewers) < 2:
        add(
            findings,
            "helix.loop.roles.reviewer_ids",
            "reviewer_ids must contain at least two unique ids",
        )
        reviewers = []
    elif not all(valid_id(item) for item in reviewers):
        add(findings, "helix.loop.roles.reviewer_ids", "reviewer id is malformed")
        reviewers = []
    priority_reviewer = roles.get("priority_reviewer_id")
    if priority_reviewer is None:
        # Absent is legitimate: with no owner directive in force the role does
        # not arise. The loop-level authority state decides whether that is
        # consistent, so nothing is reported here.
        pass
    elif not valid_id(priority_reviewer):
        add(
            findings,
            "helix.loop.roles.priority_reviewer_id",
            "priority_reviewer_id is malformed; 'the second reviewer' names nobody "
            "once there are three",
        )
    else:
        if reviewers and priority_reviewer not in reviewers:
            add(
                findings,
                "helix.loop.roles.priority_reviewer_id",
                "priority_reviewer_id must be one of reviewer_ids",
            )
        if implementer is not None and priority_reviewer == implementer:
            add(
                findings,
                "helix.loop.roles.priority_reviewer_id",
                "implementer cannot hold the owner-priority disposition role",
            )
    if implementer is not None and implementer in reviewers:
        add(
            findings,
            "helix.loop.roles.separation",
            "implementer cannot be a registered reviewer",
        )
    return implementer, list(reviewers)


TARGET_KEYS = {
    "repo",
    "path",
    "layer",
    "canonical_owner",
    "directive_refs",
    "propagation_path",
    "duplication_policy",
    "resolved_at",
}
TARGET_REQUIRED = {
    "repo",
    "path",
    "layer",
    "canonical_owner",
    "directive_refs",
    "duplication_policy",
}
DUPLICATION_POLICIES = {"canonical_only", "mirrored_byte_identical", "reference_only"}
PINNED_SOURCE_KEYS = {"ref", "content_hash", "captured_at", "edit_count"}
PINNED_SOURCE_REQUIRED = {"ref", "content_hash", "captured_at"}
CLAIM_ENVELOPE_KEYS = {"baseline_ref", "claim_snapshot_refs"}
WORKING_BRANCH_KEYS = {"name", "fixed_by_ref", "approval_ref", "remedy"}
WORKING_BRANCH_REQUIRED = {"name", "fixed_by_ref"}
BRANCH_REMEDIES = {"none", "approval_produced", "returned_and_consolidated"}
CLOCK_PHASES = {"round_start", "disposition", "ship_decision"}
MINIMUM_SHAPE_KEYS = {"owner_goal_ref", "named_items", "hash", "registered_at"}
CONTENT_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_pinned_source(
    value: Any, path: str, findings: list[Finding]
) -> None:
    """A source that can be edited later is pinned by content, not by ref."""
    shape = object_shape(
        value,
        path=path,
        required=PINNED_SOURCE_REQUIRED,
        allowed=PINNED_SOURCE_KEYS,
        findings=findings,
    )
    if shape is None:
        return
    ref = shape.get("ref")
    if not isinstance(ref, str) or not ref.strip():
        add(findings, f"{path}.ref", "pinned source needs a concrete ref")
    digest = shape.get("content_hash")
    if not isinstance(digest, str) or not CONTENT_HASH_RE.fullmatch(digest):
        add(
            findings,
            f"{path}.content_hash",
            "pinned source needs a sha256 content hash; a ref alone does not fix "
            "bytes that the author can still edit",
        )
    parse_timestamp(shape.get("captured_at"), f"{path}.captured_at", findings)
    edits = shape.get("edit_count")
    # JSON counts 1.0 as an integer, so a stored record can carry a float here.
    # Accepting it keeps this layer from disagreeing with the schema it follows.
    if edits is not None and (
        isinstance(edits, bool)
        or not isinstance(edits, (int, float))
        or (isinstance(edits, float) and not edits.is_integer())
        or edits < 0
    ):
        add(findings, f"{path}.edit_count", "edit_count must be null or a count")


def validate_target(value: Any, findings: list[Finding]) -> None:
    path = "helix.loop.target"
    shape = object_shape(
        value,
        path=path,
        required=TARGET_REQUIRED,
        allowed=TARGET_KEYS,
        findings=findings,
    )
    if shape is None:
        return
    for key in ("repo", "path", "layer", "canonical_owner"):
        field = shape.get(key)
        if not isinstance(field, str) or not field.strip():
            add(findings, f"{path}.{key}", f"target {key} must be recorded")
    refs = shape.get("directive_refs")
    if not isinstance(refs, list) or not refs:
        add(
            findings,
            f"{path}.directive_refs",
            "the target must name the directive it was resolved from",
        )
    else:
        for index, ref in enumerate(refs):
            validate_pinned_source(ref, f"{path}.directive_refs[{index}]", findings)
    policy = shape.get("duplication_policy")
    if policy not in DUPLICATION_POLICIES:
        add(findings, f"{path}.duplication_policy", "duplication policy is invalid")
    trail = shape.get("propagation_path")
    if trail is not None and not unique_text_list(trail, nonempty=True):
        add(findings, f"{path}.propagation_path", "propagation path must be unique refs")
    if shape.get("resolved_at") is not None:
        parse_timestamp(shape.get("resolved_at"), f"{path}.resolved_at", findings)


def validate_claim_envelope(value: Any, findings: list[Finding]) -> None:
    path = "helix.loop.claim_envelope"
    shape = object_shape(
        value,
        path=path,
        required=CLAIM_ENVELOPE_KEYS,
        allowed=CLAIM_ENVELOPE_KEYS,
        findings=findings,
    )
    if shape is None:
        return
    baseline = shape.get("baseline_ref")
    if not isinstance(baseline, str) or not SHA_RE.fullmatch(baseline):
        add(
            findings,
            f"{path}.baseline_ref",
            "baseline_ref must be a commit id, not a movable name: a branch ref "
            "makes the fixed half of the envelope as mutable as the half it is "
            "supposed to anchor",
        )
    refs = shape.get("claim_snapshot_refs")
    if not isinstance(refs, list) or not refs:
        add(
            findings,
            f"{path}.claim_snapshot_refs",
            "the envelope needs the pinned directive or acceptance; judging on "
            "the merge-base half alone drops the other half of the claim",
        )
    else:
        for index, ref in enumerate(refs):
            validate_pinned_source(ref, f"{path}.claim_snapshot_refs[{index}]", findings)


def validate_working_branch(value: Any, findings: list[Finding]) -> None:
    path = "helix.loop.working_branch"
    shape = object_shape(
        value,
        path=path,
        required=WORKING_BRANCH_REQUIRED,
        allowed=WORKING_BRANCH_KEYS,
        findings=findings,
    )
    if shape is None:
        return
    name = shape.get("name")
    if not isinstance(name, str) or not name.strip():
        add(findings, f"{path}.name", "the fixed working branch must be named")
    fixed_by = shape.get("fixed_by_ref")
    if not isinstance(fixed_by, str) or not fixed_by.strip():
        add(
            findings,
            f"{path}.fixed_by_ref",
            "record the ref that fixed the branch; without it there is no "
            "original to return to and the invariant is unenforceable",
        )
    remedy = shape.get("remedy")
    if remedy is not None and remedy not in BRANCH_REMEDIES:
        add(findings, f"{path}.remedy", "branch remedy is invalid")


def validate_clock_reading(value: Any, path: str, findings: list[Finding]) -> None:
    shape = object_shape(
        value,
        path=path,
        required={"at", "phase"},
        allowed={"at", "phase"},
        findings=findings,
    )
    if shape is None:
        return
    parse_timestamp(shape.get("at"), f"{path}.at", findings)
    if shape.get("phase") not in CLOCK_PHASES:
        add(findings, f"{path}.phase", "clock reading phase is invalid")


def validate_minimum_shape(value: Any, findings: list[Finding]) -> None:
    path = "helix.loop.deadline.minimum_shape"
    shape = object_shape(
        value,
        path=path,
        required=MINIMUM_SHAPE_KEYS,
        allowed=MINIMUM_SHAPE_KEYS,
        findings=findings,
    )
    if shape is None:
        return
    goal = shape.get("owner_goal_ref")
    if not isinstance(goal, str) or not goal.strip():
        add(findings, f"{path}.owner_goal_ref", "the pre-registered shape needs its owner goal")
    items = shape.get("named_items")
    if not unique_text_list(items, nonempty=True) or not items:
        add(
            findings,
            f"{path}.named_items",
            "the minimum shape is named items, never a count: '8 of 10' is not "
            "evidence when the remaining 2 are the substance",
        )
    digest = shape.get("hash")
    if not isinstance(digest, str) or not CONTENT_HASH_RE.fullmatch(digest):
        add(findings, f"{path}.hash", "the pre-registered shape needs a sha256 hash")
    parse_timestamp(shape.get("registered_at"), f"{path}.registered_at", findings)


def validate_deadline(
    value: Any,
    evaluated_at: datetime | None,
    findings: list[Finding],
) -> datetime | None:
    deadline = object_shape(
        value,
        path="helix.loop.deadline",
        required={"at", "source", "source_ref", "clock_readings", "source_pin"},
        allowed=DEADLINE_KEYS,
        findings=findings,
    )
    if deadline is None:
        return None
    source = deadline.get("source")
    at = deadline.get("at")
    source_ref = deadline.get("source_ref")
    if source not in DEADLINE_SOURCES:
        add(findings, "helix.loop.deadline.source", "deadline source is invalid")
        return None
    if source == "none":
        if at is not None or source_ref != "":
            add(
                findings,
                "helix.loop.deadline.none",
                "an absent deadline must use at=null and source_ref=\"\"",
            )
        if value.get("clock_readings"):
            add(
                findings,
                "helix.loop.deadline.clock_readings",
                "no deadline is in force, so there is nothing to read a clock "
                "against; time-awareness authority does not arise here",
            )
        if value.get("source_pin") is not None:
            add(
                findings,
                "helix.loop.deadline.source_pin",
                "no deadline is in force, so there is no source to pin",
            )
        if value.get("minimum_shape") is not None:
            add(
                findings,
                "helix.loop.deadline.minimum_shape",
                "a minimum shape is pre-registered against a deadline window; "
                "with no deadline in force there is no window to register it in",
            )
        return None
    parsed = parse_timestamp(at, "helix.loop.deadline.at", findings)
    # A deadline that no one read the clock against is a felt deadline. The
    # schema requires the array; the runtime requires that it is not empty and
    # that the pre-registered shape exists, because a promise the runtime does
    # not read is not a control.
    readings = value.get("clock_readings")
    if isinstance(readings, list):
        for index, reading in enumerate(readings):
            validate_clock_reading(
                reading, f"helix.loop.deadline.clock_readings[{index}]", findings
            )
    if value.get("minimum_shape") is not None:
        validate_minimum_shape(value.get("minimum_shape"), findings)
    if not isinstance(readings, list) or not readings:
        add(
            findings,
            "helix.loop.deadline.clock_readings",
            "an in-force deadline needs at least one real clock reading; "
            "remaining time is computed from readings, never felt",
        )
    pin = value.get("source_pin")
    if not isinstance(pin, dict):
        add(
            findings,
            "helix.loop.deadline.source_pin",
            "an in-force deadline names a source that can be edited later; pin it "
            "by content so the date it was read from cannot move",
        )
    else:
        validate_pinned_source(pin, "helix.loop.deadline.source_pin", findings)
    shape = value.get("minimum_shape")
    if not isinstance(shape, dict):
        add(
            findings,
            "helix.loop.deadline.minimum_shape",
            "an in-force deadline needs the minimum coherent set pre-registered "
            "by name; deciding at the end makes whatever passed the definition",
        )
    if not evidence_list([source_ref], nonempty=True):
        add(
            findings,
            "helix.loop.deadline.source_ref",
            "explicit deadline needs a concrete source_ref",
        )
    if parsed is not None and evaluated_at is not None:
        # An expired deadline remains visible, but it cannot create defer pressure.
        return parsed
    return parsed


def validate_percentage(value: Any, path: str, findings: list[Finding]) -> float | None:
    if value is None:
        return None
    if not finite_number(value) or not 0 <= value <= 100:
        add(findings, path, "must be null or a finite percentage from 0 to 100")
        return None
    return float(value)


def validate_usage(
    value: Any,
    evaluated_at: datetime | None,
    findings: list[Finding],
) -> bool:
    usage = object_shape(
        value,
        path="helix.loop.usage",
        required=USAGE_KEYS,
        allowed=USAGE_KEYS,
        findings=findings,
    )
    if usage is None:
        return False
    primary = validate_percentage(
        usage.get("primary_5h_remaining"),
        "helix.loop.usage.primary_5h_remaining",
        findings,
    )
    secondary = validate_percentage(
        usage.get("secondary_weekly_remaining"),
        "helix.loop.usage.secondary_weekly_remaining",
        findings,
    )
    status = usage.get("status")
    source = usage.get("source")
    source_ref = usage.get("source_ref")
    observed_at = usage.get("observed_at")
    if status not in USAGE_STATUSES:
        add(findings, "helix.loop.usage.status", "usage status is invalid")
        return False
    if source not in USAGE_SOURCES:
        add(findings, "helix.loop.usage.source", "usage source is invalid")
        return False
    if status == "unknown":
        if (
            source != "unknown"
            or primary is not None
            or secondary is not None
            or observed_at is not None
            or source_ref != ""
        ):
            add(
                findings,
                "helix.loop.usage.unknown",
                "unknown usage cannot carry readings or provenance",
            )
        return False
    observed = parse_timestamp(
        observed_at,
        "helix.loop.usage.observed_at",
        findings,
    )
    if primary is None and secondary is None:
        add(findings, "helix.loop.usage.reading", "known usage needs a coarse reading")
    if not evidence_list([source_ref], nonempty=True):
        add(
            findings,
            "helix.loop.usage.source_ref",
            "known usage needs a concrete source_ref",
        )
    if status == "fresh" and source not in TRUSTED_USAGE_SOURCES:
        add(
            findings,
            "helix.loop.usage.fresh_source",
            "fresh usage requires a primary check or session-owner observation",
        )
        return False
    if (
        status == "fresh"
        and observed is not None
        and evaluated_at is not None
    ):
        age_minutes = (evaluated_at - observed).total_seconds() / 60
        if age_minutes < 0 or age_minutes > FRESH_USAGE_MINUTES:
            add(
                findings,
                "helix.loop.usage.freshness",
                f"fresh usage must be observed within {FRESH_USAGE_MINUTES} minutes",
            )
            return False
    return (
        status == "fresh"
        and source in TRUSTED_USAGE_SOURCES
        and (primary is not None or secondary is not None)
        and (
            (primary is not None and primary <= 15)
            or (secondary is not None and secondary <= 10)
        )
    )


def validate_ship_stage(
    value: Any,
    *,
    implementer_id: str | None,
    reviewer_ids: list[str],
    findings: list[Finding],
) -> tuple[str | None, bool]:
    """Return the ship stage and whether the Edison relaxation is earned.

    The relaxation is bought with evidence, and the evidence is bought with a
    witness: only a dev-stage increment whose normal path is recorded as
    verified against a concrete check, and whose basis and check a registered
    reviewer other than the implementer attests to having confirmed, carries
    it. An unverified happy path, or one the implementer alone asserts, leaves
    the production thresholds in force.
    """
    ship = object_shape(
        value,
        path="helix.loop.ship_stage",
        required=SHIP_STAGE_KEYS,
        allowed=SHIP_STAGE_KEYS,
        findings=findings,
    )
    if ship is None:
        return None, False
    stage = ship.get("stage")
    basis = ship.get("basis")
    if stage not in SHIP_STAGES:
        add(findings, "helix.loop.ship_stage.stage", "ship stage is invalid")
        stage = None
    if basis not in SHIP_BASES:
        add(findings, "helix.loop.ship_stage.basis", "ship basis is invalid")
        basis = None
    if stage == "production" and basis is not None and basis != "production_promotion":
        add(
            findings,
            "helix.loop.ship_stage.basis",
            "a production stage must record the production_promotion basis",
        )
    if stage == "dev_deploy" and basis is not None and basis not in DEV_SHIP_BASES:
        add(
            findings,
            "helix.loop.ship_stage.basis",
            "a dev ship needs an owner directive, a non-production target, "
            "or early development as its basis",
        )
    if not evidence_list([ship.get("basis_ref")], nonempty=True):
        add(
            findings,
            "helix.loop.ship_stage.basis_ref",
            "ship stage needs a concrete basis_ref",
        )
    happy_path = object_shape(
        ship.get("happy_path"),
        path="helix.loop.ship_stage.happy_path",
        required=HAPPY_PATH_KEYS,
        allowed=HAPPY_PATH_KEYS,
        findings=findings,
    )
    verified = False
    if happy_path is not None:
        raw_verified = happy_path.get("verified")
        check_ref = happy_path.get("check_ref")
        if not isinstance(raw_verified, bool):
            add(
                findings,
                "helix.loop.ship_stage.happy_path.verified",
                "happy_path.verified must be boolean",
            )
        elif raw_verified:
            if evidence_list([check_ref], nonempty=True):
                verified = True
            else:
                add(
                    findings,
                    "helix.loop.ship_stage.happy_path.check_ref",
                    "a verified normal path needs a concrete executed check_ref",
                )
        elif check_ref is not None:
            add(
                findings,
                "helix.loop.ship_stage.happy_path.check_ref",
                "an unverified normal path cannot carry a check_ref",
            )
        if not has_text(happy_path.get("summary")):
            add(
                findings,
                "helix.loop.ship_stage.happy_path.summary",
                "happy_path summary is required",
            )
    attested = validate_ship_attestation(
        ship.get("evidence_attestation"),
        relaxation_claimed=stage == "dev_deploy" and verified,
        implementer_id=implementer_id,
        reviewer_ids=reviewer_ids,
        findings=findings,
    )
    return stage, stage == "dev_deploy" and verified and attested


def validate_ship_attestation(
    value: Any,
    *,
    relaxation_claimed: bool,
    implementer_id: str | None,
    reviewer_ids: list[str],
    findings: list[Finding],
) -> bool:
    """Check the reviewer attestation that the ship evidence is real.

    ``basis_ref`` and ``happy_path.check_ref`` are locators the implementer
    writes; a locator asserted by the party it benefits is not evidence. The
    attestation names the registered reviewer who confirmed that the basis
    denotes a real authorized non-production target or directive and that the
    normal-path check was executed on this exact head.
    """
    path = "helix.loop.ship_stage.evidence_attestation"
    if not relaxation_claimed:
        if value is not None:
            add(
                findings,
                path,
                "only a dev ship with a verified normal path carries an "
                "evidence attestation",
            )
        return False
    if value is None:
        add(
            findings,
            path,
            "a dev ship needs a registered reviewer to attest the recorded "
            "basis and normal-path check",
        )
        return False
    attestation = object_shape(
        value,
        path=path,
        required=SHIP_ATTESTATION_KEYS,
        allowed=SHIP_ATTESTATION_KEYS,
        findings=findings,
    )
    if attestation is None:
        return False
    attested = True
    reviewer_id = attestation.get("reviewer_id")
    if reviewer_id not in reviewer_ids or reviewer_id == implementer_id:
        add(
            findings,
            f"{path}.reviewer_id",
            "the attesting reviewer must be a registered reviewer who is not "
            "the implementer",
        )
        attested = False
    if not evidence_list(attestation.get("evidence_refs"), nonempty=True):
        add(
            findings,
            f"{path}.evidence_refs",
            "the attestation needs the concrete refs the reviewer confirmed",
        )
        attested = False
    return attested


def validate_objection(
    value: Any,
    *,
    path: str,
    implementer_id: str | None,
    reviewer_ids: list[str],
    finding_reviewer_id: str | None,
    findings: list[Finding],
) -> str:
    if value is None:
        return "none"
    objection = object_shape(
        value,
        path=path,
        required=OBJECTION_KEYS,
        allowed=OBJECTION_KEYS,
        findings=findings,
    )
    if objection is None:
        return "invalid"
    if objection.get("implementer_id") != implementer_id:
        add(findings, f"{path}.implementer_id", "objection must come from the implementer")
    if objection.get("refuted_claim") != "failure_sequence":
        add(
            findings,
            f"{path}.refuted_claim",
            "objection must directly refute the failure_sequence",
        )
    if not has_text(objection.get("rationale")) or len(objection["rationale"].strip()) < 20:
        add(findings, f"{path}.rationale", "objection rationale is too short")
    if not evidence_list(objection.get("evidence_refs"), nonempty=True):
        add(findings, f"{path}.evidence_refs", "objection needs concrete evidence")

    rebuttal = object_shape(
        objection.get("rebuttal"),
        path=f"{path}.rebuttal",
        required=REBUTTAL_KEYS,
        allowed=REBUTTAL_KEYS,
        findings=findings,
    )
    outcome: str | None = None
    rebuttal_reviewer: str | None = None
    if rebuttal is not None:
        rebuttal_reviewer = rebuttal.get("reviewer_id")
        if rebuttal_reviewer not in reviewer_ids:
            add(findings, f"{path}.rebuttal.reviewer_id", "rebuttal reviewer is not registered")
        if finding_reviewer_id is not None and rebuttal_reviewer != finding_reviewer_id:
            add(
                findings,
                f"{path}.rebuttal.reviewer_id",
                "the finding reviewer must issue the single rebuttal",
            )
        outcome = rebuttal.get("outcome")
        if outcome not in REBUTTAL_OUTCOMES:
            add(findings, f"{path}.rebuttal.outcome", "rebuttal outcome is invalid")
        if not has_text(rebuttal.get("rationale")):
            add(findings, f"{path}.rebuttal.rationale", "rebuttal rationale is required")
        if not evidence_list(rebuttal.get("evidence_refs"), nonempty=True):
            add(findings, f"{path}.rebuttal.evidence_refs", "rebuttal needs concrete evidence")

    tie_break = objection.get("tie_break")
    if outcome == "accept":
        if tie_break is not None:
            add(
                findings,
                f"{path}.tie_break",
                "accepted objection cannot add a tie-break round",
            )
        return "accepted"
    if outcome != "reject":
        return "invalid"
    tie = object_shape(
        tie_break,
        path=f"{path}.tie_break",
        required=TIE_BREAK_KEYS,
        allowed=TIE_BREAK_KEYS,
        findings=findings,
    )
    if tie is None:
        add(
            findings,
            f"{path}.tie_break",
            "a rejected objection needs one distinct reviewer tie-break",
        )
        return "invalid"
    tie_reviewer = tie.get("reviewer_id")
    if tie_reviewer not in reviewer_ids:
        add(findings, f"{path}.tie_break.reviewer_id", "tie-break reviewer is not registered")
    if tie_reviewer == rebuttal_reviewer:
        add(
            findings,
            f"{path}.tie_break.reviewer_id",
            "tie-break reviewer must be distinct from the rebuttal reviewer",
        )
    tie_outcome = tie.get("outcome")
    if tie_outcome not in TIE_BREAK_OUTCOMES:
        add(findings, f"{path}.tie_break.outcome", "tie-break outcome is invalid")
        return "invalid"
    if not has_text(tie.get("rationale")):
        add(findings, f"{path}.tie_break.rationale", "tie-break rationale is required")
    if not evidence_list(tie.get("evidence_refs"), nonempty=True):
        add(findings, f"{path}.tie_break.evidence_refs", "tie-break needs concrete evidence")
    return "accepted" if tie_outcome == "accept_objection" else "sustained"


def expected_priority(
    *,
    impact: str | None,
    probability_percent: float | None,
    protected_floor: str | None,
    objection_state: str,
) -> str | None:
    if objection_state == "accepted":
        return "P3"
    if impact not in IMPACT_WEIGHTS or probability_percent is None:
        return None
    if protected_floor != "none":
        return "P0"
    score = probability_percent * IMPACT_WEIGHTS[impact]
    if score >= 200:
        return "P1"
    if score >= 60:
        return "P2"
    return "P3"


def deadline_pressure(
    *,
    evaluated_at: datetime | None,
    deadline_at: datetime | None,
    estimated_fix_minutes: int | None,
) -> bool:
    if evaluated_at is None or deadline_at is None or estimated_fix_minutes is None:
        return False
    remaining_minutes = (deadline_at - evaluated_at).total_seconds() / 60
    return 0 <= remaining_minutes <= estimated_fix_minutes + DEADLINE_RESERVE_MINUTES


def validate_human_report(value: Any, path: str, findings: list[Finding]) -> bool:
    report = object_shape(
        value,
        path=path,
        required=HUMAN_REPORT_KEYS,
        allowed=HUMAN_REPORT_KEYS,
        findings=findings,
    )
    if report is None:
        return False
    valid = True
    if report.get("audience") != "human_owner":
        add(findings, f"{path}.audience", "deferred finding must be reported to human_owner")
        valid = False
    if report.get("reported") is not True:
        add(findings, f"{path}.reported", "deferred finding must already be reported")
        valid = False
    if not has_text(report.get("summary")):
        add(findings, f"{path}.summary", "human report summary is required")
        valid = False
    if not evidence_list([report.get("report_ref")], nonempty=True):
        add(findings, f"{path}.report_ref", "human report needs a concrete report_ref")
        valid = False
    return valid


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "helix-blocker-triage.schema.json"


def _schema_document() -> dict[str, Any]:
    """The canonical schema, read from disk so there is one source of truth."""
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - packaging fault
        raise ArtifactError(f"canonical schema is missing at {SCHEMA_PATH}") from exc


def _resolve(schema: Any, root: dict[str, Any]) -> Any:
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise ArtifactError(f"unsupported schema reference {ref!r}")
        node: Any = root
        for part in ref[2:].split("/"):
            node = node[part.replace("~1", "/").replace("~0", "~")]
        schema = node
        seen += 1
        if seen > 32:
            raise ArtifactError("schema reference cycle")
    return schema


_TYPE_CHECKS: dict[str, Any] = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    # JSON Schema counts 1.0 as an integer; Python does not. Using isinstance
    # alone made this evaluator reject values jsonschema accepts.
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool))
    or (isinstance(v, float) and v.is_integer()),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def _json_equal(left: Any, right: Any) -> bool:
    """JSON Schema value equality, where `true` and `1` are different values.

    Python treats booleans as integers, so `1 == True` and a plain `==` would
    let a boolean satisfy a numeric const or enum and vice versa.
    """
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    return left == right


def _schema_matches(value: Any, schema: Any, root: dict[str, Any]) -> bool:
    return not _schema_errors(value, schema, root, "", collect=False)


def _schema_errors(
    value: Any,
    schema: Any,
    root: dict[str, Any],
    path: str,
    collect: bool = True,
) -> list[tuple[str, str]]:
    """Evaluate the subset of Draft 2020-12 this schema actually uses.

    The CLI is the authoritative gate, so it has to enforce what the canonical
    schema says rather than a hand-copy of it. Reading the schema keeps the two
    from drifting: a constraint added to the file takes effect here without a
    second implementation to forget.
    """
    schema = _resolve(schema, root)
    out: list[tuple[str, str]] = []

    def fail(where: str, message: str) -> list[tuple[str, str]]:
        out.append((where or "helix", message))
        return out

    if schema is True or schema == {}:
        return out
    if schema is False:
        return fail(path, "value is not permitted here")
    if not isinstance(schema, dict):
        return out

    declared = schema.get("type")
    if declared is not None:
        names = declared if isinstance(declared, list) else [declared]
        if not any(_TYPE_CHECKS.get(name, lambda _v: True)(value) for name in names):
            return fail(path, f"must be {' or '.join(names)}")

    if "const" in schema and not _json_equal(value, schema["const"]):
        return fail(path, f"must equal {schema['const']!r}")
    if "enum" in schema and not any(
        _json_equal(value, option) for option in schema["enum"]
    ):
        return fail(path, f"must be one of {sorted(map(str, schema['enum']))}")

    if isinstance(value, str):
        # `format` is deliberately not implemented here: jsonschema treats it as
        # advisory unless an optional format library is installed, and CI does
        # not install one. Implementing it would make this evaluator stricter
        # than CI — the same divergence in the other direction. Timestamp
        # contracts are carried by `pattern`, which both engines enforce.
        pattern = schema.get("pattern")
        if pattern is not None and not re.search(pattern, value):
            return fail(path, f"must match {pattern}")
        minimum_length = schema.get("minLength")
        if minimum_length is not None and len(value) < minimum_length:
            return fail(path, f"must be at least {minimum_length} character(s)")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        low = schema.get("minimum")
        if low is not None and value < low:
            return fail(path, f"must be >= {low}")
        high = schema.get("maximum")
        if high is not None and value > high:
            return fail(path, f"must be <= {high}")

    if isinstance(value, list):
        low = schema.get("minItems")
        if low is not None and len(value) < low:
            return fail(path, f"needs at least {low} item(s)")
        high = schema.get("maxItems")
        if high is not None and len(value) > high:
            return fail(path, f"allows at most {high} item(s)")
        if schema.get("uniqueItems") and len(
            {json.dumps(item, sort_keys=True) for item in value}
        ) != len(value):
            return fail(path, "items must be unique")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                out.extend(
                    _schema_errors(item, item_schema, root, f"{path}[{index}]", collect)
                )
                if out and not collect:
                    return out

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                fail(path, f"missing required key {key!r}")
                if not collect:
                    return out
        properties = schema.get("properties", {})
        for key, sub in properties.items():
            if key in value:
                out.extend(
                    _schema_errors(
                        value[key], sub, root, f"{path}.{key}" if path else key, collect
                    )
                )
                if out and not collect:
                    return out
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    fail(path, f"unknown key {key!r}")
                    if not collect:
                        return out

    for sub in schema.get("allOf", []):
        out.extend(_schema_errors(value, sub, root, path, collect))
        if out and not collect:
            return out
    if "anyOf" in schema and not any(
        _schema_matches(value, sub, root) for sub in schema["anyOf"]
    ):
        return fail(path, "does not satisfy any permitted shape")
    if "oneOf" in schema:
        matched = sum(1 for sub in schema["oneOf"] if _schema_matches(value, sub, root))
        if matched != 1:
            return fail(path, "must satisfy exactly one permitted shape")
    if "not" in schema and _schema_matches(value, schema["not"], root):
        return fail(path, "matches a forbidden shape")
    if "if" in schema:
        branch = "then" if _schema_matches(value, schema["if"], root) else "else"
        if branch in schema:
            out.extend(_schema_errors(value, schema[branch], root, path, collect))

    return out


def validate_against_schema(record: Any) -> list[Finding]:
    """Canonical-schema findings, evaluated from the schema file itself."""
    root = _schema_document()
    return [
        Finding(code=where or "helix", message=message)
        for where, message in _schema_errors(record, root, root, "")
    ]


def validate_record_full(record: Any) -> list[Finding]:
    """The authoritative check: canonical schema, then cross-object rules.

    `fairy blocker validate` used to call the runtime checks alone, so any
    constraint expressed only in the schema — an enum value, a pattern, a
    minItems — was rejected by the contract test in CI and accepted by the CLI
    that decides. Two gates disagreeing is worse than one, because the weaker
    one is the one people run.
    """
    # Version routing first: a superseded record should be told how to upgrade,
    # not handed a shape error about the version field it legitimately carries.
    if isinstance(record, dict):
        version = record.get("schema_version")
        if version in MIGRATABLE_SCHEMA_VERSIONS:
            return [
                Finding(
                    code="helix.schema_version",
                    message=(
                        f"schema_version {version} is superseded; upgrade the "
                        "record with `fairy blocker migrate`"
                    ),
                )
            ]
    schema_findings = validate_against_schema(record)
    if schema_findings:
        # A record that is not the right shape cannot be reasoned about across
        # objects; reporting both sets would bury the shape error in noise.
        return schema_findings
    return validate_record(record)


def validate_record(record: Any) -> list[Finding]:
    findings: list[Finding] = []
    top = object_shape(
        record,
        path="helix",
        required=TOP_KEYS,
        allowed=TOP_KEYS,
        findings=findings,
    )
    if top is None:
        return findings
    schema_version = top.get("schema_version")
    if schema_version in MIGRATABLE_SCHEMA_VERSIONS:
        add(
            findings,
            "helix.schema_version",
            f"schema_version {MIGRATABLE_SCHEMA_VERSION} is superseded; upgrade "
            "the record with `fairy blocker migrate`",
        )
    elif schema_version != SCHEMA_VERSION:
        add(findings, "helix.schema_version", f"schema_version must be {SCHEMA_VERSION}")
    if top.get("artifact_type") != "helix_blocker_triage":
        add(
            findings,
            "helix.artifact_type",
            "artifact_type must be helix_blocker_triage",
        )

    loop = object_shape(
        top.get("loop"),
        path="helix.loop",
        required=LOOP_KEYS,
        allowed=LOOP_KEYS,
        findings=findings,
    )
    implementer_id: str | None = None
    reviewer_ids: list[str] = []
    evaluated_at: datetime | None = None
    deadline_at: datetime | None = None
    usage_pressure = False
    ship_stage: str | None = None
    edison_mode = False
    repo: str | None = None
    if loop is not None:
        if not valid_id(loop.get("loop_id")):
            add(findings, "helix.loop.loop_id", "loop_id is malformed")
        repo = loop.get("repo")
        if not isinstance(repo, str) or not REPO_RE.fullmatch(repo):
            add(findings, "helix.loop.repo", "repo must be owner/name")
            repo = None
        if not evidence_list([loop.get("artifact_ref")], nonempty=True):
            add(findings, "helix.loop.artifact_ref", "artifact_ref must be concrete")
        if not isinstance(loop.get("exact_head"), str) or not SHA_RE.fullmatch(
            loop["exact_head"]
        ):
            add(findings, "helix.loop.exact_head", "exact_head must be a lowercase 40-hex SHA")
        evaluated_at = parse_timestamp(
            loop.get("evaluated_at"),
            "helix.loop.evaluated_at",
            findings,
        )
        implementer_id, reviewer_ids = validate_roles(loop.get("roles"), findings)
        deadline_at = validate_deadline(loop.get("deadline"), evaluated_at, findings)
        authority = loop.get("priority_authority")
        if isinstance(authority, dict):
            active = authority.get("active")
            directive = authority.get("directive")
            if active is True:
                if directive is None:
                    add(
                        findings,
                        "helix.loop.priority_authority.directive",
                        "an active priority role must name the directive it arises "
                        "from, pinned by content",
                    )
                else:
                    validate_pinned_source(
                        directive, "helix.loop.priority_authority.directive", findings
                    )
                if loop.get("roles", {}).get("priority_reviewer_id") is None:
                    add(
                        findings,
                        "helix.loop.roles.priority_reviewer_id",
                        "the priority role is active, so exactly one reviewer holds it",
                    )
            elif active is False:
                if directive is not None:
                    add(
                        findings,
                        "helix.loop.priority_authority.directive",
                        "an inactive priority role cannot cite a directive",
                    )
                if loop.get("roles", {}).get("priority_reviewer_id") is not None:
                    add(
                        findings,
                        "helix.loop.roles.priority_reviewer_id",
                        "with no directive in force the priority role does not arise, "
                        "so no reviewer holds it",
                    )
        validate_target(loop.get("target"), findings)
        validate_claim_envelope(loop.get("claim_envelope"), findings)
        validate_working_branch(loop.get("working_branch"), findings)
        usage_pressure = validate_usage(loop.get("usage"), evaluated_at, findings)
        ship_stage, edison_mode = validate_ship_stage(
            loop.get("ship_stage"),
            implementer_id=implementer_id,
            reviewer_ids=reviewer_ids,
            findings=findings,
        )

    blockers = top.get("blockers")
    blocker_ids: list[str] = []
    deferred_ids: list[str] = []
    deferred_report_refs: list[str] = []
    retained_ids: list[str] = []
    not_blocker_ids: list[str] = []
    if not isinstance(blockers, list) or not blockers:
        add(findings, "helix.blockers", "blockers must be a non-empty list")
        blockers = []
    for index, raw in enumerate(blockers):
        path = f"helix.blockers[{index}]"
        blocker = object_shape(
            raw,
            path=path,
            required=BLOCKER_KEYS,
            allowed=BLOCKER_KEYS,
            findings=findings,
        )
        if blocker is None:
            continue
        blocker_id = blocker.get("id")
        if not valid_id(blocker_id):
            add(findings, f"{path}.id", "blocker id is malformed")
            blocker_id = None
        else:
            blocker_ids.append(blocker_id)
        if not has_text(blocker.get("summary")):
            add(findings, f"{path}.summary", "summary is required")
        failure_sequence = blocker.get("failure_sequence")
        if not has_text(failure_sequence) or len(failure_sequence.strip()) < 20:
            add(
                findings,
                f"{path}.failure_sequence",
                "failure_sequence must describe a concrete causal sequence",
            )
        if not unique_text_list(blocker.get("preconditions"), nonempty=True):
            add(findings, f"{path}.preconditions", "preconditions must be non-empty and unique")
        probability = blocker.get("probability_percent")
        if not finite_number(probability) or not 0 <= probability <= 100:
            add(
                findings,
                f"{path}.probability_percent",
                "probability_percent must be finite and between 0 and 100",
            )
            probability_value = None
        else:
            probability_value = float(probability)
        impact = blocker.get("impact")
        if impact not in IMPACTS:
            add(findings, f"{path}.impact", "impact is invalid")
            impact = None
        if not has_text(blocker.get("risk_rationale")) or len(
            blocker["risk_rationale"].strip()
        ) < 20:
            add(findings, f"{path}.risk_rationale", "risk rationale is too short")
        finding_class = blocker.get("finding_class")
        if finding_class not in FINDING_CLASSES:
            add(findings, f"{path}.finding_class", "finding class is invalid")
            finding_class = None
        protected_floor = blocker.get("protected_floor")
        if protected_floor not in PROTECTED_FLOORS:
            add(findings, f"{path}.protected_floor", "protected floor is invalid")
            protected_floor = None
        floor_basis = blocker.get("floor_basis")
        if floor_basis not in FLOOR_BASES:
            add(findings, f"{path}.floor_basis", "floor basis is invalid")
            floor_basis = None
        elif protected_floor == "none" and floor_basis != "not_applicable":
            add(
                findings,
                f"{path}.floor_basis",
                "a finding off the safety floor must record not_applicable",
            )
        elif (
            protected_floor is not None
            and protected_floor != "none"
            and floor_basis == "not_applicable"
        ):
            add(
                findings,
                f"{path}.floor_basis",
                "a safety-floor finding must record demonstrated or precautionary",
            )
        estimated_fix_minutes = blocker.get("estimated_fix_minutes")
        if (
            not isinstance(estimated_fix_minutes, int)
            or isinstance(estimated_fix_minutes, bool)
            or estimated_fix_minutes <= 0
        ):
            add(findings, f"{path}.estimated_fix_minutes", "fix estimate must be positive")
            estimated_fix_minutes = None
        if not evidence_list(blocker.get("evidence_refs"), nonempty=True):
            add(findings, f"{path}.evidence_refs", "finding needs concrete evidence")

        finding_reviewer = object_shape(
            blocker.get("finding_reviewer"),
            path=f"{path}.finding_reviewer",
            required=FINDING_REVIEWER_KEYS,
            allowed=FINDING_REVIEWER_KEYS,
            findings=findings,
        )
        finding_reviewer_id: str | None = None
        if finding_reviewer is not None:
            finding_reviewer_id = finding_reviewer.get("reviewer_id")
            if finding_reviewer_id not in reviewer_ids:
                add(
                    findings,
                    f"{path}.finding_reviewer.reviewer_id",
                    "finding reviewer is not registered",
                )
            if not evidence_list([finding_reviewer.get("finding_ref")], nonempty=True):
                add(
                    findings,
                    f"{path}.finding_reviewer.finding_ref",
                    "finding_ref must be concrete",
                )

        objection_state = validate_objection(
            blocker.get("objection"),
            path=f"{path}.objection",
            implementer_id=implementer_id,
            reviewer_ids=reviewer_ids,
            finding_reviewer_id=finding_reviewer_id,
            findings=findings,
        )
        resolution = object_shape(
            blocker.get("resolution"),
            path=f"{path}.resolution",
            required=RESOLUTION_KEYS,
            allowed=RESOLUTION_KEYS,
            findings=findings,
        )
        if resolution is None:
            continue
        disposition = resolution.get("disposition")
        if disposition not in DISPOSITIONS:
            add(findings, f"{path}.resolution.disposition", "disposition is invalid")
        priority = resolution.get("priority")
        if priority not in PRIORITIES:
            add(findings, f"{path}.resolution.priority", "priority is invalid")
        expected = expected_priority(
            impact=impact,
            probability_percent=probability_value,
            protected_floor=protected_floor,
            objection_state=objection_state,
        )
        if expected is not None and priority != expected:
            add(
                findings,
                f"{path}.resolution.priority",
                f"priority must be {expected} for the recorded risk and floor",
            )
        if not has_text(resolution.get("rationale")):
            add(findings, f"{path}.resolution.rationale", "resolution rationale is required")
        concurred_by = resolution.get("concurred_by")
        if not unique_text_list(concurred_by):
            add(findings, f"{path}.resolution.concurred_by", "concurrence ids must be unique")
            concurred_by = []
        elif not all(item in reviewer_ids for item in concurred_by):
            add(
                findings,
                f"{path}.resolution.concurred_by",
                "concurrence must come from registered reviewers",
            )
        independent_concurrence = [
            item
            for item in concurred_by
            if item in reviewer_ids and item != finding_reviewer_id
        ]
        issue_url = resolution.get("issue_url")
        human_report = resolution.get("human_report")

        if objection_state == "accepted":
            if disposition != "not_blocker":
                add(
                    findings,
                    f"{path}.resolution.disposition",
                    "accepted objection must resolve as not_blocker",
                )
        elif objection_state in {"none", "sustained"}:
            if disposition == "not_blocker":
                add(
                    findings,
                    f"{path}.resolution.disposition",
                    "not_blocker requires an accepted failure-sequence refutation",
                )
        else:
            add(
                findings,
                f"{path}.objection",
                "objection discussion is unresolved and remains fail-closed",
            )

        if disposition == "defer_issue":
            if finding_class == "happy_path":
                add(
                    findings,
                    f"{path}.resolution.disposition",
                    "a finding on the shipped normal path cannot be deferred",
                )
            # Edison Ship Gate: a dev-stage ship may defer precautionary
            # hardening on the security floor, never a demonstrated reachable
            # defect, never another floor, and never a finding of another class
            # wearing the security floor. The class is checked here because the
            # document contract promises "precautionary hardening only", and a
            # promise the runtime does not read is not a control.
            floor_deferrable = (
                edison_mode
                and protected_floor in DEV_DEFERRABLE_FLOORS
                and finding_class == "hardening"
                and floor_basis == "precautionary"
            )
            # An unapproved branch change is unconditional: it cannot be
            # relabelled precautionary to reach the dev-stage defer envelope,
            # because it is not a claim about the increment's behaviour at all.
            if protected_floor in NON_DEFERRABLE_FLOORS:
                floor_deferrable = False
                add(
                    findings,
                    f"{path}.resolution.disposition",
                    "an unapproved branch change is not deferrable at any level of "
                    "concurrence; its only exits are a cited owner approval or "
                    "returning to the recorded branch and consolidating",
                )
            if protected_floor != "none" and not floor_deferrable:
                add(
                    findings,
                    f"{path}.resolution.disposition",
                    "protected safety-floor blockers cannot be deferred",
                )
            elif floor_deferrable:
                # The precautionary claim is the one claim whose only witness
                # is the panel's reading of the failure sequence, so deferring
                # on the floor takes the whole registered panel rather than the
                # single concurrence an off-floor deferral needs.
                absent = [
                    reviewer
                    for reviewer in reviewer_ids
                    if reviewer not in concurred_by
                ]
                if absent:
                    add(
                        findings,
                        f"{path}.resolution.concurred_by",
                        "deferring a safety-floor finding needs every "
                        "registered reviewer to concur: " + ", ".join(absent),
                    )
            score = (
                probability_value * IMPACT_WEIGHTS[impact]
                if probability_value is not None and impact in IMPACT_WEIGHTS
                else math.inf
            )
            pressure = usage_pressure or deadline_pressure(
                evaluated_at=evaluated_at,
                deadline_at=deadline_at,
                estimated_fix_minutes=estimated_fix_minutes,
            )
            if edison_mode:
                if score > DEV_MAX_DEFERRABLE_RISK_SCORE or impact == "critical":
                    add(
                        findings,
                        f"{path}.resolution.defer_eligibility",
                        "a dev ship defers up to high impact within the dev risk "
                        "cap; critical impact stays fix-now",
                    )
            else:
                minor = impact in {"negligible", "low"}
                bounded_under_pressure = impact == "medium" and pressure
                if score > MAX_DEFERRABLE_RISK_SCORE or not (
                    minor or bounded_under_pressure
                ):
                    add(
                        findings,
                        f"{path}.resolution.defer_eligibility",
                        "defer requires low residual risk plus minor impact, or "
                        "medium impact with measured pressure",
                    )
            if not independent_concurrence:
                add(
                    findings,
                    f"{path}.resolution.concurred_by",
                    "defer needs at least one registered reviewer concurrence "
                    "distinct from the finding reviewer",
                )
            issue_match = ISSUE_RE.fullmatch(issue_url) if isinstance(issue_url, str) else None
            if issue_match is None or (repo is not None and issue_match.group("repo") != repo):
                add(
                    findings,
                    f"{path}.resolution.issue_url",
                    "defer needs a canonical same-repository GitHub issue URL",
                )
            validate_human_report(
                human_report,
                f"{path}.resolution.human_report",
                findings,
            )
            if isinstance(human_report, dict):
                report_ref = human_report.get("report_ref")
                if isinstance(report_ref, str):
                    deferred_report_refs.append(report_ref)
            if blocker_id is not None:
                deferred_ids.append(blocker_id)
        else:
            if issue_url is not None or human_report is not None:
                add(
                    findings,
                    f"{path}.resolution.external_artifacts",
                    "only deferred findings carry issue_url and human_report",
                )
            if disposition == "not_blocker":
                if blocker_id is not None:
                    not_blocker_ids.append(blocker_id)
            elif disposition == "fix_now" and blocker_id is not None:
                retained_ids.append(blocker_id)

    duplicates = sorted(
        blocker_id for blocker_id in set(blocker_ids) if blocker_ids.count(blocker_id) > 1
    )
    if duplicates:
        add(findings, "helix.blockers.ids", "blocker ids must be unique: " + ", ".join(duplicates))

    readback = object_shape(
        top.get("final_readback"),
        path="helix.final_readback",
        required=READBACK_KEYS,
        allowed=READBACK_KEYS,
        findings=findings,
    )
    if readback is not None:
        ship_decision = object_shape(
            readback.get("ship_decision"),
            path="helix.final_readback.ship_decision",
            required=SHIP_DECISION_KEYS,
            allowed=SHIP_DECISION_KEYS,
            findings=findings,
        )
        if ship_decision is not None:
            decision = ship_decision.get("decision")
            rationale = ship_decision.get("rationale")
            if decision not in SHIP_DECISIONS:
                add(
                    findings,
                    "helix.final_readback.ship_decision.decision",
                    "ship decision is invalid",
                )
                decision = None
            if not has_text(rationale) or len(rationale.strip()) < 20:
                add(
                    findings,
                    "helix.final_readback.ship_decision.rationale",
                    "ship decision rationale is too short",
                )
            if decision == "go" and retained_ids:
                add(
                    findings,
                    "helix.final_readback.ship_decision.decision",
                    "a ship decision of go cannot carry retained fix-now findings",
                )
            if decision == "go" and ship_stage == "dev_deploy" and not edison_mode:
                add(
                    findings,
                    "helix.final_readback.ship_decision.decision",
                    "a dev ship needs the recorded normal path verified against "
                    "a concrete check",
                )
            # Edison Ship Gate: holding a green dev increment is the
            # perfectionism failure this gate exists to stop.
            if (
                decision == "hold"
                and ship_stage == "dev_deploy"
                and edison_mode
                and not retained_ids
            ):
                add(
                    findings,
                    "helix.final_readback.ship_decision.decision",
                    "a dev increment with a verified normal path and no retained "
                    "fix-now finding cannot be held",
                )
        expected_sets = (
            ("deferred_blocker_ids", deferred_ids),
            ("retained_blocker_ids", retained_ids),
            ("not_blocker_ids", not_blocker_ids),
        )
        for key, expected_ids in expected_sets:
            value = readback.get(key)
            if not unique_text_list(value) or value != expected_ids:
                add(
                    findings,
                    f"helix.final_readback.{key}",
                    f"must exactly preserve blocker order: {expected_ids}",
                )
        if deferred_ids:
            if readback.get("reported_to_human") is not True:
                add(
                    findings,
                    "helix.final_readback.reported_to_human",
                    "deferred findings must appear in a human-facing final readback",
                )
            if not evidence_list([readback.get("report_ref")], nonempty=True):
                add(
                    findings,
                    "helix.final_readback.report_ref",
                    "deferred findings need a concrete final readback ref",
                )
            elif any(
                item != readback.get("report_ref")
                for item in deferred_report_refs
            ):
                add(
                    findings,
                    "helix.final_readback.report_ref",
                    "every deferred human report must bind to the final readback ref",
                )
        elif readback.get("reported_to_human") not in {True, False}:
            add(
                findings,
                "helix.final_readback.reported_to_human",
                "reported_to_human must be boolean",
            )
        elif readback.get("reported_to_human") is False:
            if readback.get("report_ref") != "":
                add(
                    findings,
                    "helix.final_readback.report_ref",
                    "unreported readback must use an empty report_ref",
                )
        elif not evidence_list([readback.get("report_ref")], nonempty=True):
            add(
                findings,
                "helix.final_readback.report_ref",
                "reported readback needs a concrete report_ref",
            )

    # An unapproved branch change has exactly two exits, and the record has to
    # show which one was taken. Without this the floor value can be raised and
    # the record closed with remedy "none" and no approval anywhere — the floor
    # stated in the schema but never read at runtime.
    # The envelope's immutable half is only immutable if its ref cannot move.
    # exact_head is enforced both in the schema and here; baseline_ref carries
    # the same promise and gets the same treatment.
    envelope = loop.get("claim_envelope") if isinstance(loop, dict) else None
    if isinstance(envelope, dict):
        baseline = envelope.get("baseline_ref")
        if not isinstance(baseline, str) or not SHA_RE.fullmatch(baseline):
            add(
                findings,
                "helix.loop.claim_envelope.baseline_ref",
                "baseline_ref must be a commit id, not a movable name: a branch "
                "ref makes the fixed half of the envelope as mutable as the "
                "half it is supposed to anchor",
            )

    branch_floor_raised = any(
        isinstance(blocker, dict)
        and blocker.get("protected_floor") == "unapproved_branch_change"
        for blocker in (blockers if isinstance(blockers, list) else [])
    )
    if branch_floor_raised:
        branch = loop.get("working_branch") if isinstance(loop, dict) else None
        branch = branch if isinstance(branch, dict) else {}
        remedy = branch.get("remedy")
        approval = branch.get("approval_ref")
        if remedy not in {"approval_produced", "returned_and_consolidated"}:
            add(
                findings,
                "helix.loop.working_branch.remedy",
                "an unapproved branch change must record which exit was taken: "
                "a cited owner approval, or returning to the recorded branch "
                "and consolidating",
            )
        elif remedy == "approval_produced" and not (
            isinstance(approval, str) and approval.strip()
        ):
            add(
                findings,
                "helix.loop.working_branch.approval_ref",
                "approval_produced needs the owner approval as a citable ref; "
                "a recollection is not evidence",
            )
    return findings


def require_valid(record: Any) -> None:
    findings = validate_record_full(record)
    if findings:
        detail = "; ".join(f"{item.code}: {item.message}" for item in findings)
        raise ArtifactError(detail)


def markdown_escape(value: Any) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def render_markdown(record: dict[str, Any]) -> str:
    require_valid(record)
    loop = record["loop"]
    deadline = loop["deadline"]
    deadline_summary = "none"
    if deadline["at"] is not None:
        evaluated_at = datetime.fromisoformat(
            loop["evaluated_at"].replace("Z", "+00:00").replace("z", "+00:00")
        )
        deadline_at = datetime.fromisoformat(deadline["at"].replace("Z", "+00:00").replace("z", "+00:00"))
        remaining_hours = (deadline_at - evaluated_at).total_seconds() / 3600
        deadline_summary = (
            f"{deadline['at']} ({remaining_hours:.1f}h remaining at evaluation; "
            f"{deadline['source']})"
        )
    usage = loop["usage"]
    ship = loop["ship_stage"]
    target = loop["target"]
    envelope = loop["claim_envelope"]
    branch = loop["working_branch"]
    authority = loop["priority_authority"]
    happy_path = ship["happy_path"]
    happy_path_summary = (
        f"verified against `{happy_path['check_ref']}`"
        if happy_path["verified"]
        else "not verified"
    )
    lines = [
        "# Helix Blocker Triage",
        "",
        f"- Loop: `{loop['loop_id']}`",
        f"- Repository: `{loop['repo']}`",
        f"- Exact head: `{loop['exact_head']}`",
        f"- Evaluated: `{loop['evaluated_at']}`",
        (
            f"- Ship stage: `{ship['stage']}` (basis `{ship['basis']}`, "
            f"`{ship['basis_ref']}`)"
        ),
        f"- Normal path: {happy_path_summary} — {markdown_escape(happy_path['summary'])}",
        f"- Deadline: {deadline_summary}",
        # The cards require that the record says who held the priority role,
        # where the change belongs, what the claim was pinned to, and which
        # branch the effort was fixed to. Evidence that never reaches the human
        # readback is evidence only the validator can see.
        (
            "- Priority authority: "
            + (
                f"active from `{authority['directive']['ref']}`"
                f"@`{authority['directive']['content_hash'][:12]}`, held by "
                f"`{loop['roles']['priority_reviewer_id']}`"
                if authority.get("active")
                else "not in force (no owner directive; the role does not arise)"
            )
        ),
        (
            "- Clock readings: "
            + (
                ", ".join(
                    f"`{reading['phase']}`@`{reading['at']}`"
                    for reading in deadline["clock_readings"]
                )
                or "none (no deadline in force)"
            )
        ),
        (
            "- Minimum shape: "
            + (
                "not pre-registered (no deadline in force)"
                if deadline.get("minimum_shape") is None
                else (
                    f"`{deadline['minimum_shape']['hash'][:12]}` from "
                    f"`{deadline['minimum_shape']['owner_goal_ref']}` — "
                    + ", ".join(
                        markdown_escape(item)
                        for item in deadline["minimum_shape"]["named_items"]
                    )
                )
            )
        ),
        (
            f"- Target: `{target['repo']}` `{target['path']}` "
            f"({target['layer']}, owner `{target['canonical_owner']}`, "
            f"{target['duplication_policy']})"
        ),
        (
            "- Target resolved from: "
            + ", ".join(
                f"`{ref['ref']}`@`{ref['content_hash'][:12]}`"
                for ref in target["directive_refs"]
            )
        ),
        (
            f"- Claim envelope: baseline `{envelope['baseline_ref'][:12]}` + "
            + ", ".join(
                f"`{ref['ref']}`@`{ref['content_hash'][:12]}`"
                for ref in envelope["claim_snapshot_refs"]
            )
        ),
        (
            f"- Working branch: `{branch['name']}` fixed by "
            f"`{branch['fixed_by_ref']}`"
            + (
                ""
                if branch.get("remedy") in (None, "none")
                else f" — remedy `{branch['remedy']}`"
                + (
                    f" (`{branch['approval_ref']}`)"
                    if branch.get("approval_ref")
                    else ""
                )
            )
        ),
        (
            "- Usage: "
            f"primary={usage['primary_5h_remaining']}, "
            f"secondary={usage['secondary_weekly_remaining']}, "
            f"status={usage['status']}, source={usage['source']}"
        ),
        "",
        "## Decisions",
        "",
        "| ID | Priority | Disposition | Risk score | Fix min | Floor | Issue |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for blocker in record["blockers"]:
        resolution = blocker["resolution"]
        score = blocker["probability_percent"] * IMPACT_WEIGHTS[blocker["impact"]]
        lines.append(
            "| "
            + " | ".join(
                (
                    markdown_escape(blocker["id"]),
                    markdown_escape(resolution["priority"]),
                    markdown_escape(resolution["disposition"]),
                    markdown_escape(score),
                    markdown_escape(blocker["estimated_fix_minutes"]),
                    markdown_escape(blocker["protected_floor"]),
                    markdown_escape(resolution["issue_url"] or "-"),
                )
            )
            + " |"
        )
    for blocker in record["blockers"]:
        resolution = blocker["resolution"]
        lines.extend(
            [
                "",
                f"## {markdown_escape(blocker['id'])}: {markdown_escape(blocker['summary'])}",
                "",
                f"- Failure sequence: {markdown_escape(blocker['failure_sequence'])}",
                f"- Preconditions: {markdown_escape('; '.join(blocker['preconditions']))}",
                f"- Risk rationale: {markdown_escape(blocker['risk_rationale'])}",
                f"- Resolution: `{resolution['disposition']}` / `{resolution['priority']}`",
                f"- Resolution rationale: {markdown_escape(resolution['rationale'])}",
                "- Evidence: "
                + ", ".join(
                    f"`{markdown_escape(item)}`"
                    for item in blocker["evidence_refs"]
                ),
            ]
        )
        if resolution["disposition"] == "defer_issue":
            report = resolution["human_report"]
            lines.extend(
                [
                    f"- Deferred issue: {resolution['issue_url']}",
                    f"- Human report: {markdown_escape(report['summary'])}",
                    f"- Human report ref: `{markdown_escape(report['report_ref'])}`",
                ]
            )
        if blocker["objection"] is not None:
            lines.append(
                f"- Implementer objection: {markdown_escape(blocker['objection']['rationale'])}"
            )
    readback = record["final_readback"]
    ship_decision = readback["ship_decision"]
    lines.extend(
        [
            "",
            "## Final Readback",
            "",
            f"- Ship decision: `{ship_decision['decision']}` to `{ship['stage']}`",
            f"- Ship rationale: {markdown_escape(ship_decision['rationale'])}",
            "- Ship authority: readiness only — this record states that the "
            "increment is ready for the recorded stage. It grants no deploy, "
            "merge, or access authority, and does not override the "
            "repository's own gates or the owner's standing policy.",
            "- Deferred: " + (", ".join(readback["deferred_blocker_ids"]) or "none"),
            "- Retained blockers: " + (", ".join(readback["retained_blocker_ids"]) or "none"),
            "- Not blockers: " + (", ".join(readback["not_blocker_ids"]) or "none"),
            "- Human report ref: " + (readback["report_ref"] or "not reported"),
        ]
    )
    if ship["stage"] == "dev_deploy" and readback["deferred_blocker_ids"]:
        lines.extend(
            [
                "",
                "## Promotion Debt",
                "",
                "These dev-stage deferrals re-block at production promotion "
                "under the unrelaxed thresholds:",
                "",
            ]
        )
        deferred = {
            blocker["id"]: blocker
            for blocker in record["blockers"]
            if blocker["id"] in set(readback["deferred_blocker_ids"])
        }
        for blocker_id in readback["deferred_blocker_ids"]:
            blocker = deferred[blocker_id]
            lines.append(
                f"- `{markdown_escape(blocker_id)}` "
                f"({markdown_escape(blocker['finding_class'])}, floor "
                f"`{markdown_escape(blocker['protected_floor'])}`/"
                f"`{markdown_escape(blocker['floor_basis'])}`): "
                f"{blocker['resolution']['issue_url']}"
            )
    lines.append("")
    return "\n".join(lines)


def load_record(path: Path) -> dict[str, Any]:
    canonical_artifact_path(path, "Helix blocker triage record")
    record = load_json(path)
    require_valid(record)
    assert isinstance(record, dict)
    return record


def migrate_record(record: Any) -> dict[str, Any]:
    """Upgrade a persisted schema 1.0 record to the current schema.

    A schema change that silently invalidates every stored record is a data
    break wearing a version number. The upgrade is faithful rather than
    generous: 1.0 decided under the unrelaxed thresholds, so the migrated
    record states the production stage with an unverified normal path and no
    attestation. It cannot hand an old record an envelope the old record never
    earned, and the result is validated here rather than trusted.
    """
    if not isinstance(record, dict):
        raise ArtifactError("a triage record must be a JSON object")
    version = record.get("schema_version")
    if version == SCHEMA_VERSION:
        raise ArtifactError(f"record is already schema {SCHEMA_VERSION}")
    if version not in MIGRATABLE_SCHEMA_VERSIONS:
        raise ArtifactError(
            "only schema "
            + " or ".join(MIGRATABLE_SCHEMA_VERSIONS)
            + " records can be migrated"
        )
    upgraded = copy.deepcopy(record)
    upgraded["schema_version"] = SCHEMA_VERSION

    loop = upgraded.get("loop")
    if not isinstance(loop, dict):
        raise ArtifactError("helix.loop must be an object")
    # 1.2 adds records of evidence that a 1.1 record never captured: where the
    # change belongs, which sources the claim was pinned against, which branch
    # the effort was fixed to, who held the priority role, and what the clock
    # actually read. None of that can be reconstructed from the old record, and
    # inventing it would forge exactly the provenance the fields exist to carry.
    # The upgrade therefore asks the operator for it rather than guessing.
    missing = [
        name
        for name in ("target", "claim_envelope", "working_branch")
        if not isinstance(loop.get(name), dict)
    ]
    if not isinstance(loop.get("priority_authority"), dict):
        missing.append("priority_authority")
    roles = loop.get("roles")
    if not isinstance(roles, dict) or "priority_reviewer_id" not in roles:
        missing.append("roles.priority_reviewer_id")
    deadline = loop.get("deadline")
    if not isinstance(deadline, dict):
        missing.append("deadline")
    elif deadline.get("source") == "none":
        # No deadline was in force, so there was no clock to read and no window
        # to register a shape in. Demanding them here would make the record the
        # schema calls correct impossible to migrate.
        if deadline.get("clock_readings"):
            raise ArtifactError(
                "a record with no deadline in force cannot carry clock readings"
            )
        deadline.setdefault("clock_readings", [])
        deadline.setdefault("minimum_shape", None)
        deadline.setdefault("source_pin", None)
    else:
        if not deadline.get("clock_readings"):
            missing.append("deadline.clock_readings")
        if not deadline.get("source_pin"):
            missing.append("deadline.source_pin")
    if missing:
        raise ArtifactError(
            "schema 1.2 records evidence the 1.1 record does not carry; attach it "
            "before migrating rather than letting the upgrade invent it: "
            + ", ".join(missing)
        )
    if "ship_stage" in loop:
        if version != "1.1":
            raise ArtifactError(
                f"a schema {version} record cannot already carry a ship_stage"
            )
        require_valid(upgraded)
        return upgraded
    loop["ship_stage"] = {
        "stage": "production",
        "basis": "production_promotion",
        "basis_ref": loop.get("artifact_ref"),
        "happy_path": {
            "verified": False,
            "check_ref": None,
            "summary": (
                "Migrated from schema 1.0, which recorded no normal-path check, "
                "so the unrelaxed thresholds stay in force."
            ),
        },
        "evidence_attestation": None,
    }

    blockers = upgraded.get("blockers")
    if not isinstance(blockers, list) or not blockers:
        raise ArtifactError("helix.blockers must be a non-empty list")
    for blocker in blockers:
        if not isinstance(blocker, dict):
            raise ArtifactError("every blocker must be an object")
        blocker.setdefault("finding_class", "other")
        blocker.setdefault(
            "floor_basis",
            "not_applicable" if blocker.get("protected_floor") == "none" else "demonstrated",
        )

    readback = upgraded.get("final_readback")
    if not isinstance(readback, dict):
        raise ArtifactError("helix.final_readback must be an object")
    held = bool(readback.get("retained_blocker_ids"))
    readback.setdefault(
        "ship_decision",
        {
            "decision": "hold" if held else "go",
            "rationale": (
                "Migrated from schema 1.0: a retained fix-now finding holds "
                "this increment."
                if held
                else "Migrated from schema 1.0: no fix-now finding is retained, "
                "so the recorded decision stands."
            ),
        },
    )
    require_valid(upgraded)
    return upgraded


def sample_record() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "helix_blocker_triage",
        "loop": {
            "loop_id": "helix-balance-sample",
            "repo": "bonginkan/fairy_tale",
            "artifact_ref": "https://github.com/bonginkan/fairy_tale/issues/94",
            "exact_head": "b7eaeda1afdab966f0dc1d8bb539a769030406a4",
            "evaluated_at": "2026-07-26T14:00:00+09:00",
            "roles": {
                "implementer_id": "misa-3",
                "reviewer_ids": ["codex-misa", "cc-misa-hime"],
                "priority_reviewer_id": "codex-misa",
            },
            "priority_authority": {
                "active": True,
                "directive": {
                    "ref": "source:owner-priority-directive",
                    "content_hash": "d" * 64,
                    "captured_at": "2026-07-26T13:45:00+09:00",
                    "edit_count": 0,
                },
            },
            "deadline": {
                "at": "2026-07-27T14:00:00+09:00",
                "source": "explicit_owner",
                "source_ref": "source:owner-deadline",
                "source_pin": {
                    "ref": "source:owner-deadline",
                    "content_hash": "e" * 64,
                    "captured_at": "2026-07-26T13:45:00+09:00",
                    "edit_count": 0,
                },
                "clock_readings": [
                    {"at": "2026-07-26T13:50:00+09:00", "phase": "round_start"},
                    {"at": "2026-07-26T14:30:00+09:00", "phase": "disposition"},
                    {"at": "2026-07-26T15:00:00+09:00", "phase": "ship_decision"},
                ],
                "minimum_shape": {
                    "owner_goal_ref": "source:owner-deadline",
                    "named_items": ["path identity fix", "capacity eviction guard"],
                    "hash": "a" * 64,
                    "registered_at": "2026-07-26T13:50:00+09:00",
                },
            },
            "target": {
                "repo": "bonginkan/fairy_tale",
                "path": "skills/fairy-tale/references/cards",
                "layer": "canonical skill cards",
                "canonical_owner": "bonginkan/fairy_tale",
                "directive_refs": [
                    {
                        "ref": "source:owner-directive",
                        "content_hash": "b" * 64,
                        "captured_at": "2026-07-26T13:45:00+09:00",
                        "edit_count": 0,
                    }
                ],
                "propagation_path": ["plugins/fairy-tale/skills/fairy-tale"],
                "duplication_policy": "mirrored_byte_identical",
                "resolved_at": "2026-07-26T13:45:00+09:00",
            },
            "claim_envelope": {
                "baseline_ref": "0" * 40,
                "claim_snapshot_refs": [
                    {
                        "ref": "source:owner-directive",
                        "content_hash": "b" * 64,
                        "captured_at": "2026-07-26T13:45:00+09:00",
                        "edit_count": 0,
                    }
                ],
            },
            "working_branch": {
                "name": "dev-matsumoto",
                "fixed_by_ref": "source:owner-branch-fix",
                "approval_ref": None,
                "remedy": "none",
            },
            "usage": {
                "primary_5h_remaining": 12,
                "secondary_weekly_remaining": 45,
                "status": "fresh",
                "source": "primary_check",
                "source_ref": "usage:local-guard",
                "observed_at": "2026-07-26T13:55:00+09:00",
            },
            "ship_stage": {
                "stage": "production",
                "basis": "production_promotion",
                "basis_ref": "source:release-promotion",
                "happy_path": {
                    "verified": True,
                    "check_ref": "check:release-acceptance-suite",
                    "summary": "The release acceptance suite passes on this head.",
                },
                "evidence_attestation": None,
            },
        },
        "blockers": [
            {
                "id": "minor-capacity-eviction",
                "summary": "Rare bounded capacity eviction remains",
                "failure_sequence": (
                    "A saturated optional cache evicts one low-priority entry, "
                    "which forces one later request to recompute."
                ),
                "preconditions": [
                    "optional cache is at its configured capacity",
                    "a lower-priority entry is selected for eviction",
                ],
                "probability_percent": 2,
                "impact": "low",
                "risk_rationale": (
                    "The sequence is rare and bounded to one recomputation "
                    "without data loss or authority impact."
                ),
                "finding_class": "abnormal_path",
                "protected_floor": "none",
                "floor_basis": "not_applicable",
                "estimated_fix_minutes": 180,
                "evidence_refs": ["test:capacity-eviction-probe"],
                "finding_reviewer": {
                    "reviewer_id": "codex-misa",
                    "finding_ref": "issue:review-finding",
                },
                "objection": None,
                "resolution": {
                    "disposition": "defer_issue",
                    "priority": "P3",
                    "rationale": (
                        "Low residual risk is tracked without consuming the "
                        "remaining convergence window."
                    ),
                    "concurred_by": ["cc-misa-hime"],
                    "issue_url": "https://github.com/bonginkan/fairy_tale/issues/94",
                    "human_report": {
                        "audience": "human_owner",
                        "reported": True,
                        "summary": (
                            "The rare optional-cache eviction is deferred to "
                            "issue #94 with no safety-floor impact."
                        ),
                        "report_ref": "source:owner-final-readback",
                    },
                },
            },
            {
                "id": "false-positive-finding",
                "summary": "Claimed path collision does not occur",
                "failure_sequence": (
                    "The reviewer claimed two output aliases resolve to one "
                    "path and overwrite the canonical input."
                ),
                "preconditions": ["two paths are portable aliases"],
                "probability_percent": 20,
                "impact": "medium",
                "risk_rationale": (
                    "If true, the collision would corrupt a review input, but "
                    "the exact identity probe refutes the prerequisite."
                ),
                "finding_class": "other",
                "protected_floor": "data_loss",
                "floor_basis": "demonstrated",
                "estimated_fix_minutes": 30,
                "evidence_refs": ["test:path-identity-negative"],
                "finding_reviewer": {
                    "reviewer_id": "codex-misa",
                    "finding_ref": "issue:path-collision-finding",
                },
                "objection": {
                    "implementer_id": "misa-3",
                    "refuted_claim": "failure_sequence",
                    "rationale": (
                        "The exact consumer resolves the two fixture paths to "
                        "different portable identities before any write."
                    ),
                    "evidence_refs": ["test:path-identity-negative"],
                    "rebuttal": {
                        "reviewer_id": "codex-misa",
                        "outcome": "accept",
                        "rationale": "The direct probe refutes the claimed alias.",
                        "evidence_refs": ["test:path-identity-negative"],
                    },
                    "tie_break": None,
                },
                "resolution": {
                    "disposition": "not_blocker",
                    "priority": "P3",
                    "rationale": "The failure sequence was directly refuted.",
                    "concurred_by": ["codex-misa"],
                    "issue_url": None,
                    "human_report": None,
                },
            },
        ],
        "final_readback": {
            "ship_decision": {
                "decision": "go",
                "rationale": (
                    "The acceptance suite passes and no fix-now finding is "
                    "retained, so the promotion proceeds."
                ),
            },
            "deferred_blocker_ids": ["minor-capacity-eviction"],
            "retained_blocker_ids": [],
            "not_blocker_ids": ["false-positive-finding"],
            "reported_to_human": True,
            "report_ref": "source:owner-final-readback",
        },
    }


def dev_sample_record() -> dict[str, Any]:
    """A dev-stage record whose verified normal path earns the Edison gate."""
    record = sample_record()
    record["loop"]["ship_stage"] = {
        "stage": "dev_deploy",
        "basis": "non_production_target",
        "basis_ref": "source:dev-environment-target",
        "happy_path": {
            "verified": True,
            "check_ref": "check:dev-smoke-normal-path",
            "summary": "The dev smoke run completes the normal path end to end.",
        },
        "evidence_attestation": {
            "reviewer_id": "codex-misa",
            "evidence_refs": ["run:reviewer-dev-smoke-rerun"],
        },
    }
    record["final_readback"]["ship_decision"] = {
        "decision": "go",
        "rationale": (
            "The normal path is verified on the dev target and nothing "
            "fix-now is retained, so humans get to hit it now."
        ),
    }
    return record


def legacy_sample_record() -> dict[str, Any]:
    """The canonical sample as the previous schema wrote it.

    The 1.2 evidence stays attached here because migration refuses to invent
    it: an operator upgrading a stored record supplies the target, envelope,
    branch, priority holder, and clock readings, and the upgrade validates what
    they supplied. Stripping them would test that migration fabricates, which
    is the behaviour the refusal exists to prevent.
    """
    record = sample_record()
    record["schema_version"] = MIGRATABLE_SCHEMA_VERSION
    del record["loop"]["ship_stage"]
    del record["final_readback"]["ship_decision"]
    for blocker in record["blockers"]:
        del blocker["finding_class"]
        del blocker["floor_basis"]
    return record


def run_selftest() -> int:
    controls = 0

    def check(condition: bool, label: str) -> None:
        nonlocal controls
        controls += 1
        if not condition:
            raise AssertionError(label)

    def blocked(record: dict[str, Any], contains: str) -> None:
        nonlocal controls
        controls += 1
        findings = validate_record(record)
        detail = "; ".join(item.message for item in findings)
        if contains not in detail:
            raise AssertionError(f"expected {contains!r}, got {detail!r}")

    base = sample_record()
    check(not validate_record(base), "sample record is valid")
    check("Deferred issue" in render_markdown(base), "render preserves deferred issue")
    check("Human report" in render_markdown(base), "render preserves human report")
    check("Implementer objection" in render_markdown(base), "render preserves objection")

    protected = copy.deepcopy(base)
    protected["blockers"][0]["protected_floor"] = "production"
    protected["blockers"][0]["resolution"]["priority"] = "P0"
    blocked(protected, "protected safety-floor blockers cannot be deferred")

    no_issue = copy.deepcopy(base)
    no_issue["blockers"][0]["resolution"]["issue_url"] = None
    blocked(no_issue, "canonical same-repository GitHub issue URL")

    no_report = copy.deepcopy(base)
    no_report["blockers"][0]["resolution"]["human_report"] = None
    blocked(no_report, "must be an object")

    implementer_only = copy.deepcopy(base)
    implementer_only["blockers"][0]["resolution"]["concurred_by"] = []
    blocked(implementer_only, "distinct from the finding reviewer")

    finding_reviewer_only = copy.deepcopy(base)
    finding_reviewer_only["blockers"][0]["resolution"]["concurred_by"] = [
        "codex-misa"
    ]
    blocked(finding_reviewer_only, "distinct from the finding reviewer")

    hidden_readback = copy.deepcopy(base)
    hidden_readback["final_readback"]["deferred_blocker_ids"] = []
    blocked(hidden_readback, "exactly preserve blocker order")

    mismatched_report = copy.deepcopy(base)
    mismatched_report["blockers"][0]["resolution"]["human_report"][
        "report_ref"
    ] = "source:different-report"
    blocked(mismatched_report, "bind to the final readback ref")

    unresolved = copy.deepcopy(base)
    objection = unresolved["blockers"][1]["objection"]
    assert isinstance(objection, dict)
    objection["rebuttal"]["outcome"] = "reject"
    objection["tie_break"] = None
    unresolved["blockers"][1]["resolution"]["disposition"] = "fix_now"
    unresolved["blockers"][1]["resolution"]["priority"] = "P0"
    unresolved["final_readback"]["not_blocker_ids"] = []
    unresolved["final_readback"]["retained_blocker_ids"] = ["false-positive-finding"]
    unresolved["final_readback"]["ship_decision"] = {
        "decision": "hold",
        "rationale": "A retained fix-now finding holds the promotion.",
    }
    blocked(unresolved, "distinct reviewer tie-break")

    sustained = copy.deepcopy(unresolved)
    sustained_objection = sustained["blockers"][1]["objection"]
    assert isinstance(sustained_objection, dict)
    sustained_objection["tie_break"] = {
        "reviewer_id": "cc-misa-hime",
        "outcome": "sustain_blocker",
        "rationale": "The alternative probe does not refute the unsafe write sequence.",
        "evidence_refs": ["test:path-alias-positive"],
    }
    check(not validate_record(sustained), "rejected objection converges by tie-break")

    tie_accept = copy.deepcopy(sustained)
    tie_objection = tie_accept["blockers"][1]["objection"]
    assert isinstance(tie_objection, dict)
    tie_objection["tie_break"]["outcome"] = "accept_objection"
    tie_accept["blockers"][1]["resolution"]["disposition"] = "not_blocker"
    tie_accept["blockers"][1]["resolution"]["priority"] = "P3"
    tie_accept["final_readback"]["retained_blocker_ids"] = []
    tie_accept["final_readback"]["not_blocker_ids"] = ["false-positive-finding"]
    check(not validate_record(tie_accept), "tie-break can accept direct refutation")

    bargaining = copy.deepcopy(base)
    bargaining_objection = bargaining["blockers"][1]["objection"]
    assert isinstance(bargaining_objection, dict)
    bargaining_objection["refuted_claim"] = "severity"
    blocked(bargaining, "directly refute the failure_sequence")

    fabricated_deadline = copy.deepcopy(base)
    fabricated_deadline["loop"]["deadline"]["source"] = "none"
    blocked(fabricated_deadline, "at=null")

    self_report = copy.deepcopy(base)
    self_report["loop"]["usage"]["source"] = "self_report"
    blocked(self_report, "primary check or session-owner observation")

    stale_usage = copy.deepcopy(base)
    stale_usage["loop"]["usage"]["observed_at"] = "2026-07-26T10:00:00+09:00"
    blocked(stale_usage, "observed within")

    no_pressure_high = copy.deepcopy(base)
    target = no_pressure_high["blockers"][0]
    target["impact"] = "high"
    target["probability_percent"] = 10
    target["risk_rationale"] = "A rare high-impact failure remains below the numeric risk cap."
    target["resolution"]["priority"] = "P3"
    no_pressure_high["loop"]["deadline"] = {
        "at": None,
        "source": "none",
        "source_ref": "",
    }
    no_pressure_high["loop"]["usage"] = {
        "primary_5h_remaining": None,
        "secondary_weekly_remaining": None,
        "status": "unknown",
        "source": "unknown",
        "source_ref": "",
        "observed_at": None,
    }
    blocked(no_pressure_high, "medium impact with measured pressure")

    pressure_high = copy.deepcopy(base)
    target = pressure_high["blockers"][0]
    target["impact"] = "high"
    target["probability_percent"] = 10
    target["risk_rationale"] = (
        "A rare high-impact failure remains below the numeric risk cap but "
        "is not comparatively minor."
    )
    target["resolution"]["priority"] = "P3"
    blocked(pressure_high, "medium impact with measured pressure")

    pressure_medium = copy.deepcopy(base)
    target = pressure_medium["blockers"][0]
    target["impact"] = "medium"
    target["probability_percent"] = 20
    target["risk_rationale"] = (
        "The bounded medium-impact failure reaches the risk cap while the "
        "trusted deadline and usage readings show convergence pressure."
    )
    target["resolution"]["priority"] = "P2"
    check(
        not validate_record(pressure_medium),
        "measured pressure can defer bounded medium impact",
    )

    excessive_risk = copy.deepcopy(base)
    target = excessive_risk["blockers"][0]
    target["impact"] = "critical"
    target["probability_percent"] = 20
    target["resolution"]["priority"] = "P2"
    blocked(excessive_risk, "low residual risk")

    malformed = copy.deepcopy(base)
    malformed["blockers"][0]["probability_percent"] = {}
    check(bool(validate_record(malformed)), "malformed scalar is reasoned")

    unknown = copy.deepcopy(base)
    unknown["blockers"][0]["resolution"]["extra"] = True
    blocked(unknown, "unknown keys")

    bad_report_ref = copy.deepcopy(base)
    bad_report_ref["final_readback"]["report_ref"] = "reported somewhere"
    blocked(bad_report_ref, "concrete final readback ref")

    stage_mismatch = copy.deepcopy(base)
    stage_mismatch["loop"]["ship_stage"]["basis"] = "owner_directive"
    blocked(stage_mismatch, "production_promotion basis")

    floor_basis_off_floor = copy.deepcopy(base)
    floor_basis_off_floor["blockers"][0]["floor_basis"] = "demonstrated"
    blocked(floor_basis_off_floor, "must record not_applicable")

    floor_basis_missing = copy.deepcopy(base)
    floor_basis_missing["blockers"][1]["floor_basis"] = "not_applicable"
    blocked(floor_basis_missing, "demonstrated or precautionary")

    # Edison Ship Gate controls.
    dev_base = dev_sample_record()
    check(not validate_record(dev_base), "dev-stage sample record is valid")

    dev_stage_mismatch = copy.deepcopy(dev_base)
    dev_stage_mismatch["loop"]["ship_stage"]["basis"] = "production_promotion"
    blocked(dev_stage_mismatch, "owner directive, a non-production target")

    def widen_to_high(record: dict[str, Any]) -> dict[str, Any]:
        target = record["blockers"][0]
        target["impact"] = "high"
        target["probability_percent"] = 30
        target["risk_rationale"] = (
            "The abnormal path degrades a bounded dev workflow and is tracked "
            "for the next increment rather than held before the deploy."
        )
        target["resolution"]["priority"] = "P2"
        return record

    dev_high_defer = widen_to_high(copy.deepcopy(dev_base))
    check(
        not validate_record(dev_high_defer),
        "a verified dev normal path defers high-impact abnormal-path work",
    )

    production_high_defer = widen_to_high(copy.deepcopy(base))
    blocked(production_high_defer, "medium impact with measured pressure")

    unverified_dev = widen_to_high(copy.deepcopy(dev_base))
    unverified_dev["loop"]["ship_stage"]["happy_path"] = {
        "verified": False,
        "check_ref": None,
        "summary": "The dev smoke run has not been executed on this head.",
    }
    blocked(unverified_dev, "medium impact with measured pressure")

    unverified_go = copy.deepcopy(dev_base)
    unverified_go["loop"]["ship_stage"]["happy_path"] = {
        "verified": False,
        "check_ref": None,
        "summary": "The dev smoke run has not been executed on this head.",
    }
    blocked(unverified_go, "normal path verified against a concrete check")

    unverified_with_ref = copy.deepcopy(dev_base)
    unverified_with_ref["loop"]["ship_stage"]["happy_path"] = {
        "verified": False,
        "check_ref": "check:dev-smoke-normal-path",
        "summary": "An unverified claim cannot carry a check.",
    }
    blocked(unverified_with_ref, "cannot carry a check_ref")

    dev_critical_defer = copy.deepcopy(dev_base)
    target = dev_critical_defer["blockers"][0]
    target["impact"] = "critical"
    target["probability_percent"] = 20
    target["risk_rationale"] = (
        "A critical failure stays fix-now even on a dev target because the "
        "deploy would carry it to every human tester."
    )
    target["resolution"]["priority"] = "P2"
    blocked(dev_critical_defer, "critical impact stays fix-now")

    def as_security(record: dict[str, Any], basis: str) -> dict[str, Any]:
        target = record["blockers"][0]
        target["finding_class"] = "hardening"
        target["protected_floor"] = "security"
        target["floor_basis"] = basis
        target["resolution"]["concurred_by"] = ["cc-misa-hime", "codex-misa"]
        target["summary"] = "A defence-in-depth header is still missing"
        target["failure_sequence"] = (
            "A response leaves the dev service without the hardening header, "
            "so a future reachable path would lose one defence layer."
        )
        target["risk_rationale"] = (
            "No reachable exploitation sequence has been demonstrated against "
            "the dev surface; the header is layered defence."
        )
        target["resolution"]["priority"] = "P0"
        return record

    dev_precautionary_security = as_security(copy.deepcopy(dev_base), "precautionary")
    check(
        not validate_record(dev_precautionary_security),
        "dev ship defers precautionary security hardening to an issue",
    )

    dev_demonstrated_security = as_security(copy.deepcopy(dev_base), "demonstrated")
    dev_demonstrated_security["blockers"][0]["risk_rationale"] = (
        "A reachable request sequence was demonstrated against the dev "
        "surface, so the finding is a defect rather than hardening."
    )
    blocked(dev_demonstrated_security, "protected safety-floor blockers cannot be deferred")

    production_precautionary_security = as_security(copy.deepcopy(base), "precautionary")
    blocked(
        production_precautionary_security,
        "protected safety-floor blockers cannot be deferred",
    )

    dev_precautionary_data_loss = copy.deepcopy(dev_base)
    dev_precautionary_data_loss["blockers"][0]["protected_floor"] = "data_loss"
    dev_precautionary_data_loss["blockers"][0]["floor_basis"] = "precautionary"
    dev_precautionary_data_loss["blockers"][0]["resolution"]["priority"] = "P0"
    blocked(
        dev_precautionary_data_loss,
        "protected safety-floor blockers cannot be deferred",
    )

    dev_happy_path_defer = copy.deepcopy(dev_base)
    dev_happy_path_defer["blockers"][0]["finding_class"] = "happy_path"
    blocked(dev_happy_path_defer, "shipped normal path cannot be deferred")

    # The security exception is for hardening. A reachable abnormal-path or
    # unclassified defect wearing the security floor must not reach the issue
    # queue by relabelling its basis precautionary.
    for escaping_class in ("abnormal_path", "other"):
        dev_class_escape = as_security(copy.deepcopy(dev_base), "precautionary")
        dev_class_escape["blockers"][0]["finding_class"] = escaping_class
        dev_class_escape["blockers"][0]["failure_sequence"] = (
            "An unauthenticated dev request reaches the privileged handler "
            "through the unguarded fallback route and returns tenant data."
        )
        blocked(
            dev_class_escape,
            "protected safety-floor blockers cannot be deferred",
        )

    dev_security_single_concurrence = as_security(
        copy.deepcopy(dev_base), "precautionary"
    )
    dev_security_single_concurrence["blockers"][0]["resolution"]["concurred_by"] = [
        "cc-misa-hime"
    ]
    blocked(dev_security_single_concurrence, "every registered reviewer to concur")

    unattested_dev = copy.deepcopy(dev_base)
    unattested_dev["loop"]["ship_stage"]["evidence_attestation"] = None
    blocked(unattested_dev, "registered reviewer to attest the recorded basis")

    unattested_envelope = widen_to_high(copy.deepcopy(dev_base))
    unattested_envelope["loop"]["ship_stage"]["evidence_attestation"] = None
    blocked(unattested_envelope, "medium impact with measured pressure")

    self_attested_dev = copy.deepcopy(dev_base)
    self_attested_dev["loop"]["ship_stage"]["evidence_attestation"] = {
        "reviewer_id": "misa-3",
        "evidence_refs": ["run:implementer-dev-smoke"],
    }
    blocked(self_attested_dev, "registered reviewer who is not the implementer")

    unsupported_attestation = copy.deepcopy(dev_base)
    unsupported_attestation["loop"]["ship_stage"]["evidence_attestation"][
        "evidence_refs"
    ] = []
    blocked(unsupported_attestation, "concrete refs the reviewer confirmed")

    production_attestation = copy.deepcopy(base)
    production_attestation["loop"]["ship_stage"]["evidence_attestation"] = {
        "reviewer_id": "codex-misa",
        "evidence_refs": ["run:reviewer-acceptance-rerun"],
    }
    blocked(production_attestation, "only a dev ship with a verified normal path")

    green_hold = copy.deepcopy(dev_base)
    green_hold["final_readback"]["ship_decision"] = {
        "decision": "hold",
        "rationale": "The reviewer would prefer another hardening round first.",
    }
    blocked(green_hold, "cannot be held")

    retained_go = copy.deepcopy(dev_base)
    retained = copy.deepcopy(retained_go["blockers"][0])
    retained["id"] = "retained-normal-path-defect"
    retained["finding_class"] = "happy_path"
    retained["resolution"] = {
        "disposition": "fix_now",
        "priority": "P3",
        "rationale": "The normal path must work before the dev deploy.",
        "concurred_by": ["cc-misa-hime"],
        "issue_url": None,
        "human_report": None,
    }
    retained_go["blockers"].append(retained)
    retained_go["final_readback"]["retained_blocker_ids"] = [
        "retained-normal-path-defect"
    ]
    blocked(retained_go, "go cannot carry retained fix-now findings")

    dev_render = render_markdown(dev_base)
    check("Ship stage: `dev_deploy`" in dev_render, "render states the ship stage")
    check("Ship decision: `go`" in dev_render, "render states the ship decision")
    check("Promotion Debt" in dev_render, "render carries dev promotion debt")
    check(
        "Ship authority: readiness only" in dev_render,
        "render states the readiness-only authority boundary",
    )
    check(
        "no deploy, merge, or access authority" in dev_render,
        "render denies deploy authority to the ship decision",
    )

    # Schema 1.0 compatibility: the persisted records written before the ship
    # stage existed stay readable through a tested upgrade path.
    # The priority role and its directive must agree, in both directions, or an
    # unpinned authority is recordable and a legitimate absent one is not.
    active_without_directive = copy.deepcopy(base)
    active_without_directive["loop"]["priority_authority"]["directive"] = None
    blocked(active_without_directive, "must name the directive it arises from")

    active_without_holder = copy.deepcopy(base)
    active_without_holder["loop"]["roles"]["priority_reviewer_id"] = None
    blocked(active_without_holder, "exactly one reviewer holds it")

    inactive_with_holder = copy.deepcopy(base)
    inactive_with_holder["loop"]["priority_authority"] = {
        "active": False,
        "directive": None,
    }
    blocked(inactive_with_holder, "the priority role does not arise")

    unpinned_deadline = copy.deepcopy(base)
    unpinned_deadline["loop"]["deadline"]["source_pin"] = None
    blocked(unpinned_deadline, "pin it by content")

    # A record with no deadline in force must be migratable: the schema calls it
    # correct, so the upgrade path has to accept it rather than demanding a
    # clock reading that legitimately does not exist.
    for version in MIGRATABLE_SCHEMA_VERSIONS:
        no_deadline_legacy = legacy_sample_record()
        no_deadline_legacy["schema_version"] = version
        if version == "1.0":
            no_deadline_legacy["final_readback"].pop("ship_decision", None)
            for blocker in no_deadline_legacy["blockers"]:
                blocker.pop("finding_class", None)
                blocker.pop("floor_basis", None)
        no_deadline_legacy["loop"]["deadline"] = {
            "at": None,
            "source": "none",
            "source_ref": "",
            "source_pin": None,
            "clock_readings": [],
            "minimum_shape": None,
        }
        no_deadline_legacy["loop"]["priority_authority"] = {
            "active": False,
            "directive": None,
        }
        no_deadline_legacy["loop"]["roles"]["priority_reviewer_id"] = None
        upgraded_no_deadline = migrate_record(no_deadline_legacy)
        check(
            upgraded_no_deadline["schema_version"] == SCHEMA_VERSION,
            f"a schema {version} record with no deadline in force still migrates",
        )

    # A superseded record is routed to the upgrade path, not handed a shape
    # error about the version field it correctly carries.
    for version in MIGRATABLE_SCHEMA_VERSIONS:
        superseded = legacy_sample_record()
        superseded["schema_version"] = version
        routed = validate_record_full(superseded)
        check(
            any("fairy blocker migrate" in item.message for item in routed),
            f"a schema {version} record is routed to the upgrade path",
        )

    # These validators existed but nothing called them, so the schema layer was
    # doing all the work and their cross-object rules were inert. One control
    # per validator, so a future refactor that drops the call site goes red.
    for label, mutate in (
        ("target fields", lambda r: r["loop"]["target"].__setitem__("repo", "")),
        (
            "target directive pinning",
            lambda r: r["loop"]["target"]["directive_refs"][0].__setitem__(
                "content_hash", "nope"
            ),
        ),
        (
            "envelope pinning",
            lambda r: r["loop"]["claim_envelope"]["claim_snapshot_refs"][0].__setitem__(
                "content_hash", "nope"
            ),
        ),
        ("branch naming", lambda r: r["loop"]["working_branch"].__setitem__("name", "")),
        (
            "clock reading phase",
            lambda r: r["loop"]["deadline"]["clock_readings"][0].__setitem__(
                "phase", "whenever"
            ),
        ),
        (
            "minimum shape items",
            lambda r: r["loop"]["deadline"]["minimum_shape"].__setitem__(
                "named_items", []
            ),
        ),
    ):
        wired = copy.deepcopy(base)
        mutate(wired)
        check(
            bool(validate_record(wired)),
            f"the runtime validator for {label} is reached",
        )

    # A cross-object rule the schema cannot state at all: the priority role is
    # active while no reviewer holds it. If the runtime layer were bypassed this
    # would pass, which is what makes it a wiring control rather than a shape one.
    unreachable_by_schema = copy.deepcopy(base)
    unreachable_by_schema["loop"]["roles"]["priority_reviewer_id"] = None
    check(
        not validate_against_schema(unreachable_by_schema),
        "the schema alone cannot see an unheld active priority role",
    )
    check(
        bool(validate_record(unreachable_by_schema)),
        "the runtime layer catches what the schema cannot express",
    )

    # RFC 3339 permits a lowercase zone designator, and the schema pattern
    # allows it. The parser used to accept only the uppercase form, so the two
    # layers disagreed on a legal timestamp.
    lowercase_zone = copy.deepcopy(base)
    lowercase_zone["loop"]["deadline"]["minimum_shape"]["registered_at"] = (
        "2026-07-26T13:50:00z"
    )
    check(
        not validate_record_full(lowercase_zone),
        "a lowercase RFC 3339 zone designator is accepted by both layers",
    )

    # A 1.0 record must still upgrade: the previous release promised persisted
    # records upgrade rather than expire, and the 1.2 evidence is demanded from
    # the operator rather than invented, exactly as for 1.1.
    v1_0 = legacy_sample_record()
    v1_0["schema_version"] = "1.0"
    v1_0["final_readback"].pop("ship_decision", None)
    for blocker in v1_0["blockers"]:
        blocker.pop("finding_class", None)
        blocker.pop("floor_basis", None)
    migrated_v1_0 = migrate_record(v1_0)
    check(
        migrated_v1_0["schema_version"] == SCHEMA_VERSION,
        "a schema 1.0 record chains through to the current schema",
    )
    check(
        migrated_v1_0["loop"]["ship_stage"]["stage"] == "production",
        "the 1.0 upgrade keeps the unrelaxed stage it decided under",
    )

    stripped_v1_0 = copy.deepcopy(v1_0)
    stripped_v1_0["loop"].pop("target", None)
    try:
        migrate_record(stripped_v1_0)
    except ArtifactError as exc:
        check(
            "attach it before migrating" in str(exc),
            "the 1.0 upgrade also refuses to invent the 1.2 evidence",
        )
    else:
        check(False, "the 1.0 upgrade invented the 1.2 evidence")

    # The human readback has to carry the evidence the cards require, or the
    # record satisfies the validator and tells the owner nothing.
    rendered = render_markdown(base)
    for needle in (
        "Priority authority:",
        "Clock readings:",
        "Minimum shape:",
        "Target:",
        "Claim envelope:",
        "Working branch:",
    ):
        check(needle in rendered, f"readback carries {needle.rstrip(':')!r}")

    # The unapproved-branch floor: raised without an exit, deferred at any
    # concurrence, and approval claimed without a ref. Each of these is a way
    # the value could be stated in the schema and never enforced at runtime.
    branch_no_exit = copy.deepcopy(base)
    branch_no_exit["blockers"][0]["protected_floor"] = "unapproved_branch_change"
    branch_no_exit["blockers"][0]["floor_basis"] = "demonstrated"
    blocked(branch_no_exit, "must record which exit was taken")

    branch_deferred = copy.deepcopy(dev_base)
    branch_deferred["blockers"][0]["protected_floor"] = "unapproved_branch_change"
    branch_deferred["blockers"][0]["floor_basis"] = "precautionary"
    branch_deferred["blockers"][0]["finding_class"] = "hardening"
    branch_deferred["blockers"][0]["resolution"]["disposition"] = "defer_issue"
    blocked(branch_deferred, "not deferrable at any level of concurrence")

    branch_unevidenced_approval = copy.deepcopy(base)
    branch_unevidenced_approval["blockers"][0]["protected_floor"] = (
        "unapproved_branch_change"
    )
    branch_unevidenced_approval["blockers"][0]["floor_basis"] = "demonstrated"
    branch_unevidenced_approval["loop"]["working_branch"]["remedy"] = (
        "approval_produced"
    )
    branch_unevidenced_approval["loop"]["working_branch"]["approval_ref"] = ""
    blocked(branch_unevidenced_approval, "citable ref")

    # The authoritative entrypoint must enforce the canonical schema, not a
    # hand-copy of it. Each of these is rejected by the schema file; before the
    # entrypoint was unified they were accepted by the CLI that decides.
    for label, mutate in (
        ("target", lambda r: r["loop"].__setitem__("target", {})),
        ("claim_envelope", lambda r: r["loop"].__setitem__("claim_envelope", {})),
        ("working_branch", lambda r: r["loop"].__setitem__("working_branch", {})),
        (
            "clock_readings",
            lambda r: r["loop"]["deadline"].__setitem__("clock_readings", [{}]),
        ),
        (
            "minimum_shape",
            lambda r: r["loop"]["deadline"].__setitem__("minimum_shape", {}),
        ),
        (
            "shape hash",
            lambda r: r["loop"]["deadline"]["minimum_shape"].__setitem__(
                "hash", "latest"
            ),
        ),
        (
            "fixed_by_ref",
            lambda r: r["loop"]["working_branch"].__setitem__("fixed_by_ref", ""),
        ),
        (
            "snapshot refs",
            lambda r: r["loop"]["claim_envelope"].__setitem__(
                "claim_snapshot_refs", []
            ),
        ),
    ):
        shaped = copy.deepcopy(base)
        mutate(shaped)
        check(
            bool(validate_record_full(shaped)),
            f"authoritative entrypoint enforces the schema shape of {label}",
        )

    # Both deadline branches, because the constraint is conditional: an absent
    # deadline legitimately has no clock to read and no window to register a
    # shape in, and an in-force one must have both.
    absent_deadline = copy.deepcopy(base)
    absent_deadline["loop"]["deadline"] = {
        "at": None,
        "source": "none",
        "source_ref": "",
        "source_pin": None,
        "clock_readings": [],
        "minimum_shape": None,
    }
    # With no directive in force the priority role does not arise either.
    absent_deadline["loop"]["priority_authority"] = {"active": False, "directive": None}
    absent_deadline["loop"]["roles"]["priority_reviewer_id"] = None
    check(
        not validate_record_full(absent_deadline),
        "an absent deadline needs no clock reading and no pre-registered shape",
    )

    absent_with_clock = copy.deepcopy(absent_deadline)
    absent_with_clock["loop"]["deadline"]["clock_readings"] = [
        {"at": "2026-07-26T13:50:00+09:00", "phase": "round_start"}
    ]
    blocked(absent_with_clock, "nothing to read a clock against")

    absent_with_shape = copy.deepcopy(absent_deadline)
    absent_with_shape["loop"]["deadline"]["minimum_shape"] = {
        "owner_goal_ref": "source:none",
        "named_items": ["x"],
        "hash": "c" * 64,
        "registered_at": "2026-07-26T13:50:00+09:00",
    }
    blocked(absent_with_shape, "no window to register it in")

    movable_baseline = copy.deepcopy(base)
    movable_baseline["loop"]["claim_envelope"]["baseline_ref"] = "main"
    blocked(movable_baseline, "must be a commit id, not a movable name")

    # A deadline nobody read a clock against, and one whose shape was never
    # pre-registered: both are the felt deadline the card forbids.
    unread_clock = copy.deepcopy(base)
    unread_clock["loop"]["deadline"]["clock_readings"] = []
    blocked(unread_clock, "at least one real clock reading")

    unregistered_shape = copy.deepcopy(base)
    unregistered_shape["loop"]["deadline"]["minimum_shape"] = None
    blocked(unregistered_shape, "pre-registered")

    # Migration refuses to invent the 1.2 evidence. Without a record that is
    # actually missing it, the refusal is unreachable and therefore untested.
    stripped_legacy = legacy_sample_record()
    for key in ("target", "claim_envelope", "working_branch"):
        stripped_legacy["loop"].pop(key, None)
    stripped_legacy["loop"]["roles"].pop("priority_reviewer_id", None)
    stripped_legacy["loop"]["deadline"].pop("clock_readings", None)
    try:
        migrate_record(stripped_legacy)
    except ArtifactError as exc:
        check(
            "attach it before migrating" in str(exc),
            "migration refuses to invent the evidence 1.1 never captured",
        )
    else:
        check(False, "migration invented the 1.2 evidence")

    legacy = legacy_sample_record()
    blocked(legacy, "is superseded; upgrade the record with `fairy blocker migrate`")
    migrated = migrate_record(legacy)
    check(not validate_record(migrated), "a migrated 1.0 record validates")
    check(
        migrated["loop"]["ship_stage"]["stage"] == "production"
        and migrated["loop"]["ship_stage"]["happy_path"]["verified"] is False
        and migrated["loop"]["ship_stage"]["evidence_attestation"] is None,
        "migration keeps the unrelaxed production thresholds",
    )
    check(
        all(blocker["finding_class"] == "other" for blocker in migrated["blockers"]),
        "migration classes unlabelled findings conservatively",
    )
    check(
        migrated["blockers"][1]["floor_basis"] == "demonstrated",
        "migration treats an unlabelled floor finding as demonstrated",
    )

    migrated_widened = widen_to_high(copy.deepcopy(migrated))
    blocked(migrated_widened, "medium impact with measured pressure")

    for rejected, label in (
        (sample_record(), "already current"),
        ({"schema_version": "0.9"}, "unknown version"),
    ):
        try:
            migrate_record(rejected)
        except ArtifactError:
            controls += 1
        else:
            raise AssertionError(f"migration must reject a {label} record")

    legacy_held = legacy_sample_record()
    legacy_held["blockers"][0]["resolution"] = {
        "disposition": "fix_now",
        "priority": "P3",
        "rationale": "The finding is repaired inside this increment.",
        "concurred_by": ["cc-misa-hime"],
        "issue_url": None,
        "human_report": None,
    }
    legacy_held["final_readback"]["deferred_blocker_ids"] = []
    legacy_held["final_readback"]["retained_blocker_ids"] = ["minor-capacity-eviction"]
    legacy_held["final_readback"]["reported_to_human"] = False
    legacy_held["final_readback"]["report_ref"] = ""
    migrated_held = migrate_record(legacy_held)
    check(
        migrated_held["final_readback"]["ship_decision"]["decision"] == "hold",
        "migration derives hold from a retained fix-now finding",
    )

    with tempfile.TemporaryDirectory(prefix=".helix-migrate-", dir=ROOT) as raw:
        tmp = Path(raw)
        legacy_path = tmp / "legacy.json"
        upgraded_path = tmp / "upgraded.json"
        legacy_path.write_text(
            json.dumps(legacy_sample_record(), indent=2) + "\n", encoding="utf-8"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            migrate_status = command_migrate(
                argparse.Namespace(record=legacy_path, output=upgraded_path)
            )
        check(migrate_status == 0, "CLI migration writes the upgraded record")
        check(
            not validate_record(json.loads(upgraded_path.read_text(encoding="utf-8"))),
            "the written upgrade validates from disk",
        )

    with tempfile.TemporaryDirectory(prefix=".helix-selftest-", dir=ROOT) as raw:
        tmp = Path(raw)
        record_path = tmp / "record.json"
        output_path = tmp / "record.md"
        record_path.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
        loaded = load_record(record_path)
        check(loaded["artifact_type"] == "helix_blocker_triage", "CLI load path")
        write_text_atomic(output_path, render_markdown(loaded))
        check(output_path.is_file(), "derived view writes")
        check("Risk score" in output_path.read_text(encoding="utf-8"), "render risk score")
        check("24.0h remaining" in output_path.read_text(encoding="utf-8"), "render deadline")
        alias = tmp / "record-alias.json"
        alias.symlink_to(record_path.name)
        before = record_path.read_bytes()
        for collision_output in (record_path, alias):
            try:
                command_render(
                    argparse.Namespace(record=record_path, output=collision_output)
                )
            except ArtifactError:
                controls += 1
            else:
                raise AssertionError("render collision must be blocked")
        check(record_path.read_bytes() == before, "collision leaves input unchanged")

    schema = json.loads(
        (ROOT / "schemas" / "helix-blocker-triage.schema.json").read_text(
            encoding="utf-8"
        )
    )
    check(set(schema["required"]) == TOP_KEYS, "schema top-level keys match runtime")
    check(
        set(schema["properties"]["loop"]["required"]) == LOOP_KEYS,
        "schema loop keys match runtime",
    )
    check(
        set(schema["$defs"]["blocker"]["required"]) == BLOCKER_KEYS,
        "schema blocker keys match runtime",
    )
    check(
        set(schema["$defs"]["shipStage"]["required"]) == SHIP_STAGE_KEYS,
        "schema ship-stage keys match runtime",
    )
    check(
        set(schema["$defs"]["happyPath"]["required"]) == HAPPY_PATH_KEYS,
        "schema happy-path keys match runtime",
    )
    check(
        set(schema["$defs"]["shipAttestation"]["required"]) == SHIP_ATTESTATION_KEYS,
        "schema ship-attestation keys match runtime",
    )
    check(
        schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION,
        "schema version constant matches runtime",
    )
    check(
        set(schema["$defs"]["shipDecision"]["required"]) == SHIP_DECISION_KEYS,
        "schema ship-decision keys match runtime",
    )
    check(
        set(schema["$defs"]["finalReadback"]["required"]) == READBACK_KEYS,
        "schema readback keys match runtime",
    )
    print(f"Helix blocker triage selftest OK: {controls} controls")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    record = load_record(args.record)
    print(
        "Helix blocker triage valid: "
        f"{len(record['blockers'])} finding(s), "
        f"{len(record['final_readback']['deferred_blocker_ids'])} deferred"
    )
    return 0


def command_render(args: argparse.Namespace) -> int:
    record_path = canonical_artifact_path(args.record, "Helix blocker triage record")
    require_distinct_paths(
        record_path,
        args.output,
        "record and Markdown output paths must be distinct",
    )
    record = load_record(record_path)
    write_text_atomic(args.output, render_markdown(record))
    print(args.output)
    return 0


def command_migrate(args: argparse.Namespace) -> int:
    record_path = canonical_artifact_path(args.record, "Helix blocker triage record")
    require_distinct_paths(
        record_path,
        args.output,
        "record and migrated output paths must be distinct",
    )
    upgraded = migrate_record(load_json(record_path))
    write_text_atomic(args.output, json.dumps(upgraded, indent=2) + "\n")
    print(args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a triage record")
    validate.add_argument("--record", type=Path, required=True)
    render = subparsers.add_parser("render", help="render a validated Markdown readback")
    render.add_argument("--record", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    migrate = subparsers.add_parser(
        "migrate",
        help=f"upgrade a schema {MIGRATABLE_SCHEMA_VERSION} record to {SCHEMA_VERSION}",
    )
    migrate.add_argument("--record", type=Path, required=True)
    migrate.add_argument("--output", type=Path, required=True)
    subparsers.add_parser("selftest", help="run deterministic hostile controls")
    sample = subparsers.add_parser("sample", help="validate the committed sample")
    sample.add_argument("--record", type=Path, default=DEFAULT_SAMPLE)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return command_validate(args)
        if args.command == "render":
            return command_render(args)
        if args.command == "migrate":
            return command_migrate(args)
        if args.command == "selftest":
            return run_selftest()
        if args.command == "sample":
            args.command = "validate"
            return command_validate(args)
    except (ArtifactError, OSError, json.JSONDecodeError) as exc:
        print(f"Helix blocker triage error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
