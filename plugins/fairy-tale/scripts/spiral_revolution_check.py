#!/usr/bin/env python3
"""Exercise/enforcement check for Spiral Engineering revolution records.

This is deliberately NOT a residency presence check. `fairy_tale_residency_check.py`
verifies that the spiral *spec text* exists in the docs (presence). That is not
enough: a spec can be written and then never used. PR #41 shipped the Spiral
Engineering / double-helix spec with green presence/parity/CI, yet carried no
exercised revolution record and no evidence-pairing enforcement -- a
false-negative surfaced under Jun's no-blocking critical-thinking challenge
(fairy_tale #43/#44).

This script exercises the spec: it requires at least one well-formed spiral
revolution record whose evidence-bearing fields carry CONCRETE, verifiable
references -- a URL with host+path (e.g. a commit/PR URL), a sha256: digest,
a run-/trace- id, or an existing repo path. Bare #N, bare commit shas (use a
commit URL), abbreviated or shape-only hex, and freeform prose are rejected.
A record with empty/missing/placeholder evidence fails -- so the gate cannot
be satisfied by presence alone.

Usage:
  spiral_revolution_check.py [--records DIR] [--json]

Exit code 0 = at least one record present and all records pass; 1 = otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS_DIR = ROOT / "spiral-revolutions"

# A concrete, *verifiable* reference. Each evidence entry must BE one of these
# (hostile-review hardened, fairy_tale #44 / PR #45). Rejected as NOT concrete:
# a bare short hex token (`deadbee`), a bare `#44`, a bare 40-hex sha that is only
# the right *shape* (e.g. `0000...0` / `aaaa...a` -- use a commit URL instead),
# and any freeform prose (incl. "trust me <url>"). Accepted forms:
#   - URL with host+path:        https://github.com/owner/repo/commit/<sha>
#   - sha256 digest (>=32 hex):  sha256:9e5e7b60...
#   - run-/trace- id (length):   run-20260626T0011Z-cc-...
#   - an existing repo file path: scripts/spiral_revolution_check.py
# Bare commit shas are intentionally NOT accepted: a 40-hex shape is not
# verifiable, so reference the commit by URL.
_URL = r"https?://[^\s/]+\.[^\s/]+/\S+"
_SHA256 = r"\bsha256:[0-9a-f]{32,}\b"
_RUNTRACE = r"\b(?:run|trace)-[0-9A-Za-z][0-9A-Za-z._-]{7,}\b"
CONCRETE_REF = re.compile("|".join((_URL, _SHA256, _RUNTRACE)), re.IGNORECASE)
REPO_PATH_RE = re.compile(r"(?:[\w.\-]+/)+[\w.\-]+\.(?:py|json|md|ts|tsx|js|mjs|cjs|yml|yaml|sh|toml|txt)")

# Discord user-id (snowflake): the unforgeable identity key for review calibration.
_SNOWFLAKE = re.compile(r"^[0-9]{15,21}$")

# Short label words allowed to prefix a ref (e.g. "see <url>") without the entry
# counting as freeform prose.
_LABEL_WORDS = re.compile(r"(?i)\b(?:commit|merge|pr|issue|sha|ref|run|trace|id|see|at|in|on|the|comment)\b")

# After removing refs, label words and non-alphanumerics, any leftover means the
# entry is prose with a ref smuggled in, not a clean reference. Must be empty.
_MAX_RESIDUE = 0

# Tokens that look like evidence but are not.
PLACEHOLDERS = {
    "", "todo", "tbd", "n/a", "na", "none", "null", "-", "--", "...",
    "placeholder", "xxx", "fixme", "pending", "wip", "?",
}

# Fields whose entries must each be concrete evidence references.
EVIDENCE_PATHS = (
    ("strand_pairing_evidence",),
    ("execution_strand", "validation_reviews"),
    ("risk", "burn_down_evidence"),
    ("ledger_receipt",),
)

REQUIRED_TOP = (
    "schema_version", "revolution_id", "altitude", "execution_strand",
    "learning_governance_strand", "strand_pairing_evidence", "risk",
    "mismatch_repair", "validated_governance_template", "win_condition",
    "budget_radius", "safety_floor", "ledger_receipt",
)
REQUIRED_ALTITUDE = ("current", "target", "axis")
ALTITUDE_AXES = {"autonomy", "abstraction", "scope", "delegation", "capability", "risk_burn_down"}
REQUIRED_EXEC = ("objective", "engineer_target", "validation_reviews")
REQUIRED_LEARN = ("double_loop_evaluation", "governing_variable_change", "next_altitude", "stop_or_descend")
REQUIRED_RISK = ("highest_uncertainty", "spike", "burn_down_evidence")


def _get(record: dict, path: tuple[str, ...]):
    node = record
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _entry_problem(entry) -> str | None:
    """Return why `entry` is not a clean, verifiable concrete ref, else None."""
    if not isinstance(entry, str) or not entry.strip():
        return "empty/non-string"
    if entry.strip().strip(".").lower() in PLACEHOLDERS:
        return "placeholder"
    residue = entry
    matched = False
    for match in CONCRETE_REF.finditer(entry):
        residue = residue.replace(match.group(0), " ", 1)
        matched = True
    for match in REPO_PATH_RE.finditer(entry):
        token = match.group(0)
        if ".." in token.split("/"):
            return f"repo path must not traverse with '..': {token}"
        try:
            resolved = (ROOT / token).resolve()
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            return f"repo path escapes the repo root: {token}"
        if not resolved.exists():
            return f"repo path does not exist: {token}"
        residue = residue.replace(token, " ", 1)
        matched = True
    if not matched:
        return "not a concrete ref (need URL / sha256: / run-trace id / commit URL / existing repo path)"
    # Reject prose smuggled in alongside a ref: strip label words + non-alphanumerics
    # and require the leftover to be short.
    residue = _LABEL_WORDS.sub(" ", residue)
    residue = re.sub(r"[^0-9A-Za-z]", "", residue)
    if len(residue) > _MAX_RESIDUE:
        return "freeform prose mixed with ref (keep evidence entries ref-only)"
    return None


def _check_evidence_array(value, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: must be a non-empty array (unpaired evidence)")
        return
    for index, entry in enumerate(value):
        problem = _entry_problem(entry)
        if problem:
            errors.append(f"{label}[{index}]: {problem}: {entry!r}")


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record is not a JSON object"]

    for key in REQUIRED_TOP:
        if key not in record:
            errors.append(f"missing required field: {key}")

    if record.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")

    altitude = record.get("altitude")
    if isinstance(altitude, dict):
        for key in REQUIRED_ALTITUDE:
            if not altitude.get(key):
                errors.append(f"altitude.{key}: required and non-empty")
        if altitude.get("axis") not in ALTITUDE_AXES:
            errors.append(f"altitude.axis must be one of {sorted(ALTITUDE_AXES)}")
    else:
        errors.append("altitude: required object")

    exec_strand = record.get("execution_strand")
    if isinstance(exec_strand, dict):
        for key in ("objective", "engineer_target"):
            if not exec_strand.get(key):
                errors.append(f"execution_strand.{key}: required and non-empty")
    else:
        errors.append("execution_strand: required object")

    learn = record.get("learning_governance_strand")
    if isinstance(learn, dict):
        for key in REQUIRED_LEARN:
            if not learn.get(key):
                errors.append(f"learning_governance_strand.{key}: required and non-empty")
    else:
        errors.append("learning_governance_strand: required object")

    risk = record.get("risk")
    if isinstance(risk, dict):
        for key in ("highest_uncertainty", "spike"):
            if not risk.get(key):
                errors.append(f"risk.{key}: required and non-empty")
    else:
        errors.append("risk: required object")

    mismatch = record.get("mismatch_repair")
    if not isinstance(mismatch, dict) or "mismatches" not in mismatch or not mismatch.get("repair_action"):
        errors.append("mismatch_repair: requires 'mismatches' array and non-empty 'repair_action'")

    for key in ("validated_governance_template", "win_condition", "budget_radius", "safety_floor"):
        if not record.get(key):
            errors.append(f"{key}: required and non-empty")

    # The teeth: evidence-bearing fields must carry concrete, non-placeholder refs.
    for path in EVIDENCE_PATHS:
        _check_evidence_array(_get(record, path), ".".join(path), errors)

    # Review calibration (fairy_tale #43): generalize the exercise gate to the
    # review itself, so a smooth no_block cannot pass without recorded refutation.
    _check_reviews(record, errors)

    return errors


PRINCIPALS_PATH = ROOT / "spiral-principals.json"


def _registered_principals() -> set[str] | None:
    """Load the trusted-principal registry (id keys). None = unreadable (fail closed)."""
    try:
        data = json.loads(PRINCIPALS_PATH.read_text(encoding="utf-8"))
        principals = data.get("principals", {})
        return {str(k) for k in principals} if isinstance(principals, dict) else None
    except (OSError, json.JSONDecodeError, AttributeError):
        return None


def _check_reviews(record: dict, errors: list[str]) -> None:
    # Identity keys on the unforgeable user_id, NOT the display name (aliases /
    # bot-ID-literal-in-name / spacing variants must not fool distinctness or the
    # circular-review guard). This mirrors the trust model's "judge by user_id" rule.
    implementer = record.get("implementer")
    implementer_id = record.get("implementer_id")
    if not isinstance(implementer, str) or not implementer.strip():
        errors.append("implementer: required and non-empty")
    if not isinstance(implementer_id, str) or not _SNOWFLAKE.match(implementer_id):
        errors.append("implementer_id: required, must be a Discord user id (15-21 digits)")
    # Bind identity to a registered principal: a format-valid but unregistered
    # snowflake is rejected (fail closed if the registry is unreadable).
    principals = _registered_principals()
    if principals is None:
        errors.append(f"trusted-principal registry unreadable: {PRINCIPALS_PATH.name}")
        principals = set()
    if isinstance(implementer_id, str) and _SNOWFLAKE.match(implementer_id) and implementer_id not in principals:
        errors.append(f"implementer_id '{implementer_id}' is not a registered principal ({PRINCIPALS_PATH.name})")
    reviews = record.get("reviews")
    if not isinstance(reviews, list) or len(reviews) < 2:
        errors.append("reviews: requires >= 2 entries")
        return
    reviewer_ids: list[str] = []
    for index, review in enumerate(reviews):
        label = f"reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{label}: must be an object")
            continue
        reviewer = review.get("reviewer")
        reviewer_id = review.get("reviewer_id")
        verdict = review.get("verdict")
        refute = review.get("refute_pass")
        if not isinstance(reviewer, str) or not reviewer.strip():
            errors.append(f"{label}.reviewer: required and non-empty")
        if not isinstance(reviewer_id, str) or not _SNOWFLAKE.match(reviewer_id):
            errors.append(f"{label}.reviewer_id: required, must be a Discord user id (15-21 digits)")
        elif reviewer_id not in principals:
            errors.append(f"{label}.reviewer_id '{reviewer_id}' is not a registered principal ({PRINCIPALS_PATH.name})")
        else:
            reviewer_ids.append(reviewer_id)
        if verdict not in ("block", "no_block"):
            errors.append(f"{label}.verdict: must be 'block' or 'no_block'")
        # The teeth: a no_block sign-off MUST point to a concrete refutation artifact
        # (what was actually attacked) -- prose like "reviewed carefully" is rejected.
        if verdict == "no_block":
            problem = _entry_problem(refute if isinstance(refute, str) else "")
            if problem:
                errors.append(f"{label}.refute_pass: a no_block verdict needs a concrete refutation artifact ({problem})")
        elif not (isinstance(refute, str) and refute.strip()):
            errors.append(f"{label}.refute_pass: required and non-empty")
    # >= 2 DISTINCT reviewers (by id, so duplicate entries do not count).
    if len(set(reviewer_ids)) < 2:
        errors.append("reviews: requires >= 2 DISTINCT reviewer_id (duplicate reviewers do not count)")
    # Circular-review guard, by id: the implementer must not also be a reviewer.
    if isinstance(implementer_id, str) and implementer_id in reviewer_ids:
        errors.append(f"circular review: implementer_id '{implementer_id}' must not also appear as a reviewer_id")


def _concrete_refutes(record: dict) -> list[str]:
    """The concrete refute_pass artifacts cited by a record's reviews."""
    out: list[str] = []
    reviews = record.get("reviews")
    if not isinstance(reviews, list):
        return out
    for review in reviews:
        if not isinstance(review, dict):
            continue
        refute = review.get("refute_pass")
        if isinstance(refute, str) and refute.strip() and _entry_problem(refute) is None:
            out.append(refute.strip())
    return out


_GITHUB_HOSTS = ("github.com",)


def _canon_ref(value: str) -> str:
    """Canonicalize a refute artifact for cross-record identity comparison so a
    reused artifact cannot be disguised by trivial URL variation -- without
    over-collapsing genuinely distinct ones. For a URL: lowercase; drop the query
    and any trailing slashes; keep only the fragment up to the first '?'/'&' (the
    comment anchor); strip a scheme-default port.

    Scheme is preserved per host, EXCEPT on github.com (and subdomains), where
    http always redirects to https and so reaches the same artifact -- there the
    scheme is normalized to https and both default ports (80/443) are stripped.
    For any other host, http:// and https:// are NOT assumed equal (they may be
    different servers), so the scheme is kept. Non-URL refs (sha256:, run-/trace-
    ids, repo paths) collapse to their lowercased, slash-trimmed form.
    """
    s = value.strip().lower()
    parts = urlsplit(s)
    if parts.scheme and parts.netloc:
        host = parts.hostname or parts.netloc
        try:
            port = parts.port
        except ValueError:
            port = None
        scheme = parts.scheme
        is_github = host in _GITHUB_HOSTS or any(host.endswith("." + h) for h in _GITHUB_HOSTS)
        if is_github:
            scheme = "https"
            drop_ports = (80, 443)
        else:
            drop_ports = (443,) if scheme == "https" else (80,) if scheme == "http" else ()
        netloc = host if (port is None or port in drop_ports) else f"{host}:{port}"
        path = parts.path.rstrip("/")
        fragment = re.split(r"[?&]", parts.fragment, maxsplit=1)[0].rstrip("/")
        base = f"{scheme}://{netloc}{path}"
        return f"{base}#{fragment}" if fragment else base
    return s.rstrip("/")


def check_cross_record(records: list[tuple[str, dict]]) -> tuple[list[str], dict]:
    """Cross-record review calibration (fairy_tale #43 follow-up).

    Per-record validation already requires every no_block sign-off to cite a
    concrete refutation artifact. That cannot see a rubber-stamp tell that spans
    records: pasting a *prior* turn's refute_pass forward. A given refutation
    artifact belongs to the turn that produced it -- it must not be reused as the
    evidence for a later revolution.

    ``records`` is a list of (ident, record) where ident is UNIQUE per record
    (the record's file name) -- NOT its revolution_id, so two records that share
    a revolution_id cannot launder a reuse through the collision. revolution_id
    uniqueness is enforced separately. refute artifacts are compared by their
    canonical form so URL casing / trailing-slash / appended-query variants of
    the same artifact still collide.

    Returns (errors, stats). Binding a refute_pass to its live author is out of
    scope by architecture: all three sibling agents commit/comment under one
    GitHub identity, so authorship cannot be distinguished at the GitHub layer;
    distinctness lives in the Discord user_id recorded per review.
    """
    errors: list[str] = []
    seen: dict[str, str] = {}  # canonical refute artifact -> ident that first used it
    rid_owner: dict[str, str] = {}  # revolution_id -> ident (uniqueness)
    no_block_reviews = 0
    refute_artifacts: set[str] = set()
    for ident, record in records:
        if not isinstance(record, dict):
            continue
        rid = record.get("revolution_id")
        if isinstance(rid, str) and rid.strip():
            if rid in rid_owner and rid_owner[rid] != ident:
                errors.append(
                    f"duplicate revolution_id '{rid}' across records "
                    f"('{rid_owner[rid]}' and '{ident}'): ids must be unique"
                )
            else:
                rid_owner.setdefault(rid, ident)
        reviews = record.get("reviews")
        if isinstance(reviews, list):
            for review in reviews:
                if isinstance(review, dict) and review.get("verdict") == "no_block":
                    no_block_reviews += 1
        for refute in _concrete_refutes(record):
            canon = _canon_ref(refute)
            refute_artifacts.add(canon)
            if canon in seen:
                if seen[canon] != ident:
                    errors.append(
                        f"refute_pass reused across records: {refute} (canonical "
                        f"'{canon}') appears in both '{seen[canon]}' and '{ident}' "
                        f"(each turn needs its own refutation, not a pasted-forward one)"
                    )
            else:
                seen[canon] = ident
    stats = {
        "records": len(records),
        "no_block_reviews": no_block_reviews,
        "distinct_refute_artifacts": len(refute_artifacts),
    }
    return errors, stats


def _good_record() -> dict:
    return {
        "schema_version": "1.0",
        "revolution_id": "selftest",
        "altitude": {"current": "flat loop", "target": "spiral", "axis": "abstraction"},
        "execution_strand": {
            "objective": "o",
            "engineer_target": "t",
            "validation_reviews": ["https://github.com/bonginkan/fairy_tale/pull/45"],
        },
        "learning_governance_strand": {
            "double_loop_evaluation": "e",
            "governing_variable_change": "g",
            "next_altitude": "n",
            "stop_or_descend": "s",
        },
        "strand_pairing_evidence": ["https://github.com/bonginkan/fairy_tale/issues/44"],
        "risk": {
            "highest_uncertainty": "u",
            "spike": "s",
            "burn_down_evidence": [
                "https://github.com/bonginkan/fairy_tale/commit/98341e43fce99a1157fbebec713537b406ef8e81"
            ],
        },
        "mismatch_repair": {"mismatches": ["m"], "repair_action": "r"},
        "validated_governance_template": "tpl",
        "win_condition": "w",
        "budget_radius": "b",
        "safety_floor": "f",
        "ledger_receipt": ["run-20260626T0011Z-cc-selftest-evidence"],
        "implementer": "MISA 3",
        "implementer_id": "1516725819517567077",
        "reviews": [
            {"reviewer": "CC MISA", "reviewer_id": "1510042936027381821", "verdict": "no_block",
             "refute_pass": "https://github.com/bonginkan/fairy_tale/issues/43#issuecomment-4805272898"},
            {"reviewer": "Codex MISA", "reviewer_id": "1510912873981804627", "verdict": "no_block",
             "refute_pass": "https://github.com/bonginkan/fairy_tale/pull/45#issuecomment-4805339475"},
        ],
    }


def _selftest() -> int:
    """Lock the red->green and hostile-bypass controls (fairy_tale #44 / PR #45)."""
    failures: list[str] = []

    good = _good_record()
    if validate_record(good) != []:
        failures.append(f"good record should pass but got: {validate_record(good)}")

    # Each hostile evidence value must be rejected (it slipped through pre-fix).
    hostile = {
        "empty": [],
        "placeholder": ["TODO"],
        "bare-7hex": ["deadbee"],
        "bare-issue": ["#1"],
        "prose+ref": ["trust me, reviewed carefully", "#44"],
        "abbrev-sha": ["98341e4"],
        "prose+url": ["trust me https://github.com/bonginkan/fairy_tale/pull/45"],
        "shape-sha-zero": ["0" * 40],
        "shape-sha-a": ["a" * 40],
        "path-traversal": ["scripts/../../../../../../tmp/spiral_revolution_check.py"],
    }
    for name, value in hostile.items():
        record = _good_record()
        record["strand_pairing_evidence"] = value
        if validate_record(record) == []:
            failures.append(f"hostile case '{name}' should be rejected but passed: {value!r}")

    # Review-calibration hostile cases (fairy_tale #43), keyed on user_id so that
    # display-name aliases cannot fool distinctness or the circular-review guard
    # (Codex/MISA3 round-1 bypasses: duplicate reviewer, alias self-review).
    _cc, _codex, _m3 = "1510042936027381821", "1510912873981804627", "1516725819517567077"
    _good_refute = "https://github.com/bonginkan/fairy_tale/pull/45#issuecomment-4805339475"

    def _rev(rid, refute=_good_refute, name="reviewer"):
        return {"reviewer": name, "reviewer_id": rid, "verdict": "no_block", "refute_pass": refute}

    review_hostile = {
        "no_block-empty-refute": {"reviews": [_rev(_cc, refute=""), _rev(_codex)]},
        "no_block-prose-refute": {"reviews": [_rev(_cc, refute="looked carefully, all good"), _rev(_codex)]},
        "too-few-reviewers": {"reviews": [_rev(_cc)]},
        "duplicate-reviewer-id": {"reviews": [_rev(_cc), _rev(_cc)]},
        "self-review-by-id": {"implementer_id": _cc, "reviews": [_rev(_cc), _rev(_codex)]},
        "alias-self-review-name": {
            "implementer": "MISA 3", "implementer_id": _m3,
            "reviews": [_rev(_m3, name="MISA3"), _rev(_codex)],
        },
        "missing-reviewer-id": {"reviews": [
            {"reviewer": "CC MISA", "verdict": "no_block", "refute_pass": _good_refute},
            _rev(_codex),
        ]},
        "fake-snowflake-reviewer": {"reviews": [_rev(_cc), _rev("999999999999999999", name="ghost")]},
        "all-unregistered-reviewers": {"reviews": [
            _rev("100000000000000001", name="ghost1"),
            _rev("100000000000000002", name="ghost2"),
        ]},
    }
    for name, overrides in review_hostile.items():
        record = _good_record()
        record.update(overrides)
        if validate_record(record) == []:
            failures.append(f"review-calibration case '{name}' should be rejected but passed")

    # Cross-record calibration: a refute_pass reused across records must be flagged
    # even when disguised, while distinct per-turn refutations must pass. Each
    # synthetic record sets a distinct second refute so only the FIRST can collide.
    _u1 = "https://github.com/bonginkan/fairy_tale/pull/48#issuecomment-4806074692"
    _u2 = "https://github.com/bonginkan/fairy_tale/pull/48#issuecomment-4806074854"

    def _xrec(ident_refute, other_refute):
        r = _good_record()
        r["revolution_id"] = f"rid-{ident_refute[-6:]}-{other_refute[-3:]}"
        r["reviews"] = [
            {"reviewer": "A", "reviewer_id": _cc, "verdict": "no_block", "refute_pass": ident_refute},
            {"reviewer": "B", "reviewer_id": _codex, "verdict": "no_block", "refute_pass": other_refute},
        ]
        return r

    _o1 = "https://github.com/x/y/pull/1#issuecomment-11"
    _o2 = "https://github.com/x/y/pull/2#issuecomment-22"
    # Disguised reuse of _u1 across two records -- each variant must still be flagged.
    cross_reuse = {
        "exact": _u1,
        "case-variant": _u1.replace("github.com", "GitHub.com").replace("/pull/", "/PULL/"),
        "query-after-fragment": _u1 + "?x=1",
        "query-before-fragment": _u1.replace("#", "?z=1#"),
        "trailing-slash": _u1 + "/",
        "http-scheme": _u1.replace("https://", "http://"),
        "default-port": _u1.replace("github.com", "github.com:443"),
    }
    for name, variant in cross_reuse.items():
        errs, _ = check_cross_record([("a.json", _xrec(_u1, _o1)), ("b.json", _xrec(variant, _o2))])
        if not errs:
            failures.append(f"cross-record reuse '{name}' should be flagged but passed")
    # Duplicate revolution_id must be flagged (and must not launder a reuse).
    dup_a, dup_b = _xrec(_u1, _o1), _xrec(_u2, _o2)
    dup_a["revolution_id"] = dup_b["revolution_id"] = "same-id"
    errs, _ = check_cross_record([("a.json", dup_a), ("b.json", dup_b)])
    if not any("duplicate revolution_id" in e for e in errs):
        failures.append("duplicate revolution_id should be flagged but passed")
    # Distinct per-record refutations (distinct ids + distinct artifacts) must pass.
    clean, stats = check_cross_record([("a.json", _xrec(_u1, _o1)), ("b.json", _xrec(_u2, _o2))])
    if clean:
        failures.append(f"distinct per-record refutations should pass cross-record but got: {clean}")
    if stats.get("records") != 2:
        failures.append(f"cross-record stats.records should be 2, got {stats.get('records')}")
    # On a NON-GitHub host, http:// and https:// are NOT assumed to be the same
    # artifact, so they must stay distinct (no over-collapse / false positive).
    ng_http = "http://example.test/refutation/artifact"
    ng_https = "https://example.test/refutation/artifact"
    ng_clean, _ = check_cross_record([("a.json", _xrec(ng_http, _o1)), ("b.json", _xrec(ng_https, _o2))])
    if ng_clean:
        failures.append("non-GitHub http vs https should stay distinct but was flagged (false positive)")
    # ...while a non-GitHub default-port variant of the SAME scheme is still a reuse.
    ng_port_reuse, _ = check_cross_record([
        ("a.json", _xrec(ng_https, _o1)),
        ("b.json", _xrec("https://example.test:443/refutation/artifact", _o2)),
    ])
    if not ng_port_reuse:
        failures.append("non-GitHub https default-port reuse should be flagged but passed")

    # No-records dir must fail with exit 1 (suppress its report so selftest output stays clean).
    import contextlib
    import io
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            empty_rc = main(["--records", tmp])
        if empty_rc == 0:
            failures.append("empty records dir should exit 1 but exited 0")

    if failures:
        for line in failures:
            print(f"SELFTEST FAIL: {line}")
        print("Spiral revolution selftest failed.")
        return 1
    print(
        "Spiral revolution selftest passed (good->pass; "
        "evidence: empty/placeholder/bare-hex/bare-#N/prose+ref/abbrev-sha/prose+url/shape-sha/path-traversal->reject; "
        "review-calibration: empty/prose refute_pass, <2 reviewers, self-review->reject; "
        "cross-record: reused refute_pass->reject, distinct->pass)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exercise check for spiral revolution records")
    parser.add_argument("--records", default=str(DEFAULT_RECORDS_DIR), help="records directory")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--selftest", action="store_true", help="run built-in red/green/hostile controls")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    records_dir = Path(args.records)
    files = sorted(records_dir.glob("*.json")) if records_dir.is_dir() else []

    report: dict[str, object] = {"records_dir": str(records_dir), "records": [], "passed": False}

    if not files:
        report["error"] = "no spiral revolution records found (presence-only spec is not exercised)"
        _emit(report, args.json)
        return 1

    all_ok = True
    loaded: list[tuple[str, dict]] = []
    for path in files:
        entry: dict[str, object] = {"file": str(path.relative_to(records_dir.parent) if records_dir.parent in path.parents else path)}
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entry["errors"] = [f"unreadable/invalid JSON: {exc}"]
            all_ok = False
            report["records"].append(entry)  # type: ignore[union-attr]
            continue
        errors = validate_record(record)
        entry["revolution_id"] = record.get("revolution_id") if isinstance(record, dict) else None
        entry["errors"] = errors
        if errors:
            all_ok = False
        report["records"].append(entry)  # type: ignore[union-attr]
        if isinstance(record, dict):
            # ident must be UNIQUE per record (file name) so a duplicate
            # revolution_id cannot launder a cross-record refute reuse.
            loaded.append((path.name, record))

    cross_errors, stats = check_cross_record(loaded)
    if cross_errors:
        all_ok = False
    report["cross_record_errors"] = cross_errors
    report["calibration_stats"] = stats

    report["passed"] = all_ok
    _emit(report, args.json)
    return 0 if all_ok else 1


def _emit(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    if report.get("error"):
        print(f"FAIL {report['records_dir']}: {report['error']}")
        return
    for entry in report.get("records", []):
        errors = entry.get("errors") or []
        if errors:
            print(f"FAIL {entry.get('file')} ({entry.get('revolution_id')})")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK   {entry.get('file')} ({entry.get('revolution_id')})")
    for err in report.get("cross_record_errors") or []:
        print(f"  - cross-record: {err}")
    stats = report.get("calibration_stats")
    if isinstance(stats, dict):
        print(
            f"calibration: {stats.get('records')} record(s), "
            f"{stats.get('no_block_reviews')} no_block review(s), "
            f"{stats.get('distinct_refute_artifacts')} distinct refutation artifact(s)."
        )
    print("Spiral revolution check passed." if report.get("passed") else "Spiral revolution check failed.")


if __name__ == "__main__":
    raise SystemExit(main())
