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
}


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


def add(checks: list[Check], status: str, name: str, detail: str) -> None:
    checks.append(Check(status, name, detail))


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
    canonical = ROOT / "skills" / skill / "SKILL.md"
    copy = ROOT / copy_root / skill / "SKILL.md"
    canonical_text = read_text(canonical)
    copy_text = read_text(copy)
    label = f"{copy_root}/{skill} parity"
    if canonical_text is None or copy_text is None:
        add(checks, "FAIL", label, "cannot compare because one copy is missing")
    elif canonical_text == copy_text:
        add(checks, "OK", label, "matches canonical skill")
    else:
        add(checks, "FAIL", label, "drifted from canonical skills source")


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


def check_installed_root(checks: list[Check], root: Path, strict: bool) -> None:
    status_if_missing = "FAIL" if strict else "WARN"
    for skill in REQUIRED_SKILLS:
        path = root / skill / "SKILL.md"
        text = read_text(path)
        canonical_text = read_text(ROOT / "skills" / skill / "SKILL.md")
        label = f"installed {root}/{skill}"
        if text is None:
            add(checks, status_if_missing, label, "not installed")
            continue
        missing = [marker for marker in SKILL_MARKERS[skill] if marker not in text]
        if missing:
            add(checks, "FAIL", label, f"installed copy is stale: {', '.join(missing)}")
        elif canonical_text is not None and text != canonical_text:
            status = "FAIL" if strict else "WARN"
            add(checks, status, label, "installed copy differs from canonical skill")
        else:
            add(checks, "OK", label, "installed copy has required markers")


def collect_checks(args: argparse.Namespace) -> list[Check]:
    checks: list[Check] = []

    for root in REPO_SKILL_ROOTS:
        for skill in REQUIRED_SKILLS:
            check_skill_file(checks, root, skill)

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

    if args.check_installed:
        home = Path.home()
        check_installed_root(checks, home / ".codex" / "skills", args.strict_installed)
        check_installed_root(checks, home / ".claude" / "skills", args.strict_installed)
        check_installed_root(checks, home / ".agents" / "skills", args.strict_installed)

    return checks


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
    args = parser.parse_args()

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
