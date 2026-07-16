#!/usr/bin/env python3
"""Fail-closed checker for the Finance Proposal Completeness Gate (#74).

Validates finance claim-ledger records against the gate contract in
`skills/fairy-tale/references/cards/finance-proposal-completeness-gate.md`:

  - arithmetic: displayed vs recomputed must reconcile within the stated
    rounding rule; an unverifiable claim (no formula/recomputation) blocks.
  - ledger completeness: every central claim carries metric definition,
    period/currency/unit/tax-basis, and a source locator.
  - unit-economics assumption closure: the stated business model entails cost
    rows (partner/channel-led -> channel economics; implementation/managed
    service -> setup_onboarding, support, security, incident_response;
    recurring -> feasible conversion/churn cohort schedule). Every entailed
    row needs exactly one disposition out of the closed enum
    {amount, included-in, not-applicable-with-evidence, TBD}.
  - fail-closed TBD: a TBD on an entailed driver blocks and must be counted
    in unresolved_count; a disclaimer never converts an omission to zero.
  - evidence-backed applicability: not-applicable-with-evidence requires a
    substantive reason; a supported not-applicable must NOT false-block.
  - aggregate margins inherit component coverage: an aggregate claim blocks
    when any referenced component has unresolved cost coverage.
  - heterogeneous sign-off: one arithmetic_reconciliation reviewer plus one
    completeness_negative_space reviewer, distinct identities, both bound to
    the same artifact hash; a hash mismatch invalidates both.

Usage:
  finance_completeness_check.py [--cases FILE] [--json] [--selftest]

Exit 0 = all cases match their expected verdicts (and coverage/metamorphic
requirements hold); 1 = otherwise.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = REPO_ROOT / "fixtures" / "finance-completeness" / "cases.jsonl"

DISPOSITIONS = {"amount", "included-in", "not-applicable-with-evidence", "TBD"}
METRICS = {"revenue", "gross_margin", "contribution_margin", "operating_profit", "forecast"}
REQUIRED_CLAIM_FIELDS = ("claim_id", "source", "metric", "period", "currency", "unit", "tax_basis")
SIGNOFF_ROLES = {"arithmetic_reconciliation", "completeness_negative_space"}

# Business model -> structurally entailed cost-driver classes. Model names are
# generic (no org-specific vocabulary); unknown models entail nothing extra but
# still get arithmetic/ledger/sign-off enforcement.
ENTAILMENTS = {
    "partner_led_sales": ["channel_economics"],
    "channel_sales": ["channel_economics"],
    "implementation_service": ["setup_onboarding", "support", "security", "incident_response"],
    "managed_service": ["setup_onboarding", "support", "security", "incident_response"],
    "self_serve_saas": ["onboarding_applicability"],
}
RECURRING_MODELS = {"self_serve_saas", "managed_service", "subscription", "marketplace_recurring"}


def rounding_tolerance(rule: str | None) -> float | None:
    if not rule or not isinstance(rule, str):
        return None
    rule = rule.strip().lower()
    if rule.endswith("dp") and rule[:-2].isdigit():
        return 0.5 * 10 ** -int(rule[:-2])
    return None


def check_claim_arithmetic(claim: dict, reasons: list[str]) -> None:
    displayed = claim.get("displayed_value")
    recomputed = claim.get("recomputed_value")
    if displayed is None or recomputed is None or not claim.get("formula"):
        reasons.append(f"arithmetic_unverified:{claim.get('claim_id', '?')}")
        return
    tol = rounding_tolerance(claim.get("rounding_rule"))
    if tol is None:
        reasons.append(f"rounding_rule_missing:{claim.get('claim_id', '?')}")
        return
    if abs(float(displayed) - float(recomputed)) > tol:
        reasons.append(f"arithmetic_mismatch:{claim.get('claim_id', '?')}")


def driver_index(claim: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for driver in claim.get("cost_drivers", []) or []:
        name = driver.get("name") or driver.get("entailed_class") or "?"
        index[name] = driver
        entailed_class = driver.get("entailed_class")
        if entailed_class:
            index[entailed_class] = driver
    return index


def check_driver(driver: dict, claim_id: str, reasons: list[str]) -> bool:
    """Validate one cost driver. Returns True when the driver is open (TBD)."""
    disposition = driver.get("disposition")
    name = driver.get("name") or driver.get("entailed_class") or "?"
    if disposition not in DISPOSITIONS:
        reasons.append(f"disposition_invalid:{claim_id}:{name}")
        return False
    if disposition == "TBD":
        return True
    if disposition == "amount" and not isinstance(driver.get("value"), (int, float)):
        reasons.append(f"amount_without_value:{claim_id}:{name}")
    if disposition == "included-in" and not (driver.get("included_in") or "").strip():
        reasons.append(f"included_in_dangling:{claim_id}:{name}")
    if disposition == "not-applicable-with-evidence" and len((driver.get("evidence") or "").strip()) < 10:
        reasons.append(f"unsupported_not_applicable:{claim_id}:{name}")
    return False


def claim_has_open_coverage(claim: dict) -> bool:
    return any((d.get("disposition") == "TBD") or (d.get("disposition") not in DISPOSITIONS)
               for d in claim.get("cost_drivers", []) or [])


def evaluate(ledger: dict) -> tuple[str, list[str]]:
    """Return (verdict, reasons). Verdict is 'pass' or 'block'. Fail closed."""
    reasons: list[str] = []
    if not isinstance(ledger, dict):
        return "block", ["ledger_not_object"]
    claims = ledger.get("claims") or []
    if not claims:
        reasons.append("no_claims_recorded")
    claims_by_id = {c.get("claim_id"): c for c in claims if isinstance(c, dict)}
    open_tbd = 0

    for claim in claims:
        cid = claim.get("claim_id", "?")
        for field in REQUIRED_CLAIM_FIELDS:
            if not str(claim.get(field) or "").strip():
                reasons.append(f"missing_ledger_field:{cid}:{field}")
        if claim.get("metric") not in METRICS:
            reasons.append(f"metric_undefined:{cid}")
        check_claim_arithmetic(claim, reasons)
        for driver in claim.get("cost_drivers", []) or []:
            if check_driver(driver, cid, reasons):
                open_tbd += 1
                reasons.append(f"tbd_open:{cid}:{driver.get('name') or driver.get('entailed_class') or '?'}")
        # Aggregates inherit component coverage.
        for component_id in claim.get("components", []) or []:
            component = claims_by_id.get(component_id)
            if component is None:
                reasons.append(f"component_missing:{cid}:{component_id}")
            elif claim_has_open_coverage(component):
                reasons.append(f"aggregate_incomplete_component:{cid}:{component_id}")

    # Model-entailed rows must be dispositioned on at least one claim.
    models = [m for m in (ledger.get("business_model") or []) if isinstance(m, str)]
    entailed_classes = {cls for model in models for cls in ENTAILMENTS.get(model, [])}
    dispositioned: set[str] = set()
    for claim in claims:
        for name, driver in driver_index(claim).items():
            if driver.get("disposition") in DISPOSITIONS:
                dispositioned.add(name)
    for cls in sorted(entailed_classes):
        if cls not in dispositioned:
            reasons.append(f"entailed_cost_undispositioned:{cls}")

    # Recurring models need a feasible cohort schedule.
    if any(model in RECURRING_MODELS for model in models):
        schedule = ledger.get("cohort_schedule")
        if not isinstance(schedule, dict) or not str(schedule.get("feasible_evidence") or "").strip():
            reasons.append("cohort_schedule_missing")
        else:
            churn = schedule.get("churn_monthly")
            active = schedule.get("active_months")
            if isinstance(churn, (int, float)) and isinstance(active, (int, float)) and churn > 0:
                if active > 1.5 * (1.0 / churn):
                    reasons.append("cohort_schedule_infeasible")

    declared = ledger.get("unresolved_count")
    if not isinstance(declared, int) or declared != open_tbd:
        reasons.append(f"unresolved_count_mismatch:declared={declared!r}:actual={open_tbd}")

    # Heterogeneous sign-off over the same immutable artifact.
    artifact = str(ledger.get("artifact_sha256") or "").strip()
    signoffs = [s for s in (ledger.get("signoffs") or []) if isinstance(s, dict)]
    roles = {s.get("role") for s in signoffs}
    reviewers = {s.get("reviewer") for s in signoffs if s.get("reviewer")}
    if not artifact:
        reasons.append("artifact_hash_missing")
    if roles < SIGNOFF_ROLES:
        reasons.append("signoff_roles_incomplete")
    elif len(reviewers) < 2:
        reasons.append("signoff_reviewers_not_distinct")
    for signoff in signoffs:
        if artifact and str(signoff.get("artifact_sha256") or "").strip() != artifact:
            reasons.append(f"signoff_stale_artifact:{signoff.get('role', '?')}")

    return ("block" if reasons else "pass"), reasons


def run_cases(path: Path, as_json: bool) -> int:
    if not path.exists():
        print(f"cases file not found: {path}")
        return 1
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not cases:
        print(f"no cases found in {path}")
        return 1
    failures: list[str] = []
    results = []
    model_coverage: set[str] = set()
    for case in cases:
        verdict, reasons = evaluate(case.get("ledger") or {})
        expected = case.get("expected")
        ok = verdict == expected
        for expected_reason in case.get("expected_reasons", []) or []:
            if not any(reason.startswith(expected_reason) for reason in reasons):
                ok = False
                failures.append(f"{case.get('id')}: expected reason prefix {expected_reason!r} absent (got {reasons})")
        if verdict != expected:
            failures.append(f"{case.get('id')}: verdict {verdict} != expected {expected} (reasons: {reasons})")
        model_coverage.update(case.get("industry_tags", []) or [])
        results.append({"id": case.get("id"), "verdict": verdict, "expected": expected, "ok": ok, "reasons": reasons})
    required_coverage = {"agency", "saas", "marketplace", "managed_service", "hardware", "channel_sales"}
    missing_coverage = required_coverage - model_coverage
    if missing_coverage:
        failures.append(f"industry coverage incomplete, missing: {sorted(missing_coverage)}")
    # Metamorphic requirement: at least one declared add/remove pair whose
    # verdicts differ (removing a disposition must flip pass -> block).
    pairs = {}
    for case in cases:
        pair = case.get("metamorphic_pair")
        if pair:
            pairs.setdefault(pair, []).append(case)
    flip_ok = any(
        len(members) == 2 and {members[0].get("expected"), members[1].get("expected")} == {"pass", "block"}
        for members in pairs.values()
    )
    if not flip_ok:
        failures.append("no add/remove metamorphic pair with a pass/block flip found")
    if as_json:
        print(json.dumps({"results": results, "failures": failures}, ensure_ascii=False, indent=2))
    else:
        for result in results:
            marker = "GREEN" if result["ok"] else "RED"
            print(f"[{marker:6}] {result['id']}: {result['verdict']} (expected {result['expected']})")
        for failure in failures:
            print(f"[RED   ] {failure}")
    if failures:
        print(f"finance completeness gate FAILED: {len(failures)} problem(s)")
        return 1
    print(f"finance completeness gate OK: {len(results)} case(s) match expected verdicts, "
          f"coverage + metamorphic flip present")
    return 0


def _green_ledger() -> dict:
    return {
        "artifact_sha256": "sha256:" + "a" * 64,
        "business_model": ["partner_led_sales"],
        "unresolved_count": 0,
        "claims": [{
            "claim_id": "C1", "source": "p2:table1", "metric": "gross_margin",
            "period": "FY1", "currency": "USD", "unit": "ratio", "tax_basis": "excl",
            "displayed_value": 0.60, "formula": "(rev-cogs)/rev", "recomputed_value": 0.60,
            "rounding_rule": "2dp",
            "cost_drivers": [{
                "name": "partner_fee", "entailed_class": "channel_economics",
                "disposition": "amount", "value": 0.15,
            }],
        }],
        "signoffs": [
            {"role": "arithmetic_reconciliation", "reviewer": "r1", "artifact_sha256": "sha256:" + "a" * 64},
            {"role": "completeness_negative_space", "reviewer": "r2", "artifact_sha256": "sha256:" + "a" * 64},
        ],
    }


def _selftest() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool) -> None:
        print(f"[{'GREEN' if condition else 'RED':6}] selftest: {name}")
        if not condition:
            failures.append(name)

    verdict, reasons = evaluate(_green_ledger())
    check("green ledger passes", verdict == "pass" and not reasons)

    # add/remove metamorphic: strip the entailed disposition -> must flip to block.
    removed = copy.deepcopy(_green_ledger())
    removed["claims"][0]["cost_drivers"] = []
    verdict, reasons = evaluate(removed)
    check("removing the entailed disposition flips to block",
          verdict == "block" and any(r.startswith("entailed_cost_undispositioned") for r in reasons))

    tbd = copy.deepcopy(_green_ledger())
    tbd["claims"][0]["cost_drivers"][0] = {"name": "partner_fee", "entailed_class": "channel_economics", "disposition": "TBD"}
    verdict, reasons = evaluate(tbd)
    check("TBD blocks and demands unresolved_count sync",
          verdict == "block" and any(r.startswith("tbd_open") for r in reasons)
          and any(r.startswith("unresolved_count_mismatch") for r in reasons))
    tbd["unresolved_count"] = 1
    verdict, reasons = evaluate(tbd)
    check("TBD still blocks even when honestly counted (never an accepted zero)",
          verdict == "block" and any(r.startswith("tbd_open") for r in reasons))

    hostile = copy.deepcopy(_green_ledger())
    hostile["claims"][0]["cost_drivers"][0] = {
        "name": "partner_fee", "entailed_class": "channel_economics",
        "disposition": "not-applicable-with-evidence", "evidence": "n/a",
    }
    verdict, reasons = evaluate(hostile)
    check("bare 'n/a' evidence is an unsupported applicability assertion",
          verdict == "block" and any(r.startswith("unsupported_not_applicable") for r in reasons))

    arithmetic = copy.deepcopy(_green_ledger())
    arithmetic["claims"][0]["recomputed_value"] = 0.55
    verdict, reasons = evaluate(arithmetic)
    check("arithmetic mismatch blocks", verdict == "block" and any(r.startswith("arithmetic_mismatch") for r in reasons))

    same_reviewer = copy.deepcopy(_green_ledger())
    for signoff in same_reviewer["signoffs"]:
        signoff["reviewer"] = "r1"
    verdict, reasons = evaluate(same_reviewer)
    check("homogeneous reviewers rejected", verdict == "block" and "signoff_reviewers_not_distinct" in reasons)

    stale = copy.deepcopy(_green_ledger())
    stale["signoffs"][1]["artifact_sha256"] = "sha256:" + "b" * 64
    verdict, reasons = evaluate(stale)
    check("changed artifact invalidates sign-off", verdict == "block" and any(r.startswith("signoff_stale_artifact") for r in reasons))

    if failures:
        print("finance completeness selftest FAILED.")
        return 1
    print("finance completeness selftest passed (green->pass; reject: removed disposition, TBD-as-zero, "
          "bare n/a, arithmetic drift, homogeneous reviewers, stale sign-off).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Finance Proposal Completeness Gate checker (#74)")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="JSONL acceptance cases")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--selftest", action="store_true", help="run built-in red/green/hostile controls")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    return run_cases(args.cases, args.json)


if __name__ == "__main__":
    sys.exit(main())
