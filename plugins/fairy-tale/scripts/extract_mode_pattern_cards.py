#!/usr/bin/env python3
"""Deterministic, byte-preserving extraction of SKILL.md mode-pattern cards.

Increment 2 of fairy_tale #57: move each `### <harness>` section under
`## Mode patterns` into `references/cards/<slug>.md` VERBATIM, and replace the
mode-pattern bodies in SKILL.md with a compact router table.

Verbatim contract (review gate, PR #60 thread 2026-07-02):
- A card file is exactly `# <original title>\n` + the ORIGINAL section body
  bytes (everything after the heading line up to the next section heading).
  No trimming, no whitespace normalization, no reflow.
- `--verify` re-reads every written card and byte-compares its body slice
  against the original SKILL.md byte range recorded in the manifest. The
  comparison target is ONLY the moved h3 body bytes (never router rows or any
  added text). Any mismatch exits non-zero.
- The extraction is reproducible: same input SKILL.md -> byte-identical cards,
  router table, and new SKILL.md (no timestamps, no ordering ambiguity;
  sections are processed in file order).

The ONLY non-moved text this script introduces (disclosed, reviewed as new):
- the router preamble line under `## Mode patterns`;
- the router table itself (title verbatim; "route on" column is the MECHANICAL
  first non-empty body line, truncated; card path).

Usage:
  python3 scripts/extract_mode_pattern_cards.py                # dry-run plan
  python3 scripts/extract_mode_pattern_cards.py --write        # write cards + new SKILL.md
  python3 scripts/extract_mode_pattern_cards.py --verify       # verify written cards vs manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_MD = ROOT / "skills" / "fairy-tale" / "SKILL.md"
DEFAULT_CARDS_DIR = ROOT / "skills" / "fairy-tale" / "references" / "cards"
DEFAULT_MANIFEST = ROOT / "docs" / "skill-budget" / "card-extraction-manifest.json"

MODE_PATTERNS_TITLE = "Mode patterns"
ROUTER_PREAMBLE = (
    "Route with the table below and read the linked card before applying a "
    "pattern; the cards are the canonical harness bodies.\n"
)
ROUTE_HINT_MAX = 140

HEADING_RE = re.compile(rb"^(#{2,3}) (.+)$", re.MULTILINE)


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug


def find_sections(data: bytes) -> list[dict]:
    sections = []
    for match in HEADING_RE.finditer(data):
        sections.append(
            {
                "level": len(match.group(1)),
                "title": match.group(2).decode("utf-8").strip(),
                "heading_start": match.start(),
                "body_start": match.end() + 1 if data[match.end() : match.end() + 1] == b"\n" else match.end(),
            }
        )
    for i, section in enumerate(sections):
        end = len(data)
        for later in sections[i + 1 :]:
            if later["level"] <= section["level"]:
                end = later["heading_start"]
                break
        section["section_end"] = end
    for i, section in enumerate(sections):
        nxt = sections[i + 1]["heading_start"] if i + 1 < len(sections) else len(data)
        section["body_end"] = min(section["section_end"], nxt)
    return sections


def first_route_hint(body: bytes) -> str:
    for raw_line in body.decode("utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        line = line.replace("|", "\\|")
        if len(line) > ROUTE_HINT_MAX:
            line = line[: ROUTE_HINT_MAX - 1].rstrip() + "…"
        return line
    return ""


def plan(data: bytes) -> dict:
    sections = find_sections(data)
    mode = next(
        (s for s in sections if s["level"] == 2 and s["title"] == MODE_PATTERNS_TITLE), None
    )
    if mode is None:
        raise SystemExit("no '## Mode patterns' section found")
    harnesses = [
        s
        for s in sections
        if s["level"] == 3
        and mode["heading_start"] < s["heading_start"] < mode["section_end"]
    ]
    if not harnesses:
        raise SystemExit("no h3 harness sections under Mode patterns")
    cards = []
    seen_slugs: dict[str, str] = {}
    for section in harnesses:
        slug = slugify(section["title"])
        if slug in seen_slugs:
            raise SystemExit(
                f"duplicate slug '{slug}' for '{section['title']}' and '{seen_slugs[slug]}'"
            )
        seen_slugs[slug] = section["title"]
        body = data[section["body_start"] : section["body_end"]]
        cards.append(
            {
                "title": section["title"],
                "slug": slug,
                "card_path": f"references/cards/{slug}.md",
                "old_body_start": section["body_start"],
                "old_body_end": section["body_end"],
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "route_hint": first_route_hint(body),
            }
        )
    return {
        "skill_md_sha256": hashlib.sha256(data).hexdigest(),
        "mode_intro_end": harnesses[0]["heading_start"],
        "mode_section_end": mode["section_end"],
        "cards": cards,
    }


def router_block(cards: list[dict]) -> bytes:
    lines = [ROUTER_PREAMBLE, "", "| Mode pattern | Route on | Card |", "|---|---|---|"]
    for card in cards:
        lines.append(f"| {card['title']} | {card['route_hint']} | `{card['card_path']}` |")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


def build_outputs(data: bytes, extraction: dict) -> tuple[bytes, dict[str, bytes]]:
    cards_bytes: dict[str, bytes] = {}
    for card in extraction["cards"]:
        body = data[card["old_body_start"] : card["old_body_end"]]
        cards_bytes[card["card_path"]] = b"# " + card["title"].encode("utf-8") + b"\n" + body
    new_skill = (
        data[: extraction["mode_intro_end"]]
        + router_block(extraction["cards"])
        + b"\n"
        + data[extraction["mode_section_end"] :]
    )
    return new_skill, cards_bytes


def do_verify(skill_md: Path, manifest_path: Path) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    snapshot_ref = Path(manifest["original_skill_md_snapshot"])
    if snapshot_ref.is_absolute():
        print(f"[VERIFY RED] manifest snapshot ref is an absolute local path: {snapshot_ref}")
        return 1
    original = (ROOT / snapshot_ref).read_bytes()
    if hashlib.sha256(original).hexdigest() != manifest["skill_md_sha256"]:
        failures.append("original snapshot sha mismatch vs manifest")
    for card in manifest["cards"]:
        card_file = skill_md.parent / card["card_path"]
        if not card_file.exists():
            failures.append(f"missing card: {card['card_path']}")
            continue
        card_bytes = card_file.read_bytes()
        prefix = b"# " + card["title"].encode("utf-8") + b"\n"
        if not card_bytes.startswith(prefix):
            failures.append(f"card heading drift: {card['card_path']}")
            continue
        body = card_bytes[len(prefix) :]
        old_body = original[card["old_body_start"] : card["old_body_end"]]
        if body != old_body:
            failures.append(f"NON-VERBATIM card body: {card['card_path']}")
        if hashlib.sha256(old_body).hexdigest() != card["body_sha256"]:
            failures.append(f"manifest body sha mismatch: {card['card_path']}")
    if failures:
        for failure in failures:
            print(f"[VERIFY RED] {failure}")
        return 1
    print(f"[VERIFY GREEN] {len(manifest['cards'])} cards byte-identical to original h3 bodies")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skill-md", type=Path, default=DEFAULT_SKILL_MD)
    parser.add_argument("--cards-dir", type=Path, default=DEFAULT_CARDS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true", help="write cards, new SKILL.md, manifest")
    parser.add_argument("--verify", action="store_true", help="verify written cards vs manifest")
    args = parser.parse_args()

    if args.verify:
        return do_verify(args.skill_md, args.manifest)

    data = args.skill_md.read_bytes()
    extraction = plan(data)
    new_skill, cards_bytes = build_outputs(data, extraction)
    print(f"cards: {len(extraction['cards'])}")
    print(f"new SKILL.md size: {len(new_skill)} bytes (was {len(data)})")
    if not args.write:
        for card in extraction["cards"]:
            print(f"  {card['card_path']}  <- bytes [{card['old_body_start']}, {card['old_body_end']})")
        print("dry-run only; pass --write to apply")
        return 0

    snapshot = args.manifest.parent / "skill-md-pre-extraction-snapshot.md"
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(data)
    args.cards_dir.mkdir(parents=True, exist_ok=True)
    for path, content in cards_bytes.items():
        (args.skill_md.parent / path).write_bytes(content)
    args.skill_md.write_bytes(new_skill)
    manifest = {
        "purpose": (
            "Byte-preserving extraction manifest: each card body must equal the "
            "original SKILL.md byte range. Verify with --verify against the "
            "committed pre-extraction snapshot."
        ),
        "original_skill_md_snapshot": str(snapshot.relative_to(ROOT)),
        "skill_md_sha256": extraction["skill_md_sha256"],
        "new_skill_md_sha256": hashlib.sha256(new_skill).hexdigest(),
        "router_preamble": ROUTER_PREAMBLE,
        "cards": extraction["cards"],
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(cards_bytes)} cards, new SKILL.md, snapshot, manifest {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
