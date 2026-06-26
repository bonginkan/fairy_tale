#!/usr/bin/env python3
"""Exercise/enforcement check for E2E coverage ledger records (fairy_tale helix).

This sits ON TOP of the helix arc (Loop -> Spiral -> Double-Helix -> Evolution) as
the layer that proves an end-to-end run was actually *completed*, not merely run
once or declared done. It encodes the durable lessons from driving a real product
e2e to completion: a provided test list is not proof of scope; render is not
exercise; a mutation surface entails a security-boundary battery; real failures
need a tracked repro; the environment must be left clean; and the run must hit a
real backend, never a mock -- without leaking the secrets used to reach it.

The teeth (beyond presence):
  - closure: surfaces are discovered from code/deploy, and EVERY discovered
    surface must appear in coverage[] (a discovered surface absent from the ledger
    is a closure violation). Coverage may not reference a surface that was never
    discovered (no phantom coverage). This is the Negative-Space Closure Check
    applied to e2e scope -- "shown N" is never silently "only N".
  - presence-vs-exercise: a mutation/auth/stateful surface needs exercise.verified
    true with concrete evidence; render/reachability alone (presence) does not pass
    it. A read_only surface may pass on presence.
  - boundary-companion battery: every mutation/auth/stateful surface must carry the
    full entailed companion set (auth_reject, authz_rbac, idor_impersonation,
    visibility_scope, idempotency, allowlist_boundary), each a concrete ref or a
    justified N/A. A missing/prose companion fails.
  - RED -> tracked: each red finding needs a concrete repro AND a concrete tracker
    link; you cannot report completion over an untracked failure.
  - residue zero: residue.count must be 0 with concrete evidence.
  - real backend: no_mock.asserted must be true with concrete read-back evidence.
  - secret hygiene: NO raw secret/token/credential blob may appear anywhere in the
    ledger (the reachability story may describe HOW, never leak the value).
  - review calibration: the SAME #43 contract as the spiral/evolution ledgers
    (>= 2 distinct registered reviewers; a no_block needs a concrete refute_pass;
    no self-review), reused -- not reimplemented -- from spiral_revolution_check.

Usage:
  e2e_coverage_check.py [--records DIR] [--json] [--selftest]

Exit 0 = at least one record present and all records pass; 1 = otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS_DIR = ROOT / "e2e-coverage"

# Reuse the spiral exercise gate's verified primitives instead of cloning them
# (concrete-reference validation + #43 review calibration + principal registry).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spiral_revolution_check as spiral  # noqa: E402

SURFACE_CLASSES = {"read_only", "mutation", "auth", "stateful"}
EXERCISED_CLASSES = {"mutation", "auth", "stateful"}  # render != exercise for these
REQUIRED_COMPANIONS = (
    "auth_reject", "authz_rbac", "idor_impersonation",
    "visibility_scope", "idempotency", "allowlist_boundary",
)

REQUIRED_TOP = (
    "schema_version", "run_id", "target", "environment", "no_mock",
    "surface_inventory", "coverage", "red_findings", "residue",
    "evidence_refs", "safety", "implementer", "implementer_id", "reviews",
)

# A run that mocks the system under test, or pollutes it, is not a completion.
REAL_TIERS = {"deployed", "ephemeral", "local-real"}

# Secret-shaped blobs that must never be pasted into a ledger. The reachability
# story describes HOW a session was obtained; it never carries the value. These
# patterns err toward rejecting (the author redacts) rather than leaking.
_SECRET_PATTERNS = (
    re.compile(r"\b[0-9a-fA-F]{40,}\b"),                      # long hex (hashes are fine via CONCRETE_REF allowance below)
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}\b"),         # Bearer <token>
    re.compile(r"\b[A-Za-z0-9+]{40,}={0,2}\b"),              # base64-ish blob ('/' excluded so long slash-paths are not false hits; base64url secrets start eyJ and hit the JWT rule)
    re.compile(r"(?i)\b(?:secret|token|api[_-]?key|password)\b\s*[:=]\s*\S{8,}"),  # key: value
    re.compile(r"\beyJ[A-Za-z0-9._\-]{20,}"),                # JWT
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                     # AWS access key id
)


def _nonempty_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


# A concrete e2e reference. Unlike the spiral/evolution gates -- whose evidence
# points INSIDE this repo -- an e2e run targets an EXTERNAL system, so its refs
# point at the system under test (file:line in another repo), at external
# artifacts (screenshots / report files), at routes/HTTP results, or at trackers
# (PR/issue URLs). We therefore require a concrete *token* but do NOT require the
# token to exist inside fairy_tale. Pure prose (no token) is still rejected.
_PROVENANCE = re.compile(
    r"(?:[\w.\-]+/)*[\w.\-]+\.(?:py|json|md|ts|tsx|js|mjs|cjs|yml|yaml|sh|toml|txt|"
    r"png|webm|wav|jpe?g|pdf|xlsx|docx|pptx)(?::\d+)?"
)
_METHODROUTE = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/\S+")


def _cites_concrete(value) -> bool:
    """True iff the string carries a concrete, checkable token: a URL / sha256: /
    run-trace id (spiral.CONCRETE_REF), a file path (optionally file:line), or an
    HTTP method+route. Descriptive prose around the token is allowed; prose with no
    token at all is rejected."""
    if not _nonempty_str(value):
        return False
    return bool(
        spiral.CONCRETE_REF.search(value)
        or _PROVENANCE.search(value)
        or _METHODROUTE.search(value)
    )


def _check_evidence_array(value, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: must be a non-empty array of concrete refs")
        return
    for index, entry in enumerate(value):
        if not _nonempty_str(entry):
            errors.append(f"{label}[{index}]: empty/non-string")
        elif not _cites_concrete(entry):
            errors.append(f"{label}[{index}]: not a concrete ref (URL/sha256:/run-trace/file:line/METHOD route): {entry!r}")


def _iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_strings(item)


def _check_no_secret_leak(record: dict, errors: list[str]) -> None:
    """A sha256:/url is a legitimate concrete ref; a bare long hex/base64/JWT/Bearer
    token is treated as a possible leaked secret. We exempt strings that are a
    recognised concrete ref (sha256:..., URLs) so receipts/refs are not false hits."""
    for text in _iter_strings(record):
        if spiral.CONCRETE_REF.fullmatch(text.strip()):
            continue
        for pattern in _SECRET_PATTERNS:
            for hit in pattern.finditer(text):
                token = hit.group(0)
                # allow a sha256:-prefixed digest embedded in prose
                if "sha256:" in text.lower() and re.fullmatch(r"[0-9a-fA-F]{40,}", token):
                    continue
                errors.append(
                    f"possible secret/token leaked into ledger ({pattern.pattern[:24]}...): "
                    f"redact -- the reachability story describes HOW, never the value"
                )
                return


def _check_environment(record: dict, errors: list[str]) -> None:
    env = record.get("environment")
    if not isinstance(env, dict):
        errors.append("environment: required object")
        return
    if env.get("tier") not in REAL_TIERS:
        errors.append(f"environment.tier: must be a real backend tier {sorted(REAL_TIERS)} (a mock tier is not a completion)")
    if not _cites_concrete(env.get("base_ref")):
        errors.append("environment.base_ref: must cite a concrete environment ref (deploy URL / revision)")


def _check_no_mock(record: dict, errors: list[str]) -> None:
    no_mock = record.get("no_mock")
    if not isinstance(no_mock, dict):
        errors.append("no_mock: required object")
        return
    if no_mock.get("asserted") is not True:
        errors.append("no_mock.asserted: must be true (a run that mocks the system under test is not a completion)")
    _check_evidence_array(no_mock.get("evidence"), "no_mock.evidence", errors)


def _discovered_ids(record: dict) -> set[str]:
    inv = record.get("surface_inventory")
    if not isinstance(inv, dict):
        return set()
    discovered = inv.get("discovered")
    if not isinstance(discovered, list):
        return set()
    return {d.get("id") for d in discovered if isinstance(d, dict) and _nonempty_str(d.get("id"))}


def _check_surface_inventory(record: dict, errors: list[str]) -> None:
    inv = record.get("surface_inventory")
    if not isinstance(inv, dict):
        errors.append("surface_inventory: required object")
        return
    discovered = inv.get("discovered")
    if not isinstance(discovered, list) or not discovered:
        errors.append("surface_inventory.discovered: required non-empty array (surfaces from code/deploy, not just the provided list)")
    else:
        for i, d in enumerate(discovered):
            if not isinstance(d, dict):
                errors.append(f"surface_inventory.discovered[{i}]: must be an object")
                continue
            if not _nonempty_str(d.get("id")):
                errors.append(f"surface_inventory.discovered[{i}].id: required")
            if d.get("kind") not in {"route", "panel", "endpoint", "action", "flow", "job"}:
                errors.append(f"surface_inventory.discovered[{i}].kind: invalid")
            if not _cites_concrete(d.get("source_ref")):
                errors.append(f"surface_inventory.discovered[{i}].source_ref: must cite concrete provenance (file:line / route / deploy ref)")
    closure = inv.get("closure")
    if not isinstance(closure, dict) or not isinstance(closure.get("missing_from_provided"), list):
        errors.append("surface_inventory.closure.missing_from_provided: required array (the closure-diff audit must be recorded, even if empty)")


def _check_companions(surface_id: str, companions, errors: list[str]) -> None:
    if not isinstance(companions, dict):
        errors.append(f"coverage[{surface_id}].boundary_companions: required object for mutation/auth/stateful surfaces")
        return
    for key in REQUIRED_COMPANIONS:
        if key not in companions:
            errors.append(f"coverage[{surface_id}].boundary_companions.{key}: required (entailed boundary battery incomplete)")
            continue
        value = companions[key]
        if isinstance(value, dict) and value.get("na") is True:
            if not _nonempty_str(value.get("reason")):
                errors.append(f"coverage[{surface_id}].boundary_companions.{key}: N/A needs a non-empty reason")
            continue
        if not _cites_concrete(value):
            errors.append(f"coverage[{surface_id}].boundary_companions.{key}: must cite concrete evidence, or be {{na:true, reason:...}}")


def _check_coverage(record: dict, errors: list[str]) -> None:
    coverage = record.get("coverage")
    if not isinstance(coverage, list) or not coverage:
        errors.append("coverage: required non-empty array")
        return
    discovered = _discovered_ids(record)
    covered: set[str] = set()
    for i, entry in enumerate(coverage):
        if not isinstance(entry, dict):
            errors.append(f"coverage[{i}]: must be an object")
            continue
        sid = entry.get("surface_id")
        label = sid if _nonempty_str(sid) else f"#{i}"
        if not _nonempty_str(sid):
            errors.append(f"coverage[{i}].surface_id: required")
        else:
            covered.add(sid)
            if discovered and sid not in discovered:
                errors.append(f"coverage[{label}].surface_id: not in surface_inventory.discovered (phantom coverage)")
        klass = entry.get("surface_class")
        if klass not in SURFACE_CLASSES:
            errors.append(f"coverage[{label}].surface_class: must be one of {sorted(SURFACE_CLASSES)}")
        presence = entry.get("presence")
        if not isinstance(presence, dict) or not isinstance(presence.get("verified"), bool):
            errors.append(f"coverage[{label}].presence.verified: required boolean")
        elif presence.get("verified"):
            _check_evidence_array(presence.get("evidence"), f"coverage[{label}].presence.evidence", errors)
        exercise = entry.get("exercise")
        if not isinstance(exercise, dict) or not isinstance(exercise.get("verified"), bool):
            errors.append(f"coverage[{label}].exercise.verified: required boolean")
        else:
            if klass in EXERCISED_CLASSES and exercise.get("verified") is not True:
                errors.append(
                    f"coverage[{label}].exercise.verified: a {klass} surface must be EXERCISED "
                    f"(create->read-back->delete / round-trip / continuity), not only present/rendered"
                )
            if exercise.get("verified"):
                if not _nonempty_str(exercise.get("kind")):
                    errors.append(f"coverage[{label}].exercise.kind: required and non-empty")
                _check_evidence_array(exercise.get("evidence"), f"coverage[{label}].exercise.evidence", errors)
        if klass in EXERCISED_CLASSES:
            _check_companions(label, entry.get("boundary_companions"), errors)
    # Closure: every discovered surface must be covered.
    for missing in sorted(discovered - covered):
        errors.append(f"closure violation: discovered surface {missing!r} is not in coverage[] (scope not closed)")


def _check_red_findings(record: dict, errors: list[str]) -> None:
    reds = record.get("red_findings")
    if not isinstance(reds, list):
        errors.append("red_findings: required array (may be empty)")
        return
    for i, red in enumerate(reds):
        if not isinstance(red, dict):
            errors.append(f"red_findings[{i}]: must be an object")
            continue
        rid = red.get("id") if _nonempty_str(red.get("id")) else f"#{i}"
        for key in ("id", "summary"):
            if not _nonempty_str(red.get(key)):
                errors.append(f"red_findings[{rid}].{key}: required and non-empty")
        if not _cites_concrete(red.get("repro")):
            errors.append(f"red_findings[{rid}].repro: must cite a concrete reproduction (request/steps/observed)")
        if not _cites_concrete(red.get("issue_ref")):
            errors.append(f"red_findings[{rid}].issue_ref: a RED cannot be reported without a concrete tracker link (issue/PR URL)")


def _check_residue(record: dict, errors: list[str]) -> None:
    residue = record.get("residue")
    if not isinstance(residue, dict):
        errors.append("residue: required object")
        return
    if residue.get("count") != 0:
        errors.append("residue.count: must be 0 (an e2e that pollutes the environment is not complete)")
    if not _cites_concrete(residue.get("evidence")):
        errors.append("residue.evidence: must cite concrete residue-zero verification")


def _check_safety(record: dict, errors: list[str]) -> None:
    safety = record.get("safety")
    if not isinstance(safety, dict):
        errors.append("safety: required object")
        return
    if not _nonempty_str(safety.get("secret_handling")):
        errors.append("safety.secret_handling: required and non-empty (how sessions/credentials were obtained and protected)")
    if safety.get("safety_floor_preserved") is not True:
        errors.append("safety.safety_floor_preserved: must be true (reachability/session-mint must not relax auth/authz or leak secrets)")


def validate_record(record: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record is not a JSON object"]

    for key in REQUIRED_TOP:
        if key not in record:
            errors.append(f"missing required field: {key}")

    if record.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    for key in ("run_id", "target"):
        if not _nonempty_str(record.get(key)):
            errors.append(f"{key}: required and non-empty")

    _check_environment(record, errors)
    _check_no_mock(record, errors)
    _check_surface_inventory(record, errors)
    _check_coverage(record, errors)
    _check_red_findings(record, errors)
    _check_residue(record, errors)
    _check_evidence_array(record.get("evidence_refs"), "evidence_refs", errors)
    _check_safety(record, errors)
    _check_no_secret_leak(record, errors)

    # Review calibration: reuse the spiral ledger's #43 contract verbatim.
    spiral._check_reviews(record, errors)

    return errors


def _good_record() -> dict:
    return {
        "schema_version": "1.0",
        "run_id": "selftest-e2e-run",
        "target": "example-service",
        "environment": {"tier": "deployed", "base_ref": "https://example-service-dev.a.run.app/api/widget"},
        "no_mock": {
            "asserted": True,
            "evidence": ["https://github.com/bonginkan/fairy_tale/pull/52"],
        },
        "surface_inventory": {
            "discovered": [
                {"id": "POST /api/widget", "kind": "endpoint", "source_ref": "app/api/widget/route.ts:30"},
                {"id": "panel:dashboard", "kind": "panel", "source_ref": "components/app.tsx:55"},
            ],
            "closure": {
                "provided_list_ref": "https://github.com/bonginkan/fairy_tale/pull/52",
                "missing_from_provided": ["panel:dashboard"],
            },
        },
        "coverage": [
            {
                "surface_id": "POST /api/widget",
                "surface_class": "mutation",
                "presence": {"verified": True, "evidence": ["app/api/widget/route.ts:30"]},
                "exercise": {"verified": True, "kind": "create-readback-delete",
                             "evidence": ["https://github.com/bonginkan/fairy_tale/pull/52"]},
                "boundary_companions": {
                    "auth_reject": "https://github.com/bonginkan/fairy_tale/pull/52",
                    "authz_rbac": "https://github.com/bonginkan/fairy_tale/pull/52",
                    "idor_impersonation": "app/api/widget/route.ts:30",
                    "visibility_scope": "app/api/widget/route.ts:30",
                    "idempotency": "https://github.com/bonginkan/fairy_tale/pull/52",
                    "allowlist_boundary": {"na": True, "reason": "single-tenant surface; no workspace allowlist applies"},
                },
            },
            {
                "surface_id": "panel:dashboard",
                "surface_class": "read_only",
                "presence": {"verified": True, "evidence": ["components/app.tsx:55"]},
                "exercise": {"verified": False, "kind": "render-only", "evidence": []},
            },
        ],
        "red_findings": [
            {"id": "R-1", "summary": "tenant-less create returned 500",
             "repro": "POST /api/widget without tenantId -> 500 (app/api/widget/route.ts:30)",
             "issue_ref": "https://github.com/bonginkan/fairy_tale/issues/43"},
        ],
        "residue": {"count": 0, "evidence": "https://github.com/bonginkan/fairy_tale/pull/52"},
        "evidence_refs": ["https://github.com/bonginkan/fairy_tale/pull/52"],
        "safety": {
            "secret_handling": "Session minted from the app's own signing secret read as raw bytes; the value is never recorded here.",
            "safety_floor_preserved": True,
        },
        "implementer": "CC MISA",
        "implementer_id": "1510042936027381821",
        "reviews": [
            {"reviewer": "Codex MISA", "reviewer_id": "1510912873981804627", "verdict": "no_block",
             "refute_pass": "https://github.com/bonginkan/fairy_tale/pull/52#issuecomment-1"},
            {"reviewer": "MISA 3", "reviewer_id": "1516725819517567077", "verdict": "no_block",
             "refute_pass": "https://github.com/bonginkan/fairy_tale/pull/52#issuecomment-2"},
        ],
    }


def _selftest() -> int:
    failures: list[str] = []

    good = _good_record()
    if validate_record(good) != []:
        failures.append(f"good record should pass but got: {validate_record(good)}")

    def mutated(mutator) -> dict:
        record = _good_record()
        mutator(record)
        return record

    hostile = {
        # closure: a discovered surface not covered
        "missing-surface-in-coverage": lambda r: r["surface_inventory"]["discovered"].append(
            {"id": "GET /api/secret-list", "kind": "endpoint", "source_ref": "app/api/secret/route.ts:1"}),
        # phantom coverage of an undiscovered surface
        "phantom-coverage": lambda r: r["coverage"].append(
            {"surface_id": "ghost", "surface_class": "read_only",
             "presence": {"verified": True, "evidence": ["app/api/widget/route.ts:30"]},
             "exercise": {"verified": False, "kind": "n/a", "evidence": []}}),
        # presence != exercise for a mutation surface
        "render-only-mutation": lambda r: r["coverage"][0]["exercise"].__setitem__("verified", False),
        # boundary battery incomplete
        "missing-companion": lambda r: r["coverage"][0]["boundary_companions"].pop("idempotency"),
        # prose companion (no concrete ref)
        "prose-companion": lambda r: r["coverage"][0]["boundary_companions"].__setitem__("idor_impersonation", "looked fine"),
        # na companion without reason
        "na-companion-no-reason": lambda r: r["coverage"][0]["boundary_companions"].__setitem__("allowlist_boundary", {"na": True}),
        # RED without a tracker
        "red-without-issue": lambda r: r["red_findings"][0].__setitem__("issue_ref", "will file later"),
        # RED without concrete repro
        "red-prose-repro": lambda r: r["red_findings"][0].__setitem__("repro", "it broke sometimes"),
        # residue not zero
        "nonzero-residue": lambda r: r["residue"].__setitem__("count", 3),
        # residue evidence prose
        "prose-residue-evidence": lambda r: r["residue"].__setitem__("evidence", "cleaned it up trust me"),
        # mock asserted false
        "mock-asserted-false": lambda r: r["no_mock"].__setitem__("asserted", False),
        "mock-no-evidence": lambda r: r["no_mock"].__setitem__("evidence", []),
        # mock/non-real tier
        "mock-tier": lambda r: r["environment"].__setitem__("tier", "mock"),
        "prose-base-ref": lambda r: r["environment"].__setitem__("base_ref", "the dev server"),
        # inventory empty (only provided list trusted)
        "empty-discovered": lambda r: r["surface_inventory"].__setitem__("discovered", []),
        # closure audit field absent
        "no-closure-field": lambda r: r["surface_inventory"].__setitem__("closure", {}),
        # discovered source not concrete
        "prose-source-ref": lambda r: r["surface_inventory"]["discovered"][0].__setitem__("source_ref", "somewhere in the code"),
        # safety floor relaxed
        "safety-floor-not-preserved": lambda r: r["safety"].__setitem__("safety_floor_preserved", False),
        "empty-secret-handling": lambda r: r["safety"].__setitem__("secret_handling", ""),
        # leaked secret blobs anywhere in the ledger
        "leaked-hex-secret": lambda r: r["safety"].__setitem__(
            "secret_handling", "the integration secret is 0123456789abcdef0123456789abcdef01234567"),
        "leaked-bearer": lambda r: r["evidence_refs"].append("Authorization Bearer abcdefABCDEF0123456789xyz"),
        "leaked-jwt": lambda r: r["evidence_refs"].append("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9zzzzzzzzz"),
        "leaked-keyvalue": lambda r: r["safety"].__setitem__("secret_handling", "token=supersecretvalue123"),
        # evidence not concrete
        "prose-evidence-refs": lambda r: r.__setitem__("evidence_refs", ["it worked"]),
        # bad surface class
        "bad-surface-class": lambda r: r["coverage"][0].__setitem__("surface_class", "vibes"),
    }
    for name, mutator in hostile.items():
        if validate_record(mutated(mutator)) == []:
            failures.append(f"hostile case '{name}' should be rejected but passed")

    # Review calibration is inherited from the spiral gate; spot-check one case.
    dup = _good_record()
    dup["reviews"] = [dup["reviews"][0], dup["reviews"][0]]
    if validate_record(dup) == []:
        failures.append("duplicate-reviewer case should be rejected but passed")
    selfrev = _good_record()
    selfrev["reviews"][0]["reviewer_id"] = selfrev["implementer_id"]
    if validate_record(selfrev) == []:
        failures.append("self-review case should be rejected but passed")

    import contextlib
    import io
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        with contextlib.redirect_stdout(io.StringIO()):
            if main(["--records", tmp]) == 0:
                failures.append("empty records dir should exit 1 but exited 0")

    if failures:
        for line in failures:
            print(f"SELFTEST FAIL: {line}")
        print("E2E coverage selftest failed.")
        return 1
    print(
        "E2E coverage selftest passed (good->pass; reject: missing/phantom coverage, render-only "
        "mutation, missing/prose/unjustified-NA companion, RED without issue/repro, nonzero/prose "
        "residue, mock asserted/tier/no-evidence, prose base_ref, empty discovered, missing closure "
        "audit, prose source_ref, safety-floor relaxed, leaked hex/Bearer/JWT/key=value secret, prose "
        "evidence, bad surface class, duplicate/self reviewer)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exercise check for e2e coverage ledger records")
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
        report["error"] = "no e2e coverage records found (presence-only spec is not exercised)"
        _emit(report, args.json)
        return 1

    all_ok = True
    for path in files:
        entry: dict[str, object] = {"file": str(path.name)}
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entry["errors"] = [f"unreadable/invalid JSON: {exc}"]
            all_ok = False
            report["records"].append(entry)  # type: ignore[union-attr]
            continue
        errors = validate_record(record)
        entry["run_id"] = record.get("run_id") if isinstance(record, dict) else None
        entry["errors"] = errors
        if errors:
            all_ok = False
        report["records"].append(entry)  # type: ignore[union-attr]

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
            print(f"FAIL {entry.get('file')} ({entry.get('run_id')})")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"OK   {entry.get('file')} ({entry.get('run_id')})")
    print("E2E coverage check passed." if report.get("passed") else "E2E coverage check failed.")


if __name__ == "__main__":
    raise SystemExit(main())
