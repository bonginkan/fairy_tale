#!/usr/bin/env python3
"""Deterministic, byte-preserving extraction of process.md record cards.

Increment 4 of fairy_tale #57 (WI3): move each `## <record>` section of
`references/process.md` VERBATIM into `references/process/<slug>.md`, and turn
process.md into a compact index so a task loads only the record it needs.

Shares the extraction/verify core with extract_mode_pattern_cards.py (same
original snapshot + byte-range/hash provenance, optional live-issue-bound
pinned evolutions, contained repo-relative manifest paths with traversal and
symlink escape RED, duplicate slugs a hard error).

The ONLY non-moved text this script introduces (disclosed, reviewed as new):
the index preamble line and the index table (title verbatim / mechanical
first-line hint / record path).

Usage:
  python3 scripts/extract_process_records.py                # dry-run plan
  python3 scripts/extract_process_records.py --write        # write records + index
  python3 scripts/extract_process_records.py --verify       # byte-verify vs manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from extract_mode_pattern_cards import (  # noqa: E402
    ROOT,
    do_verify,
    find_sections,
    first_route_hint,
    slugify,
)

DEFAULT_PROCESS_MD = ROOT / "skills" / "fairy-tale" / "references" / "process.md"
DEFAULT_RECORDS_DIR = ROOT / "skills" / "fairy-tale" / "references" / "process"
DEFAULT_MANIFEST = ROOT / "docs" / "skill-budget" / "process-extraction-manifest.json"
SKILL_MD_FOR_VERIFY = ROOT / "skills" / "fairy-tale" / "SKILL.md"

INDEX_PREAMBLE = (
    "Each record template lives in its own card under `references/process/`; "
    "read only the record the current task needs.\n"
)
ROUTE_HINT_MAX = 140


def plan(data: bytes) -> dict:
    sections = [s for s in find_sections(data) if s["level"] == 2]
    if not sections:
        raise SystemExit("no '## <record>' sections found in process.md")
    header_end = sections[0]["heading_start"]
    records = []
    seen: dict[str, str] = {}
    for section in sections:
        slug = slugify(section["title"])
        if slug in seen:
            raise SystemExit(f"duplicate slug '{slug}' for '{section['title']}' and '{seen[slug]}'")
        seen[slug] = section["title"]
        body = data[section["body_start"] : section["body_end"]]
        records.append(
            {
                "title": section["title"],
                "slug": slug,
                "card_path": f"references/process/{slug}.md",
                "old_body_start": section["body_start"],
                "old_body_end": section["body_end"],
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "route_hint": first_route_hint(body),
            }
        )
    return {
        "skill_md_sha256": hashlib.sha256(data).hexdigest(),
        "header_end": header_end,
        "records": records,
    }


def index_block(records: list[dict]) -> bytes:
    lines = [INDEX_PREAMBLE, "", "| Record | Use for | Card |", "|---|---|---|"]
    for record in records:
        lines.append(f"| {record['title']} | {record['route_hint']} | `{record['card_path']}` |")
    lines.append("")
    return ("\n".join(lines)).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--process-md", type=Path, default=DEFAULT_PROCESS_MD)
    parser.add_argument("--records-dir", type=Path, default=DEFAULT_RECORDS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    if args.verify:
        # Same verify core as the mode-pattern cards: repo-relative snapshot,
        # absolute manifest paths RED, byte-compare each record body.
        return do_verify(SKILL_MD_FOR_VERIFY, args.manifest)

    data = args.process_md.read_bytes()
    extraction = plan(data)
    new_index = data[: extraction["header_end"]] + index_block(extraction["records"])
    print(f"records: {len(extraction['records'])}")
    print(f"new process.md size: {len(new_index)} bytes (was {len(data)})")
    if not args.write:
        for record in extraction["records"]:
            print(f"  {record['card_path']}  <- bytes [{record['old_body_start']}, {record['old_body_end']})")
        print("dry-run only; pass --write to apply")
        return 0

    snapshot = args.manifest.parent / "process-md-pre-extraction-snapshot.md"
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(data)
    args.records_dir.mkdir(parents=True, exist_ok=True)
    for record in extraction["records"]:
        body = data[record["old_body_start"] : record["old_body_end"]]
        (SKILL_MD_FOR_VERIFY.parent / record["card_path"]).write_bytes(
            b"# " + record["title"].encode("utf-8") + b"\n" + body
        )
    args.process_md.write_bytes(new_index)
    manifest = {
        "purpose": (
            "Byte-preserving extraction manifest for process.md records; verify "
            "with extract_process_records.py --verify against the committed "
            "pre-extraction snapshot."
        ),
        "original_skill_md_snapshot": str(snapshot.relative_to(ROOT)),
        "skill_md_sha256": extraction["skill_md_sha256"],
        "new_skill_md_sha256": hashlib.sha256(new_index).hexdigest(),
        "index_preamble": INDEX_PREAMBLE,
        "cards": extraction["records"],
    }
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(extraction['records'])} records, new index, snapshot, manifest {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
