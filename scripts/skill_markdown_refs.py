#!/usr/bin/env python3
"""Resolve inline Markdown references inside a distributable skill package."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from task_artifacts import ArtifactError, exact_path_entry


REFERENCE_DEFINITION_RE = re.compile(r"^ {0,3}\[")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
BLOCK_QUOTE_RE = re.compile(r"^ {0,3}>[ \t]?")
LIST_MARKER_RE = re.compile(
    r"^(?: {0,3})(?:[*+-]|\d{1,9}[.)])(?:[ \t]{1,4}|$)"
)
BLOCK_START_RE = re.compile(
    r"^ {0,3}(?:#{1,6}(?:[ \t]+|$)|>|(?:[*+-]|\d{1,9}[.)])(?:[ \t]+|$))"
)
THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$"
)
TABLE_DELIMITER_RE = re.compile(
    r"^ {0,3}\|?(?:[ \t]*:?-+:?[ \t]*\|)+"
    r"[ \t]*:?-+:?[ \t]*\|?[ \t]*$"
)
HTML_RAW_TAG_RE = re.compile(
    r"^ {0,3}<(?P<tag>pre|script|style|textarea)(?:[ \t>]|$)",
    re.IGNORECASE,
)
HTML_BLOCK_TAG_RE = re.compile(
    r"^ {0,3}</?(?:address|article|aside|base|basefont|blockquote|body|"
    r"caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|"
    r"fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|"
    r"header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|"
    r"noframes|ol|optgroup|option|p|param|search|section|summary|table|"
    r"tbody|td|tfoot|th|thead|title|tr|track|ul)(?:[ \t/>]|$)",
    re.IGNORECASE,
)
DISTRIBUTED_SKILL_NAMES = (
    "fairy-tale",
    "fairy-tale-benchmark-feedback",
    "fairy-tale-legal-feedback",
)
COMMONMARK_ESCAPABLE = frozenset(
    "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
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


def _strip_block_quote_prefixes(line: str) -> tuple[str, int]:
    """Return block-quote child content and its container depth."""
    depth = 0
    while True:
        marker = BLOCK_QUOTE_RE.match(line)
        if marker is None:
            return line, depth
        line = line[marker.end() :]
        depth += 1


def _strip_list_prefixes(
    line: str,
    indents: list[int],
) -> tuple[str, list[int]]:
    """Return list child content and the active relative indent stack."""
    if not line.strip():
        return line, indents
    active = list(indents)
    level = 0
    while level < len(active):
        width = active[level]
        leading = len(line) - len(line.lstrip(" "))
        if leading < width:
            active = active[:level]
            break
        line = line[width:]
        level += 1
    marker = LIST_MARKER_RE.match(line)
    if marker is not None:
        active.append(marker.end())
        line = line[marker.end() :]
    return line, active


def _block_masked_lines(
    text: str,
    *,
    mask_indented: bool,
) -> list[tuple[str, tuple[int, int]]]:
    """Strip quote containers and mask their fenced, HTML, and code children."""
    masked: list[tuple[str, tuple[int, int]]] = []
    fence_char = ""
    fence_length = 0
    fence_depth = (0, 0)
    html_end = ""
    html_until_blank = False
    html_depth = (0, 0)
    list_indents: list[int] = []
    previous_quote_depth = -1
    for raw_line in text.splitlines():
        line, quote_depth = _strip_block_quote_prefixes(raw_line)
        if quote_depth != previous_quote_depth:
            list_indents = []
            previous_quote_depth = quote_depth
        line, list_indents = _strip_list_prefixes(line, list_indents)
        container_depth = (quote_depth, len(list_indents))
        if fence_char:
            if container_depth == fence_depth:
                closing = re.match(
                    rf"^ {{0,3}}{re.escape(fence_char)}"
                    rf"{{{fence_length},}}[ \t]*$",
                    line,
                )
                if closing:
                    fence_char = ""
                    fence_length = 0
                masked.append(("", container_depth))
                continue
            else:
                fence_char = ""
                fence_length = 0
        if html_end:
            if container_depth == html_depth:
                masked.append(("", container_depth))
                if re.search(html_end, line, re.IGNORECASE):
                    html_end = ""
                continue
            else:
                html_end = ""
        if html_until_blank:
            if container_depth != html_depth:
                html_until_blank = False
            elif not line.strip():
                html_until_blank = False
                masked.append((line, container_depth))
                continue
            else:
                masked.append(("", container_depth))
                continue
        opening = FENCE_OPEN_RE.match(line)
        if opening:
            marker = opening.group("fence")
            fence_char = marker[0]
            fence_length = len(marker)
            fence_depth = container_depth
            masked.append(("", container_depth))
            continue
        raw_tag = HTML_RAW_TAG_RE.match(line)
        if raw_tag:
            html_end = rf"</{raw_tag.group('tag')}>"
            html_depth = container_depth
            masked.append(("", container_depth))
            if re.search(html_end, line, re.IGNORECASE):
                html_end = ""
            continue
        if re.match(r"^ {0,3}<!--", line):
            html_end = r"-->"
        elif re.match(r"^ {0,3}<\?", line):
            html_end = r"\?>"
        elif re.match(r"^ {0,3}<![A-Z]", line):
            html_end = r">"
        elif re.match(r"^ {0,3}<!\[CDATA\[", line):
            html_end = r"\]\]>"
        if html_end:
            html_depth = container_depth
            masked.append(("", container_depth))
            if re.search(html_end, line, re.IGNORECASE):
                html_end = ""
            continue
        if HTML_BLOCK_TAG_RE.match(line):
            html_until_blank = True
            html_depth = container_depth
            masked.append(("", container_depth))
            continue
        if mask_indented and (line.startswith("    ") or line.startswith("\t")):
            masked.append(("", container_depth))
            continue
        masked.append((line, container_depth))
    return masked


def _has_unescaped_pipe(value: str) -> bool:
    return any(
        char == "|" and not _is_escaped(value, index)
        for index, char in enumerate(value)
    )


def _table_row_indexes(
    lines: list[tuple[str, tuple[int, int]]],
) -> set[int]:
    """Identify GFM table rows so inline spans cannot cross cell-row bounds."""
    rows: set[int] = set()
    for index in range(1, len(lines)):
        line, depth = lines[index]
        previous, previous_depth = lines[index - 1]
        if (
            depth != previous_depth
            or not TABLE_DELIMITER_RE.match(line)
            or not _has_unescaped_pipe(previous)
        ):
            continue
        rows.update((index - 1, index))
        following = index + 1
        while following < len(lines):
            candidate, candidate_depth = lines[following]
            if (
                candidate_depth != depth
                or not candidate.strip()
                or not _has_unescaped_pipe(candidate)
            ):
                break
            rows.add(following)
            following += 1
    return rows


def _inline_segments(text: str) -> list[str]:
    """Return block-owned inline parsing segments, including GFM table rows."""
    lines = _block_masked_lines(text, mask_indented=True)
    table_rows = _table_row_indexes(lines)
    segments: list[str] = []
    current: list[str] = []
    current_depth: tuple[int, int] | None = None

    def flush() -> None:
        nonlocal current
        if current:
            segments.append("\n".join(current))
            current = []

    for index, (line, depth) in enumerate(lines):
        if not line.strip():
            flush()
            current_depth = None
            continue
        if index in table_rows:
            flush()
            segments.append(line)
            current_depth = None
            continue
        starts_block = bool(
            BLOCK_START_RE.match(line) or THEMATIC_BREAK_RE.match(line)
        )
        if current and (depth != current_depth or starts_block):
            flush()
        if not current:
            current_depth = depth
        current.append(line)
    flush()
    return segments


def _is_escaped(value: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and value[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 1


def _decode_commonmark_escapes(value: str) -> str:
    decoded: list[str] = []
    index = 0
    while index < len(value):
        if (
            value[index] == "\\"
            and index + 1 < len(value)
            and value[index + 1] in COMMONMARK_ESCAPABLE
        ):
            decoded.append(value[index + 1])
            index += 2
            continue
        decoded.append(value[index])
        index += 1
    return "".join(decoded)


def _code_spans_and_mask(text: str) -> tuple[list[tuple[int, int, str]], str]:
    """Return CommonMark code spans and text with complete spans blanked."""
    spans: list[tuple[int, int, str]] = []
    masked = list(text)
    index = 0
    while index < len(text):
        if text[index] != "`" or _is_escaped(text, index):
            index += 1
            continue
        run_end = index + 1
        while run_end < len(text) and text[run_end] == "`":
            run_end += 1
        run_length = run_end - index
        search = run_end
        closing_start = -1
        closing_end = -1
        while search < len(text):
            candidate = text.find("`", search)
            if candidate < 0:
                break
            candidate_end = candidate + 1
            while candidate_end < len(text) and text[candidate_end] == "`":
                candidate_end += 1
            if candidate_end - candidate == run_length:
                closing_start = candidate
                closing_end = candidate_end
                break
            search = candidate_end
        if closing_start < 0:
            index = run_end
            continue
        content = text[run_end:closing_start].replace("\n", " ").replace("\r", " ")
        if (
            content.startswith(" ")
            and content.endswith(" ")
            and content.strip(" ")
        ):
            content = content[1:-1]
        spans.append((index, closing_end, content))
        for position in range(index, closing_end):
            if masked[position] not in "\r\n":
                masked[position] = " "
        index = closing_end
    return spans, "".join(masked)


def _matching_bracket(value: str, start: int) -> int | None:
    depth = 0
    index = start
    while index < len(value):
        char = value[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _skip_inline_whitespace(value: str, start: int) -> int | None:
    """Skip spaces and at most one line ending inside inline link syntax."""
    index = start
    line_endings = 0
    while index < len(value) and value[index] in " \t\r\n":
        if value[index] == "\n":
            line_endings += 1
            if line_endings > 1:
                return None
        index += 1
    return index


def _inline_title_end(value: str, start: int) -> int | None:
    pairs = {'"': '"', "'": "'", "(": ")"}
    closer = pairs.get(value[start : start + 1])
    if closer is None:
        return None
    index = start + 1
    while index < len(value):
        char = value[index]
        if char == "\\":
            index += 2
            continue
        if char == "\n" and "\n" in value[start:index]:
            return None
        if char == closer:
            return index + 1
        if closer == ")" and char == "(":
            return None
        index += 1
    return None


def _inline_link_destination(
    value: str,
    opening_parenthesis: int,
) -> tuple[str, int] | None:
    cursor = _skip_inline_whitespace(value, opening_parenthesis + 1)
    if cursor is None or cursor >= len(value):
        return None
    if value[cursor] == ")":
        return "", cursor + 1
    parsed = _destination_and_remainder(
        value[cursor:],
        stop_at_closing_parenthesis=True,
    )
    if parsed is None:
        return None
    destination, remainder, _ = parsed
    cursor += len(value[cursor:]) - len(remainder)
    if cursor < len(value) and value[cursor] == ")":
        return destination, cursor + 1
    if cursor >= len(value) or value[cursor] not in " \t\r\n":
        return None
    cursor = _skip_inline_whitespace(value, cursor)
    if cursor is None or cursor >= len(value):
        return None
    if value[cursor] == ")":
        return destination, cursor + 1
    title_end = _inline_title_end(value, cursor)
    if title_end is None:
        return None
    cursor = _skip_inline_whitespace(value, title_end)
    if cursor is None or cursor >= len(value) or value[cursor] != ")":
        return None
    return destination, cursor + 1


def _inline_destinations(value: str) -> list[str]:
    """Extract inline destinations after code/container masking."""
    destinations: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "[" or _is_escaped(value, index):
            index += 1
            continue
        closing = _matching_bracket(value, index)
        if closing is None:
            index += 1
            continue
        if closing + 1 >= len(value) or value[closing + 1] != "(":
            index = closing + 1
            continue
        parsed = _inline_link_destination(value, closing + 1)
        if parsed is None:
            index = closing + 1
            continue
        destination, end = parsed
        destinations.append(destination)
        index = end
    return destinations


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
                normalized = " ".join(
                    _decode_commonmark_escapes("".join(label)).split()
                ).casefold()
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
    *,
    stop_at_closing_parenthesis: bool = False,
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
            elif char in "\r\n":
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
        elif char in " \t\r\n":
            break
        elif char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                if stop_at_closing_parenthesis:
                    break
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
    block_lines = _block_masked_lines(text, mask_indented=False)
    definitions: dict[str, str] = {}
    segment_start = 0
    while segment_start < len(block_lines):
        depth = block_lines[segment_start][1]
        segment_end = segment_start + 1
        while (
            segment_end < len(block_lines)
            and block_lines[segment_end][1] == depth
        ):
            segment_end += 1
        lines = [line for line, _ in block_lines[segment_start:segment_end]]
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
        segment_start = segment_end
    return list(definitions.values())


def _unescaped_fragment_start(value: str) -> int | None:
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            index += 2
            continue
        if value[index] == "#":
            return index
        index += 1
    return None


def _markdown_destination_path(destination: str) -> Path | None:
    raw = destination.strip()
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1]
    if "://" in raw or raw.startswith("#"):
        return None
    fragment = _unescaped_fragment_start(raw)
    if fragment is not None:
        raw = raw[:fragment]
    raw = _decode_commonmark_escapes(raw)
    if "://" in raw or raw.startswith("#"):
        return None
    if not raw.endswith(".md"):
        return None
    return Path(raw)


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
    destinations: list[str] = []
    for inline_segment in _inline_segments(text):
        code_spans, link_text = _code_spans_and_mask(inline_segment)
        for start, end, value in code_spans:
            raw = value.strip()
            if (
                start > 0
                and inline_segment[start - 1] == "["
                and inline_segment[end:].startswith("](")
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
            if (
                "/" in raw
                or "\\" in raw
                or any(path.is_file() for path in candidates)
            ):
                refs.add(ref)
        destinations.extend(_inline_destinations(link_text))
    destinations.extend(_reference_definition_destinations(text))
    for destination in destinations:
        ref = _markdown_destination_path(destination)
        if ref is not None:
            refs.add(ref)
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
        (references / "local(v1).md").write_text(
            "# Local parenthesized\n",
            encoding="utf-8",
        )
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
            "    [indented-ref]: references/missing.md\n"
            "    [indented](references/missing.md)\n"
            "    `references/missing.md`\n"
            "<pre>\n"
            "[html-ref]: references/missing.md\n"
            "[html](references/missing.md)\n"
            "`references/missing.md`\n"
            "</pre>\n"
            "\n"
            "Paragraph remains open\n"
            "[paragraph-ref]: references/missing.md\n"
            "\n"
            "``references/local.md``\n"
            "`report.md`\n"
            "[external](https://example.com/guide.md)\n"
        )

        def findings_for(content: str) -> list[str]:
            alpha_skill.write_text(content, encoding="utf-8")
            findings, _, _ = validate_skill_markdown_refs(
                package_root,
                ("alpha", "beta"),
            )
            return findings

        findings = findings_for(base)
        controls += 1
        if findings:
            errors.append("valid package reference fixture was rejected")

        findings = findings_for(base + "`references/missing.md`\n")
        controls += 1
        if not any("references/missing.md is dangling" in item for item in findings):
            errors.append("dangling inline-code reference was not rejected")

        findings = findings_for(base + "[missing](references/missing.md)\n")
        controls += 1
        if not any("references/missing.md is dangling" in item for item in findings):
            errors.append("dangling Markdown link was not rejected")

        outside = Path(tmp) / "outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        findings = findings_for(base + "`../../outside.md`\n")
        controls += 1
        if not any("../../outside.md: escapes package root" in item for item in findings):
            errors.append("escaping Markdown reference was not rejected")

        findings = findings_for(base + "`REFERENCES/local.md`\n")
        controls += 1
        if not any("name must match exactly" in item for item in findings):
            errors.append("case-alias Markdown reference was not rejected")

        findings = findings_for(
            base + "\n[missing-ref]: references/missing.md\n"
        )
        controls += 1
        if not any(
            "references/missing.md is dangling" in item for item in findings
        ):
            errors.append("dangling reference-style link was not rejected")

        findings = findings_for(
            base + "\n[missing-multiline]:\n  references/missing.md\n"
        )
        controls += 1
        if not any(
            "references/missing.md is dangling" in item for item in findings
        ):
            errors.append("multiline reference-style link was not rejected")

        findings = findings_for(
            base + "\n[balanced](references/missing_(v1).md)\n"
        )
        controls += 1
        if not any(
            "references/missing_(v1).md is dangling" in item
            for item in findings
        ):
            errors.append("balanced inline-link destination was not rejected")

        findings = findings_for(
            base + "\n[escaped]: references/local\\(v1\\).md\n"
        )
        controls += 1
        if findings:
            errors.append("escaped CommonMark destination was rejected")

        findings = findings_for(
            base + "\n`[literal](references/missing.md)`\n"
        )
        controls += 1
        if findings:
            errors.append("inline-code pseudo-link was treated as a reference")

        findings = findings_for(
            base + "\n\\[literal](references/missing.md)\n"
        )
        controls += 1
        if findings:
            errors.append("escaped inline-link opener was treated as a reference")

        findings = findings_for(
            base
            + "\n> ```markdown\n"
            + "> [literal](references/missing.md)\n"
            + "> [literal-ref]: references/missing.md\n"
            + "> ```\n"
        )
        controls += 1
        if findings:
            errors.append("blockquoted fenced-code reference was not masked")

        findings = findings_for(
            base
            + "\n`[literal](references/missing.md)\n"
            + "continued code span`\n"
        )
        controls += 1
        if findings:
            errors.append("multiline code-span pseudo-link was not masked")

        findings = findings_for(
            base + "\n> [quoted-ref]: references/missing.md\n"
        )
        controls += 1
        if not any(
            "references/missing.md is dangling" in item for item in findings
        ):
            errors.append("blockquoted reference definition was not rejected")

        findings = findings_for(
            base
            + "\n- ```markdown\n"
            + "  [literal](references/missing.md)\n"
            + "  [literal-ref]: references/missing.md\n"
            + "  ```\n"
        )
        controls += 1
        if findings:
            errors.append("list-contained fenced-code reference was not masked")

        findings = findings_for(
            base + "\n- [listed-ref]: references/missing.md\n"
        )
        controls += 1
        if not any(
            "references/missing.md is dangling" in item for item in findings
        ):
            errors.append("list-contained reference definition was not rejected")

        findings = findings_for(
            base
            + "\n| Name | Hint | Card |\n"
            + "|---|---|---|\n"
            + "| local | ```text | `references/local.md` |\n"
        )
        controls += 1
        if findings:
            errors.append("GFM table-row reference was rejected")

        findings = findings_for(
            base + "\n[windows](references\\local.md)\n"
        )
        controls += 1
        if not any("unsafe Markdown reference" in item for item in findings):
            errors.append("literal Windows separator was not rejected")

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
