#!/usr/bin/env python3
"""Build a deterministic Fairy Tale skills tarball for GitHub Releases."""

from __future__ import annotations

import argparse
import gzip
import json
import tarfile
from pathlib import Path

import fairy_tale_residency_check


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRS = [
    ROOT / "skills" / "fairy-tale",
    ROOT / "skills" / "fairy-tale-benchmark-feedback",
    ROOT / "skills" / "fairy-tale-legal-feedback",
]
EXTRA_FILES = [
    ROOT / "LICENSE",
    ROOT / "NOTICE",
    ROOT / "README.md",
    ROOT / "README_ja.md",
    ROOT / "install.sh",
]
PACKAGE_REFERENCE_FILES = [
    ROOT / "adapters" / "workflow-scoreboard.adapter.json",
    ROOT / "docs" / "fairy-profile.md",
    ROOT / "docs" / "fairy-fusion-auto-trigger.md",
    ROOT / "docs" / "loop-engineering-automation.md",
    ROOT / "docs" / "task-artifacts.md",
    ROOT / "docs" / "workflow-impact-scoreboard.md",
    ROOT / "docs" / "skill-budget" / "routing-eval-20260702.json",
    ROOT / "examples" / "workflow-scoreboard.json",
    ROOT / "examples" / "workflow-scoreboard" / "benchmark-baseline.json",
    ROOT / "examples" / "workflow-scoreboard" / "benchmark-fairy-tale.json",
    ROOT / "examples" / "workflow-scoreboard" / "normal-baseline.json",
    ROOT / "examples" / "workflow-scoreboard" / "normal-fairy-tale.json",
    ROOT / "schemas" / "fairy-profile.schema.json",
    ROOT / "schemas" / "fairy-fusion-auto-check-input.schema.json",
    ROOT / "schemas" / "fairy-fusion-trigger-decision.schema.json",
    ROOT / "schemas" / "repo-profile-snapshot.schema.json",
    ROOT / "schemas" / "task-card.schema.json",
    ROOT / "schemas" / "validation-ledger.schema.json",
    ROOT / "schemas" / "workflow-impact-scoreboard.schema.json",
    ROOT / "scripts" / "task_artifacts.py",
    ROOT / "scripts" / "fairy_fusion_review.py",
    ROOT / "scripts" / "workflow_scoreboard.py",
]


def version() -> str:
    manifest = json.loads((ROOT / "plugins" / "fairy-tale" / ".codex-plugin" / "plugin.json").read_text())
    return str(manifest["version"])


def add_file(tar: tarfile.TarFile, source: Path, arcname: Path) -> None:
    info = tar.gettarinfo(str(source), str(arcname))
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    if source.is_file():
        with source.open("rb") as handle:
            tar.addfile(info, handle)
    else:
        tar.addfile(info)


def validate_residency() -> None:
    args = argparse.Namespace(check_installed=False, strict_installed=False, json=False, inject=False)
    checks = fairy_tale_residency_check.collect_checks(args)
    failures = [check for check in checks if check.failed]
    if failures:
        detail = "; ".join(f"{check.name}: {check.detail}" for check in failures[:5])
        raise SystemExit(f"residency check failed before packaging: {detail}")


def validate_package(output: Path, root_name: Path) -> None:
    expected = {
        str(root_name / path.relative_to(ROOT))
        for path in PACKAGE_REFERENCE_FILES
        if path.exists()
    }
    with tarfile.open(output, "r:gz") as tar:
        names = set(tar.getnames())
    missing = sorted(expected - names)
    if missing:
        raise SystemExit(
            "package missing required reference files: " + ", ".join(missing)
        )


def build(output: Path) -> Path:
    validate_residency()
    package_version = version()
    root_name = Path(f"fairy-tale-skills-{package_version}")
    output = output or (ROOT / "dist" / f"{root_name}.tar.gz")
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for source in sorted(EXTRA_FILES):
                    if source.exists():
                        add_file(tar, source, root_name / source.name)
                for source in sorted(PACKAGE_REFERENCE_FILES):
                    if source.exists():
                        add_file(tar, source, root_name / source.relative_to(ROOT))
                for skill_dir in sorted(SKILL_DIRS):
                    for path in sorted(skill_dir.rglob("*")):
                        if path.is_file():
                            add_file(tar, path, root_name / path.relative_to(ROOT))
    validate_package(output, root_name)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = build(args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
