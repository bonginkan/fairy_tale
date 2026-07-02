#!/usr/bin/env python3
"""Skill token/line budget checks for Fairy Tale SKILL.md surfaces.

Why this exists (primary sources, fetched 2026-07-02):
- Official Claude Code skill guidance: "Keep SKILL.md under 500 lines. Move
  detailed reference material to separate files."
  (https://code.claude.com/docs/en/skills)
- Post-compaction re-attachment keeps only "the first 5,000 tokens of each"
  invoked skill (25,000-token combined budget). Anything past the head window
  is silently dropped after compaction, so safety rules and the mode-pattern
  router must live inside the head window.
  (https://code.claude.com/docs/en/skills)

Token estimation basis:
- Reporting estimate: tokens ~= UTF-8 bytes / 4.0 (mid-range of the rough
  3.5-4.5 bytes-per-token band for English markdown on Claude-family BPE
  vocabularies). Display only, never used for enforcement.
- Head-window enforcement: the window must GUARANTEE survival inside the
  first 5,000 re-attached tokens, so it assumes the densest plausible
  tokenization (3.5 bytes/token): 5,000 tokens -> 17,500 bytes. Using 4.0
  here would overestimate the window (20,000 bytes) and pass content that a
  denser tokenization drops. Exact bytes, lines, and characters are always
  reported next to the estimates; the line budget keys on exact lines.

Checks (RED in --enforce mode, reported in baseline mode):
- C1 line_budget: SKILL.md total lines <= --max-lines (default 500).
- C2 head_anchors: every required section heading starts within the head
  window (default 5,000 tokens enforced at 3.5 bytes/token = 17,500 bytes).
- C3 router_table_in_head: the router table -- the content between the router
  section heading and its first subsection (or the section end when it has no
  subsections) -- is fully contained in the head window. After the router
  restructure the router section has no subsections, so this check then covers
  the entire routing surface.
- C4 inventory_parity (only with --inventory-compare): EXACT two-way heading
  parity. A stored section missing from SKILL.md is RED (silent drop), and a
  current section absent from the stored inventory is RED (untracked drift --
  regenerate with --write-inventory). This is the gate that keeps future card
  extractions from silently dropping or side-adding a harness.
- A check named in --enforce-checks that resolves to "skipped" is RED: asking
  for a gate that cannot run must fail, not silently pass.

Usage:
  python3 scripts/skill_token_budget_check.py                  # baseline report
  python3 scripts/skill_token_budget_check.py --enforce        # exit 1 on RED
  python3 scripts/skill_token_budget_check.py --json
  python3 scripts/skill_token_budget_check.py \
      --write-inventory docs/skill-budget/skill-section-inventory.json
  python3 scripts/skill_token_budget_check.py \
      --inventory-compare docs/skill-budget/skill-section-inventory.json --enforce
  python3 scripts/skill_token_budget_check.py \
      --inventory-compare docs/skill-budget/skill-section-inventory.json \
      --enforce-checks inventory_parity   # CI teeth while the line budget is a known baseline RED
  python3 scripts/skill_token_budget_check.py --selftest
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_MD = ROOT / "skills" / "fairy-tale" / "SKILL.md"
DEFAULT_REFERENCES_DIR = ROOT / "skills" / "fairy-tale" / "references"

BYTES_PER_TOKEN = 4.0  # reporting estimate only (mid-range)
HEAD_BYTES_PER_TOKEN = 3.5  # enforcement: densest plausible tokenization
DEFAULT_MAX_LINES = 500
DEFAULT_HEAD_TOKEN_BUDGET = 5000

REQUIRED_HEAD_SECTIONS = (
    "Non-negotiables",
    "Residency Guard",
    "Default workflow",
)
ROUTER_SECTION_CANDIDATES = (
    "Mode-pattern router",
    "Mode patterns",
)

HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")
CARD_REF_RE = re.compile(r"`(references/cards/[a-z0-9\-]+\.md)`")


@dataclass
class Section:
    level: int
    title: str
    line: int
    byte_offset: int
    byte_end: int
    est_tokens: int


@dataclass
class CheckResult:
    check: str
    status: str  # "green" | "red" | "skipped"
    detail: str


@dataclass
class Report:
    skill_md: str
    bytes: int
    lines: int
    chars: int
    est_tokens: int
    head_window_bytes: int
    head_token_budget: int
    max_lines: int
    estimation_basis: str
    sections: list[Section] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def red_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "red")


def parse_sections(text: bytes) -> list[Section]:
    sections: list[Section] = []
    offset = 0
    for idx, raw_line in enumerate(text.split(b"\n"), start=1):
        line = raw_line.decode("utf-8", errors="replace")
        match = HEADING_RE.match(line)
        if match:
            sections.append(
                Section(
                    level=len(match.group(1)),
                    title=match.group(2).strip(),
                    line=idx,
                    byte_offset=offset,
                    byte_end=-1,
                    est_tokens=-1,
                )
            )
        offset += len(raw_line) + 1
    total = len(text)
    for i, section in enumerate(sections):
        end = total
        for later in sections[i + 1 :]:
            if later.level <= section.level:
                end = later.byte_offset
                break
        section.byte_end = end
        section.est_tokens = round((end - section.byte_offset) / BYTES_PER_TOKEN)
    return sections


def find_section(sections: list[Section], title: str) -> Section | None:
    for section in sections:
        if section.title == title:
            return section
    return None


def router_table_end(sections: list[Section], router: Section) -> int:
    """End of the router *table*: first child subsection, else section end."""
    for section in sections:
        if section.byte_offset > router.byte_offset and section.level > router.level:
            if section.byte_offset >= router.byte_end:
                break
            return section.byte_offset
        if section.byte_offset >= router.byte_end:
            break
    return router.byte_end


def card_titles(cards_dir: Path | None) -> dict[str, str]:
    """Map card relative path -> card h1 title for every *.md in cards_dir."""
    titles: dict[str, str] = {}
    if cards_dir and cards_dir.is_dir():
        for card in sorted(cards_dir.glob("*.md")):
            first_line = card.read_text(encoding="utf-8").split("\n", 1)[0]
            if first_line.startswith("# "):
                titles[f"references/cards/{card.name}"] = first_line[2:].strip()
    return titles


def build_report(
    skill_md: Path,
    max_lines: int,
    head_token_budget: int,
    inventory_compare: Path | None,
    cards_dir: Path | None = None,
) -> Report:
    data = skill_md.read_bytes()
    text = data.decode("utf-8", errors="replace")
    head_window_bytes = int(head_token_budget * HEAD_BYTES_PER_TOKEN)
    sections = parse_sections(data)
    report = Report(
        skill_md=str(skill_md.relative_to(ROOT) if skill_md.is_relative_to(ROOT) else skill_md),
        bytes=len(data),
        lines=text.count("\n") + (0 if text.endswith("\n") else 1),
        chars=len(text),
        est_tokens=round(len(data) / BYTES_PER_TOKEN),
        head_window_bytes=head_window_bytes,
        head_token_budget=head_token_budget,
        max_lines=max_lines,
        estimation_basis=(
            f"est tokens = UTF-8 bytes / {BYTES_PER_TOKEN} (reporting only); "
            f"head window enforced at {HEAD_BYTES_PER_TOKEN} bytes/token (densest "
            "plausible tokenization); line budget uses exact lines"
        ),
        sections=sections,
    )

    # C1 line budget
    if report.lines <= max_lines:
        report.checks.append(
            CheckResult("line_budget", "green", f"{report.lines} lines <= {max_lines}")
        )
    else:
        report.checks.append(
            CheckResult(
                "line_budget",
                "red",
                f"{report.lines} lines > {max_lines} (official guidance: keep SKILL.md under 500 lines)",
            )
        )

    # C2 head anchors
    missing_or_late: list[str] = []
    for title in REQUIRED_HEAD_SECTIONS:
        section = find_section(sections, title)
        if section is None:
            missing_or_late.append(f"{title} (missing)")
        elif section.byte_offset >= head_window_bytes:
            missing_or_late.append(
                f"{title} (starts at byte {section.byte_offset} >= head window {head_window_bytes})"
            )
    router = None
    for candidate in ROUTER_SECTION_CANDIDATES:
        router = find_section(sections, candidate)
        if router is not None:
            break
    if router is None:
        missing_or_late.append(
            "router section (none of: " + ", ".join(ROUTER_SECTION_CANDIDATES) + ")"
        )
    elif router.byte_offset >= head_window_bytes:
        missing_or_late.append(
            f"{router.title} (starts at byte {router.byte_offset} >= head window {head_window_bytes})"
        )
    if missing_or_late:
        report.checks.append(CheckResult("head_anchors", "red", "; ".join(missing_or_late)))
    else:
        report.checks.append(
            CheckResult(
                "head_anchors",
                "green",
                "required sections + router anchor all start within the head window",
            )
        )

    # C3 router table containment
    if router is None:
        report.checks.append(
            CheckResult("router_table_in_head", "red", "no router section found")
        )
    else:
        table_end = router_table_end(sections, router)
        if table_end <= head_window_bytes:
            report.checks.append(
                CheckResult(
                    "router_table_in_head",
                    "green",
                    f"router table ({router.title}) ends at byte {table_end} <= {head_window_bytes}",
                )
            )
        else:
            report.checks.append(
                CheckResult(
                    "router_table_in_head",
                    "red",
                    f"router table ({router.title}) ends at byte {table_end} > head window "
                    f"{head_window_bytes}; routing surface would be dropped after compaction",
                )
            )

    # C5 router/card integrity (active when a cards dir or card refs exist)
    refs = CARD_REF_RE.findall(text)
    known_cards = card_titles(cards_dir)
    if refs or known_cards:
        problems5: list[str] = []
        dangling = [r for r in sorted(set(refs)) if r not in known_cards]
        if dangling:
            problems5.append("dangling router ref (no card file): " + "; ".join(dangling))
        orphaned = [c for c in sorted(known_cards) if c not in set(refs)]
        if orphaned:
            problems5.append("orphan card (not referenced from SKILL.md): " + "; ".join(orphaned))
        duplicates = sorted({r for r in refs if refs.count(r) > 1})
        if duplicates:
            problems5.append("card referenced more than once: " + "; ".join(duplicates))
        if problems5:
            report.checks.append(CheckResult("router_cards", "red", " | ".join(problems5)))
        else:
            report.checks.append(
                CheckResult(
                    "router_cards",
                    "green",
                    f"{len(set(refs))} router refs == {len(known_cards)} cards, no dangling/orphan/duplicate",
                )
            )
    else:
        report.checks.append(
            CheckResult("router_cards", "skipped", "no cards dir and no card refs found")
        )

    # C4 inventory parity
    if inventory_compare is None:
        report.checks.append(
            CheckResult("inventory_parity", "skipped", "no --inventory-compare path given")
        )
    elif not inventory_compare.exists():
        report.checks.append(
            CheckResult("inventory_parity", "red", f"inventory not found: {inventory_compare}")
        )
    else:
        stored = json.loads(inventory_compare.read_text(encoding="utf-8"))
        stored_titles = [s["title"] for s in stored.get("sections", [])]
        current_titles = [s.title for s in sections]
        referenced_card_titles = {
            title for path, title in card_titles(cards_dir).items() if path in set(refs)
        } if (refs or known_cards) else set()
        dropped = [
            t
            for t in stored_titles
            if t not in set(current_titles) and t not in referenced_card_titles
        ]
        card_resolved = [
            t for t in stored_titles if t not in set(current_titles) and t in referenced_card_titles
        ]
        untracked = [t for t in current_titles if t not in set(stored_titles)]
        problems: list[str] = []
        if dropped:
            problems.append(
                "dropped vs stored inventory (no SKILL.md heading, no router-referenced card): "
                + "; ".join(dropped)
            )
        if untracked:
            problems.append(
                "present but not in stored inventory (regenerate with --write-inventory): "
                + "; ".join(untracked)
            )
        stored_cards = [c["path"] for c in stored.get("cards", [])]
        if stored_cards:
            disk_cards = sorted(card_titles(cards_dir))
            missing_cards = [c for c in stored_cards if c not in set(disk_cards)]
            new_cards = [c for c in disk_cards if c not in set(stored_cards)]
            if missing_cards:
                problems.append("stored cards missing on disk: " + "; ".join(missing_cards))
            if new_cards:
                problems.append(
                    "cards on disk not in stored inventory: " + "; ".join(new_cards)
                )
        if problems:
            report.checks.append(CheckResult("inventory_parity", "red", " | ".join(problems)))
        else:
            detail = f"two-way parity: {len(stored_titles)} stored sections resolved"
            if card_resolved:
                detail += f" ({len(card_resolved)} via router-referenced cards)"
            if stored_cards:
                detail += f"; {len(stored_cards)} cards two-way"
            report.checks.append(CheckResult("inventory_parity", "green", detail))
    return report


def reference_inventory() -> list[dict]:
    refs = []
    if DEFAULT_REFERENCES_DIR.exists():
        for path in sorted(DEFAULT_REFERENCES_DIR.rglob("*.md")):
            data = path.read_bytes()
            refs.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "bytes": len(data),
                    "lines": data.count(b"\n"),
                    "est_tokens": round(len(data) / BYTES_PER_TOKEN),
                }
            )
    return refs


def cards_inventory(cards_dir: Path | None) -> list[dict]:
    rows = []
    for path, title in sorted(card_titles(cards_dir).items()):
        data = (DEFAULT_SKILL_MD.parent / path).read_bytes()
        rows.append(
            {
                "path": path,
                "title": title,
                "bytes": len(data),
                "est_tokens": round(len(data) / BYTES_PER_TOKEN),
            }
        )
    return rows


def write_inventory(report: Report, out_path: Path, cards_dir: Path | None = None) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "purpose": (
            "Parity checklist for the SKILL.md router/per-card restructure: every "
            "section listed here must remain reachable (in SKILL.md or via an "
            "extracted card referenced from the router). Compare with "
            "--inventory-compare to fail closed on silent drops."
        ),
        "skill_md": report.skill_md,
        "measured": {
            "bytes": report.bytes,
            "lines": report.lines,
            "chars": report.chars,
            "est_tokens": report.est_tokens,
            "estimation_basis": report.estimation_basis,
            "head_window_bytes": report.head_window_bytes,
            "head_token_budget": report.head_token_budget,
        },
        "sections": [asdict(s) for s in report.sections],
        "cards": cards_inventory(cards_dir),
        "references": reference_inventory(),
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md_path = out_path.with_suffix(".md")
    lines = [
        "# SKILL.md section inventory (parity checklist)",
        "",
        f"- Source: `{report.skill_md}`",
        f"- Measured: {report.bytes} bytes / {report.lines} lines / ~{report.est_tokens} est tokens",
        f"- Estimation basis: {report.estimation_basis}",
        f"- Head window: first {report.head_token_budget} est tokens (= {report.head_window_bytes} bytes)",
        "",
        "Every section below must survive the router/per-card restructure, either",
        "in SKILL.md itself or as an extracted card reachable from the router.",
        "",
        "| # | level | section | line | byte offset | est tokens | in head window |",
        "|---|-------|---------|------|-------------|------------|----------------|",
    ]
    for i, s in enumerate(report.sections, start=1):
        in_head = "yes" if s.byte_offset < report.head_window_bytes else "no"
        lines.append(
            f"| {i} | h{s.level} | {s.title} | {s.line} | {s.byte_offset} | {s.est_tokens} | {in_head} |"
        )
    lines += ["", "## References inventory", ""]
    lines.append("| path | bytes | lines | est tokens |")
    lines.append("|------|-------|-------|------------|")
    for ref in reference_inventory():
        lines.append(
            f"| {ref['path']} | {ref['bytes']} | {ref['lines']} | {ref['est_tokens']} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def print_report(report: Report) -> None:
    print(f"skill: {report.skill_md}")
    print(
        f"measured: {report.bytes} bytes | {report.lines} lines | {report.chars} chars | "
        f"~{report.est_tokens} est tokens"
    )
    print(f"basis: {report.estimation_basis}")
    print(
        f"budgets: max_lines={report.max_lines}, head={report.head_token_budget} est tokens "
        f"({report.head_window_bytes} bytes)"
    )
    for check in report.checks:
        print(f"[{check.status.upper():7}] {check.check}: {check.detail}")


def enforcement_failures(
    report: Report, enforce_all: bool, enforce_checks: str | None
) -> list[str]:
    """Resolve enforcement outcome. A check NAMED in enforce_checks that is
    'skipped' fails closed: asking for a gate that cannot run must not pass."""
    failures: list[str] = []
    if enforce_all and report.red_count:
        failures.append(f"{report.red_count} red check(s)")
    if enforce_checks:
        wanted = {name.strip() for name in enforce_checks.split(",") if name.strip()}
        by_name = {c.check: c for c in report.checks}
        unknown = wanted - set(by_name)
        if unknown:
            failures.append("unknown check name(s): " + ", ".join(sorted(unknown)))
        for name in sorted(wanted & set(by_name)):
            check = by_name[name]
            if check.status == "red":
                failures.append(f"{name}: red ({check.detail})")
            elif check.status == "skipped":
                failures.append(
                    f"{name}: skipped under enforcement -- fail closed ({check.detail})"
                )
    return failures


def selftest() -> int:
    """GREEN fixture passes all checks; RED fixture trips every gate."""
    failures: list[str] = []
    green_body = (
        "---\nname: t\n---\n\n# T\n\n## Non-negotiables\n\n- a\n\n## Residency Guard\n\n- b\n\n"
        "## Default workflow\n\n1. x\n\n## Mode-pattern router\n\n- route a -> refs/a.md\n"
    )
    red_body = (
        "---\nname: t\n---\n\n# T\n\n"
        + ("filler line\n" * 600)
        + "## Non-negotiables\n\n- a\n\n## Mode patterns\n\n"
        + "### Big harness\n\n"
        + ("harness detail\n" * 200)
    )
    with tempfile.TemporaryDirectory() as tmp:
        green = Path(tmp) / "green.md"
        green.write_text(green_body, encoding="utf-8")
        red = Path(tmp) / "red.md"
        red.write_text(red_body, encoding="utf-8")

        g = build_report(green, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, None)
        for check in g.checks:
            if check.check in {"inventory_parity", "router_cards"}:
                continue  # skipped without compare path / cards dir in this fixture
            if check.status != "green":
                failures.append(f"green fixture: {check.check} = {check.status} ({check.detail})")

        r = build_report(red, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, None)
        red_map = {c.check: c.status for c in r.checks}
        if red_map.get("line_budget") != "red":
            failures.append("red fixture: line_budget did not go red")
        if red_map.get("head_anchors") != "red":
            failures.append("red fixture: head_anchors did not go red")

        green_sections = ["Non-negotiables", "Residency Guard", "Default workflow", "Mode-pattern router"]

        # inventory parity RED (drop direction): stored section missing from the file
        inv = Path(tmp) / "inv.json"
        inv.write_text(
            json.dumps(
                {"sections": [{"title": t} for t in green_sections + ["Vanished Harness"]]}
            ),
            encoding="utf-8",
        )
        p = build_report(green, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, inv)
        parity = {c.check: c for c in p.checks}["inventory_parity"]
        if parity.status != "red" or "Vanished Harness" not in parity.detail:
            failures.append("parity fixture: dropped section did not go red")

        # inventory parity RED (untracked direction): file has a section the
        # stored inventory never recorded (subset-only parity is not parity)
        inv_subset = Path(tmp) / "inv_subset.json"
        inv_subset.write_text(
            json.dumps({"sections": [{"title": t} for t in green_sections[:-1]]}),
            encoding="utf-8",
        )
        p_extra = build_report(green, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, inv_subset)
        extra = {c.check: c for c in p_extra.checks}["inventory_parity"]
        if extra.status != "red" or "Mode-pattern router" not in extra.detail:
            failures.append("parity fixture: untracked current section did not go red")

        # inventory parity GREEN: exact two-way match
        inv_ok = Path(tmp) / "inv_ok.json"
        inv_ok.write_text(
            json.dumps({"sections": [{"title": t} for t in green_sections]}), encoding="utf-8"
        )
        p_ok = build_report(green, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, inv_ok)
        if {c.check: c.status for c in p_ok.checks}["inventory_parity"] != "green":
            failures.append("parity fixture: exact-matching inventory did not stay green")

        # enforcement fail-closed: a NAMED gate that is skipped must fail
        p_skip = build_report(green, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, None)
        if not enforcement_failures(p_skip, False, "inventory_parity"):
            failures.append("enforcement fixture: named skipped gate did not fail closed")
        if enforcement_failures(p_ok, False, "inventory_parity"):
            failures.append("enforcement fixture: named green gate failed unexpectedly")
        if not enforcement_failures(p_skip, False, "no_such_check"):
            failures.append("enforcement fixture: unknown check name did not fail")

        # card-aware fixtures: router refs + cards dir
        routed = Path(tmp) / "routed.md"
        routed.write_text(
            "## Non-negotiables\n\n- a\n\n## Residency Guard\n\n- b\n\n## Default workflow\n\n1. x\n\n"
            "## Mode-pattern router\n\n| p | hint | `references/cards/alpha-harness.md` |\n\n"
            "## Supporting references\n\n- refs\n",
            encoding="utf-8",
        )
        cards = Path(tmp) / "cards"
        cards.mkdir()
        (cards / "alpha-harness.md").write_text("# Alpha Harness\n\n- body\n", encoding="utf-8")

        # green: ref <-> card matched; old-section title resolves via card
        inv_cardaware = Path(tmp) / "inv_cards.json"
        inv_cardaware.write_text(
            json.dumps(
                {
                    "sections": [
                        {"title": t}
                        for t in [
                            "Non-negotiables",
                            "Residency Guard",
                            "Default workflow",
                            "Mode-pattern router",
                            "Supporting references",
                            "Alpha Harness",  # moved section: resolves via router-referenced card
                        ]
                    ]
                }
            ),
            encoding="utf-8",
        )
        rc_g = build_report(routed, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, inv_cardaware, cards)
        rc_map = {c.check: c for c in rc_g.checks}
        if rc_map["router_cards"].status != "green":
            failures.append(f"card fixture: matched ref/card not green ({rc_map['router_cards'].detail})")
        if rc_map["inventory_parity"].status != "green":
            failures.append(
                f"card fixture: card-resolved section not green ({rc_map['inventory_parity'].detail})"
            )

        # red: dropped section with NO card
        inv_dropped = Path(tmp) / "inv_dropped.json"
        inv_dropped.write_text(
            json.dumps({"sections": [{"title": "Non-negotiables"}, {"title": "Beta Harness"}]}),
            encoding="utf-8",
        )
        rc_d = build_report(routed, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, inv_dropped, cards)
        parity_d = {c.check: c for c in rc_d.checks}["inventory_parity"]
        if parity_d.status != "red" or "Beta Harness" not in parity_d.detail:
            failures.append("card fixture: dropped section without card did not go red")

        # red: dangling router ref
        dangling_skill = Path(tmp) / "dangling.md"
        dangling_skill.write_text(
            routed.read_text(encoding="utf-8").replace("alpha-harness", "ghost-harness"),
            encoding="utf-8",
        )
        rc_x = build_report(dangling_skill, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, None, cards)
        rx = {c.check: c for c in rc_x.checks}["router_cards"]
        if rx.status != "red" or "dangling" not in rx.detail or "orphan" not in rx.detail:
            failures.append("card fixture: dangling ref + orphan card did not go red")

        # red: stored cards vs disk (card deleted later)
        inv_with_cards = Path(tmp) / "inv_with_cards.json"
        inv_with_cards.write_text(
            json.dumps(
                {
                    "sections": [{"title": "Non-negotiables"}],
                    "cards": [
                        {"path": "references/cards/alpha-harness.md"},
                        {"path": "references/cards/vanished-card.md"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        rc_v = build_report(routed, DEFAULT_MAX_LINES, DEFAULT_HEAD_TOKEN_BUDGET, inv_with_cards, cards)
        pv = {c.check: c for c in rc_v.checks}["inventory_parity"]
        if pv.status != "red" or "vanished-card" not in pv.detail:
            failures.append("card fixture: stored card missing on disk did not go red")

        # head-window boundary: router table ending inside the 17,500-20,000
        # byte band (green under a 4.0 B/tok window, RED under the enforced
        # conservative 3.5 B/tok window)
        boundary = Path(tmp) / "boundary.md"
        pad = "x" * 78 + "\n"  # 79 bytes/line
        boundary.write_text(
            "## Non-negotiables\n\n- a\n\n## Residency Guard\n\n- b\n\n## Default workflow\n\n"
            + pad * 200  # ~15.8 KB inside Default workflow
            + "\n## Mode-pattern router\n\n"
            + ("- route x -> refs/x.md\n" * 100)  # table ends ~18.2 KB
            + "\n## Supporting references\n\n- refs\n",
            encoding="utf-8",
        )
        b = build_report(boundary, 10_000, DEFAULT_HEAD_TOKEN_BUDGET, None)
        b_map = {c.check: c.status for c in b.checks}
        if b_map.get("router_table_in_head") != "red":
            failures.append("boundary fixture: 17.5k-20k band did not go red at 3.5 B/tok")
        b_wide = build_report(boundary, 10_000, 5715, None)  # window ~20,002 bytes
        if {c.check: c.status for c in b_wide.checks}.get("router_table_in_head") != "green":
            failures.append(
                "boundary fixture: not inside the disputed band (should be green at ~20k window)"
            )

        # router containment RED: router heading anchored late, past the head window
        late_router = Path(tmp) / "late_router.md"
        late_router.write_text(
            "## Non-negotiables\n\n- a\n\n## Residency Guard\n\n- b\n\n## Default workflow\n\n1. x\n\n"
            + ("padding line for head window overflow\n" * 700)
            + "## Mode-pattern router\n\n- route a -> refs/a.md\n",
            encoding="utf-8",
        )
        lr = build_report(late_router, 10_000, DEFAULT_HEAD_TOKEN_BUDGET, None)
        lr_map = {c.check: c.status for c in lr.checks}
        if lr_map.get("head_anchors") != "red" or lr_map.get("router_table_in_head") != "red":
            failures.append("late-router fixture: head/router gates did not go red")

    if failures:
        for failure in failures:
            print(f"[SELFTEST RED] {failure}")
        return 1
    print(
        "[SELFTEST GREEN] green fixture passes; red fixtures trip "
        "line/head/router/parity gates"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skill-md", type=Path, default=DEFAULT_SKILL_MD)
    parser.add_argument(
        "--cards-dir",
        type=Path,
        default=DEFAULT_REFERENCES_DIR / "cards",
        help="mode-pattern card directory for card-aware parity and router checks",
    )
    parser.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES)
    parser.add_argument("--head-token-budget", type=int, default=DEFAULT_HEAD_TOKEN_BUDGET)
    parser.add_argument("--enforce", action="store_true", help="exit 1 if any check is red")
    parser.add_argument(
        "--enforce-checks",
        help="comma-separated check names; exit 1 only if one of THESE is red "
        "(e.g. inventory_parity while the line budget is a known baseline red)",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--write-inventory", type=Path, help="write JSON+MD section inventory")
    parser.add_argument(
        "--inventory-compare", type=Path, help="fail closed if stored sections were dropped"
    )
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    if not args.skill_md.exists():
        print(f"skill file not found: {args.skill_md}", file=sys.stderr)
        return 1

    report = build_report(
        args.skill_md,
        args.max_lines,
        args.head_token_budget,
        args.inventory_compare,
        cards_dir=args.cards_dir,
    )
    if args.write_inventory:
        write_inventory(report, args.write_inventory, cards_dir=args.cards_dir)
        print(f"inventory written: {args.write_inventory} (+ .md)")
    if args.json:
        print(
            json.dumps(
                {
                    **{k: v for k, v in asdict(report).items() if k != "sections"},
                    "sections": [asdict(s) for s in report.sections],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print_report(report)

    failures = enforcement_failures(report, args.enforce, args.enforce_checks)
    if failures:
        for failure in failures:
            print(f"ENFORCE: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
