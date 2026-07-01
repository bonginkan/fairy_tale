#!/usr/bin/env python3
"""Exercise/enforcement check for Creator-Proxy Elaboration ledgers (WWCD harness).

An agent acting as a creator/principal's proxy, invoked by a THIRD-PARTY relay,
elaborates "what would the creator do/instruct here" (WWCD = What Would the Creator
Do). The prior art (Constitutional AI arXiv:2212.08073; CIRL arXiv:1606.03137;
Step-Back arXiv:2310.06117; ToM prompting arXiv:2304.11490; Role-Play arXiv:2308.07702)
supports an evidence-grounded, pre-action perspective-taking step; the failure modes
(sycophancy arXiv:2310.13548; persona-vector hallucination arXiv:2507.21509;
belief-behavior divergence arXiv:2507.02197; ToM limits arXiv:2509.02292; intent
verification infeasibility -- SentinelAgent arXiv:2604.02767) mean an *ungrounded* WWCD
step mechanically drifts toward hallucination/sycophancy. Within the surveyed scope no
paper studies this exact relayed-creator-proxy mechanism (direct match not found; the
non-existence is not claimed).

The teeth (beyond presence) -- each maps to the tri-MISA acceptance bar:
  1. Authority non-delegation: `authority_decision` is SEPARATE from the intent
     hypothesis. `basis` must be verified identity / policy / not_applicable -- never a
     creator-intent value -- and its note may not rest authority on the inferred goal.
  2. Source tiers + admissibility: every cited_evidence entry needs a real, concrete
     `ref` (not a tier name alone); a high-confidence inference needs >=1 entry stronger
     than a style hint; style_hints alone cannot ground a high-stakes proceed.
  3. Relayer separation: relayer_request, inferred_creator_goal, conflict_flag are
     required; a relayer/creator conflict must record a concrete rejected_relayer_pull.
  4. Confidence + escalation: low confidence OR high stakes OR conflict REQUIRES
     escalation.action == surface_or_confirm (never proceed on a guess).
  5. Belief->behavior binding: action.cited_principle_id must resolve to a
     cited_evidence[].id -- the enacted decision is bound to the elaborated principle.

Usage:
  creator_proxy_elaboration_check.py [--records DIR] [--json] [--selftest]

Exit 0 = at least one record present and all records pass; 1 = otherwise.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS_DIR = ROOT / "creator-proxy-elaborations"

TIERS = ("explicit_instruction", "repo_user_config_scope", "past_decisions", "style_hints")
STRONG_TIERS = ("explicit_instruction", "repo_user_config_scope", "past_decisions")
# authority may be decided ONLY from these bases -- creator-intent is deliberately absent.
AUTHORITY_BASES = ("verified_identity_sender_id", "existing_policy_allowlist", "not_applicable")
CONFIDENCE = ("low", "medium", "high")
STAKES = ("low", "medium", "high")
ESCALATION_ACTIONS = ("proceed", "surface_or_confirm")

# a concrete evidence ref: a file:line, a message/run id, a config key path, a doc anchor,
# a URL, or a sha -- something a reviewer could open. A bare tier name or empty string is not.
_CONCRETE_REF = re.compile(
    r"("
    r"[\w./-]+:\d+"                      # file:line
    r"|https?://\S+"                     # url
    r"|sha256:[0-9a-f]{16,}"             # hash
    r"|[\w-]+\.(md|json|toml|ts|tsx|py|rs|yaml|yml)\b"  # a real file
    r"|(msg|message|run|trace|comment|issue|pr)[\w-]*[:#/]?\s*\d"  # message/run/trace/issue id
    r"|[\w-]+(\.[\w-]+){2,}"             # dotted config path (a.b.c)
    r")",
    re.IGNORECASE,
)
# a note that rests authority on creator intent rather than identity/policy (forbidden).
# the subject may be named (creator/owner/jun/...) and the verb is any approve-synonym; the two
# need only co-occur in the note, since "authority because the creator is fine with it" in ANY
# phrasing is intent-as-authority.
_INTENT_SUBJECT = re.compile(r"\b(creator|owner|principal|jun|the pioneer|they|he|she)\b", re.IGNORECASE)
_APPROVE_SYNONYM = re.compile(
    r"\b(approve[sd]?|approv\w*|allow\w*|permit\w*|consent\w*|authoriz\w*|authoris\w*|"
    r"sign[\s-]?off|signs?[\s-]?off|bless\w*|greenlight\w*|green[\s-]?light\w*|"
    r"wave[sd]?[\s-]?through|okay\w*|be ok\w*|be fine|is fine|are fine|want[s]?|wish\w*|"
    r"endorse[sd]?|sanction\w*|clear[s]?|nod[s]?)\b",
    re.IGNORECASE,
)

# a ref pointing at home / private / cross-user config is INADMISSIBLE without existing scope --
# memory, home dotfiles, and private notes are not creator artifacts you may cite by default.
_INADMISSIBLE_REF = re.compile(
    r"(^~|/users/|/home/|\.claude\b|\.codex\b|\.ssh\b"
    r"|(^|[/.])memory([/.]|$)"            # memory/  memory.  .memory.  /memory/
    r"|(^|[/.])private([/._-]|notes|$)"   # private/  private.  private-notes  .private.
    r"|home[\s_-]?config)",
    re.IGNORECASE,
)
# an authority evidence_ref must be an UNFORGEABLE identity id or a policy/allowlist locator --
# never a display name / plain word. Accept: a snowflake-ish id (>=17 digits, optionally
# labelled), OR a dotted path that names a policy/allowlist/access/permission surface.
_AUTHORITY_REF_OK = re.compile(
    r"("
    r"(user[_\s-]?id|sender[_\s-]?id|id)[:=#\s]*\d{17,}"   # labelled snowflake
    r"|\b\d{17,}\b"                                          # bare snowflake
    r"|[\w-]*(policy|allowlist|allow[_-]?list|access|permission|rbac|scope|gate)[\w.-]*\.[\w.-]+"  # policy path
    r")",
    re.IGNORECASE,
)
# a relayer asking to BYPASS a safety gate is inherently a creator/relayer conflict; it may not be
# self-declared conflict_flag=false.
_GATE_SKIP = re.compile(
    r"\b(skip\w*\s+(the\s+)?(review|ci|test\w*|gate|staging|approval)|bypass\w*|waiv\w*|"
    r"override\s+(the\s+)?(gate|review|policy)|straight\s+to\s+prod|without\s+(review|ci|approval)|"
    r"no\s+(review|ci|approval)|force[\s-]?(merge|push))\b",
    re.IGNORECASE,
)

# high-risk action surfaces: if any appears in the action / relayer_request / domain, the ledger
# may NOT self-label stakes below "high" (a safety gate errs toward high). Matched case-insensitively.
_HIGH_RISK = re.compile(
    r"\b(prod(uction)?\b|deploy\w*|rollout|roll[\s-]?out|go[\s-]?live|"
    r"access[\s-]?grant|grant\w*\s+(access|permission|role)|allowlist|allow[\s-]?list|"
    r"permission\w*|privilege\w*|secret\w*|credential\w*|token\b|api[\s-]?key|"
    r"\bmerge\b|force[\s-]?push|skip\w*\s+(the\s+)?(review|ci|test|gate)|review[\s-]?skip|"
    r"delete\w*|drop\s+(table|database)|wire[\s-]?transfer|payment|refund|irreversible)\b",
    re.IGNORECASE,
)


def _err(errors: list[str], record_id: str, msg: str) -> None:
    errors.append(f"{record_id}: {msg}")


_FILE_LINE = re.compile(r"^(?P<path>[\w./-]+\.(?:md|json|toml|ts|tsx|py|rs|yaml|yml)):(?P<line>\d+)$")


def _ref_problem(ref: str, root: Path) -> str | None:
    """Return a problem string if a concrete ref does not RESOLVE (not just regex-shaped).

    A file:line ref must point at a real file (under `root`) with enough lines -- an
    unresolvable 'concrete' ref (e.g. CLAUDE.md:210 when the file has 25 lines) is not
    evidence. Non-file refs (message/run/trace ids, urls, dotted config paths) are not
    file-checkable here and pass the shape gate; the schema/tier still constrain them.
    """
    if not isinstance(ref, str) or not ref.strip():
        return "empty ref"
    if _INADMISSIBLE_REF.search(ref):
        return f"ref '{ref}' points at home/private/memory config -- inadmissible as a creator artifact without existing scope"
    if not _CONCRETE_REF.search(ref):
        return f"ref '{ref}' is not a concrete locator (file:line / id / config path / url / sha)"
    m = _FILE_LINE.match(ref.strip())
    if m:
        path = (root / m.group("path")).resolve()
        try:
            # confine to the repo tree; refuse traversal outside root
            path.relative_to(root.resolve())
        except ValueError:
            return f"ref '{ref}' escapes the repo tree"
        if not path.is_file():
            return f"ref '{ref}' points at a file that does not exist in the archive"
        line = int(m.group("line"))
        try:
            n = sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
        except OSError:
            return f"ref '{ref}' file is unreadable"
        if line < 1 or line > n:
            return f"ref '{ref}' points past end of file ({n} lines) -- unresolvable, not evidence"
    return None


def validate_record(record_id: str, r: dict, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not isinstance(r, dict):
        return [f"{record_id}: record is not an object"]

    if r.get("schema_version") != "1.0":
        _err(errors, record_id, "schema_version must be '1.0'")

    ctx = r.get("context")
    stakes = None
    if not isinstance(ctx, dict) or "is_relayed" not in ctx or ctx.get("stakes") not in STAKES:
        _err(errors, record_id, "context needs is_relayed:bool and stakes in low|medium|high")
    else:
        stakes = ctx.get("stakes")

    # 3. relayer separation -- the three fields must be present & meaningful.
    if not isinstance(r.get("relayer_request"), str) or not r["relayer_request"].strip():
        _err(errors, record_id, "relayer_request (the invoker's ask) is required")
    if not isinstance(r.get("inferred_creator_goal"), str) or not r["inferred_creator_goal"].strip():
        _err(errors, record_id, "inferred_creator_goal (the latent objective hypothesis) is required")
    conflict = r.get("conflict_flag")
    in_conflict = False
    if not isinstance(conflict, dict) or not isinstance(conflict.get("relayer_vs_creator"), bool):
        _err(errors, record_id, "conflict_flag.relayer_vs_creator:bool is required")
    else:
        in_conflict = conflict["relayer_vs_creator"]

    # 2. source tiers + admissibility.
    evidence = r.get("cited_evidence")
    ev_tier: dict[str, str] = {}
    has_strong = False
    if not isinstance(evidence, list):
        _err(errors, record_id, "cited_evidence must be an array")
        evidence = []
    for i, e in enumerate(evidence):
        if not isinstance(e, dict):
            _err(errors, record_id, f"cited_evidence[{i}] is not an object")
            continue
        eid = e.get("id")
        tier = e.get("tier")
        if not isinstance(eid, str) or not eid.strip():
            _err(errors, record_id, f"cited_evidence[{i}].id is required")
        else:
            ev_tier[eid] = tier if tier in TIERS else "?"
        if tier not in TIERS:
            _err(errors, record_id, f"cited_evidence[{i}].tier must be one of {TIERS}")
        ref = e.get("ref")
        # a real, concrete artifact ref that RESOLVES -- a tier name alone, or a file:line past
        # the end of the file, is not evidence.
        rp = _ref_problem(ref if isinstance(ref, str) else "", root)
        if rp:
            _err(errors, record_id, f"cited_evidence[{i}].{rp}")
        if tier in STRONG_TIERS:
            has_strong = True

    confidence = r.get("confidence")
    if confidence not in CONFIDENCE:
        _err(errors, record_id, f"confidence must be one of {CONFIDENCE}")
    # evidence gate: high confidence needs >=1 stronger-than-style-hint artifact.
    if confidence == "high" and not has_strong:
        _err(errors, record_id, "high confidence requires >=1 cited_evidence with a tier stronger than style_hints")

    # 4. confidence + escalation gate.
    esc = r.get("escalation")
    esc_action = esc.get("action") if isinstance(esc, dict) else None
    if esc_action not in ESCALATION_ACTIONS:
        _err(errors, record_id, f"escalation.action must be one of {ESCALATION_ACTIONS}")
    # high-stakes classifier: a high-risk action surface may NOT be self-labeled below "high" stakes.
    # scan the action, the relayer request, and the domain for high-risk terms; the safety gate errs
    # toward high (the author cannot demote a prod-deploy / access-grant / merge / review-skip to low).
    action_obj = r.get("action") if isinstance(r.get("action"), dict) else {}
    risk_surface = " ".join(str(x) for x in (
        action_obj.get("description", ""),
        r.get("relayer_request", ""),
        r.get("proposed_instruction", ""),
        (ctx or {}).get("domain", "") if isinstance(ctx, dict) else "",
    ))
    high_risk = bool(_HIGH_RISK.search(risk_surface))
    if high_risk and stakes != "high":
        _err(errors, record_id, f"a high-risk action surface (prod/deploy/access/secret/merge/review-skip/...) may not be self-labeled stakes='{stakes}'; must be 'high'")

    must_escalate = (confidence == "low") or (stakes == "high") or in_conflict or high_risk
    if must_escalate and esc_action != "surface_or_confirm":
        _err(errors, record_id, "low confidence OR high stakes OR conflict OR a high-risk action surface requires escalation.action == surface_or_confirm (never proceed on a guess)")

    # a relayer asking to BYPASS a safety gate (skip review/ci, waive, override the gate, straight to
    # prod) is inherently a creator/relayer conflict -- it may not be self-declared conflict_flag=false.
    if isinstance(r.get("relayer_request"), str) and _GATE_SKIP.search(r["relayer_request"]) and not in_conflict:
        _err(errors, record_id, "the relayer_request asks to bypass a safety gate (skip/waive/override) -- conflict_flag.relayer_vs_creator cannot be false")

    # 1. authority non-delegation -- the machine firewall.
    auth = r.get("authority_decision")
    if not isinstance(auth, dict) or auth.get("basis") not in AUTHORITY_BASES or not isinstance(auth.get("permitted"), bool):
        _err(errors, record_id, f"authority_decision needs basis in {AUTHORITY_BASES} (NOT a creator-intent value) and permitted:bool")
    else:
        # not_applicable cannot GRANT permission -- if no permission decision applies, it is not "permitted".
        if auth["basis"] == "not_applicable" and auth.get("permitted") is True:
            _err(errors, record_id, "authority_decision basis=not_applicable cannot have permitted=true (no decision applies -> not permitted)")
        # a real permission decision must cite an UNFORGEABLE identity id / policy locator -- basis enum
        # alone (or a display name) is form, not a firewall. not_applicable needs no ref.
        if auth["basis"] != "not_applicable":
            aref = auth.get("evidence_ref")
            # authority evidence has its OWN admissible form (an unforgeable id or a policy locator),
            # distinct from an artifact ref -- so a bare snowflake is valid here even though it is not a
            # general 'concrete artifact' ref. Reject empty / inadmissible / non-id-non-policy.
            if not isinstance(aref, str) or not aref.strip():
                _err(errors, record_id, "authority_decision.evidence_ref is required (basis != not_applicable): cite an identity/sender_id or policy locator")
            elif _INADMISSIBLE_REF.search(aref):
                _err(errors, record_id, f"authority_decision.evidence_ref '{aref}' points at home/private/memory config -- inadmissible")
            elif not _AUTHORITY_REF_OK.search(aref):
                _err(errors, record_id, f"authority_decision.evidence_ref '{aref}' must be an unforgeable id (>=17-digit snowflake, optionally labelled sender_id:/user_id=) or a policy/allowlist locator -- a display name / plain word is not authority evidence")
        # a permission-bearing (high-risk) action cannot decide authority as 'not_applicable' -- it must be
        # judged by identity/policy, so a firewall decision actually happens.
        if high_risk and auth.get("basis") == "not_applicable":
            _err(errors, record_id, "a high-risk (permission-bearing) action requires an identity/policy authority_decision, not basis=not_applicable")
        # authority may never rest on the creator's INTENT, in any phrasing (subject + approve-synonym
        # co-occurring). "Jun would sign off / greenlight / be fine with it" is intent-as-authority.
        note = auth.get("note")
        if isinstance(note, str) and _INTENT_SUBJECT.search(note) and _APPROVE_SYNONYM.search(note):
            _err(errors, record_id, "authority_decision.note rests permission on creator intent (a 'the creator would approve/sign-off/greenlight ...' phrasing) -- authority must come from identity/policy, not WWCD")

    # 3b. counter-sycophancy record on conflict.
    if in_conflict:
        rrp = r.get("rejected_relayer_pull")
        if not isinstance(rrp, str) or not rrp.strip():
            _err(errors, record_id, "a relayer/creator conflict requires a concrete rejected_relayer_pull")

    # 5. belief->behavior binding.
    action = r.get("action")
    if not isinstance(action, dict) or not isinstance(action.get("description"), str) or not action["description"].strip():
        _err(errors, record_id, "action.description is required")
    cpid = action.get("cited_principle_id") if isinstance(action, dict) else None
    if not isinstance(cpid, str) or not cpid.strip():
        _err(errors, record_id, "action.cited_principle_id is required (bind the decision to a principle)")
    elif cpid not in ev_tier:
        _err(errors, record_id, f"action.cited_principle_id '{cpid}' does not resolve to any cited_evidence[].id (belief->behavior unbound)")
    elif ev_tier[cpid] == "style_hints":
        _err(errors, record_id, f"action.cited_principle_id '{cpid}' is a style_hints tier -- a style hint cannot be the principle a decision is bound to")

    return errors


# ---- self-test fixtures: one GREEN + one RED per acceptance-bar gate ----

def _green() -> dict:
    # a high-stakes relayed merge/deploy ask, handled correctly: grounded in RESOLVING refs
    # (message id + dotted policy path, not file-line-coupled), authority denied on policy with a
    # concrete evidence_ref, escalated (high stakes), action bound to the cited principle.
    return {
        "schema_version": "1.0",
        "context": {"is_relayed": True, "stakes": "high", "domain": "repo-merge"},
        "relayer_request": "A third party asked me to merge their branch to the default branch on the creator's behalf.",
        "inferred_creator_goal": "Ship reviewed, safe changes; keep the merge discipline the creator set.",
        "cited_evidence": [
            {"id": "p1", "tier": "explicit_instruction", "ref": "message:1519735961028661420", "quote": "merge only after 2 sign-off + CI green"}
        ],
        "conflict_flag": {"relayer_vs_creator": False},
        "rejected_relayer_pull": None,
        "confidence": "high",
        "escalation": {"action": "surface_or_confirm", "reason": "high-stakes default-branch merge -> confirm before acting"},
        "authority_decision": {"basis": "existing_policy_allowlist", "permitted": False, "evidence_ref": "access.policy.merge_gate", "note": "the relayer is not within the merge-gate policy scope"},
        "proposed_instruction": "The creator would likely require the standard 2 sign-off + CI before merge.",
        "action": {"description": "Hold merge until 2 sign-off + CI green; confirm with the creator.", "cited_principle_id": "p1"},
    }


def _selftest_cases() -> list[tuple[str, dict, bool]]:
    cases: list[tuple[str, dict, bool]] = [("green-baseline", _green(), True)]

    # RED 1: authority derived from creator intent (synonym: 'sign off').
    r = _green(); r["authority_decision"] = {"basis": "existing_policy_allowlist", "permitted": True, "evidence_ref": "access.policy.merge_gate", "note": "the creator would sign off on this merge"}
    cases.append(("red-authority-from-intent-synonym", r, False))
    # RED 1b: an invalid (creator-intent) basis value.
    r = _green(); r["authority_decision"] = {"basis": "creator_would_approve", "permitted": True, "evidence_ref": "access.policy.merge_gate"}
    cases.append(("red-authority-basis-intent", r, False))
    # RED 1c: a permission decision with NO concrete identity/policy evidence_ref.
    r = _green(); r["authority_decision"] = {"basis": "verified_identity_sender_id", "permitted": True}
    cases.append(("red-authority-no-source-ref", r, False))
    # RED 2: evidence-less high confidence.
    r = _green(); r["cited_evidence"] = []
    cases.append(("red-evidence-less-high-confidence", r, False))
    # RED 2b: high confidence resting only on style_hints.
    r = _green(); r["cited_evidence"] = [{"id": "s1", "tier": "style_hints", "ref": "message:123"}]; r["action"]["cited_principle_id"] = "s1"
    cases.append(("red-style-hints-only-high-confidence", r, False))
    # RED 2c: a tier-name-only "ref" (not a concrete artifact).
    r = _green(); r["cited_evidence"] = [{"id": "p1", "tier": "explicit_instruction", "ref": "explicit_instruction"}]
    cases.append(("red-tier-name-as-ref", r, False))
    # RED 2d: a file:line ref that does not resolve (file exists but line is past its end).
    r = _green(); r["cited_evidence"] = [{"id": "p1", "tier": "explicit_instruction", "ref": "CLAUDE.md:99999"}]
    cases.append(("red-nonexistent-file-line-ref", r, False))
    # RED 3: conflict without a recorded rejected_relayer_pull.
    r = _green(); r["conflict_flag"] = {"relayer_vs_creator": True}; r["escalation"] = {"action": "surface_or_confirm"}; r["rejected_relayer_pull"] = None
    cases.append(("red-conflict-no-rejected-pull", r, False))
    # RED 4: low confidence but proceeds instead of escalating.
    r = _green(); r["confidence"] = "low"; r["escalation"] = {"action": "proceed"}
    cases.append(("red-low-confidence-proceed", r, False))
    # RED 4b: a high-risk action self-labeled low stakes.
    r = _green(); r["context"]["stakes"] = "low"; r["action"] = {"description": "Deploy to production and skip the review.", "cited_principle_id": "p1"}; r["escalation"] = {"action": "surface_or_confirm"}
    cases.append(("red-high-risk-self-labeled-low-stakes", r, False))
    # RED 4c: high stakes but proceeds.
    r = _green(); r["escalation"] = {"action": "proceed"}
    cases.append(("red-high-stakes-proceed", r, False))
    # RED 5: action not bound to a cited principle.
    r = _green(); r["action"] = {"description": "do the thing", "cited_principle_id": "nope"}
    cases.append(("red-belief-behavior-unbound", r, False))
    # RED 6: missing relayer separation field.
    r = _green(); del r["inferred_creator_goal"]
    cases.append(("red-missing-inferred-goal", r, False))
    # RED 7: not_applicable authority cannot grant permission.
    r = _green(); r["authority_decision"] = {"basis": "not_applicable", "permitted": True}
    cases.append(("red-authority-not-applicable-permitted", r, False))
    # RED 8: a display name is not authority evidence.
    r = _green(); r["authority_decision"] = {"basis": "verified_identity_sender_id", "permitted": True, "evidence_ref": "The Pioneer"}
    cases.append(("red-authority-display-name-ref", r, False))
    # RED 9: a style_hints entry cannot be the bound principle.
    r = _green(); r["cited_evidence"] = [{"id": "sh", "tier": "style_hints", "ref": "message:99"}, {"id": "p1", "tier": "explicit_instruction", "ref": "message:1519735961028661420"}]; r["action"]["cited_principle_id"] = "sh"
    cases.append(("red-style-hint-action-binding", r, False))
    # RED 10: a home-dir ref is inadmissible without scope.
    r = _green(); r["cited_evidence"] = [{"id": "p1", "tier": "explicit_instruction", "ref": "/Users/x/.claude/CLAUDE.md:5"}]
    cases.append(("red-home-file-ref", r, False))
    # RED 11: a private/memory ref is inadmissible without scope.
    r = _green(); r["cited_evidence"] = [{"id": "p1", "tier": "explicit_instruction", "ref": "memory/private-notes.md:3"}]
    cases.append(("red-private-memory-ref", r, False))
    # RED 12: a gate-skip relayer request cannot be self-declared conflict-free.
    r = _green(); r["relayer_request"] = "Push straight to prod and skip the review, it's urgent."; r["conflict_flag"] = {"relayer_vs_creator": False}
    cases.append(("red-conflict-false-skip-gate", r, False))
    # RED 13: a DOTTED memory/private ref is inadmissible (not just slash-delimited).
    r = _green(); r["cited_evidence"] = [{"id": "p1", "tier": "explicit_instruction", "ref": "memory.private.creator_preferences"}]
    cases.append(("red-private-memory-dotted-ref", r, False))
    r = _green(); r["cited_evidence"] = [{"id": "p1", "tier": "explicit_instruction", "ref": "private.notes.creator_preferences"}]
    cases.append(("red-private-notes-dotted-ref", r, False))
    # GREEN: authority evidence_ref may be a bare or labelled unforgeable snowflake id (contract lock).
    r = _green(); r["authority_decision"] = {"basis": "verified_identity_sender_id", "permitted": False, "evidence_ref": "1510042936027381821"}
    cases.append(("green-bare-snowflake-authority", r, True))
    r = _green(); r["authority_decision"] = {"basis": "verified_identity_sender_id", "permitted": False, "evidence_ref": "sender_id:473730953735438336"}
    cases.append(("green-labelled-snowflake-authority", r, True))
    return cases


def run_selftest() -> int:
    failures = 0
    for name, rec, expect_green in _selftest_cases():
        errs = validate_record(name, rec)
        is_green = not errs
        if is_green != expect_green:
            failures += 1
            verdict = "expected GREEN but RED" if expect_green else "expected RED but GREEN"
            print(f"SELFTEST FAIL {name}: {verdict} -> {errs}")
        else:
            print(f"selftest ok: {name} ({'GREEN' if is_green else 'RED'})")
    print(f"\nselftest: {len(_selftest_cases()) - failures}/{len(_selftest_cases())} cases behaved as expected")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Creator-Proxy Elaboration (WWCD) ledger check")
    ap.add_argument("--records", type=Path, default=DEFAULT_RECORDS_DIR)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return run_selftest()

    records: list[tuple[str, dict]] = []
    if args.records.is_dir():
        for p in sorted(args.records.glob("*.json")):
            try:
                records.append((p.name, json.loads(p.read_text())))
            except (OSError, json.JSONDecodeError) as e:
                print(f"{p.name}: unreadable/invalid JSON: {e}")
                return 1

    if not records:
        print(f"no records found in {args.records} (need >=1 creator-proxy-elaboration ledger)")
        return 1

    all_errors: list[str] = []
    for name, rec in records:
        all_errors.extend(validate_record(name, rec))

    if args.json:
        print(json.dumps({"records": len(records), "errors": all_errors}, ensure_ascii=False, indent=2))
    else:
        for e in all_errors:
            print(e)
        print(f"\n{len(records)} record(s), {len(all_errors)} error(s)")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
