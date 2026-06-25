#!/usr/bin/env python3
"""Fail-closed distribution-parity check for the Fairy Tale skill.

The canonical skill tree and its distribution mirrors must stay byte-identical,
and inline ``references/*.md`` links in SKILL.md must resolve. This enforces, in
CI, the 4-copy parity that was previously maintained by hand (and therefore
drifted under concurrent edits). Exits non-zero on any drift so a PR that
updates one copy but not all four fails fast.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Canonical skill tree + its distribution mirrors.
CANONICAL = ROOT / "skills" / "fairy-tale"
MIRRORS = (
    ROOT / ".claude" / "skills" / "fairy-tale",
    ROOT / ".agents" / "skills" / "fairy-tale",
    ROOT / "plugins" / "fairy-tale" / "skills" / "fairy-tale",
)

# Inline-reference form used inside SKILL.md, e.g. `references/process.md`.
REF_RE = re.compile(r"`(references/[A-Za-z0-9._/\-]+\.md)`")


def md_files(base: Path) -> dict[Path, Path]:
    """Map relative path -> absolute path for every *.md under ``base``."""
    return {p.relative_to(base): p for p in base.rglob("*.md") if p.is_file()}


def check_parity() -> list[str]:
    errors: list[str] = []
    if not CANONICAL.exists():
        return [f"canonical skill tree missing: {CANONICAL.relative_to(ROOT)}"]
    canonical = md_files(CANONICAL)
    for mirror in MIRRORS:
        rel_mirror = mirror.relative_to(ROOT)
        if not mirror.exists():
            errors.append(f"missing mirror: {rel_mirror}")
            continue
        mirrored = md_files(mirror)
        for rel in sorted(set(canonical) - set(mirrored)):
            errors.append(f"{rel_mirror}: missing {rel}")
        for rel in sorted(set(mirrored) - set(canonical)):
            errors.append(f"{rel_mirror}: extra {rel}")
        for rel in sorted(set(canonical) & set(mirrored)):
            if canonical[rel].read_bytes() != mirrored[rel].read_bytes():
                errors.append(f"{rel_mirror}: byte mismatch {rel}")
    return errors


def check_inline_refs() -> list[str]:
    errors: list[str] = []
    skill = CANONICAL / "SKILL.md"
    if not skill.exists():
        return [f"missing {skill.relative_to(ROOT)}"]
    for ref in sorted(set(REF_RE.findall(skill.read_text(encoding="utf-8")))):
        if not (CANONICAL / ref).exists():
            errors.append(f"SKILL.md dangling inline ref: {ref}")
    return errors


def main() -> int:
    errors = check_parity() + check_inline_refs()
    if errors:
        print("Fairy Tale distribution parity FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    copies = 1 + len(MIRRORS)
    print(
        f"Fairy Tale distribution parity OK: {copies} skill copies byte-identical "
        "(*.md) and SKILL.md inline references resolve."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
