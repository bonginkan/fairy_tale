#!/usr/bin/env python3
"""Build a deterministic Fairy Tale skills tarball for GitHub Releases."""

from __future__ import annotations

import argparse
import gzip
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRS = [
    ROOT / "skills" / "fairy-tale",
    ROOT / "skills" / "fairy-tale-legal-feedback",
]
EXTRA_FILES = [
    ROOT / "LICENSE",
    ROOT / "NOTICE",
    ROOT / "README.md",
    ROOT / "README_ja.md",
    ROOT / "install.sh",
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


def build(output: Path) -> Path:
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
                for skill_dir in sorted(SKILL_DIRS):
                    for path in sorted(skill_dir.rglob("*")):
                        if path.is_file():
                            add_file(tar, path, root_name / path.relative_to(ROOT))
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
