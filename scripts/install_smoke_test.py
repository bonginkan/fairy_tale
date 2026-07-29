#!/usr/bin/env python3
"""Smoke-test skill-only installation references."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from skill_markdown_refs import (
    distributed_skill_names,
    validate_skill_markdown_refs,
)


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_INSTALLED_FILES = (
    Path("fairy-tale") / "references" / "loop-engineering-automation.md",
    Path("fairy-tale") / "references" / "feedback-governance.md",
    Path("fairy-tale") / "references" / "openmythos-external-adapter.md",
    Path("fairy-tale") / "references" / "similarity-refactoring-adapter.md",
    Path("fairy-tale")
    / "references"
    / "cards"
    / "e3-minimum-sufficient-execution-harness.md",
    Path("fairy-tale")
    / "references"
    / "process"
    / "helix-blocker-triage-record.md",
)


def run_install(
    target: Path,
    source: Path,
    *,
    force: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        "sh",
        str(source / "install.sh"),
        "--source",
        str(source),
        "--target",
        str(target),
        "--create",
        "--allow-outside-home",
    ]
    if force:
        command.append("--force")
    return subprocess.run(command, check=check, capture_output=True, text=True)


def file_digests(base: Path) -> dict[Path, str]:
    """Map relative path -> sha256 for every file under ``base``."""
    return {
        path.relative_to(base): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }


def installed_skill_names(target: Path) -> set[str]:
    if not target.is_dir():
        return set()
    return {
        entry.name
        for entry in target.iterdir()
        if (entry / "SKILL.md").is_file()
    }


def validate_distribution(target: Path, source_skills: Path) -> list[str]:
    """Compare what shipped against the source tree, name and byte.

    Presence alone cannot see the two failures that actually happen: a skill
    added to the tree but never distributed, and a destination copy that
    drifted from the source while keeping the same file count.
    """
    failures: list[str] = []
    expected = set(distributed_skill_names(source_skills))
    installed = installed_skill_names(target)

    for name in sorted(expected - installed):
        failures.append(f"source skill was not installed: {name}")
    for name in sorted(installed - expected):
        failures.append(f"installed skill is absent from the source: {name}")

    for name in sorted(expected & installed):
        source_files = file_digests(source_skills / name)
        installed_files = file_digests(target / name)
        for rel in sorted(set(source_files) - set(installed_files)):
            failures.append(f"{name}: source file was not installed: {rel}")
        for rel in sorted(set(installed_files) - set(source_files)):
            failures.append(f"{name}: installed file is absent from the source: {rel}")
        for rel in sorted(set(source_files) & set(installed_files)):
            if source_files[rel] != installed_files[rel]:
                failures.append(f"{name}: installed content differs from the source: {rel}")
    return failures


def validate_install(target: Path, source: Path) -> list[str]:
    failures = validate_distribution(target, source / "skills")

    for required in REQUIRED_INSTALLED_FILES:
        if not (target / required).exists():
            failures.append(f"missing required installed companion: {required}")

    ref_failures, _, _ = validate_skill_markdown_refs(target)
    failures.extend(ref_failures)
    return failures


def selftest_distribution_checks() -> tuple[list[str], int]:
    """Prove the comparison fails on the drift it exists to catch.

    A check never observed failing is indistinguishable from one that cannot
    fail, which is how a skill that shipped nowhere passed CI for weeks.
    """
    failures: list[str] = []
    controls = 0
    with tempfile.TemporaryDirectory(prefix="fairy-tale-install-control-") as tmp:
        root = Path(tmp)
        source_skills = root / "source"
        target = root / "target"
        for base in (source_skills, target):
            skill = base / "sample-skill"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("canonical\n")
            (skill / "reference.md").write_text("companion\n")

        controls += 1
        if validate_distribution(target, source_skills):
            failures.append("identical trees were reported as drift")

        drifted = target / "sample-skill" / "SKILL.md"
        drifted.write_text("drifted\n")
        controls += 1
        if not validate_distribution(target, source_skills):
            failures.append("content drift at an unchanged file count went unseen")
        drifted.write_text("canonical\n")

        uninstalled = target / "sample-skill" / "reference.md"
        uninstalled.unlink()
        controls += 1
        if not validate_distribution(target, source_skills):
            failures.append("a source file that never shipped went unseen")
        uninstalled.write_text("companion\n")

        added = source_skills / "later-skill"
        added.mkdir()
        (added / "SKILL.md").write_text("added after the target was built\n")
        controls += 1
        if not validate_distribution(target, source_skills):
            failures.append("a skill absent from the distribution went unseen")
        shutil.rmtree(added)

        stray = target / "stray-skill"
        stray.mkdir()
        (stray / "SKILL.md").write_text("no source counterpart\n")
        controls += 1
        if not validate_distribution(target, source_skills):
            failures.append("an installed skill with no source went unseen")
        shutil.rmtree(stray)
    return failures, controls


def run_update_path_controls(source: Path) -> list[str]:
    """Exercise what happens on the second run against a populated target.

    An installer that refuses every populated target can only ever install
    once, so a lane keeps whatever version it was first given and a skill
    added later never reaches it. These controls pin that contract down.
    """
    failures: list[str] = []
    source_skills = source / "skills"
    names = distributed_skill_names(source_skills)
    if not names:
        return ["no skills found to exercise the update path"]
    sample = names[-1]

    with tempfile.TemporaryDirectory(prefix="fairy-tale-install-update-") as tmp:
        target = Path(tmp) / "skills"
        run_install(target, source)
        baseline = {name: file_digests(target / name) for name in names}

        repeated = run_install(target, source, force=False, check=False)
        if repeated.returncode != 0:
            failures.append(
                "re-running over an identical target was refused: "
                f"rc={repeated.returncode}"
            )
        if {name: file_digests(target / name) for name in names} != baseline:
            failures.append("re-running over an identical target modified it")

        shutil.rmtree(target / sample)
        restored = run_install(target, source, force=False, check=False)
        if restored.returncode != 0:
            failures.append(
                f"a skill missing from the target was not installed: {sample}: "
                f"rc={restored.returncode}"
            )
        elif file_digests(target / sample) != baseline[sample]:
            failures.append(f"re-installed skill differs from the source: {sample}")

        drifted = target / sample / "SKILL.md"
        drifted.write_text(drifted.read_text() + "\ndrift\n")
        after_drift = file_digests(target / sample)
        refused = run_install(target, source, force=False, check=False)
        if refused.returncode != 2:
            failures.append(
                f"a drifted target was not refused: rc={refused.returncode}"
            )
        if file_digests(target / sample) != after_drift:
            failures.append("a refused run modified the target")

        repaired = run_install(target, source, force=True, check=False)
        if repaired.returncode != 0:
            failures.append(f"--force did not replace drift: rc={repaired.returncode}")
        elif file_digests(target / sample) != baseline[sample]:
            failures.append(f"--force left the skill unlike the source: {sample}")

        if len(names) >= 2:
            blocker = names[0]
            blocked = target / blocker / "SKILL.md"
            blocked.write_text(blocked.read_text() + "\ndrift\n")
            shutil.rmtree(target / sample)
            partial = run_install(target, source, force=False, check=False)
            if partial.returncode != 2:
                failures.append(
                    "a destination that cannot be replaced was not reported: "
                    f"rc={partial.returncode}"
                )
            if not (target / sample).is_dir():
                failures.append(
                    "a refused destination kept a later skill out of the target: "
                    f"{sample}"
                )
            run_install(target, source)

        linked_to = Path(tmp) / "elsewhere"
        shutil.copytree(source_skills / sample, linked_to)
        shutil.rmtree(target / sample)
        (target / sample).symlink_to(linked_to, target_is_directory=True)
        symlinked = run_install(target, source, force=False, check=False)
        if symlinked.returncode != 2:
            failures.append(
                f"a symlinked destination was not refused: rc={symlinked.returncode}"
            )
        if not (target / sample).is_symlink():
            failures.append("a refused symlinked destination was modified")
        forced = run_install(target, source, force=True, check=False)
        if forced.returncode != 0 or (target / sample).is_symlink():
            failures.append("--force did not replace a symlinked destination")
        elif file_digests(target / sample) != baseline[sample]:
            failures.append(f"--force left the replaced skill unlike the source: {sample}")
    return failures


def run_boundary_controls(source: Path) -> list[str]:
    """Refuse, before writing, the targets that resolve somewhere else.

    A boundary tested against the path as written let a symlinked target write
    outside it, and a target that resolved onto the source deleted the tree
    being installed while installing it.
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="fairy-tale-install-boundary-") as tmp:
        root = Path(tmp)
        home = root / "home"
        outside = root / "outside"
        home.mkdir()
        outside.mkdir()
        link = home / "skills-link"
        link.symlink_to(outside, target_is_directory=True)

        escaped = subprocess.run(
            [
                "sh",
                str(source / "install.sh"),
                "--source",
                str(source),
                "--target",
                str(link),
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home)},
        )
        if escaped.returncode == 0:
            failures.append("a symlinked target reaching outside HOME was accepted")
        if any(outside.iterdir()):
            failures.append("a target outside HOME was written to before refusal")

        # --create builds the missing part of the path under whatever the
        # existing part turns out to be, so the symlink need not be the target
        # itself to lead out of $HOME.
        buried = subprocess.run(
            [
                "sh",
                str(source / "install.sh"),
                "--source",
                str(source),
                "--target",
                str(link / "deep" / "skills"),
                "--create",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home)},
        )
        if buried.returncode == 0:
            failures.append("a symlinked ancestor was accepted with --create")
        if any(outside.iterdir()):
            failures.append("a target reached through a symlinked ancestor was written")

        # `..` in a part of the path that does not exist yet still applies
        # once the path is walked, so a target can climb out of $HOME through
        # a directory that is only about to be created.
        climbed = subprocess.run(
            [
                "sh",
                str(source / "install.sh"),
                "--source",
                str(source),
                "--target",
                f"{home}/new/../../outside/climbed/skills",
                "--create",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home)},
        )
        if climbed.returncode == 0:
            failures.append("a target climbing out of HOME with .. was accepted")
        if (outside / "climbed").exists():
            failures.append("a target that climbed out of HOME was written")

        inside = home / "nested" / "skills"
        allowed = subprocess.run(
            [
                "sh",
                str(source / "install.sh"),
                "--source",
                str(source),
                "--target",
                str(inside),
                "--create",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(home)},
        )
        if allowed.returncode != 0:
            failures.append(
                f"a target inside HOME was refused: rc={allowed.returncode}"
            )

        staged = root / "staged"
        staged.mkdir()
        shutil.copytree(source / "skills", staged / "skills")
        shutil.copy(source / "install.sh", staged / "install.sh")
        before = sorted(path.name for path in (staged / "skills").iterdir())
        overlapping = subprocess.run(
            [
                "sh",
                str(staged / "install.sh"),
                "--source",
                str(staged),
                "--target",
                str(staged / "skills"),
                "--allow-outside-home",
                "--force",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if overlapping.returncode == 0:
            failures.append("a target overlapping the source tree was accepted")
        after = sorted(path.name for path in (staged / "skills").iterdir())
        if after != before:
            failures.append(
                f"a refused run consumed the source tree: {before} -> {after}"
            )

        climbing = subprocess.run(
            [
                "sh",
                str(staged / "install.sh"),
                "--source",
                str(staged),
                "--target",
                f"{staged}/new/../skills",
                "--allow-outside-home",
                "--create",
                "--force",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if climbing.returncode == 0:
            failures.append("a target reaching the source through .. was accepted")
        reached = sorted(path.name for path in (staged / "skills").iterdir())
        if reached != before:
            failures.append(
                f"a target reaching the source through .. consumed it: "
                f"{before} -> {reached}"
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()

    source = args.source.resolve()
    with tempfile.TemporaryDirectory(prefix="fairy-tale-install-smoke-") as tmp:
        target = Path(tmp) / "skills"
        print(run_install(target, source).stdout, end="")
        failures = validate_install(target, source)
        failures.extend(run_update_path_controls(source))
        failures.extend(run_boundary_controls(source))
        control_failures, controls = selftest_distribution_checks()
        failures.extend(control_failures)
        if failures:
            for failure in failures:
                print(f"FAIL {failure}", file=sys.stderr)
            return 1
        print(
            f"OK install smoke passed for {target} "
            f"({controls} distribution controls)"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
