#!/usr/bin/env python3
"""Fail-closed checker for the Finance Proposal Completeness Gate (#74).

Validates finance claim-ledger records against the gate contract in
`skills/fairy-tale/references/cards/finance-proposal-completeness-gate.md`.
The teeth (all fail-closed — nothing is trusted from self-attestation):

  - strict schema: unknown keys anywhere in the ledger, malformed types, and
    missing required fields block. `business_model` must be a list drawn from
    a CLOSED model registry — an unrecognized or malformed model cannot
    certify that nothing extra is entailed, so it blocks.
  - deterministic arithmetic: the checker re-executes each claim's `formula`
    over its stated `inputs` with a restricted AST evaluator (+,-,*,/ only)
    and compares the result to `displayed_value` under the claim's rounding
    rule. Aggregate claims are recomputed from component displayed values via
    required, normalized `weights`. A formula the checker cannot execute, a
    missing input, a NaN/inf anywhere, or a self-asserted value with no
    executable backing blocks. `recomputed_value` in the record is ignored —
    recomputation is the checker's job.
  - unit-economics assumption closure: the stated business model entails cost
    rows (partner/channel -> channel economics; implementation/managed
    service -> setup_onboarding, support, security, incident_response;
    recurring -> feasible conversion/churn cohort schedule consistent with
    the revenue drivers). Every entailed row needs exactly one disposition
    out of {amount, included-in, not-applicable-with-evidence, TBD}.
  - disposition teeth: `TBD` blocks and must reconcile with unresolved_count
    (never an accepted zero); `included-in` must reference an existing cost
    driver, claim, or formula input in the SAME ledger and carry a
    substantive allocation_basis; `not-applicable-with-evidence` needs a
    citable locator-shaped anchor, not prose length; duplicate or unnamed
    drivers block.
  - aggregates inherit component coverage; heterogeneous sign-off
    (arithmetic_reconciliation + completeness_negative_space, distinct
    reviewers) binds to one `sha256:<64 hex>` artifact hash; any mismatch
    invalidates.

Usage:
  finance_completeness_check.py [--cases FILE] [--json] [--selftest]

Exit 0 = all cases match their expected verdicts (and coverage/metamorphic
requirements hold); 1 = otherwise.
"""

from __future__ import annotations

import argparse
import ast
import copy
import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = REPO_ROOT / "fixtures" / "finance-completeness" / "cases.jsonl"

DISPOSITIONS = {"amount", "included-in", "not-applicable-with-evidence", "TBD"}
METRICS = {"revenue", "gross_margin", "contribution_margin", "operating_profit", "forecast"}
REQUIRED_CLAIM_FIELDS = ("claim_id", "source", "metric", "period", "currency", "unit", "tax_basis")
SIGNOFF_ROLES = {"arithmetic_reconciliation", "completeness_negative_space"}
ARTIFACT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# A not-applicable disposition needs a *citable* reason: some locator-shaped
# anchor (page/section/contract/appendix/terms/URL/cell), not just prose length.
EVIDENCE_ANCHOR_RE = re.compile(
    r"(p\.?\s?\d+|§|\bappendix\b|\bcontract\b|\bpage\b|\bterms\b|\bclause\b|\bschedule\b|https?://|\bcell\s?[A-Z]+\d+)",
    re.IGNORECASE,
)

# Strict schema: the only keys each object may carry. Unknown keys block —
# a typo'd field must never silently weaken a disposition or a driver.
LEDGER_KEYS = {"artifact_sha256", "business_model", "unresolved_count", "claims", "cohort_schedule", "signoffs"}
CLAIM_KEYS = {
    "claim_id", "source", "metric", "period", "currency", "unit", "tax_basis",
    "displayed_value", "formula", "inputs", "rounding_rule", "revenue_drivers",
    "cost_drivers", "assumptions", "evidence_status", "sensitivity",
    "depends_on", "components", "weights",
}
DRIVER_KEYS = {"name", "entailed_class", "disposition", "value", "included_in", "allocation_basis", "evidence"}
SIGNOFF_KEYS = {"role", "reviewer", "artifact_sha256"}
COHORT_KEYS = {"conversion", "churn_monthly", "active_months", "feasible_evidence"}
REVENUE_DRIVER_REQUIRED = ("price", "volume", "start_month", "active_months")
REVENUE_DRIVER_KEYS = set(REVENUE_DRIVER_REQUIRED) | {"conversion", "churn_monthly", "setup_fee"}

# Business model -> structurally entailed cost-driver classes. Model names are
# generic (no org-specific vocabulary). The registry is CLOSED and fail-closed:
# a ledger whose business_model is malformed or names an unrecognized model
# blocks, because an unknown motion cannot certify that nothing extra is
# entailed.
ENTAILMENTS = {
    "partner_led_sales": ["channel_economics"],
    "channel_sales": ["channel_economics"],
    "implementation_service": ["setup_onboarding", "support", "security", "incident_response"],
    "managed_service": ["setup_onboarding", "support", "security", "incident_response"],
    "self_serve_saas": ["onboarding_applicability"],
}
RECURRING_MODELS = {"self_serve_saas", "managed_service", "subscription", "marketplace_recurring"}
# Models with no entailments beyond the always-on arithmetic/ledger/sign-off
# rules must still be REGISTERED here to pass — that is the fail-closed teeth.
KNOWN_MODELS = set(ENTAILMENTS) | RECURRING_MODELS | {
    "direct_sales", "marketplace_take_rate", "hardware_sales", "one_time_license",
}


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def safe_eval_formula(formula: str, inputs: dict) -> float | None:
    """Deterministically recompute a claim formula over its stated inputs.

    Only +, -, *, /, unary +/-, parentheses, numeric literals, and input names
    are allowed. Any parse error, unknown name, non-finite operand, or
    non-finite result returns None (the caller blocks): a formula the checker
    cannot execute is unverified, never trusted.
    """
    try:
        tree = ast.parse(formula, mode="eval")
    except (SyntaxError, ValueError):
        return None

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            return left / right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = ev(node.operand)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.Name):
            value = inputs[node.id]
            if not is_finite_number(value):
                raise ValueError(f"non-finite input {node.id}")
            return float(value)
        if isinstance(node, ast.Constant) and is_finite_number(node.value):
            return float(node.value)
        raise ValueError(f"disallowed node {type(node).__name__}")

    try:
        result = ev(tree)
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) else None


def rounding_tolerance(rule: object) -> float | None:
    if not isinstance(rule, str):
        return None
    rule = rule.strip().lower()
    if rule.endswith("dp") and rule[:-2].isdigit():
        return 0.5 * 10 ** -int(rule[:-2])
    return None


def check_unknown_keys(obj: dict, allowed: set[str], where: str, reasons: list[str]) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        reasons.append(f"schema_unknown_keys:{where}:{','.join(unknown)}")


def check_claim_arithmetic(claim: dict, claims_by_id: dict, reasons: list[str]) -> None:
    cid = claim.get("claim_id", "?")
    displayed = claim.get("displayed_value")
    if not is_finite_number(displayed):
        reasons.append(f"non_finite_value:{cid}:displayed_value")
        return
    tol = rounding_tolerance(claim.get("rounding_rule"))
    if tol is None:
        reasons.append(f"rounding_rule_missing:{cid}")
        return
    components = claim.get("components")
    if components:
        weights = claim.get("weights")
        if not isinstance(weights, dict) or set(weights) != set(components):
            reasons.append(f"aggregate_weights_missing:{cid}")
            return
        if not all(is_finite_number(w) for w in weights.values()):
            reasons.append(f"non_finite_value:{cid}:weights")
            return
        if abs(sum(float(w) for w in weights.values()) - 1.0) > 0.01:
            reasons.append(f"aggregate_weights_unnormalized:{cid}")
            return
        total = 0.0
        for component_id in components:
            component = claims_by_id.get(component_id)
            if component is None:
                return  # component_missing is reported by the closure walk
            component_value = component.get("displayed_value")
            if not is_finite_number(component_value):
                reasons.append(f"non_finite_value:{cid}:component:{component_id}")
                return
            total += float(weights[component_id]) * float(component_value)
        recomputed = total
    else:
        formula = claim.get("formula")
        inputs = claim.get("inputs")
        if not isinstance(formula, str) or not formula.strip() or not isinstance(inputs, dict) or not inputs:
            reasons.append(f"arithmetic_unverified:{cid}")
            return
        recomputed = safe_eval_formula(formula, inputs)
        if recomputed is None:
            reasons.append(f"formula_not_executable:{cid}")
            return
    if abs(float(displayed) - recomputed) > tol:
        reasons.append(f"arithmetic_mismatch:{cid}")


def check_revenue_drivers(claim: dict, reasons: list[str]) -> None:
    cid = claim.get("claim_id", "?")
    drivers = claim.get("revenue_drivers")
    if not isinstance(drivers, dict):
        reasons.append(f"revenue_drivers_missing:{cid}")
        return
    check_unknown_keys(drivers, REVENUE_DRIVER_KEYS, f"{cid}:revenue_drivers", reasons)
    for key in REVENUE_DRIVER_REQUIRED:
        if not is_finite_number(drivers.get(key)):
            reasons.append(f"revenue_driver_missing:{cid}:{key}")


def check_driver(driver: dict, claim_id: str, valid_targets: set[str], reasons: list[str]) -> bool:
    """Validate one cost driver. Returns True when the driver is open (TBD)."""
    check_unknown_keys(driver, DRIVER_KEYS, f"{claim_id}:driver", reasons)
    name = (driver.get("name") or "").strip()
    if not name:
        reasons.append(f"driver_unnamed:{claim_id}")
        return False
    disposition = driver.get("disposition")
    if disposition not in DISPOSITIONS:
        reasons.append(f"disposition_invalid:{claim_id}:{name}")
        return False
    if disposition == "TBD":
        return True
    if disposition == "amount" and not is_finite_number(driver.get("value")):
        reasons.append(f"amount_without_value:{claim_id}:{name}")
    if disposition == "included-in":
        target = (driver.get("included_in") or "").strip()
        if not target or target == name or target not in valid_targets:
            reasons.append(f"included_in_dangling:{claim_id}:{name}")
        if len((driver.get("allocation_basis") or "").strip()) < 15:
            reasons.append(f"included_in_without_allocation_basis:{claim_id}:{name}")
    if disposition == "not-applicable-with-evidence":
        evidence = (driver.get("evidence") or "").strip()
        if len(evidence) < 25 or not EVIDENCE_ANCHOR_RE.search(evidence):
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
    check_unknown_keys(ledger, LEDGER_KEYS, "ledger", reasons)

    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims or not all(isinstance(c, dict) for c in claims):
        reasons.append("no_claims_recorded")
        claims = [c for c in (claims or []) if isinstance(c, dict)]
    claims_by_id = {c.get("claim_id"): c for c in claims}

    # Referential targets an `included-in` may point at: other driver names,
    # claim ids, and formula input names — all within THIS ledger.
    valid_targets: set[str] = set()
    for claim in claims:
        valid_targets.update(k for k in (claim.get("inputs") or {}) if isinstance(k, str))
        if isinstance(claim.get("claim_id"), str):
            valid_targets.add(claim["claim_id"])
        for driver in claim.get("cost_drivers", []) or []:
            if isinstance(driver, dict) and isinstance(driver.get("name"), str):
                valid_targets.add(driver["name"].strip())

    open_tbd = 0
    for claim in claims:
        cid = claim.get("claim_id", "?")
        check_unknown_keys(claim, CLAIM_KEYS, str(cid), reasons)
        for field in REQUIRED_CLAIM_FIELDS:
            if not str(claim.get(field) or "").strip():
                reasons.append(f"missing_ledger_field:{cid}:{field}")
        if claim.get("metric") not in METRICS:
            reasons.append(f"metric_undefined:{cid}")
        check_claim_arithmetic(claim, claims_by_id, reasons)
        check_revenue_drivers(claim, reasons)
        seen_names: set[str] = set()
        for driver in claim.get("cost_drivers", []) or []:
            if not isinstance(driver, dict):
                reasons.append(f"driver_unnamed:{cid}")
                continue
            name = (driver.get("name") or "").strip()
            if name:
                if name in seen_names:
                    reasons.append(f"duplicate_cost_driver:{cid}:{name}")
                seen_names.add(name)
            if check_driver(driver, cid, valid_targets - {name}, reasons):
                open_tbd += 1
                reasons.append(f"tbd_open:{cid}:{name or '?'}")
        for component_id in claim.get("components", []) or []:
            component = claims_by_id.get(component_id)
            if component is None:
                reasons.append(f"component_missing:{cid}:{component_id}")
            elif claim_has_open_coverage(component):
                reasons.append(f"aggregate_incomplete_component:{cid}:{component_id}")

    # Fail-closed business-model registry.
    models_raw = ledger.get("business_model")
    if not isinstance(models_raw, list) or not models_raw or not all(isinstance(m, str) for m in models_raw):
        reasons.append("business_model_malformed")
        models: list[str] = []
    else:
        models = models_raw
        unknown_models = sorted(set(models) - KNOWN_MODELS)
        if unknown_models:
            reasons.append(f"business_model_unrecognized:{','.join(unknown_models)}")

    entailed_classes = {cls for model in models for cls in ENTAILMENTS.get(model, [])}
    dispositioned: set[str] = set()
    for claim in claims:
        for driver in claim.get("cost_drivers", []) or []:
            if isinstance(driver, dict) and driver.get("disposition") in DISPOSITIONS:
                for key in ("name", "entailed_class"):
                    if isinstance(driver.get(key), str):
                        dispositioned.add(driver[key].strip())
    for cls in sorted(entailed_classes):
        if cls not in dispositioned:
            reasons.append(f"entailed_cost_undispositioned:{cls}")

    # Recurring models need a feasible cohort schedule consistent with the
    # revenue drivers actually used.
    if any(model in RECURRING_MODELS for model in models):
        schedule = ledger.get("cohort_schedule")
        if not isinstance(schedule, dict) or not str(schedule.get("feasible_evidence") or "").strip():
            reasons.append("cohort_schedule_missing")
        else:
            check_unknown_keys(schedule, COHORT_KEYS, "cohort_schedule", reasons)
            churn = schedule.get("churn_monthly")
            active = schedule.get("active_months")
            if not (is_finite_number(churn) and is_finite_number(active)):
                reasons.append("cohort_schedule_missing")
            else:
                if churn > 0 and active > 1.5 * (1.0 / churn):
                    reasons.append("cohort_schedule_infeasible")
                for claim in claims:
                    claimed_active = (claim.get("revenue_drivers") or {}).get("active_months")
                    if is_finite_number(claimed_active) and float(claimed_active) > float(active):
                        reasons.append(f"cohort_inconsistent_active_months:{claim.get('claim_id', '?')}")

    declared = ledger.get("unresolved_count")
    if not isinstance(declared, int) or isinstance(declared, bool) or declared != open_tbd:
        reasons.append(f"unresolved_count_mismatch:declared={declared!r}:actual={open_tbd}")

    # Heterogeneous sign-off over the same immutable artifact.
    artifact = str(ledger.get("artifact_sha256") or "").strip()
    if not ARTIFACT_HASH_RE.match(artifact):
        reasons.append("artifact_hash_invalid")
    signoffs = [s for s in (ledger.get("signoffs") or []) if isinstance(s, dict)]
    for signoff in signoffs:
        check_unknown_keys(signoff, SIGNOFF_KEYS, f"signoff:{signoff.get('role', '?')}", reasons)
    roles = {s.get("role") for s in signoffs}
    reviewers = {s.get("reviewer") for s in signoffs if s.get("reviewer")}
    if roles < SIGNOFF_ROLES:
        reasons.append("signoff_roles_incomplete")
    elif len(reviewers) < 2:
        reasons.append("signoff_reviewers_not_distinct")
    for signoff in signoffs:
        if str(signoff.get("artifact_sha256") or "").strip() != artifact:
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
    pairs: dict[str, list[dict]] = {}
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
    # Every fail-closed bypass class must keep at least one RED fixture.
    required_red = {
        "business_model_malformed", "business_model_unrecognized", "included_in_dangling",
        "included_in_without_allocation_basis", "unsupported_not_applicable",
        "formula_not_executable", "non_finite_value", "duplicate_cost_driver",
        "artifact_hash_invalid", "schema_unknown_keys", "arithmetic_mismatch",
        "entailed_cost_undispositioned", "tbd_open", "aggregate_incomplete_component",
        "revenue_driver_missing",
    }
    covered_red = set()
    for case in cases:
        if case.get("expected") == "block":
            for reason in case.get("expected_reasons", []) or []:
                covered_red.add(reason.split(":", 1)[0])
    missing_red = required_red - covered_red
    if missing_red:
        failures.append(f"missing RED fixtures for bypass classes: {sorted(missing_red)}")
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
    print(f"finance completeness gate OK: {len(results)} case(s) match expected verdicts; "
          f"industry coverage, metamorphic flip, and per-bypass RED fixtures present")
    return 0


def _green_ledger() -> dict:
    return {
        "artifact_sha256": "sha256:" + "a" * 64,
        "business_model": ["partner_led_sales"],
        "unresolved_count": 0,
        "claims": [{
            "claim_id": "C1", "source": "p2:table1", "metric": "gross_margin",
            "period": "FY1", "currency": "USD", "unit": "ratio", "tax_basis": "excl",
            "displayed_value": 0.60, "formula": "(rev-cogs-fee)/rev",
            "inputs": {"rev": 100.0, "cogs": 25.0, "fee": 15.0},
            "rounding_rule": "2dp",
            "revenue_drivers": {"price": 10.0, "volume": 10, "start_month": 1, "active_months": 12},
            "cost_drivers": [{
                "name": "partner_fee", "entailed_class": "channel_economics",
                "disposition": "amount", "value": 15.0,
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

    def probe(name: str, mutate, expected_prefix: str) -> None:
        ledger = copy.deepcopy(_green_ledger())
        mutate(ledger)
        verdict, reasons = evaluate(ledger)
        check(name, verdict == "block" and any(r.startswith(expected_prefix) for r in reasons))

    verdict, reasons = evaluate(_green_ledger())
    check("green ledger passes", verdict == "pass" and not reasons)

    # add/remove metamorphic: strip the entailed disposition -> must flip to block.
    probe("removing the entailed disposition flips to block",
          lambda l: l["claims"][0].update(cost_drivers=[]), "entailed_cost_undispositioned")

    def set_tbd(l):
        l["claims"][0]["cost_drivers"][0] = {"name": "partner_fee", "entailed_class": "channel_economics", "disposition": "TBD"}
    probe("TBD blocks and demands unresolved_count sync", set_tbd, "tbd_open")

    def honest_tbd(l):
        set_tbd(l)
        l["unresolved_count"] = 1
    probe("TBD still blocks even when honestly counted (never an accepted zero)", honest_tbd, "tbd_open")

    # Hostile probes from PR #75 review (Codex MISA + MISA 3, 2026-07-16).
    probe("string business_model blocks (fail-open bypass)",
          lambda l: l.update(business_model="partner_led_sales"), "business_model_malformed")
    probe("unrecognized business model blocks",
          lambda l: l.update(business_model=["quantum_consulting"]), "business_model_unrecognized")

    def dangling_include(l):
        l["claims"][0]["cost_drivers"][0] = {
            "name": "partner_fee", "entailed_class": "channel_economics",
            "disposition": "included-in", "included_in": "somewhere_else",
            "allocation_basis": "absorbed in the delivery retainer line",
        }
    probe("included-in must reference an existing ledger line", dangling_include, "included_in_dangling")

    def include_no_basis(l):
        l["claims"][0]["cost_drivers"][0] = {
            "name": "partner_fee", "entailed_class": "channel_economics",
            "disposition": "included-in", "included_in": "cogs",
        }
    probe("included-in without an allocation basis blocks", include_no_basis, "included_in_without_allocation_basis")

    def long_uncited_na(l):
        l["claims"][0]["cost_drivers"][0] = {
            "name": "partner_fee", "entailed_class": "channel_economics",
            "disposition": "not-applicable-with-evidence",
            "evidence": "this is definitely not applicable because we say so at length",
        }
    probe("long but uncited n/a evidence blocks (anchor required)", long_uncited_na, "unsupported_not_applicable")

    probe("non-executable formula blocks (no self-asserted recomputation)",
          lambda l: l["claims"][0].update(formula="not a formula"), "formula_not_executable")
    probe("formula referencing a missing input blocks",
          lambda l: l["claims"][0].update(inputs={"rev": 100.0}), "formula_not_executable")
    probe("displayed value diverging from executed formula blocks",
          lambda l: l["claims"][0].update(displayed_value=0.99), "arithmetic_mismatch")
    probe("NaN displayed value blocks",
          lambda l: l["claims"][0].update(displayed_value=float("nan")), "non_finite_value")
    probe("NaN formula input blocks",
          lambda l: l["claims"][0]["inputs"].update(rev=float("inf")), "formula_not_executable")

    def duplicate_driver(l):
        l["claims"][0]["cost_drivers"].append(dict(l["claims"][0]["cost_drivers"][0]))
    probe("duplicate cost driver blocks", duplicate_driver, "duplicate_cost_driver")

    probe("missing revenue drivers block",
          lambda l: l["claims"][0].pop("revenue_drivers"), "revenue_drivers_missing")
    probe("invalid artifact hash blocks",
          lambda l: l.update(artifact_sha256="sha256:xyz"), "artifact_hash_invalid")
    probe("unknown schema key blocks (typo cannot weaken a rule)",
          lambda l: l["claims"][0].update(dispositon_notes="oops"), "schema_unknown_keys")

    def same_reviewer(l):
        for signoff in l["signoffs"]:
            signoff["reviewer"] = "r1"
    probe("homogeneous reviewers rejected", same_reviewer, "signoff_reviewers_not_distinct")

    def stale_signoff(l):
        l["signoffs"][1]["artifact_sha256"] = "sha256:" + "b" * 64
    probe("changed artifact invalidates sign-off", stale_signoff, "signoff_stale_artifact")

    if failures:
        print("finance completeness selftest FAILED.")
        return 1
    print("finance completeness selftest passed (green->pass; hostile probes from PR #75 review all block: "
          "fail-open model, dangling/basis-less included-in, uncited n/a, non-executable/self-asserted "
          "arithmetic, NaN, duplicates, schema drift, stale sign-off).")
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
