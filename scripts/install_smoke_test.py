#!/usr/bin/env python3
"""Smoke-test skill-only installation references."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from skill_markdown_refs import (
    DISTRIBUTED_SKILL_NAMES,
    validate_skill_markdown_refs,
)


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILLS = DISTRIBUTED_SKILL_NAMES
REQUIRED_INSTALLED_FILES = (
    Path("fairy-tale") / "references" / "loop-engineering-automation.md",
    Path("fairy-tale") / "references" / "feedback-governance.md",
    Path("fairy-tale") / "references" / "openmythos-external-adapter.md",
    Path("fairy-tale") / "references" / "similarity-refactoring-adapter.md",
)
def run_install(target: Path, source: Path) -> None:
    subprocess.run(
        [
            "sh",
            str(source / "install.sh"),
            "--source",
            str(source),
            "--target",
            str(target),
            "--create",
            "--force",
            "--allow-outside-home",
        ],
        check=True,
    )


def validate_install(target: Path) -> list[str]:
    failures: list[str] = []
    for skill in REQUIRED_SKILLS:
        skill_file = target / skill / "SKILL.md"
        if not skill_file.exists():
            failures.append(f"missing installed skill: {skill_file}")

    for required in REQUIRED_INSTALLED_FILES:
        if not (target / required).exists():
            failures.append(f"missing required installed companion: {required}")

    ref_failures, _, _ = validate_skill_markdown_refs(target)
    failures.extend(ref_failures)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()

    source = args.source.resolve()
    with tempfile.TemporaryDirectory(prefix="fairy-tale-install-smoke-") as tmp:
        target = Path(tmp) / "skills"
        run_install(target, source)
        failures = validate_install(target)
        if failures:
            for failure in failures:
                print(f"FAIL {failure}", file=sys.stderr)
            return 1
        print(f"OK install smoke passed for {target}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
