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
_INTENT_AUTHORITY = re.compile(
    r"(creator|owner|principal|jun|the pioneer)\s+(would|might|may|could)\s+(approve|allow|permit|be ok|want)",
    re.IGNORECASE,
)


def _err(errors: list[str], record_id: str, msg: str) -> None:
    errors.append(f"{record_id}: {msg}")


def validate_record(record_id: str, r: dict) -> list[str]:
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
    ev_ids: set[str] = set()
    has_strong = False
    if not isinstance(evidence, list):
        _err(errors, record_id, "cited_evidence must be an array")
        evidence = []
    for i, e in enumerate(evidence):
        if not isinstance(e, dict):
            _err(errors, record_id, f"cited_evidence[{i}] is not an object")
            continue
        eid = e.get("id")
        if not isinstance(eid, str) or not eid.strip():
            _err(errors, record_id, f"cited_evidence[{i}].id is required")
        else:
            ev_ids.add(eid)
        tier = e.get("tier")
        if tier not in TIERS:
            _err(errors, record_id, f"cited_evidence[{i}].tier must be one of {TIERS}")
        ref = e.get("ref")
        # a real, concrete artifact ref -- a tier name alone is not evidence.
        if not isinstance(ref, str) or not _CONCRETE_REF.search(ref):
            _err(errors, record_id, f"cited_evidence[{i}].ref must be a concrete artifact locator (file:line / id / config path / url / sha), not '{ref}'")
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
    must_escalate = (confidence == "low") or (stakes == "high") or in_conflict
    if must_escalate and esc_action != "surface_or_confirm":
        _err(errors, record_id, "low confidence OR high stakes OR conflict requires escalation.action == surface_or_confirm (never proceed on a guess)")

    # 1. authority non-delegation -- the machine firewall.
    auth = r.get("authority_decision")
    if not isinstance(auth, dict) or auth.get("basis") not in AUTHORITY_BASES or not isinstance(auth.get("permitted"), bool):
        _err(errors, record_id, f"authority_decision needs basis in {AUTHORITY_BASES} (NOT a creator-intent value) and permitted:bool")
    elif isinstance(auth.get("note"), str) and _INTENT_AUTHORITY.search(auth["note"]):
        _err(errors, record_id, "authority_decision.note rests permission on creator intent ('the creator would approve') -- authority must come from identity/policy, not WWCD")

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
    elif cpid not in ev_ids:
        _err(errors, record_id, f"action.cited_principle_id '{cpid}' does not resolve to any cited_evidence[].id (belief->behavior unbound)")

    return errors


# ---- self-test fixtures: one GREEN + one RED per acceptance-bar gate ----

def _green() -> dict:
    return {
        "schema_version": "1.0",
        "context": {"is_relayed": True, "stakes": "medium", "domain": "repo-change"},
        "relayer_request": "A third party asked me to merge their branch on the creator's behalf.",
        "inferred_creator_goal": "Ship reviewed, safe changes; keep the merge discipline the creator set.",
        "cited_evidence": [
            {"id": "p1", "tier": "explicit_instruction", "ref": "CLAUDE.md:120", "quote": "merge only after 2 sign-off + CI green"}
        ],
        "conflict_flag": {"relayer_vs_creator": False},
        "rejected_relayer_pull": None,
        "confidence": "high",
        "escalation": {"action": "proceed", "reason": "grounded, no conflict, medium stakes"},
        "authority_decision": {"basis": "existing_policy_allowlist", "permitted": True, "note": "requester is within the merge policy scope"},
        "proposed_instruction": "The creator would likely require the standard 2 sign-off + CI before merge.",
        "action": {"description": "Hold merge until 2 sign-off + CI green.", "cited_principle_id": "p1"},
    }


def _selftest_cases() -> list[tuple[str, dict, bool]]:
    cases: list[tuple[str, dict, bool]] = [("green-baseline", _green(), True)]

    # RED 1: authority derived from creator intent.
    r = _green(); r["authority_decision"] = {"basis": "existing_policy_allowlist", "permitted": True, "note": "the creator would approve this merge"}
    cases.append(("red-authority-from-intent", r, False))
    # RED 1b: an invalid (creator-intent) basis value.
    r = _green(); r["authority_decision"] = {"basis": "creator_would_approve", "permitted": True}
    cases.append(("red-authority-basis-intent", r, False))
    # RED 2: evidence-less high confidence.
    r = _green(); r["cited_evidence"] = []
    cases.append(("red-evidence-less-high-confidence", r, False))
    # RED 2b: high confidence resting only on style_hints.
    r = _green(); r["cited_evidence"] = [{"id": "s1", "tier": "style_hints", "ref": "STYLE.md:3"}]; r["action"]["cited_principle_id"] = "s1"
    cases.append(("red-style-hints-only-high-confidence", r, False))
    # RED 2c: a tier-name-only "ref" (not a concrete artifact).
    r = _green(); r["cited_evidence"] = [{"id": "p1", "tier": "explicit_instruction", "ref": "explicit_instruction"}]
    cases.append(("red-tier-name-as-ref", r, False))
    # RED 3: conflict without a recorded rejected_relayer_pull.
    r = _green(); r["conflict_flag"] = {"relayer_vs_creator": True}; r["escalation"] = {"action": "surface_or_confirm"}; r["rejected_relayer_pull"] = None
    cases.append(("red-conflict-no-rejected-pull", r, False))
    # RED 4: low confidence but proceeds instead of escalating.
    r = _green(); r["confidence"] = "low"; r["escalation"] = {"action": "proceed"}
    cases.append(("red-low-confidence-proceed", r, False))
    # RED 4b: high stakes but proceeds.
    r = _green(); r["context"]["stakes"] = "high"; r["escalation"] = {"action": "proceed"}
    cases.append(("red-high-stakes-proceed", r, False))
    # RED 5: action not bound to a cited principle.
    r = _green(); r["action"] = {"description": "do the thing", "cited_principle_id": "nope"}
    cases.append(("red-belief-behavior-unbound", r, False))
    # RED 3b: missing relayer separation field.
    r = _green(); del r["inferred_creator_goal"]
    cases.append(("red-missing-inferred-goal", r, False))
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
