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
}
SHIP_STAGE_KEYS = {"stage", "basis", "basis_ref", "happy_path", "evidence_attestation"}
HAPPY_PATH_KEYS = {"verified", "check_ref", "summary"}
SHIP_ATTESTATION_KEYS = {"reviewer_id", "evidence_refs"}
SHIP_DECISION_KEYS = {"decision", "rationale"}
ROLE_KEYS = {"implementer_id", "reviewer_ids", "priority_reviewer_id"}
DEADLINE_KEYS = {"at", "source", "source_ref", "clock_readings", "minimum_shape"}
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
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
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
    if not valid_id(priority_reviewer):
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


def validate_deadline(
    value: Any,
    evaluated_at: datetime | None,
    findings: list[Finding],
) -> datetime | None:
    deadline = object_shape(
        value,
        path="helix.loop.deadline",
        required={"at", "source", "source_ref", "clock_readings"},
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
        return None
    parsed = parse_timestamp(at, "helix.loop.deadline.at", findings)
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
    if schema_version == MIGRATABLE_SCHEMA_VERSION:
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
    return findings


def require_valid(record: Any) -> None:
    findings = validate_record(record)
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
            loop["evaluated_at"].replace("Z", "+00:00")
        )
        deadline_at = datetime.fromisoformat(deadline["at"].replace("Z", "+00:00"))
        remaining_hours = (deadline_at - evaluated_at).total_seconds() / 3600
        deadline_summary = (
            f"{deadline['at']} ({remaining_hours:.1f}h remaining at evaluation; "
            f"{deadline['source']})"
        )
    usage = loop["usage"]
    ship = loop["ship_stage"]
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
    if version != MIGRATABLE_SCHEMA_VERSION:
        raise ArtifactError(
            f"only schema {MIGRATABLE_SCHEMA_VERSION} records can be migrated"
        )
    upgraded = copy.deepcopy(record)
    upgraded["schema_version"] = SCHEMA_VERSION

    loop = upgraded.get("loop")
    if not isinstance(loop, dict):
        raise ArtifactError("helix.loop must be an object")
    if "ship_stage" in loop:
        raise ArtifactError("a schema 1.0 record cannot already carry a ship_stage")
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
        "schema_version": "1.1",
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
            },
            "deadline": {
                "at": "2026-07-27T14:00:00+09:00",
                "source": "explicit_owner",
                "source_ref": "source:owner-deadline",
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
    """The canonical sample as schema 1.0 wrote it, before the ship stage."""
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
