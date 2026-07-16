#!/usr/bin/env python3
"""Deterministic, byte-preserving extraction of SKILL.md mode-pattern cards.

Increment 2 of fairy_tale #57: move each `### <harness>` section under
`## Mode patterns` into `references/cards/<slug>.md` VERBATIM, and replace the
mode-pattern bodies in SKILL.md with a compact router table.

Extraction provenance contract (review gate, PR #60 thread 2026-07-02):
- A card file is exactly `# <original title>\n` + the ORIGINAL section body
  bytes at extraction time (everything after the heading line up to the next
  section heading). No trimming, whitespace normalization, or reflow occurs.
- `--verify` re-reads every written card and byte-compares its body slice
  against the original SKILL.md byte range recorded in the manifest. A card
  intentionally evolved after extraction must instead carry a reviewed
  `evolution` object with its current body SHA-256 plus a live same-repository
  GitHub issue URL, stable node ID, body/title anchor, and reason. The original
  snapshot/body hash is still verified and never rewritten. Repository-relative
  paths are containment-checked, including symlinks. Any unpinned or unverifiable
  drift exits non-zero.
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
  python3 scripts/extract_mode_pattern_cards.py --selftest     # run verifier red-lock controls
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
EXPECTED_REPOSITORY = "bonginkan/fairy_tale"

HEADING_RE = re.compile(rb"^(#{2,3}) (.+)$", re.MULTILINE)
GITHUB_ISSUE_RE = re.compile(
    r"https://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/issues/"
    r"(?P<number>[1-9][0-9]*)"
)


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


def resolve_contained_path(base: Path, raw_ref: object, label: str) -> tuple[Path | None, str | None]:
    """Resolve an existing relative path without allowing lexical or symlink escape."""
    if not isinstance(raw_ref, str) or not raw_ref.strip():
        return None, f"invalid {label}: {raw_ref!r}"
    ref = Path(raw_ref)
    if ref.is_absolute() or ".." in ref.parts or ref == Path("."):
        return None, f"non-repo-relative {label}: {raw_ref}"
    candidate = base / ref
    try:
        resolved_base = base.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except OSError:
        return None, f"missing {label}: {raw_ref}"
    try:
        resolved.relative_to(resolved_base)
    except ValueError:
        return None, f"{label} escapes its allowed root: {raw_ref}"
    return resolved, None


def fetch_github_issue(issue_url: str) -> dict[str, Any]:
    """Read an issue from GitHub so provenance is not a URL-shape assertion."""
    match = GITHUB_ISSUE_RE.fullmatch(issue_url)
    if match is None:
        raise ValueError("invalid GitHub issue URL")
    repository = f"{match.group('owner')}/{match.group('repo')}"
    if repository != EXPECTED_REPOSITORY:
        raise ValueError(f"issue repository must be {EXPECTED_REPOSITORY}")
    api_url = (
        f"https://api.github.com/repos/{repository}/issues/{match.group('number')}"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fairy-tale-extraction-provenance-verifier",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(api_url, headers=headers), timeout=15) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"GitHub issue lookup failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("GitHub issue response was not an object")
    return payload


def do_verify(
    skill_md: Path,
    manifest_path: Path,
    issue_loader: Callable[[str], dict[str, Any]] = fetch_github_issue,
) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = []
    snapshot_ref = manifest.get("original_skill_md_snapshot")
    snapshot_path, snapshot_error = resolve_contained_path(
        ROOT, snapshot_ref, "manifest snapshot ref"
    )
    if snapshot_error:
        print(f"[VERIFY RED] {snapshot_error}")
        return 1
    assert snapshot_path is not None
    original = snapshot_path.read_bytes()
    if hashlib.sha256(original).hexdigest() != manifest["skill_md_sha256"]:
        failures.append("original snapshot sha mismatch vs manifest")
    original_count = 0
    evolved_count = 0
    issue_cache: dict[str, dict[str, Any] | ValueError] = {}
    for card in manifest["cards"]:
        card_ref = card.get("card_path")
        card_file, card_path_error = resolve_contained_path(
            skill_md.parent, card_ref, "card path in manifest"
        )
        if card_path_error:
            failures.append(card_path_error)
            continue
        assert card_file is not None
        card_bytes = card_file.read_bytes()
        prefix = b"# " + card["title"].encode("utf-8") + b"\n"
        if not card_bytes.startswith(prefix):
            failures.append(f"card heading drift: {card['card_path']}")
            continue
        body = card_bytes[len(prefix) :]
        old_body = original[card["old_body_start"] : card["old_body_end"]]
        if hashlib.sha256(old_body).hexdigest() != card["body_sha256"]:
            failures.append(f"manifest body sha mismatch: {card['card_path']}")
        evolution = card.get("evolution")
        if evolution is None:
            original_count += 1
            if body != old_body:
                failures.append(f"UNPINNED post-extraction drift: {card['card_path']}")
            continue
        evolved_count += 1
        if not isinstance(evolution, dict):
            failures.append(f"malformed evolution entry: {card['card_path']}")
            continue
        expected_evolution_keys = {
            "current_body_sha256",
            "issue",
            "issue_anchor",
            "issue_node_id",
            "reason",
        }
        if set(evolution) != expected_evolution_keys:
            failures.append(f"invalid evolution keys: {card['card_path']}")
            continue
        current_sha = evolution.get("current_body_sha256")
        if not isinstance(current_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", current_sha):
            failures.append(f"invalid evolution sha: {card['card_path']}")
            continue
        issue = evolution.get("issue")
        issue_match = GITHUB_ISSUE_RE.fullmatch(issue) if isinstance(issue, str) else None
        if issue_match is None:
            failures.append(f"invalid evolution issue: {card['card_path']}")
        elif f"{issue_match.group('owner')}/{issue_match.group('repo')}" != EXPECTED_REPOSITORY:
            failures.append(f"wrong-repository evolution issue: {card['card_path']}")
        issue_anchor = evolution.get("issue_anchor")
        if not isinstance(issue_anchor, str) or not issue_anchor.strip():
            failures.append(f"missing evolution issue anchor: {card['card_path']}")
        issue_node_id = evolution.get("issue_node_id")
        if not isinstance(issue_node_id, str) or not issue_node_id.startswith("I_"):
            failures.append(f"invalid evolution issue node id: {card['card_path']}")
        if not isinstance(evolution.get("reason"), str) or not evolution["reason"].strip():
            failures.append(f"missing evolution reason: {card['card_path']}")
        if issue_match is not None and isinstance(issue_anchor, str) and issue_anchor.strip():
            if issue not in issue_cache:
                try:
                    issue_cache[issue] = issue_loader(issue)
                except ValueError as exc:
                    issue_cache[issue] = exc
            issue_record = issue_cache[issue]
            if isinstance(issue_record, ValueError):
                failures.append(
                    f"unverified evolution issue: {card['card_path']} ({issue_record})"
                )
            else:
                if issue_record.get("html_url") != issue:
                    failures.append(f"evolution issue URL mismatch: {card['card_path']}")
                if "pull_request" in issue_record:
                    failures.append(f"evolution reference is a pull request: {card['card_path']}")
                if issue_record.get("node_id") != issue_node_id:
                    failures.append(f"evolution issue identity mismatch: {card['card_path']}")
                issue_text = f"{issue_record.get('title') or ''}\n{issue_record.get('body') or ''}"
                if issue_anchor not in issue_text:
                    failures.append(f"evolution issue anchor missing: {card['card_path']}")
        if hashlib.sha256(body).hexdigest() != current_sha:
            failures.append(f"evolved body sha mismatch: {card['card_path']}")
        if body == old_body:
            failures.append(f"redundant evolution entry: {card['card_path']}")
    if failures:
        for failure in failures:
            print(f"[VERIFY RED] {failure}")
        return 1
    print(
        f"[VERIFY GREEN] {len(manifest['cards'])} cards: "
        f"{original_count} original bodies + {evolved_count} pinned evolutions"
    )
    return 0


def run_selftest() -> int:
    """Lock the original/evolved provenance contract with positive and RED controls."""
    with tempfile.TemporaryDirectory(prefix=".extract-selftest-", dir=ROOT) as raw_tmp:
        tmp = Path(raw_tmp)
        skill_md = tmp / "skills" / "fairy-tale" / "SKILL.md"
        card_path = skill_md.parent / "references" / "cards" / "example.md"
        snapshot = tmp / "original.md"
        manifest_path = tmp / "manifest.json"
        original = b"## Mode patterns\n\n### Example\nOriginal body.\n"
        original_body = b"Original body.\n"
        body_start = original.index(original_body)
        body_end = body_start + len(original_body)
        snapshot.write_bytes(original)
        skill_md.parent.mkdir(parents=True)
        skill_md.write_bytes(b"## Mode patterns\n")
        card_path.parent.mkdir(parents=True)
        original_card = b"# Example\n" + original_body
        card_path.write_bytes(original_card)
        base_manifest = {
            "original_skill_md_snapshot": str(snapshot.relative_to(ROOT)),
            "skill_md_sha256": hashlib.sha256(original).hexdigest(),
            "cards": [
                {
                    "title": "Example",
                    "card_path": "references/cards/example.md",
                    "old_body_start": body_start,
                    "old_body_end": body_end,
                    "body_sha256": hashlib.sha256(original_body).hexdigest(),
                }
            ],
        }

        valid_issue_url = "https://github.com/bonginkan/fairy_tale/issues/1"
        valid_issue = {
            "html_url": valid_issue_url,
            "node_id": "I_example",
            "title": "Example contract evolution",
            "body": "The Example card is intentionally evolved.",
        }

        def fake_issue_loader(issue_url: str) -> dict[str, Any]:
            if issue_url != valid_issue_url:
                raise ValueError("fixture issue does not exist")
            return valid_issue

        def verify(manifest: dict) -> int:
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                return do_verify(skill_md, manifest_path, issue_loader=fake_issue_loader)

        controls = []
        controls.append(("original body", verify(copy.deepcopy(base_manifest)), 0))

        evolved_body = b"Evolved body.\n"
        card_path.write_bytes(b"# Example\n" + evolved_body)
        evolved_manifest = copy.deepcopy(base_manifest)
        evolved_manifest["cards"][0]["evolution"] = {
            "current_body_sha256": hashlib.sha256(evolved_body).hexdigest(),
            "issue": valid_issue_url,
            "issue_anchor": "Example",
            "issue_node_id": "I_example",
            "reason": "reviewed contract evolution",
        }
        controls.append(("pinned evolution", verify(evolved_manifest), 0))

        controls.append(("unpinned drift", verify(copy.deepcopy(base_manifest)), 1))

        stale_manifest = copy.deepcopy(evolved_manifest)
        stale_manifest["cards"][0]["evolution"]["current_body_sha256"] = "0" * 64
        controls.append(("stale evolution hash", verify(stale_manifest), 1))

        unbound_manifest = copy.deepcopy(evolved_manifest)
        unbound_manifest["cards"][0]["evolution"]["issue"] = "issue 1"
        controls.append(("unbound evolution metadata", verify(unbound_manifest), 1))

        absolute_snapshot = copy.deepcopy(base_manifest)
        absolute_snapshot["original_skill_md_snapshot"] = str(snapshot)
        controls.append(("absolute snapshot path", verify(absolute_snapshot), 1))

        traversal_snapshot = copy.deepcopy(base_manifest)
        snapshot_relative = snapshot.relative_to(ROOT)
        traversal_snapshot["original_skill_md_snapshot"] = str(
            snapshot_relative.parent / "nested" / ".." / snapshot_relative.name
        )
        controls.append(("snapshot traversal", verify(traversal_snapshot), 1))

        absolute_card = copy.deepcopy(base_manifest)
        absolute_card["cards"][0]["card_path"] = str(card_path)
        controls.append(("absolute card path", verify(absolute_card), 1))

        traversal_card = copy.deepcopy(base_manifest)
        traversal_card["cards"][0]["card_path"] = (
            "references/cards/nested/../example.md"
        )
        controls.append(("card traversal", verify(traversal_card), 1))

        nonexistent_issue = copy.deepcopy(evolved_manifest)
        nonexistent_issue["cards"][0]["evolution"]["issue"] = (
            "https://github.com/bonginkan/fairy_tale/issues/999999999"
        )
        controls.append(("nonexistent evolution issue", verify(nonexistent_issue), 1))

        unrelated_issue = copy.deepcopy(evolved_manifest)
        unrelated_issue["cards"][0]["evolution"]["issue_anchor"] = "Unrelated card"
        controls.append(("unrelated evolution issue", verify(unrelated_issue), 1))

        wrong_issue_identity = copy.deepcopy(evolved_manifest)
        wrong_issue_identity["cards"][0]["evolution"]["issue_node_id"] = "I_wrong"
        controls.append(("wrong evolution issue identity", verify(wrong_issue_identity), 1))

    failures = [name for name, actual, expected in controls if actual != expected]
    if failures:
        for name in failures:
            print(f"[SELFTEST RED] unexpected verifier result: {name}")
        return 1
    print(f"[SELFTEST GREEN] {len(controls)} extraction provenance controls")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skill-md", type=Path, default=DEFAULT_SKILL_MD)
    parser.add_argument("--cards-dir", type=Path, default=DEFAULT_CARDS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--write", action="store_true", help="write cards, new SKILL.md, manifest")
    parser.add_argument("--verify", action="store_true", help="verify written cards vs manifest")
    parser.add_argument("--selftest", action="store_true", help="run verifier red-lock controls")
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()
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
            "Extraction provenance manifest: each original card body must equal "
            "the recorded SKILL.md byte range unless a reviewed, issue-bound "
            "evolution pins its current body hash. Verify with --verify against "
            "the committed pre-extraction snapshot."
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
