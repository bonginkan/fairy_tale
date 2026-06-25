#!/usr/bin/env python3
"""Smoke-test skill-only installation references."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILLS = (
    "fairy-tale",
    "fairy-tale-benchmark-feedback",
    "fairy-tale-legal-feedback",
)
REQUIRED_INSTALLED_FILES = (
    Path("fairy-tale") / "references" / "loop-engineering-automation.md",
    Path("fairy-tale") / "references" / "feedback-governance.md",
    Path("fairy-tale") / "references" / "openmythos-external-adapter.md",
    Path("fairy-tale") / "references" / "similarity-refactoring-adapter.md",
)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


def inline_markdown_refs(skill_file: Path) -> list[Path]:
    refs: list[Path] = []
    text = skill_file.read_text(encoding="utf-8")
    for match in INLINE_CODE_RE.finditer(text):
        raw = match.group(1).strip()
        if "://" in raw or raw.startswith("#") or not raw.endswith(".md"):
            continue
        if any(char.isspace() for char in raw):
            continue
        refs.append(Path(raw))
    return sorted(set(refs))


def resolve_ref(skill_dir: Path, ref: Path) -> Path:
    if ref.is_absolute():
        return ref
    return (skill_dir / ref).resolve()


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

    fairy_skill_dir = target / "fairy-tale"
    fairy_skill_file = fairy_skill_dir / "SKILL.md"
    if not fairy_skill_file.exists():
        return failures

    for ref in inline_markdown_refs(fairy_skill_file):
        path = resolve_ref(fairy_skill_dir, ref)
        try:
            path.relative_to(target.resolve())
        except ValueError:
            failures.append(f"reference escapes install target: {ref}")
            continue
        if not path.exists():
            failures.append(f"missing markdown reference from SKILL.md: {ref}")
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
