#!/usr/bin/env python3
"""Fail-closed distribution-parity check for the Fairy Tale skill.

The canonical skill tree and its distribution mirrors must stay byte-identical,
and inline Markdown references across every distributable skill file must
resolve. This enforces, in CI, the 4-copy parity that was previously maintained
by hand (and therefore drifted under concurrent edits). Exits non-zero on any
drift so a PR that updates one copy but not all four fails fast.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from skill_markdown_refs import (
    distributed_skill_names,
    selftest_skill_markdown_refs,
    validate_skill_markdown_refs,
)

ROOT = Path(__file__).resolve().parents[1]
SKILL_PACKAGE_ROOT = ROOT / "skills"

# Never searched for mirrors: VCS internals, build output, vendored trees.
DISCOVERY_SKIP_DIRS = {".git", "__pycache__", "dist", "node_modules", "target"}


def mirror_roots(root: Path = ROOT) -> tuple[Path, ...]:
    """Discover every skills/ tree that mirrors the canonical one.

    Discovered, never listed. A roster of mirror roots is the same defect the
    skill roster was: a root added later is simply never checked, and a line
    deleted from the list takes its coverage with it without anything failing.
    """
    package_root = root / "skills"
    names = set(distributed_skill_names(package_root))
    if not names:
        return ()
    roots: list[Path] = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in DISCOVERY_SKIP_DIRS]
        here = Path(dirpath)
        if here.name != "skills" or here == package_root:
            continue
        if any((here / name).is_dir() for name in names):
            roots.append(here)
    return tuple(sorted(roots))

# Companion artifacts (adapters / schemas / scripts / docs / resources / ledgers /
# crates / ...) are also mirrored into the plugin package. The skill *.md parity
# above did NOT cover them, so mirror drift slipped through (fairy_tale #7 / #22;
# seen on PR #46 and #9). Discovery is fully dynamic from the plugin side: every
# file the plugin ships whose root counterpart exists is a "mirrored companion"
# and must stay byte-identical. No hardcoded dir allow-list -- a newly mirrored
# class (adapters, docs, resources, crates, ...) is covered automatically. A file
# present in only one side is NOT a mirror (root-only tooling is never
# force-mirrored; plugin-only files have no source to drift from).
PLUGIN_ROOT = ROOT / "plugins" / "fairy-tale"
COMPANION_SKIP_PARTS = {"__pycache__"}
COMPANION_SKIP_FILES = {".DS_Store"}
# skills/ parity is already owned by check_parity() (the 4-copy *.md tree), so it
# is excluded here to avoid double-coverage. Verified: the plugin skills/ subtree
# ships no non-.md files, so nothing is lost by delegating it to check_parity().
COMPANION_EXCLUDE_TOP = {"skills"}

def md_files(base: Path) -> dict[Path, Path]:
    """Map relative path -> absolute path for every *.md under ``base``."""
    return {p.relative_to(base): p for p in base.rglob("*.md") if p.is_file()}


def check_parity(root: Path = ROOT) -> tuple[list[str], int, int]:
    errors: list[str] = []
    package_root = root / "skills"
    if not package_root.is_dir():
        return [f"canonical skill tree missing: {package_root.name}"], 0, 0
    names = distributed_skill_names(package_root)
    if not names:
        return [f"no skills found under {package_root.name}"], 0, 0
    roots = mirror_roots(root)
    if not roots:
        # Nothing to compare against reads exactly like nothing wrong.
        return [f"no distribution mirrors found under {root}"], len(names), 0
    for name in names:
        canonical = md_files(package_root / name)
        for mirror_root in roots:
            mirror = mirror_root / name
            rel_mirror = mirror.relative_to(root)
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
    return errors, len(names), len(roots)


def selftest_parity_discovery() -> tuple[list[str], int]:
    """Prove the mirror check fails when there is nothing left to compare.

    A parity run that found no mirrors reported success, so a mirror set that
    shrank -- or vanished -- looked exactly like a mirror set that agreed.
    """
    failures: list[str] = []
    controls = 0
    with tempfile.TemporaryDirectory(prefix="fairy-tale-parity-control-") as tmp:
        root = Path(tmp)
        canonical = root / "skills" / "sample-skill"
        canonical.mkdir(parents=True)
        (canonical / "SKILL.md").write_text("canonical\n")
        mirror = root / ".claude" / "skills" / "sample-skill"
        mirror.mkdir(parents=True)
        (mirror / "SKILL.md").write_text("canonical\n")

        controls += 1
        errors, skills, roots = check_parity(root)
        if errors or (skills, roots) != (1, 1):
            failures.append(
                "a discovered, matching mirror was not accepted: "
                f"{errors} skills={skills} roots={roots}"
            )

        (mirror / "SKILL.md").write_text("drifted\n")
        controls += 1
        if not check_parity(root)[0]:
            failures.append("drift in a discovered mirror went unseen")
        (mirror / "SKILL.md").write_text("canonical\n")

        shutil.rmtree(root / ".claude")
        controls += 1
        errors, _, roots = check_parity(root)
        if not errors or roots:
            failures.append("a run with no mirror left was reported as success")
    return failures, controls


def companion_candidates() -> list[Path]:
    """Root-relative paths the plugin ships that also exist at the repo root.

    Discovered from the plugin tree so the set of mirrored dirs is never
    hardcoded: anything under plugins/fairy-tale/ (except the skills/ tree, which
    check_parity() owns) whose root counterpart exists is a mirrored companion.
    """
    rels: list[Path] = []
    if not PLUGIN_ROOT.is_dir():
        return rels
    for p in sorted(PLUGIN_ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(PLUGIN_ROOT)
        if COMPANION_SKIP_PARTS & set(rel.parts):
            continue
        if p.name in COMPANION_SKIP_FILES:
            continue
        if rel.parts and rel.parts[0] in COMPANION_EXCLUDE_TOP:
            continue
        if (ROOT / rel).is_file():
            rels.append(rel)
    return rels


def check_companion_parity() -> tuple[list[str], int]:
    """Byte-parity for every artifact the plugin mirrors from the repo root.

    A file is a mirrored companion iff it exists in BOTH the root and the plugin,
    so root-only tooling is never force-mirrored -- but any file the plugin does
    ship must match its root source exactly, or it fails fast.
    """
    errors: list[str] = []
    checked = 0
    for rel in companion_candidates():
        checked += 1
        if (ROOT / rel).read_bytes() != (PLUGIN_ROOT / rel).read_bytes():
            errors.append(f"companion mirror drift: {rel} != plugins/fairy-tale/{rel}")
    return errors, checked


def main() -> int:
    companion_errors, companions = check_companion_parity()
    ref_errors, markdown_files, markdown_refs = validate_skill_markdown_refs(
        SKILL_PACKAGE_ROOT
    )
    ref_selftest_errors, ref_controls = selftest_skill_markdown_refs()
    parity_errors, skills, roots = check_parity()
    discovery_errors, discovery_controls = selftest_parity_discovery()
    errors = (
        parity_errors
        + discovery_errors
        + ref_errors
        + ref_selftest_errors
        + companion_errors
    )
    if errors:
        print("Fairy Tale distribution parity FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    copies = skills * (1 + roots)
    print(
        f"Fairy Tale distribution parity OK: {copies} skill copies byte-identical "
        f"(*.md) across {skills} skills and {roots} discovered mirrors "
        f"({discovery_controls} discovery controls), {companions} mirrored "
        f"companion artifacts byte-identical, and "
        f"{markdown_refs} Markdown references across {markdown_files} packaged "
        f"Markdown files resolve ({ref_controls} negative/positive controls)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
