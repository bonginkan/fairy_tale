#!/usr/bin/env python3
"""Fail-closed checker for the Finance Proposal Completeness Gate (#74).

Validates finance claim-ledger records against the gate contract in
`skills/fairy-tale/references/cards/finance-proposal-completeness-gate.md`.
The teeth (all fail-closed — nothing is trusted from self-attestation):

  - strict schema that EXPRESSES the #74 contract: unknown keys anywhere
    block, while every record field #74 requires (metric definition, period/
    currency/unit/tax basis, displayed value, formula + inputs, revenue
    drivers, cost dispositions, assumptions, evidence status, sensitivity,
    cross-claim dependencies, unresolved counts, sign-offs) is REQUIRED.
    `business_model` must be a list drawn from a CLOSED registry.
  - deterministic, ledger-bound arithmetic: each formula is re-executed over
    its stated `inputs` (restricted AST evaluator), and every input key must
    be BOUND to the ledger via `input_bindings` — a cost-driver name, a
    revenue-driver key, an arithmetic expression over those, or a declared
    `assumption:<id>` — with numeric bindings reconciled to the input value.
    A recorded `recomputed_value` is allowed but must equal the checker's own
    execution. Constant formulas, unused-but-non-finite inputs, and margins
    outside plausible range block.
  - unit-economics assumption closure: the stated business model entails cost
    rows; recurring models need a complete cohort schedule (conversion,
    churn, active months, feasibility evidence) numerically consistent with
    the claims' revenue drivers.
  - disposition teeth: `TBD` blocks and must reconcile with unresolved_count;
    `included-in` needs an existing in-ledger target, a substantive
    allocation basis, a locator-anchored `source`, and a period matching the
    claim; `not-applicable-with-evidence` needs an identifier-bearing anchor.
  - sign-off teeth: malformed entries, unknown roles, a required role whose
    reviewer is missing, homogeneous reviewers, and stale artifact hashes all
    block; an extra role can never substitute for a required one.
  - refutable coverage: `REASON_CLASSES` is the checker-side canonical list
    of every emittable block reason; the case runner enforces that the
    acceptance fixtures plus the selftest probes cover ALL classes, so the
    fixture set can never quietly validate a shrunken contract.

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
MARGIN_METRICS = {"gross_margin", "contribution_margin"}
EVIDENCE_STATUSES = {"cited", "assumed", "mixed"}
REQUIRED_CLAIM_FIELDS = ("claim_id", "source", "metric", "period", "currency", "unit", "tax_basis")
REQUIRED_CONTEXT_FIELDS = ("assumptions", "evidence_status", "sensitivity", "depends_on")
SIGNOFF_ROLES = {"arithmetic_reconciliation", "completeness_negative_space"}
ARTIFACT_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# A citable anchor must carry an identifier, not a bare word: "p4", "§2",
# "appendix B", "page 12", "clause 4", "schedule A", a URL, or a cell ref.
EVIDENCE_ANCHOR_RE = re.compile(
    r"(p\.?\s?\d+|§\s?\d+|\bappendix\s+[A-Z0-9]|\bpage\s+\d+|\bclause\s+\d+|\bschedule\s+[A-Z0-9]"
    r"|https?://\S+|\bcell\s?[A-Z]+\d+)",
    re.IGNORECASE,
)

LEDGER_KEYS = {
    "artifact_sha256", "business_model", "unresolved_count", "claims",
    "cohort_schedule", "signoffs", "blockers", "uncertainties",
}
CLAIM_KEYS = {
    "claim_id", "source", "metric", "period", "currency", "unit", "tax_basis",
    "displayed_value", "formula", "inputs", "input_bindings", "recomputed_value",
    "rounding_rule", "revenue_drivers", "cost_drivers", "assumptions",
    "evidence_status", "sensitivity", "depends_on", "components", "weights",
}
DRIVER_KEYS = {"name", "entailed_class", "disposition", "value", "included_in", "allocation_basis", "source", "period", "evidence"}
SIGNOFF_KEYS = {"role", "reviewer", "artifact_sha256"}
COHORT_REQUIRED = ("conversion", "churn_monthly", "active_months")
COHORT_KEYS = set(COHORT_REQUIRED) | {"feasible_evidence"}
REVENUE_DRIVER_REQUIRED = ("price", "volume", "start_month", "active_months")
REVENUE_DRIVER_KEYS = set(REVENUE_DRIVER_REQUIRED) | {"conversion", "churn_monthly", "setup_fee"}

# Business model -> structurally entailed cost-driver classes. Model names are
# generic (no org-specific vocabulary). The registry is CLOSED and fail-closed.
ENTAILMENTS = {
    "partner_led_sales": ["channel_economics"],
    "channel_sales": ["channel_economics"],
    "implementation_service": ["setup_onboarding", "support", "security", "incident_response"],
    "managed_service": ["setup_onboarding", "support", "security", "incident_response"],
    "self_serve_saas": ["onboarding_applicability"],
}
RECURRING_MODELS = {"self_serve_saas", "managed_service", "subscription", "marketplace_recurring"}
KNOWN_MODELS = set(ENTAILMENTS) | RECURRING_MODELS | {
    "direct_sales", "marketplace_take_rate", "hardware_sales", "one_time_license",
}

# Canonical list of every block-reason class this checker can emit. The case
# runner requires fixtures + selftest probes to cover ALL of these — coverage
# is judged against THIS list, never against what the fixtures self-declare.
REASON_CLASSES = (
    "ledger_not_object", "schema_unknown_keys", "no_claims_recorded",
    "duplicate_claim_id", "missing_ledger_field", "metric_undefined",
    "claim_context_missing", "assumption_malformed", "evidence_status_invalid",
    "depends_on_dangling", "non_finite_value", "rounding_rule_missing",
    "aggregate_weights_missing", "aggregate_weights_unnormalized",
    "arithmetic_unverified", "formula_not_executable", "formula_constant",
    "formula_underspecified", "formula_input_unbound", "formula_input_mismatch",
    "assumption_missing", "recomputed_value_inconsistent", "arithmetic_mismatch",
    "margin_out_of_range", "revenue_drivers_missing", "revenue_driver_missing",
    "driver_unnamed", "disposition_invalid", "amount_without_value",
    "included_in_dangling", "included_in_without_allocation_basis",
    "included_in_without_source", "included_in_period_mismatch",
    "unsupported_not_applicable", "tbd_open", "duplicate_cost_driver",
    "component_missing", "aggregate_incomplete_component",
    "business_model_malformed", "business_model_unrecognized",
    "entailed_cost_undispositioned", "cohort_schedule_missing",
    "cohort_schedule_infeasible", "cohort_inconsistent_active_months",
    "cohort_inconsistent_conversion", "cohort_inconsistent_churn",
    "unresolved_count_mismatch", "artifact_hash_invalid", "signoff_malformed",
    "signoff_role_unknown", "signoff_reviewer_missing", "signoff_roles_incomplete",
    "signoff_reviewers_not_distinct", "signoff_stale_artifact",
)

# Classes exercised by the built-in selftest probes (the case runner unions
# these with fixture-declared expected reasons when judging coverage; both the
# selftest and the case run execute in CI, so the union is honest).
SELFTEST_COVERED = {
    "ledger_not_object", "no_claims_recorded", "duplicate_claim_id",
    "missing_ledger_field", "metric_undefined", "claim_context_missing",
    "assumption_malformed", "evidence_status_invalid", "depends_on_dangling",
    "rounding_rule_missing", "aggregate_weights_missing",
    "aggregate_weights_unnormalized", "arithmetic_unverified",
    "formula_constant", "formula_underspecified", "formula_input_unbound",
    "formula_input_mismatch", "assumption_missing",
    "recomputed_value_inconsistent", "margin_out_of_range",
    "revenue_drivers_missing", "revenue_driver_missing", "driver_unnamed",
    "disposition_invalid", "amount_without_value", "included_in_without_source",
    "included_in_period_mismatch", "component_missing",
    "cohort_schedule_infeasible", "cohort_inconsistent_active_months",
    "cohort_inconsistent_conversion", "cohort_inconsistent_churn",
    "unresolved_count_mismatch", "signoff_malformed", "signoff_role_unknown",
    "signoff_reviewer_missing", "signoff_roles_incomplete",
    "signoff_reviewers_not_distinct", "signoff_stale_artifact",
    "non_finite_value", "formula_not_executable", "schema_unknown_keys",
    "business_model_malformed", "business_model_unrecognized",
    "entailed_cost_undispositioned", "tbd_open", "duplicate_cost_driver",
    "included_in_dangling", "included_in_without_allocation_basis",
    "unsupported_not_applicable", "artifact_hash_invalid", "arithmetic_mismatch",
    "cohort_schedule_missing",
}


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def formula_names(formula: str) -> set[str] | None:
    try:
        tree = ast.parse(formula, mode="eval")
    except (SyntaxError, ValueError):
        return None
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def safe_eval_formula(formula: str, inputs: dict) -> float | None:
    """Deterministically evaluate an arithmetic expression over `inputs`.

    Only +, -, *, /, unary +/-, parentheses, numeric literals, and input names
    are allowed. Any parse error, unknown name, non-finite operand, or
    non-finite result returns None (the caller blocks)."""
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


def has_anchor(text: object) -> bool:
    return isinstance(text, str) and len(text.strip()) >= 25 and bool(EVIDENCE_ANCHOR_RE.search(text))


def check_unknown_keys(obj: dict, allowed: set[str], where: str, reasons: list[str]) -> None:
    unknown = sorted(set(obj) - allowed)
    if unknown:
        reasons.append(f"schema_unknown_keys:{where}:{','.join(unknown)}")


def binding_namespace(claim: dict) -> dict[str, float]:
    namespace: dict[str, float] = {}
    for key, value in (claim.get("revenue_drivers") or {}).items():
        if is_finite_number(value):
            namespace[key] = float(value)
    for driver in claim.get("cost_drivers", []) or []:
        if isinstance(driver, dict) and driver.get("disposition") == "amount":
            name = (driver.get("name") or "").strip()
            if name and is_finite_number(driver.get("value")):
                namespace[name] = float(driver["value"])
    return namespace


def assumption_ids(claim: dict) -> set[str]:
    ids: set[str] = set()
    for entry in claim.get("assumptions") or []:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            ids.add(entry["id"])
    return ids


def check_claim_context(claim: dict, claim_ids: set[str], reasons: list[str]) -> None:
    cid = claim.get("claim_id", "?")
    for field in REQUIRED_CONTEXT_FIELDS:
        if field not in claim:
            reasons.append(f"claim_context_missing:{cid}:{field}")
    assumptions = claim.get("assumptions")
    if assumptions is not None:
        if not isinstance(assumptions, list):
            reasons.append(f"assumption_malformed:{cid}")
        else:
            for entry in assumptions:
                if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) \
                        or len(str(entry.get("text") or "").strip()) < 10:
                    reasons.append(f"assumption_malformed:{cid}")
                    break
    if "evidence_status" in claim and claim.get("evidence_status") not in EVIDENCE_STATUSES:
        reasons.append(f"evidence_status_invalid:{cid}")
    if "sensitivity" in claim and len(str(claim.get("sensitivity") or "").strip()) < 10:
        reasons.append(f"claim_context_missing:{cid}:sensitivity")
    depends = claim.get("depends_on")
    if depends is not None:
        if not isinstance(depends, list):
            reasons.append(f"claim_context_missing:{cid}:depends_on")
        else:
            for dep in depends:
                if dep not in claim_ids:
                    reasons.append(f"depends_on_dangling:{cid}:{dep}")


def check_claim_arithmetic(claim: dict, claims_by_id: dict, reasons: list[str]) -> None:
    cid = claim.get("claim_id", "?")
    displayed = claim.get("displayed_value")
    if not is_finite_number(displayed):
        reasons.append(f"non_finite_value:{cid}:displayed_value")
        return
    metric = claim.get("metric")
    if metric in MARGIN_METRICS and not (-10.0 <= float(displayed) <= 1.0):
        reasons.append(f"margin_out_of_range:{cid}")
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
        for key, value in inputs.items():
            if not is_finite_number(value):
                reasons.append(f"non_finite_value:{cid}:input:{key}")
                return
        names = formula_names(formula)
        if names is not None:
            if not names:
                reasons.append(f"formula_constant:{cid}")
                return
            if metric in MARGIN_METRICS and len(names) < 2:
                reasons.append(f"formula_underspecified:{cid}")
        recomputed = safe_eval_formula(formula, inputs)
        if recomputed is None:
            reasons.append(f"formula_not_executable:{cid}")
            return
        check_input_bindings(claim, inputs, reasons)
    recorded = claim.get("recomputed_value")
    if recorded is not None and (not is_finite_number(recorded) or abs(float(recorded) - recomputed) > tol):
        reasons.append(f"recomputed_value_inconsistent:{cid}")
    if abs(float(displayed) - recomputed) > tol:
        reasons.append(f"arithmetic_mismatch:{cid}")


def check_input_bindings(claim: dict, inputs: dict, reasons: list[str]) -> None:
    """Every formula input must be BOUND to the ledger: a cost-driver amount,
    a revenue-driver key, an expression over those, or a declared assumption.
    Numeric bindings must reconcile with the stated input value."""
    cid = claim.get("claim_id", "?")
    bindings = claim.get("input_bindings")
    if not isinstance(bindings, dict):
        for key in inputs:
            reasons.append(f"formula_input_unbound:{cid}:{key}")
        return
    namespace = binding_namespace(claim)
    declared_assumptions = assumption_ids(claim)
    for key, value in inputs.items():
        binding = bindings.get(key)
        if not isinstance(binding, str) or not binding.strip():
            reasons.append(f"formula_input_unbound:{cid}:{key}")
            continue
        binding = binding.strip()
        if binding.startswith("assumption:"):
            if binding.split(":", 1)[1] not in declared_assumptions:
                reasons.append(f"assumption_missing:{cid}:{key}")
            continue
        resolved = safe_eval_formula(binding, namespace)
        if resolved is None:
            reasons.append(f"formula_input_unbound:{cid}:{key}")
        elif not math.isclose(resolved, float(value), rel_tol=1e-6, abs_tol=1e-9):
            reasons.append(f"formula_input_mismatch:{cid}:{key}")


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


def check_driver(driver: dict, claim: dict, valid_targets: set[str], reasons: list[str]) -> bool:
    """Validate one cost driver. Returns True when the driver is open (TBD)."""
    claim_id = claim.get("claim_id", "?")
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
        if not has_anchor(driver.get("source")):
            reasons.append(f"included_in_without_source:{claim_id}:{name}")
        period = (driver.get("period") or "").strip()
        claim_period = str(claim.get("period") or "").strip()
        if not period or (claim_period and period != claim_period):
            reasons.append(f"included_in_period_mismatch:{claim_id}:{name}")
    if disposition == "not-applicable-with-evidence" and not has_anchor(driver.get("evidence")):
        reasons.append(f"unsupported_not_applicable:{claim_id}:{name}")
    return False


def claim_has_open_coverage(claim: dict) -> bool:
    return any((d.get("disposition") == "TBD") or (d.get("disposition") not in DISPOSITIONS)
               for d in claim.get("cost_drivers", []) or [] if isinstance(d, dict))


def evaluate(ledger: dict) -> tuple[str, list[str]]:
    """Return (verdict, reasons). Verdict is 'pass' or 'block'. Fail closed."""
    reasons: list[str] = []
    if not isinstance(ledger, dict):
        return "block", ["ledger_not_object"]
    check_unknown_keys(ledger, LEDGER_KEYS, "ledger", reasons)

    raw_claims = ledger.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims or not all(isinstance(c, dict) for c in raw_claims):
        reasons.append("no_claims_recorded")
    claims = [c for c in (raw_claims or []) if isinstance(c, dict)]
    claim_id_list = [c.get("claim_id") for c in claims]
    for cid in {c for c in claim_id_list if claim_id_list.count(c) > 1}:
        reasons.append(f"duplicate_claim_id:{cid}")
    claims_by_id = {c.get("claim_id"): c for c in claims}
    claim_ids = set(claims_by_id)

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
        check_claim_context(claim, claim_ids, reasons)
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
            if check_driver(driver, claim, valid_targets - {name}, reasons):
                open_tbd += 1
                reasons.append(f"tbd_open:{cid}:{name or '?'}")
        for component_id in claim.get("components", []) or []:
            component = claims_by_id.get(component_id)
            if component is None:
                reasons.append(f"component_missing:{cid}:{component_id}")
            elif claim_has_open_coverage(component):
                reasons.append(f"aggregate_incomplete_component:{cid}:{component_id}")

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

    if any(model in RECURRING_MODELS for model in models):
        schedule = ledger.get("cohort_schedule")
        if not isinstance(schedule, dict) or not str(schedule.get("feasible_evidence") or "").strip() \
                or not all(is_finite_number(schedule.get(key)) for key in COHORT_REQUIRED):
            reasons.append("cohort_schedule_missing")
        else:
            check_unknown_keys(schedule, COHORT_KEYS, "cohort_schedule", reasons)
            churn = float(schedule["churn_monthly"])
            active = float(schedule["active_months"])
            if churn > 0 and active > 1.5 * (1.0 / churn):
                reasons.append("cohort_schedule_infeasible")
            for claim in claims:
                drivers = claim.get("revenue_drivers") or {}
                cid = claim.get("claim_id", "?")
                claimed_active = drivers.get("active_months")
                if is_finite_number(claimed_active) and float(claimed_active) > active:
                    reasons.append(f"cohort_inconsistent_active_months:{cid}")
                for key, reason in (("conversion", "cohort_inconsistent_conversion"),
                                    ("churn_monthly", "cohort_inconsistent_churn")):
                    claimed = drivers.get(key)
                    if is_finite_number(claimed) and not math.isclose(
                            float(claimed), float(schedule[key]), rel_tol=1e-6, abs_tol=1e-9):
                        reasons.append(f"{reason}:{cid}")

    declared = ledger.get("unresolved_count")
    if not isinstance(declared, int) or isinstance(declared, bool) or declared != open_tbd:
        reasons.append(f"unresolved_count_mismatch:declared={declared!r}:actual={open_tbd}")

    artifact = str(ledger.get("artifact_sha256") or "").strip()
    if not ARTIFACT_HASH_RE.match(artifact):
        reasons.append("artifact_hash_invalid")
    raw_signoffs = ledger.get("signoffs") or []
    signoffs: list[dict] = []
    for entry in raw_signoffs if isinstance(raw_signoffs, list) else [raw_signoffs]:
        if not isinstance(entry, dict):
            reasons.append("signoff_malformed")
            continue
        check_unknown_keys(entry, SIGNOFF_KEYS, f"signoff:{entry.get('role', '?')}", reasons)
        if entry.get("role") not in SIGNOFF_ROLES:
            reasons.append(f"signoff_role_unknown:{entry.get('role', '?')}")
            continue
        signoffs.append(entry)
    reviewers_by_role: dict[str, set[str]] = {}
    for role in sorted(SIGNOFF_ROLES):
        entries = [s for s in signoffs if s.get("role") == role]
        if not entries:
            reasons.append("signoff_roles_incomplete")
            continue
        named = {str(s.get("reviewer") or "").strip() for s in entries} - {""}
        if not named:
            reasons.append(f"signoff_reviewer_missing:{role}")
        reviewers_by_role[role] = named
    role_sets = list(reviewers_by_role.values())
    if len(role_sets) == len(SIGNOFF_ROLES) and all(role_sets):
        if set.union(*role_sets) and len(set.union(*role_sets)) < 2:
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
    # Coverage is judged against the checker's canonical REASON_CLASSES list:
    # every emittable class needs a RED fixture or a selftest probe (both run
    # in CI). The fixture set can never quietly validate a shrunken contract.
    covered = set(SELFTEST_COVERED)
    for case in cases:
        if case.get("expected") == "block":
            for reason in case.get("expected_reasons", []) or []:
                covered.add(reason.split(":", 1)[0])
    unknown_declared = {
        reason.split(":", 1)[0]
        for case in cases for reason in (case.get("expected_reasons") or [])
    } - set(REASON_CLASSES)
    if unknown_declared:
        failures.append(f"fixtures declare unknown reason classes: {sorted(unknown_declared)}")
    missing_classes = set(REASON_CLASSES) - covered
    if missing_classes:
        failures.append(f"REASON_CLASSES without fixture/selftest coverage: {sorted(missing_classes)}")
    stale_selftest = SELFTEST_COVERED - set(REASON_CLASSES)
    if stale_selftest:
        failures.append(f"selftest claims coverage of unknown classes: {sorted(stale_selftest)}")
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
    print(f"finance completeness gate OK: {len(results)} case(s) match expected verdicts; industry coverage, "
          f"metamorphic flip, and full REASON_CLASSES coverage ({len(REASON_CLASSES)} classes) present")
    return 0


def _green_ledger() -> dict:
    hash_value = "sha256:" + "a" * 64
    return {
        "artifact_sha256": hash_value,
        "business_model": ["partner_led_sales"],
        "unresolved_count": 0,
        "claims": [{
            "claim_id": "C1", "source": "p2:table1", "metric": "gross_margin",
            "period": "FY1", "currency": "USD", "unit": "ratio", "tax_basis": "excl",
            "displayed_value": 0.60, "formula": "(rev-cogs-fee)/rev",
            "inputs": {"rev": 100.0, "cogs": 25.0, "fee": 15.0},
            "input_bindings": {"rev": "price*volume", "cogs": "assumption:a1", "fee": "partner_fee"},
            "rounding_rule": "2dp",
            "revenue_drivers": {"price": 10.0, "volume": 10, "start_month": 1, "active_months": 12},
            "assumptions": [{"id": "a1", "text": "COGS from supplier quote p2 line 4", "evidence_status": "cited"}],
            "evidence_status": "cited",
            "sensitivity": "margin moves 5pt per 10% COGS swing",
            "depends_on": [],
            "cost_drivers": [{
                "name": "partner_fee", "entailed_class": "channel_economics",
                "disposition": "amount", "value": 15.0,
            }],
        }],
        "signoffs": [
            {"role": "arithmetic_reconciliation", "reviewer": "r1", "artifact_sha256": hash_value},
            {"role": "completeness_negative_space", "reviewer": "r2", "artifact_sha256": hash_value},
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
    check("non-dict ledger blocks", evaluate("nope")[1] == ["ledger_not_object"])  # type: ignore[arg-type]

    probe("removing the entailed disposition flips to block",
          lambda l: l["claims"][0].update(cost_drivers=[]), "entailed_cost_undispositioned")

    def set_tbd(l):
        l["claims"][0]["cost_drivers"][0] = {"name": "partner_fee", "entailed_class": "channel_economics", "disposition": "TBD"}
        l["claims"][0]["input_bindings"]["fee"] = "assumption:a1"
    probe("TBD blocks and demands unresolved_count sync", set_tbd, "tbd_open")

    def honest_tbd(l):
        set_tbd(l)
        l["unresolved_count"] = 1
    probe("TBD still blocks even when honestly counted", honest_tbd, "tbd_open")

    # --- fix-1 probes (PR #75 round 1) ---
    probe("string business_model blocks", lambda l: l.update(business_model="partner_led_sales"), "business_model_malformed")
    probe("unrecognized business model blocks", lambda l: l.update(business_model=["quantum_consulting"]), "business_model_unrecognized")

    def dangling_include(l):
        l["claims"][0]["cost_drivers"][0] = {
            "name": "partner_fee", "entailed_class": "channel_economics",
            "disposition": "included-in", "included_in": "somewhere_else",
            "allocation_basis": "absorbed in the delivery retainer line",
            "source": "contract schedule B p3", "period": "FY1",
        }
        l["claims"][0]["input_bindings"]["fee"] = "assumption:a1"
    probe("included-in must reference an existing ledger line", dangling_include, "included_in_dangling")

    def include_no_basis(l):
        dangling_include(l)
        l["claims"][0]["cost_drivers"][0]["included_in"] = "cogs"
        l["claims"][0]["cost_drivers"][0].pop("allocation_basis")
    probe("included-in without an allocation basis blocks", include_no_basis, "included_in_without_allocation_basis")

    def long_uncited_na(l):
        l["claims"][0]["cost_drivers"][0] = {
            "name": "partner_fee", "entailed_class": "channel_economics",
            "disposition": "not-applicable-with-evidence",
            "evidence": "this is definitely not applicable because we say so at length",
        }
        l["claims"][0]["input_bindings"]["fee"] = "assumption:a1"
    probe("long but uncited n/a evidence blocks", long_uncited_na, "unsupported_not_applicable")

    probe("non-executable formula blocks", lambda l: l["claims"][0].update(formula="not a formula"), "formula_not_executable")
    probe("displayed value diverging from executed formula blocks",
          lambda l: l["claims"][0].update(displayed_value=0.75), "arithmetic_mismatch")
    probe("NaN displayed value blocks", lambda l: l["claims"][0].update(displayed_value=float("nan")), "non_finite_value")

    def duplicate_driver(l):
        l["claims"][0]["cost_drivers"].append(dict(l["claims"][0]["cost_drivers"][0]))
    probe("duplicate cost driver blocks", duplicate_driver, "duplicate_cost_driver")
    probe("missing revenue drivers block", lambda l: l["claims"][0].pop("revenue_drivers"), "revenue_drivers_missing")
    probe("partial revenue drivers block", lambda l: l["claims"][0]["revenue_drivers"].pop("volume"), "revenue_driver_missing")
    probe("invalid artifact hash blocks", lambda l: l.update(artifact_sha256="sha256:xyz"), "artifact_hash_invalid")
    probe("unknown schema key blocks", lambda l: l["claims"][0].update(dispositon_notes="oops"), "schema_unknown_keys")

    # --- fix-2 probes (PR #75 round 2: ledger-bound arithmetic + contract fields) ---
    probe("driver value diverging from bound formula input blocks",
          lambda l: l["claims"][0]["cost_drivers"][0].update(value=99.0), "formula_input_mismatch")
    probe("revenue-driver value diverging from bound input blocks",
          lambda l: l["claims"][0]["revenue_drivers"].update(price=999.0), "formula_input_mismatch")
    probe("unbound formula input blocks", lambda l: l["claims"][0]["input_bindings"].pop("cogs"), "formula_input_unbound")
    probe("binding to an undeclared assumption blocks",
          lambda l: l["claims"][0].update(assumptions=[]), "assumption_missing")
    probe("malformed assumption entries block",
          lambda l: l["claims"][0].update(assumptions=[{"id": "a1", "text": "short"}]), "assumption_malformed")
    probe("recorded recomputed_value must equal the checker's execution",
          lambda l: l["claims"][0].update(recomputed_value=0.99), "recomputed_value_inconsistent")
    probe("constant formula blocks", lambda l: l["claims"][0].update(formula="0.6", input_bindings={"rev": "price*volume", "cogs": "assumption:a1", "fee": "partner_fee"}), "formula_constant")

    def single_name_margin(l):
        l["claims"][0].update(formula="rev/rev" if False else "rev", displayed_value=100.0,
                              input_bindings={"rev": "price*volume", "cogs": "assumption:a1", "fee": "partner_fee"})
        l["claims"][0]["displayed_value"] = 1.0
        l["claims"][0]["formula"] = "rev*0+1"
    probe("margin formula referencing a single input blocks", single_name_margin, "formula_underspecified")
    probe("margin above 1 blocks", lambda l: l["claims"][0].update(displayed_value=42.0), "margin_out_of_range")
    probe("missing claim context blocks", lambda l: l["claims"][0].pop("sensitivity"), "claim_context_missing")
    probe("invalid evidence status blocks", lambda l: l["claims"][0].update(evidence_status="vibes"), "evidence_status_invalid")
    probe("dangling depends_on blocks", lambda l: l["claims"][0].update(depends_on=["C9"]), "depends_on_dangling")

    def dup_claim(l):
        l["claims"].append(copy.deepcopy(l["claims"][0]))
    probe("duplicate claim id blocks", dup_claim, "duplicate_claim_id")
    probe("missing metric blocks", lambda l: l["claims"][0].update(metric="alpha"), "metric_undefined")
    probe("missing required claim field blocks", lambda l: l["claims"][0].update(currency=""), "missing_ledger_field")
    probe("empty claims block", lambda l: l.update(claims=[]), "no_claims_recorded")
    probe("missing rounding rule blocks", lambda l: l["claims"][0].pop("rounding_rule"), "rounding_rule_missing")
    probe("formula without inputs blocks", lambda l: l["claims"][0].update(inputs={}), "arithmetic_unverified")
    probe("amount without a finite value blocks",
          lambda l: l["claims"][0]["cost_drivers"][0].pop("value"), "amount_without_value")
    probe("unnamed driver blocks", lambda l: l["claims"][0]["cost_drivers"].append({"disposition": "amount", "value": 1.0}), "driver_unnamed")
    probe("invalid disposition blocks",
          lambda l: l["claims"][0]["cost_drivers"][0].update(disposition="maybe"), "disposition_invalid")
    probe("unresolved count mismatch blocks", lambda l: l.update(unresolved_count=3), "unresolved_count_mismatch")

    def include_ok_then(mutator):
        def apply(l):
            l["claims"][0]["cost_drivers"][0] = {
                "name": "partner_fee", "entailed_class": "channel_economics",
                "disposition": "included-in", "included_in": "cogs",
                "allocation_basis": "fee absorbed into supplier COGS per agreement",
                "source": "contract schedule B p3", "period": "FY1",
            }
            l["claims"][0]["input_bindings"]["fee"] = "assumption:a1"
            mutator(l["claims"][0]["cost_drivers"][0])
        return apply
    probe("included-in without an anchored source blocks",
          include_ok_then(lambda d: d.update(source="the finance team said so during standup")), "included_in_without_source")
    probe("included-in period mismatch blocks",
          include_ok_then(lambda d: d.update(period="FY9")), "included_in_period_mismatch")

    def aggregate_base(l):
        l["claims"][0]["depends_on"] = []
        second = copy.deepcopy(l["claims"][0])
        second["claim_id"] = "C2"
        agg = {
            "claim_id": "C0", "source": "p9:agg", "metric": "gross_margin", "period": "FY1",
            "currency": "USD", "unit": "ratio", "tax_basis": "excl", "displayed_value": 0.60,
            "rounding_rule": "2dp", "components": ["C1", "C2"], "weights": {"C1": 0.5, "C2": 0.5},
            "revenue_drivers": {"price": 10.0, "volume": 20, "start_month": 1, "active_months": 12},
            "assumptions": [], "evidence_status": "cited",
            "sensitivity": "tracks component margins one-for-one", "depends_on": ["C1", "C2"],
        }
        l["claims"] = [agg, l["claims"][0], second]
    def missing_weights(l):
        aggregate_base(l)
        l["claims"][0].pop("weights")
    probe("aggregate without weights blocks", missing_weights, "aggregate_weights_missing")
    def bad_weights(l):
        aggregate_base(l)
        l["claims"][0]["weights"] = {"C1": 0.9, "C2": 0.9}
    probe("unnormalized aggregate weights block", bad_weights, "aggregate_weights_unnormalized")
    def ghost_component(l):
        aggregate_base(l)
        l["claims"][0]["components"] = ["C1", "C9"]
        l["claims"][0]["weights"] = {"C1": 0.5, "C9": 0.5}
        l["claims"][0]["depends_on"] = ["C1"]
    probe("missing component blocks", ghost_component, "component_missing")

    def recurring(l):
        l["business_model"] = ["subscription", "partner_led_sales"]
        l["cohort_schedule"] = {"conversion": 0.3, "churn_monthly": 0.05, "active_months": 12,
                                "feasible_evidence": "cohort table p7 supports 12 active months"}
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
    def infeasible(l):
        recurring(l)
        l["cohort_schedule"]["active_months"] = 90
        l["claims"][0]["revenue_drivers"]["active_months"] = 12
    probe("infeasible cohort schedule blocks", infeasible, "cohort_schedule_infeasible")
    def cohort_missing(l):
        recurring(l)
        l["cohort_schedule"].pop("conversion")
    probe("cohort schedule missing conversion blocks", cohort_missing, "cohort_schedule_missing")
    def active_months_drift(l):
        recurring(l)
        l["claims"][0]["revenue_drivers"]["active_months"] = 24
    probe("claim active months beyond schedule blocks", active_months_drift, "cohort_inconsistent_active_months")
    def conversion_drift(l):
        recurring(l)
        l["claims"][0]["revenue_drivers"]["conversion"] = 0.9
    probe("claim conversion diverging from cohort blocks", conversion_drift, "cohort_inconsistent_conversion")
    def churn_drift(l):
        recurring(l)
        l["claims"][0]["revenue_drivers"]["churn_monthly"] = 0.001
    probe("claim churn diverging from cohort blocks", churn_drift, "cohort_inconsistent_churn")

    probe("malformed sign-off entry blocks", lambda l: l["signoffs"].append("i approve"), "signoff_malformed")
    probe("unknown sign-off role blocks",
          lambda l: l["signoffs"].append({"role": "vibes_reviewer", "reviewer": "r3", "artifact_sha256": l["artifact_sha256"]}),
          "signoff_role_unknown")

    def role_without_reviewer(l):
        l["signoffs"][1]["reviewer"] = ""
        l["signoffs"].append({"role": "arithmetic_reconciliation", "reviewer": "r3", "artifact_sha256": l["artifact_sha256"]})
    probe("required role with no named reviewer blocks (extra role cannot substitute)",
          role_without_reviewer, "signoff_reviewer_missing")
    probe("missing required role blocks", lambda l: l.update(signoffs=[l["signoffs"][0]]), "signoff_roles_incomplete")

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
    print(f"finance completeness selftest passed ({len(SELFTEST_COVERED)} reason classes probed; "
          "green->pass; every PR #75 round-1/round-2 hostile probe blocks).")
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
