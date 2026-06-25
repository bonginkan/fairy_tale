#!/usr/bin/env python3
"""Fail-closed residency checks for Fairy Tale agent integrations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SKILLS = (
    "fairy-tale",
    "fairy-tale-benchmark-feedback",
    "fairy-tale-legal-feedback",
)

SKILL_MARKERS = {
    "fairy-tale": (
        "Residency Guard",
        "Implementation Validation Gate",
        "Benchmark Delta Harness",
        "Latent Structure Harness",
        "Loop Engineering and Job Automation Harness",
        "fairy-tale-benchmark-feedback",
    ),
    "fairy-tale-benchmark-feedback": (
        "SWE-Bench Pro",
        "HLE-style",
        "ExploitBench",
        "Promotion Rules",
    ),
    "fairy-tale-legal-feedback": (
        "Required Closure Sweep",
        "Fairy Fusion Review",
        "Evaluated Feedback Loop",
    ),
}

SKILL_REFERENCE_MARKERS = {
    Path("fairy-tale/references/genius-methods.md"): (
        "Accessible Genius Methods",
        "Margin-of-Safety Thesis Gate",
        "Financial Engineering Replication Gate",
    ),
    Path("fairy-tale/references/process.md"): (
        "Accessible genius method record",
        "Loop engineering operating record",
        "External-channel ingestion record",
        "Job automation delegation record",
    ),
    Path("fairy-tale/references/feedback-governance.md"): (
        "Feedback Governance",
        "promotion",
        "prune",
    ),
    Path("fairy-tale/references/openmythos-external-adapter.md"): (
        "OpenMythos External Adapter",
        "adapter",
        "Upstream",
    ),
    Path("fairy-tale/references/similarity-refactoring-adapter.md"): (
        "Similarity Refactoring Adapter",
        "similarity",
        "refactoring",
    ),
    Path("fairy-tale/references/loop-engineering-automation.md"): (
        "Loop Engineering and Job Automation",
        "External-Channel Ingestion",
        "Fairy Tale Self-Pilot",
    ),
    Path("fairy-tale/references/sources.md"): (
        "Historical and Silicon Valley method sources",
        "Investing and financial engineering method sources",
        "Loop engineering and job automation sources",
    ),
}

IGNORED_TREE_PARTS = {
    "__pycache__",
}

IGNORED_TREE_FILES = {
    ".DS_Store",
}

REPO_SKILL_ROOTS = (
    Path("skills"),
    Path("plugins/fairy-tale/skills"),
    Path(".agents/skills"),
    Path(".claude/skills"),
)

CANONICAL_COMPARE_ROOTS = (
    Path("plugins/fairy-tale/skills"),
    Path(".agents/skills"),
    Path(".claude/skills"),
)

MANIFESTS = {
    Path("plugins/fairy-tale/.codex-plugin/plugin.json"): "Codex plugin",
    Path("plugins/fairy-tale/.claude-plugin/plugin.json"): "Claude Code plugin",
}

MARKETPLACES = (
    Path(".agents/plugins/marketplace.json"),
    Path(".claude-plugin/marketplace.json"),
)

GUARD_FILES = {
    Path("AGENTS.md"): (
        ".agents/skills/fairy-tale/SKILL.md",
        "scripts/fairy_tale_residency_check.py",
    ),
    Path("CLAUDE.md"): (
        ".claude/skills/fairy-tale/SKILL.md",
        "scripts/fairy_tale_residency_check.py",
    ),
}

RUNNER_MARKERS = {
    Path("scripts/latent_structure_harness.py"): (
        "Generic latent-structure ledger",
        "pre-act",
        "promotion_decision",
    ),
    Path("scripts/swebench_pro_run.py"): (
        "fairy-tale",
        "fairy-tale-benchmark-feedback",
        "Validation gate",
    ),
    Path("scripts/hle_codex_tools_runner.py"): (
        "fairy-tale plugin",
        "fairy-tale-benchmark-feedback",
        "xhigh",
    ),
    Path("scripts/genius_method_eval.py"): (
        "Accessible Genius Method",
        "placebo",
        "paired",
    ),
    Path("scripts/agentic_loop_eval.py"): (
        "Agentic Loop",
        "scored_observation_effects",
        "headroom",
    ),
    Path("scripts/agentic_loop_runner.py"): (
        "controlled Agentic Loop",
        "hidden_validators",
        "allowed_actions",
    ),
    Path("scripts/agentic_loop_codex_solver.py"): (
        "action-only solver",
        "FORBIDDEN_REQUEST_FIELDS",
        "--ignore-rules",
    ),
}

HOOK_FILES = {
    Path("plugins/fairy-tale/hooks/hooks.json"): (
        "SessionStart",
        "CLAUDE_PLUGIN_ROOT",
        "fairy_tale_residency_check.py",
        "--inject",
    ),
}

LATENT_STRUCTURE_FILES = {
    Path("schemas/latent-structure-ledger.schema.json"): (
        "Fairy Tale Latent Structure Ledger",
        "negative_evidence",
        "promotion_decision",
    ),
    Path("adapters/latent-structure-harness.adapter.json"): (
        "latent-structure-harness",
        "domain-neutral",
        "bench",
    ),
    Path("docs/latent-structure-harness.md"): (
        "Latent Structure Harness",
        "domain-neutral",
        "pre-act",
    ),
    Path("plugins/fairy-tale/schemas/latent-structure-ledger.schema.json"): (
        "Fairy Tale Latent Structure Ledger",
        "negative_evidence",
        "promotion_decision",
    ),
    Path("plugins/fairy-tale/scripts/latent_structure_harness.py"): (
        "Generic latent-structure ledger",
        "pre-act",
        "promotion_decision",
    ),
    Path("plugins/fairy-tale/adapters/latent-structure-harness.adapter.json"): (
        "latent-structure-harness",
        "domain-neutral",
        "bench",
    ),
    Path("plugins/fairy-tale/docs/latent-structure-harness.md"): (
        "Latent Structure Harness",
        "domain-neutral",
        "pre-act",
    ),
}

GENIUS_METHOD_EVAL_FILES = {
    Path("docs/genius-method-eval-plan.md"): (
        "Empirical Experiment Ledger",
        "control",
        "placebo",
        "treatment",
    ),
    Path("fixtures/genius-method-eval/empirical-smoke.jsonl"): (
        "empirical-positive-validator-claim-001",
        "empirical-negative-formatting-001",
    ),
    Path("plugins/fairy-tale/scripts/genius_method_eval.py"): (
        "Accessible Genius Method",
        "placebo",
        "paired",
    ),
}

AGENTIC_LOOP_FILES = {
    Path("docs/agentic-loop-design.md"): (
        "Agentic Loop Design Plan",
        "headroom_recovery_rate",
        "scored_observation_effects",
    ),
    Path("scripts/agentic_loop_eval.py"): (
        "Agentic Loop",
        "scored_observation_effects",
        "placebo_loop",
    ),
    Path("scripts/agentic_loop_runner.py"): (
        "controlled Agentic Loop",
        "hidden_validators",
        "allowed_actions",
    ),
    Path("scripts/agentic_loop_codex_solver.py"): (
        "action-only solver",
        "workspace_path",
        "FORBIDDEN_RESPONSE_FIELDS",
    ),
    Path("fixtures/agentic-loop/smoke.jsonl"): (
        "agentic-loop-smoke-public-probe-001",
        "agentic-loop-smoke-negative-format-001",
    ),
    Path("plugins/fairy-tale/docs/agentic-loop-design.md"): (
        "Agentic Loop Design Plan",
        "headroom_recovery_rate",
        "scored_observation_effects",
    ),
    Path("plugins/fairy-tale/scripts/agentic_loop_eval.py"): (
        "Agentic Loop",
        "scored_observation_effects",
        "placebo_loop",
    ),
    Path("plugins/fairy-tale/scripts/agentic_loop_runner.py"): (
        "controlled Agentic Loop",
        "hidden_validators",
        "allowed_actions",
    ),
    Path("plugins/fairy-tale/scripts/agentic_loop_codex_solver.py"): (
        "action-only solver",
        "workspace_path",
        "FORBIDDEN_RESPONSE_FIELDS",
    ),
}

LOOP_ENGINEERING_FILES = {
    Path("docs/loop-engineering-automation.md"): (
        "Loop Engineering and Job Automation",
        "External-Channel Ingestion",
        "Fairy Tale Self-Pilot",
    ),
    Path("plugins/fairy-tale/docs/loop-engineering-automation.md"): (
        "Loop Engineering and Job Automation",
        "External-Channel Ingestion",
        "Fairy Tale Self-Pilot",
    ),
}

INSTALL_SMOKE_FILES = {
    Path("scripts/install_smoke_test.py"): (
        "install.sh",
        "inline_markdown_refs",
        "loop-engineering-automation.md",
    ),
    Path("plugins/fairy-tale/scripts/install_smoke_test.py"): (
        "install.sh",
        "inline_markdown_refs",
        "loop-engineering-automation.md",
    ),
}

STANDING_INSTRUCTION = (
    "[fairy-tale] Residency active: apply Fable/Mythos-informed workflow this "
    "session.\n"
    "- Set an explicit budget (time, context, tool calls, write scope) before "
    "long tasks.\n"
    "- Work evidence-driven and validation-gated; preserve sources and "
    "provenance.\n"
    "- Keep security work defensive-only and within authorized targets.\n"
    "- Do not fan out broad parallel agents without an explicit cap.\n"
    "- Validate before claiming completion. Invoke the `fairy-tale` skill for "
    "substantive coding, research, loop engineering, job automation, benchmark, "
    "legal, or defensive-security work."
)

STANDING_INSTRUCTION_MARKERS = (
    "loop engineering",
    "job automation",
)


@dataclass
class Check:
    status: str
    name: str
    detail: str

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"


def rel(path: Path) -> Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def read_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def add(checks: list[Check], status: str, name: str, detail: str) -> None:
    checks.append(Check(status, name, detail))


def tree_files(root: Path) -> list[Path] | None:
    if not root.exists():
        return None
    files: list[Path] = []
    for path in root.rglob("*"):
        rel_path = path.relative_to(root)
        if any(part in IGNORED_TREE_PARTS for part in rel_path.parts):
            continue
        if path.name in IGNORED_TREE_FILES:
            continue
        if path.is_file():
            files.append(rel_path)
    return sorted(files)


def compare_tree(canonical: Path, copy: Path) -> str | None:
    canonical_files = tree_files(canonical)
    copy_files = tree_files(copy)
    if canonical_files is None or copy_files is None:
        return "cannot compare because one tree is missing"

    canonical_set = set(canonical_files)
    copy_set = set(copy_files)
    missing = sorted(canonical_set - copy_set)
    extra = sorted(copy_set - canonical_set)
    if missing or extra:
        details = []
        if missing:
            details.append("missing: " + ", ".join(str(path) for path in missing[:5]))
        if extra:
            details.append("extra: " + ", ".join(str(path) for path in extra[:5]))
        return "; ".join(details)

    drifted = [
        rel_path
        for rel_path in canonical_files
        if read_bytes(canonical / rel_path) != read_bytes(copy / rel_path)
    ]
    if drifted:
        return "drifted files: " + ", ".join(str(path) for path in drifted[:5])
    return None


def check_skill_file(checks: list[Check], root: Path, skill: str) -> None:
    path = ROOT / root / skill / "SKILL.md"
    text = read_text(path)
    label = f"{root}/{skill}"
    if text is None:
        add(checks, "FAIL", label, "missing SKILL.md")
        return

    markers = SKILL_MARKERS[skill]
    missing = [marker for marker in markers if marker not in text]
    if missing:
        add(checks, "FAIL", label, f"missing markers: {', '.join(missing)}")
    else:
        add(checks, "OK", label, "required markers present")


def check_copy_parity(checks: list[Check], copy_root: Path, skill: str) -> None:
    canonical = ROOT / "skills" / skill
    copy = ROOT / copy_root / skill
    label = f"{copy_root}/{skill} parity"
    mismatch = compare_tree(canonical, copy)
    if mismatch is None:
        add(checks, "OK", label, "matches canonical skill tree")
    else:
        add(checks, "FAIL", label, mismatch)


def check_manifest(checks: list[Check], path: Path, label: str) -> None:
    full_path = ROOT / path
    text = read_text(full_path)
    if text is None:
        add(checks, "FAIL", label, f"missing {path}")
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        add(checks, "FAIL", label, f"invalid JSON: {exc}")
        return

    failures = []
    if data.get("name") != "fairy-tale":
        failures.append("name must be fairy-tale")
    if data.get("skills") != "./skills/":
        failures.append("skills must be ./skills/")
    if not data.get("version"):
        failures.append("version is required")

    if failures:
        add(checks, "FAIL", label, "; ".join(failures))
    else:
        add(checks, "OK", label, f"{path} points at ./skills/")


def check_marketplace(checks: list[Check], path: Path) -> None:
    text = read_text(ROOT / path)
    label = f"{path}"
    if text is None:
        add(checks, "FAIL", label, "missing marketplace")
        return
    missing = [marker for marker in ("fairy-tale", "./plugins/fairy-tale") if marker not in text]
    if missing:
        add(checks, "FAIL", label, f"missing markers: {', '.join(missing)}")
    else:
        add(checks, "OK", label, "marketplace references plugin package")


def check_contains(checks: list[Check], path: Path, markers: Iterable[str], name: str | None = None) -> None:
    text = read_text(ROOT / path)
    label = name or str(path)
    if text is None:
        add(checks, "FAIL", label, f"missing {path}")
        return
    missing = [marker for marker in markers if marker not in text]
    if missing:
        add(checks, "FAIL", label, f"missing markers: {', '.join(missing)}")
    else:
        add(checks, "OK", label, "required markers present")


def check_standing_instruction(checks: list[Check]) -> None:
    missing = [
        marker
        for marker in STANDING_INSTRUCTION_MARKERS
        if marker not in STANDING_INSTRUCTION
    ]
    if missing:
        add(
            checks,
            "FAIL",
            "SessionStart standing instruction",
            "missing markers: " + ", ".join(missing),
        )
    else:
        add(
            checks,
            "OK",
            "SessionStart standing instruction",
            "loop engineering and job automation markers present",
        )


def check_installed_root(checks: list[Check], root: Path, strict: bool) -> None:
    status_if_missing = "FAIL" if strict else "WARN"
    for skill in REQUIRED_SKILLS:
        path = root / skill / "SKILL.md"
        text = read_text(path)
        label = f"installed {root}/{skill}"
        if text is None:
            add(checks, status_if_missing, label, "not installed")
            continue
        missing = [marker for marker in SKILL_MARKERS[skill] if marker not in text]
        if missing:
            add(checks, "FAIL", label, f"installed copy is stale: {', '.join(missing)}")
        else:
            mismatch = compare_tree(ROOT / "skills" / skill, root / skill)
            if mismatch is None:
                add(checks, "OK", label, "installed copy matches canonical skill tree")
                continue
            status = "FAIL" if strict else "WARN"
            add(checks, status, label, mismatch)


def collect_checks(args: argparse.Namespace) -> list[Check]:
    checks: list[Check] = []

    for root in REPO_SKILL_ROOTS:
        for skill in REQUIRED_SKILLS:
            check_skill_file(checks, root, skill)
        for path, markers in SKILL_REFERENCE_MARKERS.items():
            check_contains(
                checks,
                root / path,
                markers,
                f"{root}/{path}",
            )

    for root in CANONICAL_COMPARE_ROOTS:
        for skill in REQUIRED_SKILLS:
            check_copy_parity(checks, root, skill)

    for path, label in MANIFESTS.items():
        check_manifest(checks, path, label)

    for path in MARKETPLACES:
        check_marketplace(checks, path)

    for path, markers in GUARD_FILES.items():
        check_contains(checks, path, markers, f"{path} residency rule")

    for path, markers in RUNNER_MARKERS.items():
        check_contains(checks, path, markers, f"{path} prompt residency")

    for path, markers in HOOK_FILES.items():
        check_contains(checks, path, markers, f"{path} residency hook")

    for path, markers in LATENT_STRUCTURE_FILES.items():
        check_contains(checks, path, markers, f"{path} latent-structure artifact")

    for path, markers in GENIUS_METHOD_EVAL_FILES.items():
        check_contains(checks, path, markers, f"{path} genius-method eval artifact")

    for path, markers in AGENTIC_LOOP_FILES.items():
        check_contains(checks, path, markers, f"{path} agentic-loop artifact")

    for path, markers in LOOP_ENGINEERING_FILES.items():
        check_contains(checks, path, markers, f"{path} loop-engineering artifact")

    for path, markers in INSTALL_SMOKE_FILES.items():
        check_contains(checks, path, markers, f"{path} install smoke artifact")

    check_standing_instruction(checks)

    if args.check_installed:
        home = Path.home()
        check_installed_root(checks, home / ".codex" / "skills", args.strict_installed)
        check_installed_root(checks, home / ".claude" / "skills", args.strict_installed)
        check_installed_root(checks, home / ".agents" / "skills", args.strict_installed)

    return checks


def inject_residency() -> int:
    """Plugin SessionStart residency: verify locally shipped skills, emit the
    standing instruction, and fail open so a degraded install never blocks a
    session from starting."""
    skills_root = ROOT / "skills"
    degraded: list[str] = []
    for skill in REQUIRED_SKILLS:
        text = read_text(skills_root / skill / "SKILL.md")
        if text is None:
            degraded.append(f"{skill}: missing")
            continue
        gaps = [marker for marker in SKILL_MARKERS[skill] if marker not in text]
        if gaps:
            degraded.append(f"{skill}: stale ({', '.join(gaps)})")
    print(STANDING_INSTRUCTION)
    if degraded:
        print("[fairy-tale] residency degraded: " + "; ".join(degraded), file=sys.stderr)
    return 0


def print_human(checks: list[Check]) -> None:
    for check in checks:
        print(f"{check.status:4} {check.name}: {check.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Fairy Tale skill/plugin residency before long agent runs."
    )
    parser.add_argument(
        "--check-installed",
        action="store_true",
        help="also inspect user-level ~/.codex, ~/.claude, and ~/.agents skill installs",
    )
    parser.add_argument(
        "--strict-installed",
        action="store_true",
        help="treat missing user-level installs as failures instead of warnings",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON results")
    parser.add_argument(
        "--inject",
        action="store_true",
        help="emit standing residency context for a plugin SessionStart hook (fail-open)",
    )
    args = parser.parse_args()

    if args.inject:
        return inject_residency()

    checks = collect_checks(args)
    failed = [check for check in checks if check.failed]

    if args.json:
        payload = {
            "ok": not failed,
            "root": str(ROOT),
            "checks": [check.__dict__ for check in checks],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_human(checks)
        print()
        if failed:
            print(f"Fairy Tale residency check failed: {len(failed)} failure(s).")
        else:
            print("Fairy Tale residency check passed.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
