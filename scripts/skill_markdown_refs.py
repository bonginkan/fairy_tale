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
REFERENCE_DEFINITION_RE = re.compile(r"^ {0,3}\[")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
BLOCK_START_RE = re.compile(
    r"^ {0,3}(?:#{1,6}(?:[ \t]+|$)|>|(?:[*+-]|\d{1,9}[.)])(?:[ \t]+|$))"
)
THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$"
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


def _code_masked_lines(text: str, *, mask_indented: bool) -> list[str]:
    """Mask fenced code, plus indented code when scanning inline syntax."""
    masked: list[str] = []
    fence_char = ""
    fence_length = 0
    for line in text.splitlines():
        if fence_char:
            closing = re.match(
                rf"^ {{0,3}}{re.escape(fence_char)}"
                rf"{{{fence_length},}}[ \t]*$",
                line,
            )
            if closing:
                fence_char = ""
                fence_length = 0
            masked.append("")
            continue
        opening = FENCE_OPEN_RE.match(line)
        if opening:
            marker = opening.group("fence")
            fence_char = marker[0]
            fence_length = len(marker)
            masked.append("")
            continue
        if mask_indented and (line.startswith("    ") or line.startswith("\t")):
            masked.append("")
            continue
        masked.append(line)
    return masked


def _reference_label_and_tail(
    lines: list[str],
    start: int,
) -> tuple[str, str, int] | None:
    """Parse a possibly multiline reference label and its post-colon tail."""
    opening = REFERENCE_DEFINITION_RE.match(lines[start])
    if not opening:
        return None
    label: list[str] = []
    line_index = start
    offset = opening.end()
    while line_index < len(lines):
        line = lines[line_index]
        if line_index > start:
            if not line.strip():
                return None
            label.append(" ")
            offset = 0
        escaped = False
        while offset < len(line):
            char = line[offset]
            if escaped:
                label.append(char)
                escaped = False
            elif char == "\\":
                label.append(char)
                escaped = True
            elif char == "[":
                return None
            elif char == "]":
                remainder = line[offset + 1 :]
                if not remainder.startswith(":"):
                    return None
                normalized = " ".join("".join(label).split()).casefold()
                if not normalized or len(normalized) > 999:
                    return None
                return normalized, remainder[1:].lstrip(" \t"), line_index
            else:
                label.append(char)
            offset += 1
        line_index += 1
    return None


def _destination_and_remainder(
    value: str,
) -> tuple[str, str, bool] | None:
    """Parse one CommonMark destination and retain its separator state."""
    value = value.lstrip(" \t")
    if not value:
        return None
    if value.startswith("<"):
        escaped = False
        for index, char in enumerate(value[1:], start=1):
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "<":
                return None
            elif char == ">":
                remainder = value[index + 1 :]
                if not remainder.strip(" \t"):
                    remainder = ""
                separated = not remainder or remainder[0] in " \t"
                return value[: index + 1], remainder, separated
        return None

    escaped = False
    depth = 0
    end = 0
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char in " \t":
            break
        elif char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return None
            depth -= 1
        elif char in "<>":
            return None
        end = index + 1
    if end == 0 or depth:
        return None
    remainder = value[end:]
    if not remainder.strip(" \t"):
        remainder = ""
    separated = not remainder or remainder[0] in " \t"
    return value[:end], remainder, separated


def _title_end(
    lines: list[str],
    start: int,
    value: str,
) -> int | None:
    """Return the final line of a valid, blank-free CommonMark title."""
    value = value.lstrip(" \t")
    pairs = {'"': '"', "'": "'", "(": ")"}
    closer = pairs.get(value[:1])
    if closer is None:
        return None
    line_index = start
    offset = 1
    while line_index < len(lines):
        line = value if line_index == start else lines[line_index]
        if line_index > start and not line.strip():
            return None
        escaped = False
        while offset < len(line):
            char = line[offset]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == closer:
                if line[offset + 1 :].strip(" \t"):
                    return None
                return line_index
            elif closer == ")" and char == "(":
                return None
            offset += 1
        line_index += 1
        offset = 0
    return None


def _parse_reference_definition(
    lines: list[str],
    start: int,
) -> tuple[str, str, int] | None:
    """Parse one complete definition and return label, destination, line count."""
    label_and_tail = _reference_label_and_tail(lines, start)
    if label_and_tail is None:
        return None
    label, tail, line_index = label_and_tail
    destination = _destination_and_remainder(tail)
    if destination is None:
        if tail or line_index + 1 >= len(lines):
            return None
        line_index += 1
        destination = _destination_and_remainder(lines[line_index])
        if destination is None:
            return None

    raw_destination, remainder, separated = destination
    end_index = line_index
    if remainder:
        if not separated:
            return None
        title_end = _title_end(lines, line_index, remainder)
        if title_end is None:
            return None
        end_index = title_end
    elif line_index + 1 < len(lines):
        next_line = lines[line_index + 1].lstrip(" \t")
        if next_line[:1] in {'"', "'", "("}:
            title_end = _title_end(lines, line_index + 1, next_line)
            if title_end is not None:
                end_index = title_end
    return label, raw_destination, end_index - start + 1


def _reference_definition_destinations(text: str) -> list[str]:
    """Extract first-wins definitions without crossing code or paragraphs."""
    lines = _code_masked_lines(text, mask_indented=False)
    definitions: dict[str, str] = {}
    paragraph_open = False
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            paragraph_open = False
            index += 1
            continue

        if not paragraph_open:
            definition = _parse_reference_definition(lines, index)
            if definition is not None:
                label, destination, consumed = definition
                definitions.setdefault(label, destination)
                paragraph_open = False
                index += consumed
                continue

        if (
            line.startswith("    ")
            or line.startswith("\t")
            or BLOCK_START_RE.match(line)
            or THEMATIC_BREAK_RE.match(line)
        ):
            paragraph_open = False
        else:
            paragraph_open = True
        index += 1
    return list(definitions.values())


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
    inline_text = "\n".join(_code_masked_lines(text, mask_indented=True))
    for match in INLINE_CODE_RE.finditer(inline_text):
        raw = match.group("value").strip()
        if (
            match.start() > 0
            and inline_text[match.start() - 1] == "["
            and inline_text[match.end() :].startswith("](")
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
    destinations = [
        match.group("destination")
        for match in MARKDOWN_LINK_RE.finditer(inline_text)
    ]
    destinations.extend(_reference_definition_destinations(text))
    for destination in destinations:
        raw = destination.strip().strip("<>")
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
            "\n"
            "[local-ref]: references/local.md \"Local definition\"\n"
            "[multiline-ref]:\n"
            "  references/local.md\n"
            "[angle-ref]: <references/local.md>\n"
            "[next-title-ref]: references/local.md\n"
            "  \"Local title\"\n"
            "[spaced-next-title-ref]:\n"
            "  references/local.md  \n"
            "  'Spaced local title'\n"
            "[multiline-title-ref]: references/local.md '\n"
            "Local\n"
            "definition\n"
            "'\n"
            "[\n"
            "multiline-label\n"
            "]: references/local.md\n"
            "[external-ref]: https://example.com/guide.md\n"
            "[duplicate-ref]: references/local.md\n"
            "[duplicate-ref]: references/missing.md\n"
            "[invalid-trailing]: references/missing.md \"title\" trailing\n"
            "\n"
            "[local via definition][local-ref]\n"
            "```\n"
            "[fenced-ref]: references/missing.md\n"
            "`references/missing.md`\n"
            "[fenced](references/missing.md)\n"
            "```\n"
            "Paragraph remains open\n"
            "[paragraph-ref]: references/missing.md\n"
            "\n"
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
            base + "\n[missing-ref]: references/missing.md\n",
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

        alpha_skill.write_text(
            base + "\n[missing-multiline]:\n  references/missing.md\n",
            encoding="utf-8",
        )
        findings, _, _ = validate_skill_markdown_refs(
            package_root, ("alpha", "beta")
        )
        controls += 1
        if not any(
            "references/missing.md is dangling" in item for item in findings
        ):
            errors.append("multiline reference-style link was not rejected")

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
