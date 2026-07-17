#!/usr/bin/env python3
"""Resolve inline Markdown references inside a distributable skill package."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from task_artifacts import ArtifactError, exact_path_entry


INLINE_CODE_RE = re.compile(r"(?P<fence>`+)(?P<value>[^`\n]+)(?P=fence)")
MARKDOWN_LINK_RE = re.compile(
    r"""\]\(\s*(?P<destination><[^>\n]+>|[^\s)\n]+)"""
    r"""(?:\s+[^)\n]+)?\s*\)"""
)
REFERENCE_DEFINITION_RE = re.compile(
    r"""^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*"""
    r"""(?P<destination><[^>\n]+>|[^\s\n]+)(?:[ \t]+.*)?$""",
    re.MULTILINE,
)
DISTRIBUTED_SKILL_NAMES = (
    "fairy-tale",
    "fairy-tale-benchmark-feedback",
    "fairy-tale-legal-feedback",
)


def skill_dirs(
    package_root: Path,
    skill_names: tuple[str, ...],
) -> tuple[list[Path], list[str]]:
    """Return exact, non-symlink distributable skill roots and findings."""
    directories: list[Path] = []
    errors: list[str] = []
    for name in sorted(skill_names):
        try:
            skill_dir = exact_path_entry(
                package_root / name,
                f"distributable skill root {name}",
                allow_missing=True,
                expected_kind="directory",
            )
            if skill_dir is None:
                errors.append(f"missing distributable skill: {name}/SKILL.md")
                continue
            skill_file = exact_path_entry(
                skill_dir / "SKILL.md",
                f"distributable skill entrypoint {name}/SKILL.md",
                allow_missing=True,
            )
            if skill_file is None:
                errors.append(f"missing distributable skill: {name}/SKILL.md")
                continue
            directories.append(skill_dir)
        except ArtifactError as exc:
            errors.append(str(exc))
    return directories, errors


def _candidate_paths(
    package_root: Path,
    skill_dir: Path,
    source: Path,
    ref: Path,
) -> list[Path]:
    candidates = (
        source.parent / ref,
        skill_dir / ref,
        package_root / ref,
    )
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _exact_candidate(
    package_root: Path,
    candidate: Path,
    label: str,
) -> tuple[Path | None, str | None]:
    try:
        parts = candidate.relative_to(package_root).parts
    except ValueError:
        return None, "escapes package root"

    current = package_root
    meaningful = [part for part in parts if part not in ("", ".")]
    for index, part in enumerate(meaningful):
        if part == "..":
            if current == package_root:
                return None, "escapes package root"
            current = current.parent
            continue
        expected_kind = "file" if index == len(meaningful) - 1 else "directory"
        try:
            resolved = exact_path_entry(
                current / part,
                label,
                allow_missing=True,
                expected_kind=expected_kind,
            )
        except ArtifactError as exc:
            return None, str(exc)
        if resolved is None:
            return None, None
        current = resolved
    return current, None


def markdown_references(
    package_root: Path,
    skill_dir: Path,
    source: Path,
) -> list[Path]:
    """Extract local ``*.md`` code spans and Markdown link destinations.

    A bare unresolved filename such as an output ``report.md`` is not assumed
    to be a package reference. Paths with a directory component are explicit
    references, as are bare filenames that resolve relative to the source,
    skill, or package root.
    """
    refs: set[Path] = set()
    text = source.read_text(encoding="utf-8")
    for match in INLINE_CODE_RE.finditer(text):
        raw = match.group("value").strip()
        if (
            match.start() > 0
            and text[match.start() - 1] == "["
            and text[match.end() :].startswith("](")
        ):
            continue
        if (
            "://" in raw
            or raw.startswith("#")
            or not raw.endswith(".md")
            or any(char.isspace() for char in raw)
        ):
            continue
        ref = Path(raw)
        candidates = _candidate_paths(package_root, skill_dir, source, ref)
        if "/" in raw or "\\" in raw or any(path.is_file() for path in candidates):
            refs.add(ref)
    for pattern in (MARKDOWN_LINK_RE, REFERENCE_DEFINITION_RE):
        for match in pattern.finditer(text):
            raw = match.group("destination").strip().strip("<>")
            if "://" in raw or raw.startswith("#"):
                continue
            raw = raw.split("#", 1)[0]
            if raw.endswith(".md"):
                refs.add(Path(raw))
    return sorted(refs, key=lambda path: path.as_posix())


def validate_skill_markdown_refs(
    package_root: Path,
    skill_names: tuple[str, ...] = DISTRIBUTED_SKILL_NAMES,
) -> tuple[list[str], int, int]:
    """Validate every inline Markdown reference in every packaged skill."""
    package_root = package_root.resolve()
    errors: list[str] = []
    checked_files = 0
    checked_refs = 0
    directories, skill_errors = skill_dirs(package_root, skill_names)
    errors.extend(skill_errors)
    if not directories:
        return errors, 0, 0

    for skill_dir in directories:
        for source in sorted(skill_dir.rglob("*.md")):
            if not source.is_file():
                continue
            checked_files += 1
            source_label = source.relative_to(package_root).as_posix()
            if source.is_symlink():
                errors.append(f"{source_label}: Markdown source cannot be a symlink")
                continue
            for ref in markdown_references(package_root, skill_dir, source):
                checked_refs += 1
                ref_label = ref.as_posix()
                if ref.is_absolute() or "\\" in str(ref):
                    errors.append(
                        f"{source_label}: unsafe Markdown reference: {ref_label}"
                    )
                    continue
                contained: list[Path] = []
                candidate_errors: list[str] = []
                for candidate in _candidate_paths(
                    package_root, skill_dir, source, ref
                ):
                    resolved, candidate_error = _exact_candidate(
                        package_root,
                        candidate,
                        f"Markdown reference {ref_label}",
                    )
                    if candidate_error and candidate_error not in candidate_errors:
                        candidate_errors.append(candidate_error)
                    if resolved is not None and resolved not in contained:
                        contained.append(resolved)
                if len(contained) > 1:
                    targets = ", ".join(
                        path.relative_to(package_root).as_posix()
                        for path in contained
                    )
                    errors.append(
                        f"{source_label}: ambiguous Markdown reference "
                        f"{ref_label}: {targets}"
                    )
                elif not contained and candidate_errors:
                    errors.append(
                        f"{source_label}: Markdown reference {ref_label}: "
                        + "; ".join(candidate_errors)
                    )
                elif not contained:
                    errors.append(
                        f"{source_label}: Markdown reference "
                        f"{ref_label} is dangling"
                    )
    return errors, checked_files, checked_refs


def selftest_skill_markdown_refs() -> tuple[list[str], int]:
    """Exercise positive, dangling-code, dangling-link, and escape controls."""
    errors: list[str] = []
    controls = 0
    with tempfile.TemporaryDirectory(prefix="fairy-markdown-refs-") as tmp:
        package_root = Path(tmp) / "skills"
        alpha = package_root / "alpha"
        beta = package_root / "beta"
        references = alpha / "references"
        references.mkdir(parents=True)
        beta.mkdir(parents=True)
        (references / "local.md").write_text("# Local\n", encoding="utf-8")
        (beta / "SKILL.md").write_text("# Beta\n", encoding="utf-8")
        alpha_skill = alpha / "SKILL.md"
        base = (
            "# Alpha\n\n"
            "`references/local.md`\n"
            "`../beta/SKILL.md`\n"
            "[local](references/local.md)\n"
            "[local with title](references/local.md \"Local reference\")\n"
            "[local-ref]: references/local.md \"Local definition\"\n"
            "[local via definition][local-ref]\n"
            "``references/local.md``\n"
            "`report.md`\n"
            "[external](https://example.com/guide.md)\n"
        )
        alpha_skill.write_text(base, encoding="utf-8")

        findings, _, _ = validate_skill_markdown_refs(
            package_root, ("alpha", "beta")
        )
        controls += 1
        if findings:
            errors.append("valid package reference fixture was rejected")

        alpha_skill.write_text(
            base + "`references/missing.md`\n", encoding="utf-8"
        )
        findings, _, _ = validate_skill_markdown_refs(
            package_root, ("alpha", "beta")
        )
        controls += 1
        if not any("references/missing.md is dangling" in item for item in findings):
            errors.append("dangling inline-code reference was not rejected")

        alpha_skill.write_text(
            base + "[missing](references/missing.md)\n", encoding="utf-8"
        )
        findings, _, _ = validate_skill_markdown_refs(
            package_root, ("alpha", "beta")
        )
        controls += 1
        if not any("references/missing.md is dangling" in item for item in findings):
            errors.append("dangling Markdown link was not rejected")

        outside = Path(tmp) / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        alpha_skill.write_text(base + "`../../outside.md`\n", encoding="utf-8")
        findings, _, _ = validate_skill_markdown_refs(
            package_root, ("alpha", "beta")
        )
        controls += 1
        if not any("../../outside.md: escapes package root" in item for item in findings):
            errors.append("escaping Markdown reference was not rejected")

        alpha_skill.write_text(
            base + "`REFERENCES/local.md`\n", encoding="utf-8"
        )
        findings, _, _ = validate_skill_markdown_refs(
            package_root, ("alpha", "beta")
        )
        controls += 1
        if not any("name must match exactly" in item for item in findings):
            errors.append("case-alias Markdown reference was not rejected")

        alpha_skill.write_text(
            base + "[missing-ref]: references/missing.md\n",
            encoding="utf-8",
        )
        findings, _, _ = validate_skill_markdown_refs(
            package_root, ("alpha", "beta")
        )
        controls += 1
        if not any(
            "references/missing.md is dangling" in item for item in findings
        ):
            errors.append("dangling reference-style link was not rejected")

        linked_source = Path(tmp) / "linked-skill-source"
        linked_source.mkdir()
        (linked_source / "SKILL.md").write_text("# Linked\n", encoding="utf-8")
        (package_root / "linked").symlink_to(
            linked_source, target_is_directory=True
        )
        findings, _, _ = validate_skill_markdown_refs(package_root, ("linked",))
        controls += 1
        if not any("skill root linked cannot be a symlink" in item for item in findings):
            errors.append("symlinked distributable skill root was not rejected")
    return errors, controls
