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
import unicodedata
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
    "observed_frame", "central_claim_inventory", "artifact_verdict",
    "materiality_threshold", "minimum_closure_conditions", "cross_page_conflicts",
    "segments", "revenue_streams",
}
SEGMENT_KEYS = {"name", "source"}
STREAM_KEYS = {"id", "description", "source"}
CONFLICT_KEYS = {"id", "claim_ids", "description", "resolution"}
INVENTORY_KEYS = {"count", "claim_ids", "enumeration_basis"}
MATERIALITY_KEYS = {"value", "unit", "basis"}
# Closed unit registry with DEFAULT CAPS (#74 defaults: 5 margin points,
# relative 10% of revenue): a self-set "1000 bananas" threshold can never
# launder material uncertainty; a task-supplied STRICTER (smaller) threshold
# is always accepted. (Round-9 fix: round 8 wrongly relaxed margin_pt to 10.)
MATERIALITY_UNIT_CAPS = {"margin_pt": 5.0, "revenue_pct": 10.0}
CLOSURE_CONDITION_KEYS = {"id", "text", "satisfied"}
CLAIM_KEYS = {
    "claim_id", "source", "metric", "period", "currency", "unit", "tax_basis",
    "segment", "displayed_value", "formula", "inputs", "input_bindings",
    "recomputed_value", "rounding_rule", "revenue_drivers", "cost_drivers",
    "assumptions", "evidence_status", "sensitivity", "depends_on",
    "components", "weights", "stream_ids",
}
DRIVER_KEYS = {"name", "entailed_class", "disposition", "value", "basis", "included_in", "allocation_basis", "covered_scope", "source", "period", "evidence"}
ASSUMPTION_KEYS = {"id", "text", "evidence_status", "value"}
UNCERTAINTY_KEYS = {"id", "text", "impact_value", "impact_unit", "evidence", "decision_reversing"}
SIGNOFF_KEYS = {"role", "reviewer", "artifact_sha256", "verdict", "coverage"}
# Verdict enum synced to the issue #74 contract (canonical uppercase).
SIGNOFF_VERDICTS = {"PASS", "PASS_WITH_WARNINGS", "BLOCK"}
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
    # fix-3 (PR #75 round 3): ledger-anchored assumptions, consumed costs,
    # cohort math, and the remaining #74 required record fields.
    "assumption_value_missing", "assumption_value_mismatch", "cost_driver_unbound",
    "cohort_math_missing", "recomputed_value_missing", "signoff_verdict_missing",
    "signoff_blocked", "signoff_coverage_incomplete", "closure_state_missing",
    "blockers_not_recorded", "blockers_open", "unit_metric_mismatch",
    "margin_formula_shape", "cohort_domain_invalid", "revenue_driver_domain_invalid",
    # fix-4 (PR #75 round 4): the binding space is CLOSED over the executed
    # formula, margins keep revenue shape, and claim sources are locators.
    "formula_input_unused", "binding_unused", "margin_numerator_shape",
    "margin_denominator_not_revenue", "source_not_locator",
    "assumption_unused", "amount_without_source", "amount_period_mismatch",
    "included_in_without_scope", "included_in_host_unresolved",
    "uncertainty_malformed", "uncertainty_unbounded", "uncertainty_decision_reversing",
    # fix-5 (PR #75 round 5): economic effect (not mere reference), acyclic
    # dependency graphs, and fully fail-closed nested records.
    "formula_input_ineffective", "cost_sign_inverted", "depends_on_cycle",
    "component_duplicate", "amount_without_basis",
    # fix-6 (PR #75 round 6): perturbation reaches the LEDGER anchors,
    # observed frame / inventory / artifact verdict are schema, impact bounds
    # are numeric with cumulative materiality.
    "anchor_ineffective", "observed_frame_missing", "inventory_mismatch",
    "artifact_verdict_missing", "artifact_verdict_blocked", "materiality_exceeded",
    "binding_mixed_roles", "aggregate_weight_domain", "component_period_mismatch",
    # fix-7 (PR #75 round 7): directional cohort/revenue anchors, aggregates
    # anchored to revenue shares and a shared basis, and no self-declared
    # thresholds/inventories/riders.
    "revenue_sign_inverted", "aggregate_weight_unanchored",
    "component_basis_mismatch", "materiality_threshold_unanchored",
    "cohort_factor_inverted", "closure_condition_unsatisfied",
    # fix-8 (PR #75 round 8): profit direction, executed-revenue weights,
    # recurring driver completeness, and the cross-page conflict contract.
    "cross_page_conflict_unrecorded", "cross_page_conflict_malformed",
    "cross_page_conflict_unresolved", "cohort_factor_duplicated",
    # fix-10 (PR #75 round 10): the same revenue stream may never be counted
    # twice inside one claim's formula.
    "duplicate_revenue_stream", "segment_undeclared",
    # fix-12 (PR #75 round 12): declared stream identity + exact scale contract.
    "stream_undeclared", "revenue_binding_scale_invalid",
)

# NOTE (PR #75 round 3): coverage of REASON_CLASSES is judged against the
# acceptance FIXTURES ONLY — a hand-maintained "the selftest covers X" set is
# itself self-attestation, so it was removed. The selftest remains a fast
# red/green control layer but proves nothing about coverage.


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def formula_names(formula: str) -> set[str] | None:
    try:
        tree = ast.parse(formula, mode="eval")
    except (SyntaxError, ValueError):
        return None
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def substituted_formula_tree(claim: dict) -> ast.AST | None:
    """The formula AST with each input Name replaced by its binding AST
    (assumption-bound inputs stay as leaves): the claim's full symbolic
    derivation from ledger anchors."""
    formula = claim.get("formula")
    if not isinstance(formula, str) or not formula.strip():
        return None
    try:
        tree = ast.parse(formula.strip(), mode="eval")
    except (SyntaxError, ValueError):
        return None
    bindings = claim.get("input_bindings") or {}

    class Substitute(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name):
            binding = bindings.get(node.id)
            if isinstance(binding, str) and not binding.strip().startswith("assumption:"):
                try:
                    return ast.parse(binding.strip(), mode="eval").body
                except (SyntaxError, ValueError):
                    return node
            return node

    return Substitute().visit(tree)


def factor_degrees(node: ast.AST, factor: str) -> set[int]:
    """Possible per-additive-term multiplicative degrees of `factor` in the
    subtree: Mult sums degrees, Div subtracts, Add/Sub unions terms. Degree
    > 1 in any term is compounding; < 0 is inverse semantics."""
    if isinstance(node, ast.Expression):
        return factor_degrees(node.body, factor)
    if isinstance(node, ast.BinOp):
        left, right = factor_degrees(node.left, factor), factor_degrees(node.right, factor)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return left | right
        if isinstance(node.op, ast.Mult):
            return {a + b for a in left for b in right}
        if isinstance(node.op, ast.Div):
            return {a - b for a in left for b in right}
        return left | right
    if isinstance(node, ast.UnaryOp):
        return factor_degrees(node.operand, factor)
    if isinstance(node, ast.Name):
        return {1 if node.id == factor else 0}
    return {0}


def canonical_identity(value: str) -> str:
    """One normalizer for every identity axis (registry, membership, conflict
    grouping): Unicode NFKC + whitespace collapse + casefold. Divergent
    normalizers are how identities leak (PR #75 round 13)."""
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def constant_expr_value(node: ast.AST) -> float | None:
    """Evaluate a finite, name-free arithmetic subtree for canonicalization."""
    if isinstance(node, ast.Expression):
        return constant_expr_value(node.body)
    if isinstance(node, ast.Constant) and is_finite_number(node.value):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = constant_expr_value(node.operand)
        if value is None:
            return None
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = constant_expr_value(node.left)
        right = constant_expr_value(node.right)
        if left is None or right is None:
            return None
        try:
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            else:
                result = left / right
        except ZeroDivisionError:
            return None
        return result if math.isfinite(result) else None
    return None


def canonical_number(value: float) -> str:
    rounded = round(float(value), 12)
    if rounded == 0:
        rounded = 0.0
    if rounded.is_integer():
        return str(int(rounded))
    return repr(rounded)


def canonical_multiplicative_expr(node: ast.AST) -> str:
    """Normalize multiplication and division into one coefficient/factor form.

    Constants are accumulated through both operators, so economically equal
    shares such as ``x * 0.5``, ``x / 2``, and ``x * 100 / 200`` cannot mint
    different declared streams. Symbolic numerator and denominator factors
    remain explicit; this is normalization, not cancellation.
    """
    def parts(current: ast.AST) -> tuple[float, list[str], list[str]] | None:
        value = constant_expr_value(current)
        if value is not None:
            return value, [], []
        if isinstance(current, ast.UnaryOp) and isinstance(current.op, (ast.UAdd, ast.USub)):
            resolved = parts(current.operand)
            if resolved is None:
                return None
            coefficient, numerator, denominator = resolved
            return (-coefficient if isinstance(current.op, ast.USub) else coefficient,
                    numerator, denominator)
        if isinstance(current, ast.BinOp) and isinstance(current.op, (ast.Mult, ast.Div)):
            left = parts(current.left)
            right = parts(current.right)
            if left is None or right is None:
                return None
            left_coefficient, left_numerator, left_denominator = left
            right_coefficient, right_numerator, right_denominator = right
            if isinstance(current.op, ast.Mult):
                return (left_coefficient * right_coefficient,
                        left_numerator + right_numerator,
                        left_denominator + right_denominator)
            if abs(right_coefficient) <= 1e-15:
                return None
            return (left_coefficient / right_coefficient,
                    left_numerator + right_denominator,
                    left_denominator + right_numerator)
        return 1.0, [canonical_expr(current)], []

    resolved = parts(node)
    if resolved is None:
        return ast.dump(node)
    coefficient, numerator, denominator = resolved
    if abs(coefficient) <= 1e-12:
        return "0"
    if abs(coefficient - 1.0) > 1e-12 or not numerator:
        numerator.append(canonical_number(coefficient))
    numerator = sorted(numerator)
    denominator = sorted(denominator)
    numerator_text = numerator[0] if len(numerator) == 1 else "(" + "*".join(numerator) + ")"
    if not denominator:
        return numerator_text
    denominator_text = denominator[0] if len(denominator) == 1 else "(" + "*".join(denominator) + ")"
    return f"({numerator_text}/{denominator_text})"


def canonical_expr(node: ast.AST) -> str:
    """Order-independent canonical form: commutative chains sort their
    operands, so `price*volume` and `volume*price` are the SAME expression.
    Finite constant subtrees and arithmetic identity elements are folded, so
    syntactic padding (`*1`, `/1`, `+0`, `-0`) cannot mint a new stream."""
    if isinstance(node, ast.Expression):
        return canonical_expr(node.body)
    constant_value = constant_expr_value(node)
    if constant_value is not None:
        return canonical_number(constant_value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        return canonical_multiplicative_expr(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
        return canonical_multiplicative_expr(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        op_type = type(node.op)
        raw_operands: list[ast.AST] = []
        def collect(n: ast.AST) -> None:
            if isinstance(n, ast.BinOp) and isinstance(n.op, op_type):
                collect(n.left)
                collect(n.right)
            else:
                raw_operands.append(n)
        collect(node)
        # Fold constants so neutral elements can never mint a "different"
        # expression: price+0 IS price (round 13).
        constant_sum = 0.0
        operands: list[str] = []
        for operand in raw_operands:
            value = constant_expr_value(operand)
            if value is not None:
                constant_sum += value
            else:
                operands.append(canonical_expr(operand))
        if abs(constant_sum) > 1e-12:
            operands.append(canonical_number(constant_sum))
        if len(operands) == 1:
            return operands[0]
        return "(" + "+".join(sorted(operands)) + ")"
    if isinstance(node, ast.BinOp):
        right_value = constant_expr_value(node.right)
        if isinstance(node.op, ast.Sub) and right_value is not None and abs(right_value) <= 1e-12:
            return canonical_expr(node.left)
        if isinstance(node.op, ast.Div) and right_value is not None and abs(right_value - 1.0) <= 1e-12:
            return canonical_expr(node.left)
        symbol = "-" if isinstance(node.op, ast.Sub) else "/"
        return f"({canonical_expr(node.left)}{symbol}{canonical_expr(node.right)})"
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.UAdd):
            return canonical_expr(node.operand)
        sign = "-" if isinstance(node.op, ast.USub) else "+"
        return f"({sign}{canonical_expr(node.operand)})"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return ast.dump(node)


def additive_term_scales(expression: str) -> list[float] | None:
    """Net constant multiplier of each top-level additive term (all anchors
    set to 1). Quantities come from anchors; constants only PARTITION a
    stream, so every term's scale must stay <= 1."""
    try:
        tree = ast.parse(expression, mode="eval").body
    except (SyntaxError, ValueError):
        return None
    terms: list[ast.AST] = []
    def split_terms(n: ast.AST) -> None:
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)):
            split_terms(n.left)
            split_terms(n.right)
        else:
            terms.append(n)
    split_terms(tree)
    scales: list[float] = []
    for term in terms:
        names = {n.id for n in ast.walk(term) if isinstance(n, ast.Name)}
        value = safe_eval_formula(ast.unparse(term), {name: 1.0 for name in names})
        if value is None:
            return None
        scales.append(abs(value))
    return scales


def divisor_names(formula: str) -> set[str]:
    """Names appearing anywhere inside a divisor position of the expression."""
    try:
        tree = ast.parse(formula, mode="eval")
    except (SyntaxError, ValueError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            found.update(n.id for n in ast.walk(node.right) if isinstance(n, ast.Name))
    return found


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


def is_locator(text: object) -> bool:
    """A claim source must be a locator (page/cell/section/URL), not a token."""
    return isinstance(text, str) and len(text.strip()) >= 5 and bool(EVIDENCE_ANCHOR_RE.search(text))


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
            seen_ids: set[str] = set()
            bound_ids = {
                b.strip().split(":", 1)[1]
                for b in (claim.get("input_bindings") or {}).values()
                if isinstance(b, str) and b.strip().startswith("assumption:")
            }
            for entry in assumptions:
                if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) \
                        or len(str(entry.get("text") or "").strip()) < 10:
                    reasons.append(f"assumption_malformed:{cid}")
                    break
                check_unknown_keys(entry, ASSUMPTION_KEYS, f"{cid}:assumption:{entry['id']}", reasons)
                if entry["id"] in seen_ids:
                    reasons.append(f"assumption_malformed:{cid}:duplicate:{entry['id']}")
                seen_ids.add(entry["id"])
                if entry.get("evidence_status") not in EVIDENCE_STATUSES:
                    reasons.append(f"evidence_status_invalid:{cid}:assumption:{entry['id']}")
                # Assumptions ARE the arithmetic contract: an entry no binding
                # consumes is unvalidated context posing as evidence.
                if entry["id"] not in bound_ids:
                    reasons.append(f"assumption_unused:{cid}:{entry['id']}")
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
    if metric in MARGIN_METRICS:
        if not (-10.0 <= float(displayed) <= 1.0):
            reasons.append(f"margin_out_of_range:{cid}")
        # A margin is a ratio over revenue: ratio unit, top-level quotient,
        # a revenue-bound denominator, and a numerator derived from it. Sign
        # conventions inside the numerator stay the arithmetic reviewer's
        # charge (verdict + coverage are required).
        if str(claim.get("unit") or "").strip().lower() != "ratio":
            reasons.append(f"unit_metric_mismatch:{cid}")
        formula = claim.get("formula")
        if isinstance(formula, str) and formula.strip():
            try:
                root = ast.parse(formula, mode="eval").body
            except (SyntaxError, ValueError):
                root = None  # formula_not_executable is reported downstream
            if root is not None:
                if not (isinstance(root, ast.BinOp) and isinstance(root.op, ast.Div)
                        and isinstance(root.right, ast.Name)):
                    reasons.append(f"margin_formula_shape:{cid}")
                else:
                    denominator = root.right.id
                    numerator_names = {n.id for n in ast.walk(root.left) if isinstance(n, ast.Name)}
                    if denominator not in numerator_names:
                        reasons.append(f"margin_numerator_shape:{cid}")
                    binding = (claim.get("input_bindings") or {}).get(denominator)
                    if not isinstance(binding, str) or binding.strip().startswith("assumption:") \
                            or not (formula_names(binding.strip()) or set()) \
                            or not (formula_names(binding.strip()) or set()) <= REVENUE_DRIVER_KEYS:
                        reasons.append(f"margin_denominator_not_revenue:{cid}")
    tol = rounding_tolerance(claim.get("rounding_rule"))
    if tol is None:
        reasons.append(f"rounding_rule_missing:{cid}")
        return
    components = claim.get("components")
    if components:
        aggregate_stream_ids = claim.get("stream_ids")
        if aggregate_stream_ids is not None:
            if not isinstance(aggregate_stream_ids, dict):
                reasons.append(f"stream_undeclared:{cid}:stream_ids_malformed")
            else:
                check_unknown_keys(aggregate_stream_ids, set(), f"{cid}:stream_ids", reasons)
        weights = claim.get("weights")
        if not isinstance(weights, dict) or set(weights) != set(components):
            reasons.append(f"aggregate_weights_missing:{cid}")
            return
        if not all(is_finite_number(w) for w in weights.values()):
            reasons.append(f"non_finite_value:{cid}:weights")
            return
        # A mix weight lives in (0, 1]: negative or zero weights let a pair
        # like 2.0/-1.0 "normalize" while inverting a component's sign.
        if any(not (0 < float(w) <= 1) for w in weights.values()):
            reasons.append(f"aggregate_weight_domain:{cid}")
            return
        if abs(sum(float(w) for w in weights.values()) - 1.0) > 0.01:
            reasons.append(f"aggregate_weights_unnormalized:{cid}")
            return
        total = 0.0
        component_revenues: dict[str, float] = {}
        component_streams: dict[str, list[str]] = {}
        for component_id in components:
            component = claims_by_id.get(component_id)
            if component is None:
                return  # component_missing is reported by the closure walk
            component_value = component.get("displayed_value")
            if not is_finite_number(component_value):
                reasons.append(f"non_finite_value:{cid}:component:{component_id}")
                return
            # Aggregating across periods launders a different period's margin
            # into this claim's basis; mixing metrics/currencies/tax bases
            # blends incomparable numbers.
            if str(component.get("period") or "").strip() != str(claim.get("period") or "").strip():
                reasons.append(f"component_period_mismatch:{cid}:{component_id}")
            for basis_field in ("metric", "currency", "unit", "tax_basis"):
                if str(component.get(basis_field) or "").strip() != str(claim.get(basis_field) or "").strip():
                    reasons.append(f"component_basis_mismatch:{cid}:{component_id}:{basis_field}")
            summary = resolved_revenue_summary(component, claims_by_id)
            if summary is None:
                # Never silently skip revenue anchoring for a nested or
                # malformed component. The component/graph checks report the
                # structural cause; this reason closes the weight gate.
                reasons.append(f"aggregate_weight_unanchored:{cid}:{component_id}:revenue_unresolved")
            else:
                component_revenues[component_id], component_streams[component_id] = summary
            total += float(weights[component_id]) * float(component_value)
        # The same declared leaf stream may never feed the aggregate twice,
        # including through nested component aggregates.
        stream_owners: dict[str, str] = {}
        for component_id in components:
            for stream_id in component_streams.get(component_id, []):
                if stream_id in stream_owners:
                    reasons.append(f"duplicate_revenue_stream:{cid}:{stream_id}")
                else:
                    stream_owners[stream_id] = component_id
        # Weights are ANCHORED to component revenue shares, never self-declared.
        if len(component_revenues) == len(components) and sum(component_revenues.values()) > 0:
            revenue_total = sum(component_revenues.values())
            for component_id, revenue in component_revenues.items():
                if abs(float(weights[component_id]) - revenue / revenue_total) > 0.01:
                    reasons.append(f"aggregate_weight_unanchored:{cid}:{component_id}")
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
            # The input space is CLOSED over the executed formula: an input
            # the formula never reads is a smuggling surface for fake
            # consumption/cohort bindings (PR #75 round 4).
            for key in sorted(set(inputs) - names):
                reasons.append(f"formula_input_unused:{cid}:{key}")
        recomputed = safe_eval_formula(formula, inputs)
        if recomputed is None:
            reasons.append(f"formula_not_executable:{cid}")
            return
        check_input_bindings(claim, inputs, reasons)
        check_cost_consumption(claim, reasons)
        check_economic_effect(claim, formula, inputs, recomputed, reasons)
        check_anchor_effect(claim, formula, reasons)
    if "recomputed_value" not in claim:
        reasons.append(f"recomputed_value_missing:{cid}")
    else:
        recorded = claim.get("recomputed_value")
        if not is_finite_number(recorded) or abs(float(recorded) - recomputed) > tol:
            reasons.append(f"recomputed_value_inconsistent:{cid}")
    if abs(float(displayed) - recomputed) > tol:
        reasons.append(f"arithmetic_mismatch:{cid}")


def binding_referenced_names(claim: dict) -> set[str]:
    """Names consumed by this claim's non-assumption binding expressions."""
    names: set[str] = set()
    for binding in (claim.get("input_bindings") or {}).values():
        if isinstance(binding, str) and not binding.strip().startswith("assumption:"):
            found = formula_names(binding.strip())
            if found:
                names.update(found)
    return names


def check_economic_effect(claim: dict, formula: str, inputs: dict, baseline: float, reasons: list[str]) -> None:
    """Reference is not effect (PR #75 round 5): a `*0` coefficient can name a
    factor without letting it move the result. Perturb each input and demand a
    response; on margin/profit claims, an input bound to an amount cost driver
    must move the result DOWN when the cost goes up."""
    cid = claim.get("claim_id", "?")
    metric = claim.get("metric")
    cost_driver_names = {
        (d.get("name") or "").strip()
        for d in claim.get("cost_drivers", []) or []
        if isinstance(d, dict) and d.get("disposition") == "amount"
    } - {""}
    bindings = claim.get("input_bindings") or {}
    for key, value in inputs.items():
        if not is_finite_number(value):
            return  # non_finite_value already reported
        perturbed_value = float(value) * 1.01 if float(value) != 0 else 0.01
        perturbed = safe_eval_formula(formula, {**inputs, key: perturbed_value})
        if perturbed is None:
            continue  # division-by-zero style edge; executability already gated
        if perturbed == baseline:  # exact: tiny real effects must not false-block
            reasons.append(f"formula_input_ineffective:{cid}:{key}")
            continue
        binding = bindings.get(key)
        if metric in (MARGIN_METRICS | {"operating_profit"}) and isinstance(binding, str) \
                and not binding.strip().startswith("assumption:"):
            binding_names = formula_names(binding.strip()) or set()
            if binding_names and binding_names <= cost_driver_names and perturbed > baseline + 1e-12:
                reasons.append(f"cost_sign_inverted:{cid}:{key}")


def resolve_from_anchors(claim: dict, formula: str, namespace: dict, assumption_values: dict) -> float | None:
    """Re-derive the inputs from bindings over a (possibly perturbed) anchor
    namespace, then execute the formula — the full ledger-to-result path."""
    derived: dict[str, float] = {}
    for key, binding in (claim.get("input_bindings") or {}).items():
        if not isinstance(binding, str) or not binding.strip():
            return None
        binding = binding.strip()
        if binding.startswith("assumption:"):
            value = assumption_values.get(binding.split(":", 1)[1])
            if value is None:
                return None
            derived[key] = value
        else:
            resolved = safe_eval_formula(binding, namespace)
            if resolved is None:
                return None
            derived[key] = resolved
    return safe_eval_formula(formula, derived)


def check_anchor_effect(claim: dict, formula: str, reasons: list[str]) -> None:
    """Perturbation must reach the LEDGER anchors (PR #75 round 6): hiding
    `*0` inside a binding expression leaves the formula input responsive
    while the recorded driver has zero economic effect. Perturb each anchor
    (amount drivers, revenue drivers, assumption values) end-to-end through
    bindings + formula; every referenced anchor must move the result, and a
    cost anchor on a margin/profit claim must move it DOWN."""
    cid = claim.get("claim_id", "?")
    metric = claim.get("metric")
    namespace = binding_namespace(claim)
    assumption_values = {
        entry["id"]: float(entry["value"])
        for entry in (claim.get("assumptions") or [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and is_finite_number(entry.get("value"))
    }
    baseline = resolve_from_anchors(claim, formula, namespace, assumption_values)
    if baseline is None:
        return  # binding/executability failures already reported
    cost_anchor_names = {
        (d.get("name") or "").strip()
        for d in claim.get("cost_drivers", []) or []
        if isinstance(d, dict) and d.get("disposition") == "amount"
    } - {""}
    referenced = binding_referenced_names(claim)
    bound_assumptions = {
        b.strip().split(":", 1)[1]
        for b in (claim.get("input_bindings") or {}).values()
        if isinstance(b, str) and b.strip().startswith("assumption:")
    }
    def perturb(value: float) -> float:
        return value * 1.01 if value != 0 else 0.01
    for anchor in sorted((set(namespace) & referenced) | (bound_assumptions & set(assumption_values))):
        if anchor in namespace:
            result = resolve_from_anchors(claim, formula, {**namespace, anchor: perturb(namespace[anchor])}, assumption_values)
        else:
            result = resolve_from_anchors(claim, formula, namespace,
                                          {**assumption_values, anchor: perturb(assumption_values[anchor])})
        if result is None:
            continue
        if result == baseline:  # exact: a tiny-but-real effect must not false-block
            reasons.append(f"anchor_ineffective:{cid}:{anchor}")
        elif anchor in cost_anchor_names and metric in (MARGIN_METRICS | {"operating_profit"}) \
                and result > baseline:
            reasons.append(f"cost_sign_inverted:{cid}:{anchor}")
        elif anchor in REVENUE_DRIVER_KEYS and metric in ("revenue", "forecast", "operating_profit") \
                and result < baseline:
            # More price/volume/conversion/months can never mean LESS revenue
            # or less operating profit: an inverse (divided or negated)
            # revenue term shows up here directionally.
            reasons.append(f"revenue_sign_inverted:{cid}:{anchor}")


def check_cost_consumption(claim: dict, reasons: list[str]) -> None:
    """On margin/profit claims, every amount cost driver must be consumed by
    the bound arithmetic — a recorded cost that never enters the math is a
    silent omission, not bookkeeping."""
    if claim.get("metric") not in (MARGIN_METRICS | {"operating_profit"}):
        return
    cid = claim.get("claim_id", "?")
    consumed = binding_referenced_names(claim)
    for driver in claim.get("cost_drivers", []) or []:
        if isinstance(driver, dict) and driver.get("disposition") == "amount":
            name = (driver.get("name") or "").strip()
            if name and name not in consumed:
                reasons.append(f"cost_driver_unbound:{cid}:{name}")


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
    assumptions_by_id = {
        entry["id"]: entry
        for entry in (claim.get("assumptions") or [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    # Bindings are closed over the inputs (which are closed over the formula):
    # a binding for a key the formula never consumes is a smuggling surface.
    for key in sorted(set(bindings) - set(inputs)):
        reasons.append(f"binding_unused:{cid}:{key}")
    # Stream identity is DECLARED, never inferred (round 12): every
    # revenue-role input maps to a distinct stream id from the ledger's
    # anchored registry via `stream_ids`. The only machine dedup contracts
    # are EXACT: identical canonical expression + identical value is the
    # same stream, and per-term constant scales must stay <= 1 (constants
    # PARTITION a stream — a 2x coefficient can never inflate an anchor).
    declared_streams = {
        entry["id"]
        for entry in (claim.get("_ledger_revenue_streams") or [])
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"].strip()
    }
    stream_ids = claim.get("stream_ids")
    if stream_ids is None:
        stream_ids = {}
    elif not isinstance(stream_ids, dict):
        # A truthy non-object must be a REASONED block, never an exception.
        reasons.append(f"stream_undeclared:{cid}:stream_ids_malformed")
        stream_ids = {}
    revenue_input_keys = {
        key
        for key, binding in bindings.items()
        if key in inputs and isinstance(binding, str) and not binding.strip().startswith("assumption:")
        and (formula_names(binding.strip()) or set())
        and (formula_names(binding.strip()) or set()) <= REVENUE_DRIVER_KEYS
    }
    check_unknown_keys(stream_ids, revenue_input_keys, f"{cid}:stream_ids", reasons)
    seen_stream_ids: dict[str, str] = {}
    seen_canonical: dict[tuple, str] = {}
    for key in sorted(inputs):
        binding = bindings.get(key)
        if not isinstance(binding, str) or binding.strip().startswith("assumption:"):
            continue
        names = formula_names(binding.strip()) or set()
        if names and names <= REVENUE_DRIVER_KEYS:
            scales = additive_term_scales(binding.strip())
            if scales is None or any(scale > 1 + 1e-9 for scale in scales):
                reasons.append(f"revenue_binding_scale_invalid:{cid}:{key}")
            stream_id = stream_ids.get(key)
            if not isinstance(stream_id, str) or not stream_id.strip() or stream_id not in declared_streams:
                reasons.append(f"stream_undeclared:{cid}:{key}")
            elif stream_id in seen_stream_ids:
                reasons.append(f"duplicate_revenue_stream:{cid}:{key}")
            else:
                seen_stream_ids[stream_id] = key
            if is_finite_number(inputs.get(key)):
                try:
                    canon = canonical_expr(ast.parse(binding.strip(), mode="eval"))
                except (SyntaxError, ValueError):
                    canon = binding.strip()
                exact = (canon, round(float(inputs[key]), 9))
                if exact in seen_canonical:
                    reasons.append(f"duplicate_revenue_stream:{cid}:{key}")
                else:
                    seen_canonical[exact] = key
    for key, value in inputs.items():
        binding = bindings.get(key)
        if not isinstance(binding, str) or not binding.strip():
            reasons.append(f"formula_input_unbound:{cid}:{key}")
            continue
        binding = binding.strip()
        if binding.startswith("assumption:"):
            entry = assumptions_by_id.get(binding.split(":", 1)[1])
            if entry is None:
                reasons.append(f"assumption_missing:{cid}:{key}")
            elif not is_finite_number(entry.get("value")):
                # An assumption feeding arithmetic must RECORD its number —
                # otherwise the input value is self-attested (PR #75 round 3).
                reasons.append(f"assumption_value_missing:{cid}:{key}")
            elif not math.isclose(float(entry["value"]), float(value), rel_tol=1e-6, abs_tol=1e-9):
                reasons.append(f"assumption_value_mismatch:{cid}:{key}")
            continue
        resolved = safe_eval_formula(binding, namespace)
        if resolved is None:
            reasons.append(f"formula_input_unbound:{cid}:{key}")
            continue
        if not math.isclose(resolved, float(value), rel_tol=1e-6, abs_tol=1e-9):
            reasons.append(f"formula_input_mismatch:{cid}:{key}")
        # One input never mixes revenue and cost anchors: the roles carry
        # opposite signs, so a mixed binding hides a cost inside revenue.
        binding_names = formula_names(binding) or set()
        cost_names = {
            (d.get("name") or "").strip()
            for d in claim.get("cost_drivers", []) or []
            if isinstance(d, dict) and (d.get("name") or "").strip()
        }
        if binding_names & REVENUE_DRIVER_KEYS and binding_names & cost_names:
            reasons.append(f"binding_mixed_roles:{cid}:{key}")


def executed_revenue(component: dict) -> float | None:
    """A component's ACTUAL revenue: the sum of its executed revenue-side
    input values (bindings referencing only revenue-driver keys — which
    includes setup fees and cohort factors), or the displayed value itself
    for revenue/forecast components. Never a bare price*volume shortcut."""
    if component.get("metric") in ("revenue", "forecast"):
        value = component.get("displayed_value")
        return float(value) if is_finite_number(value) else None
    total = 0.0
    found = False
    inputs = component.get("inputs") or {}
    stream_ids = component.get("stream_ids")
    if not isinstance(stream_ids, dict):
        stream_ids = {}
    seen_ids: set[str] = set()
    for key, binding in (component.get("input_bindings") or {}).items():
        if not isinstance(binding, str) or binding.strip().startswith("assumption:"):
            continue
        names = formula_names(binding.strip()) or set()
        if names and names <= REVENUE_DRIVER_KEYS and is_finite_number(inputs.get(key)):
            # One declared stream id counts once toward executed revenue
            # (round 12); undeclared/duplicate ids block at claim level.
            stream_id = stream_ids.get(key)
            if isinstance(stream_id, str):
                if stream_id in seen_ids:
                    continue
                seen_ids.add(stream_id)
            total += float(inputs[key])
            found = True
    return total if found else None


def direct_revenue_stream_ids(component: dict) -> list[str]:
    """Declared stream ids for executed revenue-role inputs on one leaf claim."""
    inputs = component.get("inputs") or {}
    stream_ids = component.get("stream_ids")
    if not isinstance(stream_ids, dict):
        return []
    result: list[str] = []
    for key, binding in (component.get("input_bindings") or {}).items():
        if not isinstance(binding, str) or binding.strip().startswith("assumption:"):
            continue
        names = formula_names(binding.strip()) or set()
        stream_id = stream_ids.get(key)
        if names and names <= REVENUE_DRIVER_KEYS and is_finite_number(inputs.get(key)) \
                and isinstance(stream_id, str) and stream_id.strip():
            result.append(stream_id)
    return result


def resolved_revenue_summary(component: dict, claims_by_id: dict,
                             visiting: set[str] | None = None) -> tuple[float, list[str]] | None:
    """Resolve revenue and leaf stream ids through an aggregate component DAG."""
    components = component.get("components") or []
    if not components:
        revenue = executed_revenue(component)
        return (revenue, direct_revenue_stream_ids(component)) if revenue is not None else None

    cid = component.get("claim_id")
    active = set(visiting or ())
    if not isinstance(cid, str) or cid in active:
        return None
    active.add(cid)
    total = 0.0
    streams: list[str] = []
    for component_id in components:
        child = claims_by_id.get(component_id)
        if child is None:
            return None
        summary = resolved_revenue_summary(child, claims_by_id, active)
        if summary is None:
            return None
        child_revenue, child_streams = summary
        total += child_revenue
        streams.extend(child_streams)
    return total, streams


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
    for key, value in drivers.items():
        if not is_finite_number(value):
            continue  # missing/malformed handled above or by schema
        value = float(value)
        if key in ("price", "volume", "active_months") and value <= 0:
            reasons.append(f"revenue_driver_domain_invalid:{cid}:{key}")
        if key == "start_month" and value < 1:
            reasons.append(f"revenue_driver_domain_invalid:{cid}:{key}")
        if key == "conversion" and not (0 < value <= 1):
            reasons.append(f"revenue_driver_domain_invalid:{cid}:{key}")
        if key == "churn_monthly" and not (0 <= value < 1):
            reasons.append(f"revenue_driver_domain_invalid:{cid}:{key}")


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
    claim_period = str(claim.get("period") or "").strip()
    if disposition == "amount":
        if not is_finite_number(driver.get("value")):
            reasons.append(f"amount_without_value:{claim_id}:{name}")
        # An amount is a number ON A STATED BASIS: an explicit basis record
        # (per-unit/monthly/percent-of-revenue, tax treatment), its own
        # anchored source, and the claim's period.
        if len((driver.get("basis") or "").strip()) < 10:
            reasons.append(f"amount_without_basis:{claim_id}:{name}")
        if not has_anchor(driver.get("source")) and not is_locator(driver.get("source")):
            reasons.append(f"amount_without_source:{claim_id}:{name}")
        period = (driver.get("period") or "").strip()
        if not period or (claim_period and period != claim_period):
            reasons.append(f"amount_period_mismatch:{claim_id}:{name}")
    if disposition == "included-in":
        target = (driver.get("included_in") or "").strip()
        if not target or target == name or target not in valid_targets:
            reasons.append(f"included_in_dangling:{claim_id}:{name}")
        else:
            # When the host is another cost driver, that host must itself be
            # a resolved amount — absorbing into an unresolved line is a
            # laundering path for TBD.
            host = next((d for d in claim.get("cost_drivers", []) or []
                         if isinstance(d, dict) and (d.get("name") or "").strip() == target), None)
            if host is not None and not (host.get("disposition") == "amount" and is_finite_number(host.get("value"))):
                reasons.append(f"included_in_host_unresolved:{claim_id}:{name}")
        # Issue #74: an included-in carries its absorbed AMOUNT or an
        # allocation basis — either anchors the absorption; neither blocks.
        if not is_finite_number(driver.get("value")) and len((driver.get("allocation_basis") or "").strip()) < 15:
            reasons.append(f"included_in_without_allocation_basis:{claim_id}:{name}")
        if len((driver.get("covered_scope") or "").strip()) < 10:
            reasons.append(f"included_in_without_scope:{claim_id}:{name}")
        if not has_anchor(driver.get("source")):
            reasons.append(f"included_in_without_source:{claim_id}:{name}")
        period = (driver.get("period") or "").strip()
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

    # Revenue-stream registry (round 12): declared identities with anchored
    # sources, canonically distinct — the stream axis mirrors the segment
    # axis so no identity is ever inferred.
    streams_registry = ledger.get("revenue_streams")
    valid_stream_entries: list[dict] = []
    if isinstance(streams_registry, list):
        seen_stream_keys: set[str] = set()
        for entry in streams_registry:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"].strip() \
                    and len(str(entry.get("description") or "").strip()) >= 10 \
                    and is_locator(entry.get("source")):
                check_unknown_keys(entry, STREAM_KEYS, f"stream:{entry['id']}", reasons)
                canon_id = canonical_identity(entry["id"])
                if canon_id in seen_stream_keys:
                    reasons.append(f"stream_undeclared:registry_duplicate:{canon_id}")
                seen_stream_keys.add(canon_id)
                valid_stream_entries.append(entry)
            else:
                reasons.append("stream_undeclared:registry_malformed")

    open_tbd = 0
    for claim in claims:
        claim["_ledger_revenue_streams"] = valid_stream_entries
        cid = claim.get("claim_id", "?")
        check_unknown_keys(claim, CLAIM_KEYS | {"_ledger_revenue_streams"}, str(cid), reasons)
        for field in REQUIRED_CLAIM_FIELDS:
            if not str(claim.get(field) or "").strip():
                reasons.append(f"missing_ledger_field:{cid}:{field}")
        if str(claim.get("source") or "").strip() and not is_locator(claim.get("source")):
            reasons.append(f"source_not_locator:{cid}")
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
        components_list = claim.get("components", []) or []
        for component_id in {c for c in components_list if components_list.count(c) > 1}:
            reasons.append(f"component_duplicate:{cid}:{component_id}")
        for component_id in components_list:
            component = claims_by_id.get(component_id)
            if component is None:
                reasons.append(f"component_missing:{cid}:{component_id}")
            elif claim_has_open_coverage(component):
                reasons.append(f"aggregate_incomplete_component:{cid}:{component_id}")

    # Dependency/aggregate graph must be a DAG: self-references and cycles
    # make "component coverage" and recomputation ill-founded.
    graph: dict[str, set[str]] = {}
    for claim in claims:
        cid = claim.get("claim_id")
        edges = set()
        for field in ("depends_on", "components"):
            for target in claim.get(field, []) or []:
                if isinstance(target, str):
                    edges.add(target)
        graph[cid] = edges
        if cid in edges:
            reasons.append(f"depends_on_cycle:{cid}:self")
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in graph}
    def _visit(node: str, path: list[str]) -> None:
        color[node] = GRAY
        for neighbor in graph.get(node, ()):  # missing targets reported elsewhere
            if neighbor not in graph:
                continue
            if color[neighbor] == GRAY:
                reasons.append(f"depends_on_cycle:{neighbor}:{'->'.join(path + [node, neighbor])}")
            elif color[neighbor] == WHITE:
                _visit(neighbor, path + [node])
        color[node] = BLACK
    for node in graph:
        if color[node] == WHITE:
            _visit(node, [])

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
            conversion = float(schedule["conversion"])
            if not (0 < conversion <= 1) or not (0 <= churn < 1) or active <= 0:
                reasons.append("cohort_domain_invalid")
            if churn > 0 and active > 1.5 * (1.0 / churn):
                reasons.append("cohort_schedule_infeasible")
            for claim in claims:
                drivers = claim.get("revenue_drivers") or {}
                cid = claim.get("claim_id", "?")
                # Recurring economics REQUIRE the cohort drivers on record.
                for key in ("conversion", "churn_monthly"):
                    if not is_finite_number(drivers.get(key)):
                        reasons.append(f"revenue_driver_missing:{cid}:{key}")
                claimed_active = drivers.get("active_months")
                if is_finite_number(claimed_active) and float(claimed_active) > active:
                    reasons.append(f"cohort_inconsistent_active_months:{cid}")
                for key, reason in (("conversion", "cohort_inconsistent_conversion"),
                                    ("churn_monthly", "cohort_inconsistent_churn")):
                    claimed = drivers.get(key)
                    if is_finite_number(claimed) and not math.isclose(
                            float(claimed), float(schedule[key]), rel_tol=1e-6, abs_tol=1e-9):
                        reasons.append(f"{reason}:{cid}")
                # Recurring claims must actually USE the cohort math: a bare
                # price*volume revenue side (in a forecast OR inside a margin
                # denominator) is a completeness bypass. Per-unit claims that
                # never touch volume are exempt.
                used = binding_referenced_names(claim)
                if claim.get("metric") in ("revenue", "forecast") or "volume" in used:
                    if not {"conversion", "active_months"} <= used:
                        reasons.append(f"cohort_math_missing:{cid}")
                # Cohort factors MULTIPLY revenue exactly once per stream
                # (#74). Symbolic degree analysis on the FULLY SUBSTITUTED
                # derivation (round 10 — replaces the per-expression counts
                # that false-blocked additive streams and missed alias
                # splits): per additive term, degree > 1 is compounding and
                # degree < 0 is inverse semantics. Additive streams each
                # using a factor once (degrees {0,1}) stay GREEN. Margins
                # analyze numerator and denominator SEPARATELY — a revenue
                # denominator carrying cohort factors is correct math, so the
                # root quotient must not subtract its degrees away.
                cohort_factors = {"conversion", "active_months"}
                tree = substituted_formula_tree(claim)
                if tree is not None:
                    subtrees = [tree]
                    if claim.get("metric") in MARGIN_METRICS:
                        body = tree.body if isinstance(tree, ast.Expression) else tree
                        if isinstance(body, ast.BinOp) and isinstance(body.op, ast.Div):
                            subtrees = [body.left, body.right]
                    for factor in sorted(cohort_factors):
                        flagged = False
                        for subtree in subtrees:
                            degrees = factor_degrees(subtree, factor)
                            if any(d > 1 for d in degrees):
                                reasons.append(f"cohort_factor_duplicated:{cid}:{factor}")
                                flagged = True
                                break
                            if any(d < 0 for d in degrees):
                                reasons.append(f"cohort_factor_inverted:{cid}")
                                flagged = True
                                break
                            # Nonlinear shapes like conversion/(1+conversion)
                            # net to degree {0,1} yet are not multiplicative
                            # cohort math: a factor on BOTH sides of any
                            # quotient inside the derivation blocks (the
                            # margin ROOT quotient is analyzed per side, so
                            # correct margins stay green).
                            for node in ast.walk(subtree):
                                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                                    if any(d > 0 for d in factor_degrees(node.left, factor)) \
                                            and any(d > 0 for d in factor_degrees(node.right, factor)):
                                        reasons.append(f"cohort_factor_inverted:{cid}")
                                        flagged = True
                                        break
                            if flagged:
                                break
                # One binding = one stream = each cohort factor at most once
                # per EXPRESSION (round 11): `conversion+conversion` inside a
                # single binding is a hidden 2x coefficient; combined streams
                # must be written as separate inputs (which the additive
                # positive control exercises).
                for expression in [claim.get("formula")] + list((claim.get("input_bindings") or {}).values()):
                    if not isinstance(expression, str) or expression.strip().startswith("assumption:"):
                        continue
                    try:
                        expr_tree = ast.parse(expression.strip(), mode="eval").body
                    except (SyntaxError, ValueError):
                        continue
                    expr_names = [n.id for n in ast.walk(expr_tree) if isinstance(n, ast.Name)]
                    for factor in cohort_factors:
                        if expr_names.count(factor) > 1:
                            reasons.append(f"cohort_factor_duplicated:{cid}:{factor}")
                    # Exact coefficient contract (rounds 12-13): a cohort
                    # factor counts ONCE at coefficient one. The judgment is
                    # the term's NET constant multiplier (anchors=1), so /2
                    # (a 0.5 rate) is green while 2*conversion AND
                    # conversion/0.5 (net 2) block. The factor must also be a
                    # pure multiplicative leaf: 1+conversion (an additive
                    # offset) is not cohort multiplication.
                    def mult_terms(node):
                        for term in ([node] if not (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)))
                                     else []):
                            yield term
                        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
                            yield from mult_terms(node.left)
                            yield from mult_terms(node.right)
                    for term in mult_terms(expr_tree):
                        term_names = {n.id for n in ast.walk(term) if isinstance(n, ast.Name)}
                        if not (term_names & cohort_factors):
                            continue
                        # Share-like constants only (rounds 13-14). Evaluate
                        # the multiplicative constant ratio as a unit, so
                        # `x*100/200` is the same 0.5 share as `x/2`. Explicit
                        # numerator growth must be balanced by at least as much
                        # divisor reduction; `2*x*0.3` therefore remains a
                        # masked 2x and `/0.5` remains inflationary.
                        def coefficient_invalid(node: ast.AST) -> bool:
                            numerator_growth = 1.0
                            denominator_reduction = 1.0
                            denominator_share = False

                            def collect_constants(current: ast.AST, inverted: bool = False) -> None:
                                nonlocal numerator_growth, denominator_reduction, denominator_share
                                if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div):
                                    collect_constants(current.left, inverted)
                                    collect_constants(current.right, not inverted)
                                    return
                                if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Mult):
                                    collect_constants(current.left, inverted)
                                    collect_constants(current.right, inverted)
                                    return
                                if isinstance(current, ast.UnaryOp):
                                    collect_constants(current.operand, inverted)
                                    return
                                value = constant_expr_value(current)
                                if value is None:
                                    return
                                magnitude = abs(value)
                                if inverted:
                                    if magnitude < 1 - 1e-9:
                                        denominator_share = True
                                    elif magnitude > 1 + 1e-9:
                                        denominator_reduction *= magnitude
                                elif magnitude > 1 + 1e-9:
                                    numerator_growth *= magnitude

                            collect_constants(node)
                            return denominator_share or numerator_growth > denominator_reduction + 1e-9

                        if coefficient_invalid(term):
                            reasons.append(f"cohort_factor_duplicated:{cid}:coefficient")
                        # non-multiplicative use: the factor under an Add/Sub
                        # nested INSIDE the term (the term itself is not an
                        # additive node by construction).
                        for node in ast.walk(term):
                            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
                                inner = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
                                if inner & cohort_factors:
                                    reasons.append(f"cohort_factor_inverted:{cid}")
                                    break

    declared = ledger.get("unresolved_count")
    if not isinstance(declared, int) or isinstance(declared, bool) or declared != open_tbd:
        reasons.append(f"unresolved_count_mismatch:declared={declared!r}:actual={open_tbd}")

    # Closure state is an explicit, required record: open blockers must be
    # enumerated, and a ledger that DECLARES open blockers can never pass.
    blockers = ledger.get("blockers")
    uncertainties = ledger.get("uncertainties")
    if not isinstance(blockers, list) or not isinstance(uncertainties, list):
        reasons.append("closure_state_missing")
    else:
        if open_tbd > len(blockers):
            reasons.append(f"blockers_not_recorded:open={open_tbd}:recorded={len(blockers)}")
        if blockers:
            reasons.append("blockers_open")
        # Uncertainties are structured: each must state a bounded impact, and
        # one that could reverse the decision blocks outright.
        # Impact bounds are NUMERIC (a free string can declare itself
        # unbounded and pass), and cumulative materiality is evaluated
        # against a declared threshold.
        threshold = ledger.get("materiality_threshold")
        threshold_ok = isinstance(threshold, dict) and is_finite_number(threshold.get("value")) \
            and float(threshold.get("value") or 0) > 0 and str(threshold.get("unit") or "").strip() \
            and len(str(threshold.get("basis") or "").strip()) >= 10
        if threshold_ok:
            check_unknown_keys(threshold, MATERIALITY_KEYS, "materiality_threshold", reasons)
            unit = str(threshold["unit"]).strip()
            # The unit registry is CLOSED and capped, and the basis must be a
            # locator: "1000 bananas per internal decision" can never pass.
            if unit not in MATERIALITY_UNIT_CAPS or float(threshold["value"]) > MATERIALITY_UNIT_CAPS[unit] \
                    or not is_locator(threshold.get("basis")):
                reasons.append("materiality_threshold_unanchored")
                threshold_ok = False
        if uncertainties and not threshold_ok:
            reasons.append("materiality_exceeded:threshold_missing")
        cumulative = 0.0
        for entry in uncertainties:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) \
                    or len(str(entry.get("text") or "").strip()) < 10:
                reasons.append("uncertainty_malformed")
                continue
            check_unknown_keys(entry, UNCERTAINTY_KEYS, f"uncertainty:{entry['id']}", reasons)
            if not isinstance(entry.get("decision_reversing"), bool):
                # The reversal flag is a required boolean: leaving it out (or
                # stringly-typing it) must never read as "not reversing".
                reasons.append(f"uncertainty_malformed:{entry['id']}:decision_reversing")
            elif entry["decision_reversing"]:
                reasons.append(f"uncertainty_decision_reversing:{entry['id']}")
            if not is_finite_number(entry.get("impact_value")) or not is_locator(entry.get("evidence")):
                # A numeric impact still needs a locator-anchored source: a
                # self-declared number is not a bound.
                reasons.append(f"uncertainty_unbounded:{entry['id']}")
                continue
            unit = str(entry.get("impact_unit") or "").strip()
            if not unit or (threshold_ok and unit != str(threshold.get("unit")).strip()):
                reasons.append(f"uncertainty_malformed:{entry['id']}:impact_unit")
                continue
            cumulative += abs(float(entry["impact_value"]))
        if threshold_ok and cumulative > float(threshold["value"]):
            reasons.append(f"materiality_exceeded:cumulative={cumulative}:threshold={threshold['value']}")

    # #74 frame contract: what was reviewed, how many central claims exist,
    # and the overall artifact verdict are explicit records — coverage over
    # an undeclared frame is unprovable.
    if not is_locator(ledger.get("observed_frame")) or len(str(ledger.get("observed_frame") or "").strip()) < 10:
        reasons.append("observed_frame_missing")
    inventory = ledger.get("central_claim_inventory")
    if not isinstance(inventory, dict) or not isinstance(inventory.get("count"), int) \
            or isinstance(inventory.get("count"), bool) \
            or not isinstance(inventory.get("claim_ids"), list) \
            or not is_locator(inventory.get("enumeration_basis")):
        reasons.append("inventory_mismatch:record_missing")
    else:
        check_unknown_keys(inventory, INVENTORY_KEYS, "central_claim_inventory", reasons)
        # Identity, not just cardinality: the inventory names the exact claim
        # IDs, and both the set and the count must match the recorded claims.
        if inventory["count"] != len(claims) or set(inventory["claim_ids"]) != {c for c in claim_ids if c} \
                or len(inventory["claim_ids"]) != len(claims):
            reasons.append(f"inventory_mismatch:declared={inventory['count']}:recorded={len(claims)}")
    artifact_verdict = ledger.get("artifact_verdict")
    if artifact_verdict not in SIGNOFF_VERDICTS:
        reasons.append("artifact_verdict_missing")
    elif artifact_verdict == "BLOCK":
        reasons.append("artifact_verdict_blocked")
    # Segment identity is CANONICAL, never free text (round 10): segments a
    # claim uses must be declared in a ledger registry with an anchored
    # source, so a self-invented label can never split a conflict group.
    canonical_segment = canonical_identity

    segments_registry = ledger.get("segments")
    declared_segments: set[str] = set()
    if isinstance(segments_registry, list):
        for entry in segments_registry:
            if isinstance(entry, dict) and isinstance(entry.get("name"), str) and is_locator(entry.get("source")):
                check_unknown_keys(entry, SEGMENT_KEYS, f"segment:{entry['name']}", reasons)
                canon = canonical_segment(entry["name"])
                if canon in declared_segments:
                    # Two registry entries collapsing to one canonical name is
                    # a laundering surface, never a legitimate registry.
                    reasons.append(f"segment_undeclared:registry_duplicate:{canon}")
                declared_segments.add(canon)
            else:
                reasons.append("segment_undeclared:registry_malformed")
    for claim in claims:
        segment = str(claim.get("segment") or "").strip()
        if segment and canonical_segment(segment) not in declared_segments:
            reasons.append(f"segment_undeclared:{claim.get('claim_id', '?')}:{segment}")

    # Cross-page conflicts (#74): same-basis claims showing different values
    # must be RECORDED with an anchored resolution — and the record must be
    # referentially sound. Components of one aggregate are separate lines,
    # not conflicts.
    conflicts = ledger.get("cross_page_conflicts")
    component_ids = {t for c in claims for t in (c.get("components") or []) if isinstance(t, str)}
    recorded_pairs: set[frozenset] = set()
    if not isinstance(conflicts, list):
        reasons.append("cross_page_conflict_unrecorded:record_missing")
    else:
        for entry in conflicts:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) \
                    or not isinstance(entry.get("claim_ids"), list) \
                    or not all(isinstance(c, str) and c in claim_ids for c in entry.get("claim_ids") or []) \
                    or len(entry.get("claim_ids") or []) < 2 \
                    or len(str(entry.get("description") or "").strip()) < 10:
                reasons.append("cross_page_conflict_malformed")
                continue
            check_unknown_keys(entry, CONFLICT_KEYS, f"conflict:{entry['id']}", reasons)
            if not is_locator(entry.get("resolution")):
                reasons.append(f"cross_page_conflict_unresolved:{entry['id']}")
            recorded_pairs.add(frozenset(entry["claim_ids"]))
        basis_groups: dict[tuple, list] = {}
        for claim in claims:
            # segment/subject identity: two lines about DIFFERENT segments are
            # legitimately different numbers, never a conflict (round 9).
            # Casefolded (round 10): "Enterprise" vs "enterprise" is the SAME
            # segment — spelling drift can never dodge a conflict record.
            key = tuple(canonical_identity(str(claim.get(f) or ""))
                        for f in ("metric", "period", "currency", "unit", "tax_basis", "segment"))
            basis_groups.setdefault(key, []).append(claim)
        for group in basis_groups.values():
            candidates = [c for c in group if c.get("claim_id") not in component_ids and not c.get("components")]
            for i, first in enumerate(candidates):
                for second in candidates[i + 1:]:
                    a, b = first.get("displayed_value"), second.get("displayed_value")
                    if is_finite_number(a) and is_finite_number(b) and abs(float(a) - float(b)) > 1e-9:
                        pair = frozenset({first.get("claim_id"), second.get("claim_id")})
                        if not any(pair <= recorded for recorded in recorded_pairs):
                            reasons.append(
                                f"cross_page_conflict_unrecorded:{first.get('claim_id')}:{second.get('claim_id')}")

    # Minimum closure conditions are explicit records; any unsatisfied one blocks.
    closure_conditions = ledger.get("minimum_closure_conditions")
    if not isinstance(closure_conditions, list) or not closure_conditions:
        reasons.append("closure_state_missing:minimum_closure_conditions")
    else:
        for entry in closure_conditions:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) \
                    or len(str(entry.get("text") or "").strip()) < 10 \
                    or not isinstance(entry.get("satisfied"), bool):
                reasons.append("closure_state_missing:minimum_closure_conditions")
                continue
            check_unknown_keys(entry, CLOSURE_CONDITION_KEYS, f"closure_condition:{entry['id']}", reasons)
            if not entry["satisfied"]:
                reasons.append(f"closure_condition_unsatisfied:{entry['id']}")

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
        # Every accepted entry is individually complete: a blank entry can
        # never ride along beside a valid one (PR #75 round 5).
        coverage = entry.get("coverage")
        if not str(entry.get("reviewer") or "").strip() or not isinstance(coverage, list) or not coverage \
                or not all(isinstance(c, str) for c in coverage) \
                or not set(coverage) <= {c for c in claim_ids if c} \
                or not str(entry.get("artifact_sha256") or "").strip():
            # Non-empty, claim-anchored coverage per ENTRY: an empty-coverage
            # rider can never pad a role.
            reasons.append(f"signoff_malformed:{entry.get('role', '?')}")
        verdict_value = entry.get("verdict")
        if verdict_value not in SIGNOFF_VERDICTS:
            reasons.append(f"signoff_verdict_missing:{entry.get('role', '?')}")
        elif verdict_value == "BLOCK":
            reasons.append(f"signoff_blocked:{entry.get('role', '?')}")
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
        # Reviewer-specific coverage: each required role must have inspected
        # every claim; an extra role's coverage never substitutes.
        covered_claims: set[str] = set()
        for s in entries:
            coverage = s.get("coverage")
            if isinstance(coverage, list):
                covered_claims.update(c for c in coverage if isinstance(c, str))
        if claim_ids - covered_claims:
            reasons.append(f"signoff_coverage_incomplete:{role}")
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
    # Coverage is judged against the checker's canonical REASON_CLASSES list
    # using the FIXTURES ALONE (PR #75 round 3): every emittable class needs a
    # RED fixture whose expected reason was actually produced by evaluate() in
    # THIS run — deleting a rule (or its fixture) turns the run RED. A
    # hand-maintained "the selftest covers X" set would be self-attestation.
    executed_covered: set[str] = set()
    for result in results:
        if result["expected"] == "block" and result["ok"]:
            declared = {r.split(":", 1)[0] for r in next(
                (case.get("expected_reasons") or [] for case in cases if case.get("id") == result["id"]), [])}
            produced = {r.split(":", 1)[0] for r in result["reasons"]}
            executed_covered.update(declared & produced)
    unknown_declared = {
        reason.split(":", 1)[0]
        for case in cases for reason in (case.get("expected_reasons") or [])
    } - set(REASON_CLASSES)
    if unknown_declared:
        failures.append(f"fixtures declare unknown reason classes: {sorted(unknown_declared)}")
    missing_classes = set(REASON_CLASSES) - executed_covered
    if missing_classes:
        failures.append(f"REASON_CLASSES without an executed RED fixture: {sorted(missing_classes)}")
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
        "blockers": [],
        "uncertainties": [],
        "observed_frame": "full proposal deck p1-p12 including appendix A",
        "central_claim_inventory": {"count": 1, "claim_ids": ["C1"],
                                    "enumeration_basis": "every revenue/margin figure on p2 table 1"},
        "artifact_verdict": "PASS",
        "minimum_closure_conditions": [{"id": "mc1", "satisfied": True,
                                        "text": "every entailed cost row carries a resolved disposition"}],
        "cross_page_conflicts": [],
        "segments": [],
        "revenue_streams": [{"id": "core_subscription", "description": "core subscription revenue stream",
                             "source": "revenue model p2 table 1"}],
        "claims": [{
            "claim_id": "C1", "source": "p2:table1", "metric": "gross_margin",
            "period": "FY1", "currency": "USD", "unit": "ratio", "tax_basis": "excl",
            "displayed_value": 0.60, "formula": "(rev-cogs-fee)/rev",
            "inputs": {"rev": 100.0, "cogs": 25.0, "fee": 15.0},
            "input_bindings": {"rev": "price*volume", "cogs": "assumption:a1", "fee": "partner_fee"},
            "stream_ids": {"rev": "core_subscription"},
            "recomputed_value": 0.60,
            "rounding_rule": "2dp",
            "revenue_drivers": {"price": 10.0, "volume": 10, "start_month": 1, "active_months": 12},
            "assumptions": [{"id": "a1", "text": "COGS from supplier quote p2 line 4", "evidence_status": "cited", "value": 25.0}],
            "evidence_status": "cited",
            "sensitivity": "margin moves 5pt per 10% COGS swing",
            "depends_on": [],
            "cost_drivers": [{
                "name": "partner_fee", "entailed_class": "channel_economics",
                "disposition": "amount", "value": 15.0,
                "basis": "flat fee per period, tax-exclusive",
                "source": "partner agreement p3 clause 2", "period": "FY1",
            }],
        }],
        "signoffs": [
            {"role": "arithmetic_reconciliation", "reviewer": "r1", "artifact_sha256": hash_value,
             "verdict": "PASS", "coverage": ["C1"]},
            {"role": "completeness_negative_space", "reviewer": "r2", "artifact_sha256": hash_value,
             "verdict": "PASS", "coverage": ["C1"]},
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
    equivalent_half_shares = {
        canonical_expr(ast.parse(expression, mode="eval"))
        for expression in (
            "price*volume*0.5", "price*volume/2", "price*volume*(1/2)",
            "(price*volume*4)/8", "volume*price/(4/2)", "(price/2)*volume",
            "-(-price*volume/2)",
        )
    }
    check("finite multiplicative/divisive half-share forms share one canonical expression",
          len(equivalent_half_shares) == 1)
    check("zero and non-finite divisors remain fail-closed",
          safe_eval_formula("price/0", {"price": 1.0}) is None
          and safe_eval_formula("price/1e999", {"price": 1.0}) is None)

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

    # --- fix-3 probes (PR #75 round 3: ledger-anchored numbers + record fields) ---
    probe("assumption feeding arithmetic must record its number",
          lambda l: l["claims"][0]["assumptions"][0].pop("value"), "assumption_value_missing")
    probe("assumption value diverging from the bound input blocks",
          lambda l: l["claims"][0]["assumptions"][0].update(value=0.0), "assumption_value_mismatch")
    probe("duplicate assumption ids block",
          lambda l: l["claims"][0]["assumptions"].append(dict(l["claims"][0]["assumptions"][0])), "assumption_malformed")
    probe("an amount cost never consumed by the bound math blocks",
          lambda l: l["claims"][0]["cost_drivers"].append({"name": "mystery_cost", "disposition": "amount", "value": 7.0}),
          "cost_driver_unbound")
    probe("missing recomputed_value blocks (it is a required #74 record field)",
          lambda l: l["claims"][0].pop("recomputed_value"), "recomputed_value_missing")
    probe("missing closure state (blockers/uncertainties) blocks",
          lambda l: l.pop("blockers"), "closure_state_missing")
    probe("a ledger declaring open blockers can never pass",
          lambda l: l.update(blockers=["channel fee treatment disputed"]), "blockers_open")
    probe("missing sign-off verdict blocks",
          lambda l: l["signoffs"][0].pop("verdict"), "signoff_verdict_missing")
    probe("a reviewer block verdict blocks the gate",
          lambda l: l["signoffs"][1].update(verdict="BLOCK"), "signoff_blocked")
    probe("reviewer coverage must span every claim per required role",
          lambda l: l["signoffs"][1].update(coverage=[]), "signoff_coverage_incomplete")
    probe("margin unit must be a ratio", lambda l: l["claims"][0].update(unit="USD"), "unit_metric_mismatch")

    def not_a_ratio(l):
        l["claims"][0].update(formula="rev-cogs-fee", displayed_value=60.0, recomputed_value=60.0)
    probe("margin formula must be a quotient", not_a_ratio, "margin_formula_shape")
    probe("revenue driver domain violations block",
          lambda l: l["claims"][0]["revenue_drivers"].update(conversion=3.0), "revenue_driver_domain_invalid")

    def recurring_forecast_no_cohort_math(l):
        l["business_model"] = ["subscription", "partner_led_sales"]
        l["cohort_schedule"] = {"conversion": 0.3, "churn_monthly": 0.05, "active_months": 12,
                                "feasible_evidence": "cohort table p7 supports 12 active months"}
        l["claims"][0].update(metric="forecast", displayed_value=100.0, recomputed_value=100.0,
                              formula="rev", unit="USD_thousand")
    probe("recurring forecast that ignores conversion/active-months blocks",
          recurring_forecast_no_cohort_math, "cohort_math_missing")

    def bad_cohort_domain(l):
        recurring_forecast_no_cohort_math(l)
        l["cohort_schedule"]["conversion"] = 0.0
    probe("cohort domain violations block", bad_cohort_domain, "cohort_domain_invalid")

    # --- fix-4 probes (PR #75 round 4: closed binding space + nested evidence) ---
    def phantom_input(l):
        l["claims"][0]["inputs"]["ghost"] = 1.0
        l["claims"][0]["input_bindings"]["ghost"] = "conversion*active_months"
    probe("an input the formula never reads blocks (phantom consumption surface)",
          phantom_input, "formula_input_unused")
    probe("a binding for a key outside the inputs blocks",
          lambda l: l["claims"][0]["input_bindings"].update(ghost="partner_fee"), "binding_unused")
    def swapped_numerator(l):
        l["claims"][0].update(formula="(cogs+fee)/rev", displayed_value=0.40, recomputed_value=0.40)
    probe("a margin numerator not derived from its denominator blocks", swapped_numerator, "margin_numerator_shape")
    def cost_denominator(l):
        l["claims"][0].update(formula="(rev-cogs-fee)/cogs", displayed_value=2.4, recomputed_value=2.4)
    probe("a margin denominator not bound to revenue drivers blocks", cost_denominator, "margin_denominator_not_revenue")
    probe("a token claim source is not a locator",
          lambda l: l["claims"][0].update(source="x"), "source_not_locator")
    def unused_assumption(l):
        l["claims"][0]["assumptions"].append(A2 := {"id": "a9", "text": "context nobody's arithmetic consumes here",
                                                    "evidence_status": "assumed", "value": 1.0})
    probe("an assumption no binding consumes blocks", unused_assumption, "assumption_unused")
    probe("an assumption with an out-of-enum evidence status blocks",
          lambda l: l["claims"][0]["assumptions"][0].update(evidence_status="vibes"), "evidence_status_invalid")
    probe("an amount without its own anchored source blocks",
          lambda l: l["claims"][0]["cost_drivers"][0].pop("source"), "amount_without_source")
    probe("an amount on a different period than the claim blocks",
          lambda l: l["claims"][0]["cost_drivers"][0].update(period="FY9"), "amount_period_mismatch")

    def include_no_scope(l):
        l["claims"][0]["cost_drivers"][0] = {
            "name": "partner_fee", "entailed_class": "channel_economics",
            "disposition": "included-in", "included_in": "cogs",
            "allocation_basis": "fee absorbed into supplier COGS per agreement",
            "source": "contract schedule B p3", "period": "FY1",
        }
        l["claims"][0]["input_bindings"]["fee"] = "assumption:a2"
        l["claims"][0]["assumptions"].append({"id": "a2", "text": "partner fee estimate from agreement p9",
                                              "evidence_status": "cited", "value": 15.0})
    probe("included-in without a covered scope blocks", include_no_scope, "included_in_without_scope")

    def unresolved_host(l):
        include_no_scope(l)
        l["claims"][0]["cost_drivers"][0]["covered_scope"] = "partner fee line in full"
        l["claims"][0]["cost_drivers"][0]["included_in"] = "host_line"
        l["claims"][0]["cost_drivers"].append({"name": "host_line", "disposition": "TBD"})
        l["unresolved_count"] = 1
        l["blockers"] = ["host line pending"]
    probe("absorbing into an unresolved host blocks", unresolved_host, "included_in_host_unresolved")

    def with_threshold(l):
        l["materiality_threshold"] = {"value": 5.0, "unit": "margin_pt", "basis": "board materiality policy p1"}
    probe("a malformed uncertainty entry blocks",
          lambda l: (with_threshold(l), l.update(uncertainties=["it might rain"]))[-1], "uncertainty_malformed")
    probe("an uncertainty without a numeric impact blocks",
          lambda l: (with_threshold(l), l.update(uncertainties=[{"id": "u1", "text": "churn could exceed the modeled rate",
                                                                 "decision_reversing": False}]))[-1],
          "uncertainty_unbounded")
    probe("a decision-reversing uncertainty blocks",
          lambda l: (with_threshold(l), l.update(uncertainties=[{"id": "u1", "text": "churn could exceed the modeled rate",
                                                                 "impact_value": 3.0, "impact_unit": "margin_pt", "evidence": "sensitivity table p7 row 3",
                                                                 "decision_reversing": True}]))[-1],
          "uncertainty_decision_reversing")

    # --- fix-5 probes (PR #75 round 5: effect, DAG, fail-closed nested records) ---
    def zero_coefficient(l):
        l["claims"][0].update(formula="(rev-cogs-fee*0)/rev", displayed_value=0.75, recomputed_value=0.75)
    probe("a *0 coefficient references without effect and blocks", zero_coefficient, "formula_input_ineffective")

    def cost_added(l):
        l["claims"][0].update(formula="(rev-cogs+fee)/rev", displayed_value=0.90, recomputed_value=0.90)
    probe("a cost that INCREASES a margin blocks (sign inversion)", cost_added, "cost_sign_inverted")
    probe("self-dependency blocks", lambda l: l["claims"][0].update(depends_on=["C1"]), "depends_on_cycle")

    def cycle(l):
        second = copy.deepcopy(l["claims"][0])
        second["claim_id"] = "C2"
        second["depends_on"] = ["C1"]
        l["claims"][0]["depends_on"] = ["C2"]
        l["claims"].append(second)
        for s in l["signoffs"]:
            s["coverage"] = ["C1", "C2"]
    probe("a dependency cycle across claims blocks", cycle, "depends_on_cycle")

    def dup_component(l):
        second = copy.deepcopy(l["claims"][0]); second["claim_id"] = "C2"
        agg = {"claim_id": "C0", "source": "p9:agg", "metric": "gross_margin", "period": "FY1",
               "currency": "USD", "unit": "ratio", "tax_basis": "excl", "displayed_value": 0.6,
               "recomputed_value": 0.6, "rounding_rule": "2dp", "components": ["C1", "C1"],
               "weights": {"C1": 1.0}, "revenue_drivers": {"price": 10.0, "volume": 20, "start_month": 1, "active_months": 12},
               "assumptions": [], "evidence_status": "cited",
               "sensitivity": "tracks component margins one-for-one", "depends_on": ["C1"]}
        l["claims"] = [agg, l["claims"][0], second]
        for s in l["signoffs"]:
            s["coverage"] = ["C0", "C1", "C2"]
    probe("duplicate aggregate components block", dup_component, "component_duplicate")
    probe("an amount without an explicit basis blocks",
          lambda l: l["claims"][0]["cost_drivers"][0].pop("basis"), "amount_without_basis")
    probe("an uncertainty without the boolean reversal flag blocks",
          lambda l: (with_threshold(l), l.update(uncertainties=[{"id": "u1", "text": "churn could exceed the modeled rate",
                                                                 "impact_value": 3.0, "impact_unit": "margin_pt", "evidence": "sensitivity table p7 row 3"}]))[-1],
          "uncertainty_malformed")
    def blank_signoff_rider(l):
        l["signoffs"].append({"role": "arithmetic_reconciliation"})
    probe("a blank sign-off entry cannot ride beside a valid one", blank_signoff_rider, "signoff_malformed")

    # --- fix-6 probes (PR #75 round 6: anchors, frame, materiality) ---
    def hidden_zero_anchor(l):
        l["claims"][0]["input_bindings"]["fee"] = "partner_fee*0"
        l["claims"][0]["inputs"]["fee"] = 0.0
        l["claims"][0].update(displayed_value=0.75, recomputed_value=0.75)
    probe("a *0 hidden inside a binding leaves the ledger anchor ineffective and blocks",
          hidden_zero_anchor, "anchor_ineffective")

    def mixed_positive_cost(l):
        l["claims"][0]["input_bindings"]["rev"] = "price*volume+partner_fee"
        l["claims"][0]["inputs"]["rev"] = 115.0
        l["claims"][0].update(displayed_value=0.652, recomputed_value=0.652, rounding_rule="3dp")
    probe("a cost mixed into a revenue binding blocks (mixed roles)",
          mixed_positive_cost, "binding_mixed_roles")
    def negative_weight(l):
        second = copy.deepcopy(l["claims"][0]); second["claim_id"] = "C2"
        agg = {"claim_id": "C0", "source": "p9:agg", "metric": "gross_margin", "period": "FY1",
               "currency": "USD", "unit": "ratio", "tax_basis": "excl", "displayed_value": 0.6,
               "recomputed_value": 0.6, "rounding_rule": "2dp", "components": ["C1", "C2"],
               "weights": {"C1": 2.0, "C2": -1.0}, "revenue_drivers": {"price": 10.0, "volume": 20, "start_month": 1, "active_months": 12},
               "assumptions": [], "evidence_status": "cited",
               "sensitivity": "tracks component margins one-for-one", "depends_on": ["C1", "C2"]}
        l["claims"] = [agg, l["claims"][0], second]
        for s in l["signoffs"]:
            s["coverage"] = ["C0", "C1", "C2"]
        l["central_claim_inventory"]["count"] = 3
    probe("negative aggregate weights block even when they sum to one", negative_weight, "aggregate_weight_domain")
    def cross_period_component(l):
        negative_weight(l)
        l["claims"][0]["weights"] = {"C1": 0.5, "C2": 0.5}
        l["claims"][2]["period"] = "FY2"
    probe("a cross-period component in an aggregate blocks", cross_period_component, "component_period_mismatch")
    probe("a missing observed frame blocks", lambda l: l.pop("observed_frame"), "observed_frame_missing")
    probe("an inventory count diverging from recorded claims blocks",
          lambda l: l["central_claim_inventory"].update(count=5), "inventory_mismatch")
    probe("a missing artifact verdict blocks", lambda l: l.pop("artifact_verdict"), "artifact_verdict_missing")
    probe("a blocked artifact verdict blocks the gate", lambda l: l.update(artifact_verdict="BLOCK"), "artifact_verdict_blocked")
    probe("uncertainties without a materiality threshold block",
          lambda l: l.update(uncertainties=[{"id": "u1", "text": "churn could exceed the modeled rate",
                                             "impact_value": 1.0, "impact_unit": "margin_pt", "evidence": "sensitivity table p7 row 3",
                                             "decision_reversing": False}]),
          "materiality_exceeded")
    def cumulative_materiality(l):
        with_threshold(l)
        l["uncertainties"] = [
            {"id": "u1", "text": "churn could exceed the modeled rate", "impact_value": 3.0,
             "impact_unit": "margin_pt", "evidence": "sensitivity table p7 row 3", "decision_reversing": False},
            {"id": "u2", "text": "hosting price increase at renewal window", "impact_value": 2.5,
             "impact_unit": "margin_pt", "evidence": "vendor notice appendix C", "decision_reversing": False},
        ]
    probe("correlated uncertainties exceeding the materiality threshold block",
          cumulative_materiality, "materiality_exceeded")

    def included_in_value_only(l):
        l["claims"][0]["cost_drivers"][0] = {
            "name": "partner_fee", "entailed_class": "channel_economics",
            "disposition": "included-in", "included_in": "cogs", "value": 15.0,
            "covered_scope": "partner fee line in full",
            "source": "master services contract schedule B p3", "period": "FY1",
        }
        l["claims"][0]["input_bindings"]["fee"] = "assumption:a2"
        l["claims"][0]["assumptions"].append({"id": "a2", "text": "partner fee inside COGS per agreement p3",
                                              "evidence_status": "cited", "value": 15.0})
    def check_positive(name: str, mutate) -> None:
        ledger = copy.deepcopy(_green_ledger())
        mutate(ledger)
        verdict, reasons = evaluate(ledger)
        check(name, verdict == "pass" and not reasons)
    check_positive("included-in with an absorbed amount and no allocation basis passes (issue: amount OR basis)",
                   included_in_value_only)

    # --- fix-7 probes (PR #75 round 7: direction, anchored aggregates, no self-declaration) ---
    def inverse_cohort(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0].update(formula="rev/(conv*months)", displayed_value=2.7778, recomputed_value=2.7778,
                              rounding_rule="4dp")
        l["claims"][0]["inputs"] = {"rev": 100.0, "conv": 0.3, "months": 120.0}
        l["claims"][0]["input_bindings"] = {"rev": "price*volume", "conv": "conversion", "months": "active_months*10"}
        l["claims"][0]["revenue_drivers"]["active_months"] = 12
    probe("a divided cohort factor blocks (inverse semantics)", inverse_cohort, "cohort_factor_inverted")

    def unanchored_weights(l):
        dup = None
        second = copy.deepcopy(l["claims"][0]); second["claim_id"] = "C2"
        second["revenue_drivers"] = {"price": 10.0, "volume": 90, "start_month": 1, "active_months": 12}
        second["inputs"] = {"rev": 900.0, "cogs": 225.0, "fee": 135.0}
        second["input_bindings"] = {"rev": "price*volume", "cogs": "assumption:a1", "fee": "partner_fee"}
        second["assumptions"] = [{"id": "a1", "text": "COGS from supplier quote p2 line 4", "evidence_status": "cited", "value": 225.0}]
        second["cost_drivers"] = [{"name": "partner_fee", "entailed_class": "channel_economics",
                                   "disposition": "amount", "value": 135.0,
                                   "basis": "flat fee per period, tax-exclusive",
                                   "source": "partner agreement p3 clause 2", "period": "FY1"}]
        agg = {"claim_id": "C0", "source": "p9:agg", "metric": "gross_margin", "period": "FY1",
               "currency": "USD", "unit": "ratio", "tax_basis": "excl", "displayed_value": 0.6,
               "recomputed_value": 0.6, "rounding_rule": "2dp", "components": ["C1", "C2"],
               "weights": {"C1": 0.5, "C2": 0.5},
               "revenue_drivers": {"price": 10.0, "volume": 100, "start_month": 1, "active_months": 12},
               "assumptions": [], "evidence_status": "cited",
               "sensitivity": "tracks component margins one-for-one", "depends_on": ["C1", "C2"]}
        l["claims"] = [agg, l["claims"][0], second]
        for s in l["signoffs"]:
            s["coverage"] = ["C0", "C1", "C2"]
        l["central_claim_inventory"] = {"count": 3, "claim_ids": ["C0", "C1", "C2"],
                                        "enumeration_basis": "every margin figure p2-p9 tables"}
    probe("self-declared 50/50 weights over 10/90 revenue block", unanchored_weights, "aggregate_weight_unanchored")

    def basis_mismatch(l):
        unanchored_weights(l)
        l["claims"][0]["weights"] = {"C1": 0.1, "C2": 0.9}
        l["claims"][2]["currency"] = "EUR"
    probe("a component in another currency blocks", basis_mismatch, "component_basis_mismatch")
    probe("a banana-unit self-set materiality threshold blocks",
          lambda l: l.update(uncertainties=[{"id": "u1", "text": "churn could exceed the modeled rate",
                                             "impact_value": 1.0, "impact_unit": "bananas", "decision_reversing": False}],
                             materiality_threshold={"value": 1000.0, "unit": "bananas",
                                                    "basis": "internal team decision without any source"}),
          "materiality_threshold_unanchored")
    probe("an inventory naming wrong claim ids blocks even with a matching count",
          lambda l: l["central_claim_inventory"].update(claim_ids=["C9"]), "inventory_mismatch")
    probe("an unsatisfied minimum closure condition blocks",
          lambda l: l["minimum_closure_conditions"][0].update(satisfied=False), "closure_condition_unsatisfied")
    probe("missing minimum closure conditions block",
          lambda l: l.pop("minimum_closure_conditions"), "closure_state_missing")
    def empty_coverage_rider(l):
        l["signoffs"].append({"role": "arithmetic_reconciliation", "reviewer": "r3",
                              "artifact_sha256": l["artifact_sha256"], "verdict": "PASS", "coverage": []})
    probe("an empty-coverage sign-off rider blocks", empty_coverage_rider, "signoff_malformed")

    # --- fix-9 probes (PR #75 round 9) ---
    def alias_split_conversion(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
        l["claims"][0].update(formula="a*b", displayed_value=32.4, recomputed_value=32.4, rounding_rule="1dp")
        l["claims"][0]["inputs"] = {"a": 0.3, "b": 108.0}
        l["claims"][0]["input_bindings"] = {"a": "conversion", "b": "price*volume*conversion*active_months*0.3"}
    probe("conversion split across a formula alias and a binding still compounds and blocks",
          alias_split_conversion, "cohort_factor_duplicated")

    def cap_violation(l):
        with_threshold(l)
        l["materiality_threshold"]["value"] = 7.0
        l["uncertainties"] = [{"id": "u1", "text": "churn could exceed the modeled rate",
                               "impact_value": 6.5, "impact_unit": "margin_pt",
                               "evidence": "sensitivity table p7 row 3", "decision_reversing": False}]
    probe("a 7pt margin threshold exceeds the #74 5pt default and blocks", cap_violation, "materiality_threshold_unanchored")

    def segment_positive(l):
        second = copy.deepcopy(l["claims"][0])
        second["claim_id"] = "C2"
        second["source"] = "p8:segment-table"
        second["segment"] = "enterprise"
        second["displayed_value"] = 0.55
        second["recomputed_value"] = 0.55
        second["inputs"] = {"rev": 100.0, "cogs": 30.0, "fee": 15.0}
        second["assumptions"] = [{"id": "a1", "text": "COGS from enterprise sheet p8 line 2",
                                  "evidence_status": "cited", "value": 30.0}]
        l["claims"][0]["segment"] = "self_serve"
        l["segments"] = [{"name": "self_serve", "source": "segment definitions p2 table 1"},
                         {"name": "enterprise", "source": "segment definitions p2 table 1"}]
        l["claims"].append(second)
        for s in l["signoffs"]:
            s["coverage"] = ["C1", "C2"]
        l["central_claim_inventory"] = {"count": 2, "claim_ids": ["C1", "C2"],
                                        "enumeration_basis": "every margin figure p1-p8 tables"}
    check_positive("different-segment margins with diverging values pass without a conflict record",
                   segment_positive)

    # --- fix-10 probes (PR #75 round 10) ---
    def additive_streams_positive(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
        c = l["claims"][0]
        c.update(formula="new_rev+expansion_rev", displayed_value=75.6, recomputed_value=75.6, rounding_rule="1dp")
        c["inputs"] = {"new_rev": 54.0, "expansion_rev": 21.6}
        c["input_bindings"] = {"new_rev": "price*volume*conversion*active_months*0.15",
                               "expansion_rev": "setup_fee*volume*conversion*active_months*0.15"}
        c["stream_ids"] = {"new_rev": "new_business", "expansion_rev": "expansion"}
        l["revenue_streams"] = [
            {"id": "new_business", "description": "new business cohort revenue", "source": "revenue model p2 table 1"},
            {"id": "expansion", "description": "expansion setup-fee revenue", "source": "revenue model p2 table 2"}]
        c["revenue_drivers"]["setup_fee"] = 4.0
        c["assumptions"] = []
    check_positive("additive revenue streams each using cohort factors once pass (round-10 false-block)",
                   additive_streams_positive)

    def formula_double_count(l):
        c = l["claims"][0]
        c.update(formula="(rev+rev2-cogs-fee)/rev", displayed_value=1.6, recomputed_value=1.6)
        c["inputs"] = {"rev": 100.0, "rev2": 100.0, "cogs": 25.0, "fee": 15.0}
        c["input_bindings"] = {"rev": "price*volume", "rev2": "volume*price",
                               "cogs": "assumption:a1", "fee": "partner_fee"}
    probe("the same revenue stream aliased twice inside one formula blocks", formula_double_count, "duplicate_revenue_stream")

    def segment_case_drift(l):
        segment_positive(l)
        l["claims"][0]["segment"] = "Enterprise"
        l["claims"][1]["segment"] = "enterprise"
    probe("segment case drift cannot dodge a same-segment conflict record", segment_case_drift, "cross_page_conflict_unrecorded")
    def undeclared_segment(l):
        l["claims"][0]["segment"] = "made_up_label"
    probe("a segment missing from the anchored registry blocks", undeclared_segment, "segment_undeclared")

    # --- fix-11 probes (PR #75 round 11) ---
    def nonlinear_cohort(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
        c = l["claims"][0]
        c.update(formula="rev*share", displayed_value=23.0769, recomputed_value=23.0769, rounding_rule="4dp")
        c["inputs"] = {"rev": 100.0, "share": 0.230769}
        c["input_bindings"] = {"rev": "price*volume", "share": "conversion/(1+conversion)*active_months*0.0833325"}
    probe("a nonlinear cohort quotient blocks even at net degree {0,1}", nonlinear_cohort, "cohort_factor_inverted")

    def additive_same_factor(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
        c = l["claims"][0]
        c.update(formula="rev", displayed_value=216.0, recomputed_value=216.0, rounding_rule="1dp")
        c["inputs"] = {"rev": 216.0}
        c["input_bindings"] = {"rev": "price*volume*(conversion+conversion)*active_months*0.3"}
    probe("conversion+conversion hidden in one binding is a 2x coefficient and blocks",
          additive_same_factor, "cohort_factor_duplicated")

    def scaled_duplicate_stream(l):
        c = l["claims"][0]
        c.update(formula="(rev+rev2-cogs-fee)/rev", displayed_value=2.6, recomputed_value=2.6,
                 metric="operating_profit", unit="JPY_million")
        c["inputs"] = {"rev": 100.0, "rev2": 200.0, "cogs": 25.0, "fee": 15.0}
        c["input_bindings"] = {"rev": "price*volume", "rev2": "2*price*volume",
                               "cogs": "assumption:a1", "fee": "partner_fee"}
    probe("a constant-scaled copy of the same stream blocks (2*price*volume)",
          scaled_duplicate_stream, "revenue_binding_scale_invalid")

    def coefficient_double(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
        c = l["claims"][0]
        c.update(formula="rev", displayed_value=216.0, recomputed_value=216.0, rounding_rule="1dp")
        c["inputs"] = {"rev": 216.0}
        c["input_bindings"] = {"rev": "price*volume*2*conversion*active_months*0.3"}
    probe("an integer coefficient on a cohort factor (2*conversion) blocks", coefficient_double, "cohort_factor_duplicated:C1:coefficient")

    # --- fix-13 probes (PR #75 round 13) ---
    def recurring_stream_base(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
        l["claims"][0]["assumptions"] = []
        l["claims"][0]["stream_ids"] = {"rev": "core_subscription"}

    def half_rate(l):
        recurring_stream_base(l)
        c = l["claims"][0]
        c.update(formula="rev", displayed_value=18.0, recomputed_value=18.0, rounding_rule="1dp")
        c["inputs"] = {"rev": 18.0}
        c["input_bindings"] = {"rev": "price*volume*conversion*active_months/2/10"}
    check_positive("a 0.5 rate written as /2 passes (share-like divisor)", half_rate)

    def normalized_half_rate(l):
        recurring_stream_base(l)
        c = l["claims"][0]
        c.update(formula="rev", displayed_value=180.0, recomputed_value=180.0, rounding_rule="1dp")
        c["inputs"] = {"rev": 180.0}
        c["input_bindings"] = {"rev": "price*volume*conversion*active_months*100/200"}
    check_positive("a 100/200 constant ratio is the same valid 0.5 share as /2",
                   normalized_half_rate)

    def inflating_divisor(l):
        recurring_stream_base(l)
        c = l["claims"][0]
        c.update(formula="rev", displayed_value=216.0, recomputed_value=216.0, rounding_rule="1dp")
        c["inputs"] = {"rev": 216.0}
        c["input_bindings"] = {"rev": "price*volume*conversion/0.5*active_months*0.3"}
    probe("a divisor constant below one inflates and blocks (conversion/0.5)",
          inflating_divisor, "cohort_factor_duplicated:C1:coefficient")

    def masked_double(l):
        recurring_stream_base(l)
        c = l["claims"][0]
        c.update(formula="rev", displayed_value=216.0, recomputed_value=216.0, rounding_rule="1dp")
        c["inputs"] = {"rev": 216.0}
        c["input_bindings"] = {"rev": "price*volume*2*conversion*active_months*0.3"}
    probe("a 2x coefficient cannot hide behind a masking share (2*x*0.3)",
          masked_double, "cohort_factor_duplicated:C1:coefficient")

    def additive_offset(l):
        recurring_stream_base(l)
        c = l["claims"][0]
        c.update(formula="rev", displayed_value=130.0, recomputed_value=130.0, rounding_rule="1dp")
        c["inputs"] = {"rev": 130.0}
        c["input_bindings"] = {"rev": "price*volume*(1+conversion)"}
    probe("an additive cohort offset (1+conversion) is not cohort multiplication",
          additive_offset, "cohort_factor_inverted")

    def neutral_element(l):
        c = l["claims"][0]
        c.update(formula="(rev+rev2-cogs-fee)/rev", displayed_value=1.6, recomputed_value=1.6)
        c["inputs"] = {"rev": 100.0, "rev2": 100.0, "cogs": 25.0, "fee": 15.0}
        c["input_bindings"] = {"rev": "price*volume", "rev2": "1*price*volume",
                               "cogs": "assumption:a1", "fee": "partner_fee"}
        c["stream_ids"] = {"rev": "core_subscription", "rev2": "s2"}
        l["revenue_streams"].append({"id": "s2", "description": "allegedly different stream",
                                     "source": "revenue model p9 table 2"})
    probe("the *1 neutral element cannot mint a different stream", neutral_element, "duplicate_revenue_stream")

    def neutral_divisor(l):
        c = l["claims"][0]
        c.update(formula="(rev+rev2-cogs-fee)/rev", displayed_value=1.6, recomputed_value=1.6)
        c["inputs"] = {"rev": 100.0, "rev2": 100.0, "cogs": 25.0, "fee": 15.0}
        c["input_bindings"] = {"rev": "price*volume", "rev2": "price*volume/1",
                               "cogs": "assumption:a1", "fee": "partner_fee"}
        c["stream_ids"] = {"rev": "core_subscription", "rev2": "s2"}
        l["revenue_streams"].append({"id": "s2", "description": "allegedly different stream",
                                     "source": "revenue model p9 table 2"})
    probe("the /1 neutral element cannot mint a different stream",
          neutral_divisor, "duplicate_revenue_stream")

    def equivalent_half_share(l):
        c = l["claims"][0]
        c.update(formula="(rev+rev2-cogs-fee)/rev", displayed_value=1.2, recomputed_value=1.2)
        c["inputs"] = {"rev": 50.0, "rev2": 50.0, "cogs": 25.0, "fee": 15.0}
        c["input_bindings"] = {"rev": "price*volume*0.5", "rev2": "price*volume/2",
                               "cogs": "assumption:a1", "fee": "partner_fee"}
        c["stream_ids"] = {"rev": "core_subscription", "rev2": "s2"}
        l["revenue_streams"].append({"id": "s2", "description": "allegedly different stream",
                                     "source": "revenue model p9 table 2"})
    probe("equivalent multiplicative and divisive shares cannot mint different streams",
          equivalent_half_share, "duplicate_revenue_stream")

    def cancelling_root_signs(l):
        equivalent_half_share(l)
        l["claims"][0]["input_bindings"]["rev2"] = "-(-price*volume/2)"
    probe("cancelling root unary signs cannot mint a different stream",
          cancelling_root_signs, "duplicate_revenue_stream")
    probe("an empty stream id blocks",
          lambda l: (l["claims"][0].update(stream_ids={"rev": " "}),)[0] or None
          if False else l["claims"][0].update(stream_ids={"rev": " "}), "stream_undeclared")
    probe("a truthy non-object stream_ids is a reasoned block, never an exception",
          lambda l: l["claims"][0].update(stream_ids=["oops"]), "stream_undeclared")
    probe("a typo key in stream_ids is rejected by the nested strict schema",
          lambda l: l["claims"][0]["stream_ids"].update(reveneu="core_subscription"),
          "schema_unknown_keys")

    def cross_component_stream(l):
        aggregate_base(l)
        for claim in l["claims"][1:]:
            claim["stream_ids"] = {"rev": "core_subscription"}
        l["central_claim_inventory"]["claim_ids"] = ["C0", "C1", "C2"]
        l["central_claim_inventory"]["count"] = 3
    probe("the same declared stream feeding two aggregate components blocks",
          cross_component_stream, "duplicate_revenue_stream")

    def nested_cross_component_stream(l):
        cross_component_stream(l)
        top, first, second = l["claims"]
        middle = copy.deepcopy(top)
        middle.update(claim_id="Cmid", components=["C1"], weights={"C1": 1.0}, depends_on=["C1"])
        top.update(components=["Cmid", "C2"], weights={"Cmid": 0.5, "C2": 0.5},
                   depends_on=["Cmid", "C2"])
        l["claims"] = [top, middle, first, second]
        claim_ids = ["C0", "Cmid", "C1", "C2"]
        l["central_claim_inventory"].update(count=4, claim_ids=claim_ids)
        for signoff in l["signoffs"]:
            signoff["coverage"] = claim_ids
    probe("duplicate leaf streams cannot be laundered through a nested aggregate",
          nested_cross_component_stream, "duplicate_revenue_stream")

    def nfkc_grouping(l):
        segment_positive(l)
        # both claims REGISTER distinct-looking segments that NFKC-collapse:
        # grouping must see one segment and demand a conflict record.
        l["claims"][0]["segment"] = "enterprise"
        l["claims"][1]["segment"] = "\uff45\uff4e\uff54\uff45\uff52\uff50\uff52\uff49\uff53\uff45"
    probe("NFKC-equivalent claim segments group together in conflict detection",
          nfkc_grouping, "cross_page_conflict_unrecorded")

    def registry_whitespace_launder(l):
        segment_positive(l)
        l["segments"] = [{"name": "Enterprise North", "source": "segment definitions p2 table 1"},
                         {"name": "enterprise  north", "source": "segment definitions p2 table 1"}]
        l["claims"][0]["segment"] = "Enterprise North"
        l["claims"][1]["segment"] = "enterprise  north"
    probe("registry entries collapsing to one canonical segment block",
          registry_whitespace_launder, "segment_undeclared:registry_duplicate")

    def equal_value_distinct_streams(l):
        c = l["claims"][0]
        c.update(formula="rev+side_rev-cogs-fee", displayed_value=160.0, recomputed_value=160.0,
                 metric="operating_profit", unit="JPY_million", rounding_rule="1dp")
        c["revenue_drivers"]["setup_fee"] = 10.0
        c["inputs"] = {"rev": 100.0, "side_rev": 100.0, "cogs": 25.0, "fee": 15.0}
        c["input_bindings"] = {"rev": "price*volume", "side_rev": "setup_fee*volume",
                               "cogs": "assumption:a1", "fee": "partner_fee"}
        c["stream_ids"] = {"rev": "core_subscription", "side_rev": "setup_fees"}
        l["revenue_streams"].append({"id": "setup_fees", "description": "one-time setup fee revenue",
                                     "source": "revenue model p2 table 3"})
    check_positive("equal-value streams over DIFFERENT anchors pass (declared distinct streams)",
                   equal_value_distinct_streams)

    probe("a revenue input without a declared stream id blocks",
          lambda l: l["claims"][0].update(stream_ids={}), "stream_undeclared")

    def nfkc_segment(l):
        segment_positive(l)
        l["segments"].append({"name": "\uff25\uff4e\uff54\uff45\uff52\uff50\uff52\uff49\uff53\uff45",
                              "source": "segment definitions p2 table 1"})
    probe("a full-width Unicode twin of a declared segment blocks (NFKC canonicalization)",
          nfkc_segment, "segment_undeclared:registry_duplicate")

    def revenue_inverted(l):
        recurring_forecast_no_cohort_math(l)
        l["claims"][0]["revenue_drivers"].update(conversion=0.3, churn_monthly=0.05)
        l["claims"][0].update(formula="conv*months-rev", displayed_value=-96.4, recomputed_value=-96.4,
                              rounding_rule="1dp")
        l["claims"][0]["inputs"] = {"rev": 100.0, "conv": 0.3, "months": 12.0}
        l["claims"][0]["input_bindings"] = {"rev": "price*volume", "conv": "conversion", "months": "active_months"}
    probe("revenue moving DOWN when volume moves up blocks", revenue_inverted, "revenue_sign_inverted")
    check_positive("a PASS_WITH_WARNINGS verdict with bounded uncertainties passes",
                   lambda l: (with_threshold(l),
                              l.update(artifact_verdict="PASS_WITH_WARNINGS",
                                       uncertainties=[{"id": "u1", "text": "churn could run 1pt above the modeled rate",
                                                       "impact_value": 2.0, "impact_unit": "margin_pt",
                                                       "evidence": "sensitivity table p7 row 2",
                                                       "decision_reversing": False}]))[-1])

    if failures:
        print("finance completeness selftest FAILED.")
        return 1
    print("finance completeness selftest passed (green->pass; PR #75 round-1..16 hostile probes block). "
          "NOTE: coverage proof lives in the fixtures run, not here.")
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
