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
  `evolution` chain: an ordered list where each entry pins the body SHA-256 it
  produced, the body SHA-256 it superseded, and a live same-repository GitHub
  issue URL, stable node ID, body/title anchor, and reason. Entry 0 supersedes
  the extracted original and the last entry authorises the body on disk. An
  entry may not credit an issue older than its predecessor's, and one issue
  authorises one entry, so a later authorisation cannot overwrite an earlier
  one in place. The original snapshot/body hash is still verified and never
  rewritten. Repository-relative paths are containment-checked, including
  symlinks. Any unpinned or unverifiable drift exits non-zero.
- What one manifest can and cannot show. Read alone, a chain shows that its
  bodies are internally linked and that its authorising issues are consistent
  with that order. It does NOT show that a named issue is the one that
  authorised a body -- another issue of the right vintage passes -- nor that a
  body it lists ever existed, nor that the chain was never shortened: an entry
  dropped WITH its successor relinked to the predecessor leaves a chain that
  verifies. Only an unrelinked drop breaks a link.
- `--append-only-base REV` supplies what one manifest cannot: the same file at
  an immutable earlier revision. Every authorisation recorded at REV must still
  be recorded, in the same relative order; entries may be inserted (this is how
  #103 was recovered) but never removed or reordered. REV must be a PR base SHA
  or merge-base -- never HEAD, which in a fresh checkout IS the file under test,
  making the comparison trivially true. CI binds this to the merge base, so the
  append-only property holds from the merge that introduced it forward; the
  history declared in that merge is a claim, not a proof.
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


ISO_INSTANT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


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
        # An evolution chain is ORDERED and append-only: entry 0 is the first
        # reviewed evolution, the last entry authorises the body on disk now.
        # A single object would make each re-pin erase its predecessor, so a
        # card that evolved twice could name only its newest authorisation.
        if not isinstance(evolution, list) or not evolution:
            failures.append(f"malformed evolution chain: {card['card_path']}")
            continue
        chain_shas: list[str] = []
        chain_links: list[str] = []
        chain_created: list[str | None] = []
        chain_ok = True
        for position, entry in enumerate(evolution):
            where = f"{card['card_path']}[{position}]"
            entry_created: str | None = None
            if not isinstance(entry, dict):
                failures.append(f"malformed evolution entry: {where}")
                chain_ok = False
                continue
            expected_evolution_keys = {
                "current_body_sha256",
                "supersedes_body_sha256",
                "issue",
                "issue_anchor",
                "issue_node_id",
                "reason",
            }
            if set(entry) != expected_evolution_keys:
                failures.append(f"invalid evolution keys: {where}")
                chain_ok = False
                continue
            current_sha = entry.get("current_body_sha256")
            if not isinstance(current_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", current_sha):
                failures.append(f"invalid evolution sha: {where}")
                chain_ok = False
                continue
            supersedes = entry.get("supersedes_body_sha256")
            if not isinstance(supersedes, str) or not re.fullmatch(r"[0-9a-f]{64}", supersedes):
                failures.append(f"invalid evolution supersedes sha: {where}")
                chain_ok = False
                continue
            chain_shas.append(current_sha)
            chain_links.append(supersedes)
            issue = entry.get("issue")
            issue_match = GITHUB_ISSUE_RE.fullmatch(issue) if isinstance(issue, str) else None
            if issue_match is None:
                failures.append(f"invalid evolution issue: {where}")
            elif f"{issue_match.group('owner')}/{issue_match.group('repo')}" != EXPECTED_REPOSITORY:
                failures.append(f"wrong-repository evolution issue: {where}")
            issue_anchor = entry.get("issue_anchor")
            if not isinstance(issue_anchor, str) or not issue_anchor.strip():
                failures.append(f"missing evolution issue anchor: {where}")
            issue_node_id = entry.get("issue_node_id")
            if not isinstance(issue_node_id, str) or not issue_node_id.startswith("I_"):
                failures.append(f"invalid evolution issue node id: {where}")
            if not isinstance(entry.get("reason"), str) or not entry["reason"].strip():
                failures.append(f"missing evolution reason: {where}")
            if issue_match is not None and isinstance(issue_anchor, str) and issue_anchor.strip():
                if issue not in issue_cache:
                    try:
                        issue_cache[issue] = issue_loader(issue)
                    except ValueError as exc:
                        issue_cache[issue] = exc
                issue_record = issue_cache[issue]
                if isinstance(issue_record, ValueError):
                    failures.append(f"unverified evolution issue: {where} ({issue_record})")
                else:
                    if issue_record.get("html_url") != issue:
                        failures.append(f"evolution issue URL mismatch: {where}")
                    if "pull_request" in issue_record:
                        failures.append(f"evolution reference is a pull request: {where}")
                    if issue_record.get("node_id") != issue_node_id:
                        failures.append(f"evolution issue identity mismatch: {where}")
                    issue_text = f"{issue_record.get('title') or ''}\n{issue_record.get('body') or ''}"
                    if issue_anchor not in issue_text:
                        failures.append(f"evolution issue anchor missing: {where}")
                    created_at = issue_record.get("created_at")
                    if not isinstance(created_at, str) or not ISO_INSTANT_RE.fullmatch(created_at):
                        failures.append(f"evolution issue has no usable created_at: {where}")
                    else:
                        entry_created = created_at
            chain_created.append(entry_created)
        if not chain_ok:
            continue
        # A body hash may authorise exactly one position. Without this, a
        # duplicated or reordered history reads as a longer chain that still
        # ends on the live body.
        if len(set(chain_shas)) != len(chain_shas):
            failures.append(f"duplicate evolution body sha in chain: {card['card_path']}")
        # One issue authorises one entry. Reusing an identity lets a later
        # authorisation overwrite an earlier one in place -- the chain keeps its
        # length and its links, and the replaced authorisation is simply gone,
        # which is the loss this chain exists to prevent.
        chain_identities = [
            entry.get("issue_node_id")
            for entry in evolution
            if isinstance(entry, dict) and isinstance(entry.get("issue_node_id"), str)
        ]
        if len(set(chain_identities)) != len(chain_identities):
            failures.append(f"repeated evolution authorisation in chain: {card['card_path']}")
        # Each entry names the body it replaced, so the chain is linked rather
        # than merely ordered: entry 0 replaces the extracted original, and
        # every later entry replaces its predecessor. Dropping, reordering, or
        # inserting an entry breaks a link, which is what makes a *silently
        # shortened* history detectable at all.
        expected_link = card["body_sha256"]
        for position, (link, produced) in enumerate(zip(chain_links, chain_shas)):
            if link != expected_link:
                failures.append(
                    f"evolution chain link broken at {card['card_path']}[{position}]: "
                    f"supersedes {link[:12]}, expected {expected_link[:12]}"
                )
                break
            expected_link = produced
        # The link fixes the order of BODIES. It does not say which issue
        # authorised which body: swapping the issue metadata of two entries
        # leaves every hash intact. Authorisation cannot run backwards in time,
        # so the issues along a chain must not get older as the chain advances.
        # created_at comes from the issue records already fetched above, so this
        # costs no additional request.
        for position in range(1, len(chain_created)):
            earlier, later = chain_created[position - 1], chain_created[position]
            if earlier is None or later is None:
                continue
            if later < earlier:
                failures.append(
                    f"evolution attribution out of order at {card['card_path']}[{position}]: "
                    f"authorising issue is older than its predecessor's"
                )
                break
        body_sha = hashlib.sha256(body).hexdigest()
        if chain_shas and chain_shas[-1] != body_sha:
            # Either the body moved without a new entry, or an entry that is not
            # the current authorisation was ordered last.
            if body_sha in chain_shas:
                failures.append(f"evolution chain out of order: {card['card_path']}")
            else:
                failures.append(f"evolved body sha mismatch: {card['card_path']}")
        if body == old_body:
            failures.append(f"redundant evolution entry: {card['card_path']}")
    if failures:
        for failure in failures:
            print(f"[VERIFY RED] {failure}")
        return 1
    entry_count = sum(
        len(card["evolution"])
        for card in manifest["cards"]
        if isinstance(card.get("evolution"), list)
    )
    print(
        f"[VERIFY GREEN] {len(manifest['cards'])} cards: "
        f"{original_count} original bodies + {evolved_count} evolved cards "
        f"carrying {entry_count} pinned authorisations"
    )
    return 0


def chain_identity(entry: Any) -> tuple[str, str] | None:
    """The part of a pin that must survive every later edit."""
    if not isinstance(entry, dict):
        return None
    node_id = entry.get("issue_node_id")
    sha = entry.get("current_body_sha256")
    if not isinstance(node_id, str) or not isinstance(sha, str):
        return None
    return (node_id, sha)


def normalised_chain(card: Any) -> list[tuple[str, str] | None]:
    """Read a chain from either shape, so a base predating the list still compares."""
    if not isinstance(card, dict):
        return []
    evolution = card.get("evolution")
    if evolution is None:
        return []
    entries = evolution if isinstance(evolution, list) else [evolution]
    return [chain_identity(entry) for entry in entries]


def verify_append_only(head_manifest: dict, base_manifest: dict) -> list[str]:
    """Every authorisation the base recorded must still be recorded, in order.

    A chain cannot prove on its own that it was never shortened: an editor who
    drops an entry can relink the survivor to the original and leave a chain
    that verifies. The missing piece is an independent record of what the chain
    held before, which is what the base revision is. Entries may be inserted --
    this repository recovered #103 that way -- but never removed or reordered.
    """
    failures: list[str] = []
    head_by_path = {
        card.get("card_path"): card
        for card in head_manifest.get("cards", [])
        if isinstance(card, dict)
    }
    for base_card in base_manifest.get("cards", []):
        if not isinstance(base_card, dict):
            continue
        base_chain = [item for item in normalised_chain(base_card) if item is not None]
        if not base_chain:
            continue
        path = base_card.get("card_path")
        head_card = head_by_path.get(path)
        if head_card is None:
            failures.append(f"card with a recorded chain is gone from the manifest: {path}")
            continue
        head_chain = [item for item in normalised_chain(head_card) if item is not None]
        position = 0
        for wanted in base_chain:
            while position < len(head_chain) and head_chain[position] != wanted:
                position += 1
            if position == len(head_chain):
                node_id, sha = wanted
                failures.append(
                    f"authorisation dropped or reordered since the base revision: "
                    f"{path} ({node_id} -> {sha[:12]})"
                )
                break
            position += 1
    return failures


def do_verify_append_only(manifest_path: Path, base_rev: str, relative: str) -> int:
    """Compare the working manifest against the same file at an immutable revision."""
    import subprocess

    try:
        base_bytes = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{base_rev}:{relative}"],
            capture_output=True,
            check=True,
        ).stdout
    except FileNotFoundError:
        print("[APPEND-ONLY RED] git is not available, so the base manifest cannot be read")
        return 1
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode("utf-8", "replace").strip().splitlines()
        print(
            f"[APPEND-ONLY RED] cannot read {relative} at {base_rev}: "
            f"{detail[-1] if detail else 'unknown error'}"
        )
        return 1
    try:
        base_manifest = json.loads(base_bytes.decode("utf-8"))
        head_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"[APPEND-ONLY RED] manifest is not readable JSON: {exc}")
        return 1
    failures = verify_append_only(head_manifest, base_manifest)
    if failures:
        for failure in failures:
            print(f"[APPEND-ONLY RED] {failure}")
        return 1
    recorded = sum(
        len([item for item in normalised_chain(card) if item is not None])
        for card in base_manifest.get("cards", [])
    )
    print(f"[APPEND-ONLY GREEN] {recorded} authorisation(s) at {base_rev} still recorded")
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
            "created_at": "2026-01-02T03:04:05Z",
        }
        later_issue_url = "https://github.com/bonginkan/fairy_tale/issues/2"
        later_issue = {
            "html_url": later_issue_url,
            "node_id": "I_example_later",
            "title": "Example second contract evolution",
            "body": "The Example card is intentionally evolved again.",
            "created_at": "2026-02-03T04:05:06Z",
        }
        fixture_issues = {valid_issue_url: valid_issue, later_issue_url: later_issue}

        def fake_issue_loader(issue_url: str) -> dict[str, Any]:
            if issue_url not in fixture_issues:
                raise ValueError("fixture issue does not exist")
            return fixture_issues[issue_url]

        def verify(manifest: dict) -> int:
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                return do_verify(skill_md, manifest_path, issue_loader=fake_issue_loader)

        controls = []
        controls.append(("original body", verify(copy.deepcopy(base_manifest)), 0))

        original_sha = hashlib.sha256(original_body).hexdigest()

        def pin(
            current: bytes,
            supersedes: str,
            reason: str,
            issue: dict[str, str] | None = None,
        ) -> dict[str, str]:
            source = issue or valid_issue
            return {
                "current_body_sha256": hashlib.sha256(current).hexdigest(),
                "supersedes_body_sha256": supersedes,
                "issue": source["html_url"],
                "issue_anchor": "Example",
                "issue_node_id": source["node_id"],
                "reason": reason,
            }

        evolved_body = b"Evolved body.\n"
        card_path.write_bytes(b"# Example\n" + evolved_body)
        evolved_manifest = copy.deepcopy(base_manifest)
        evolved_manifest["cards"][0]["evolution"] = [
            pin(evolved_body, original_sha, "reviewed contract evolution")
        ]
        controls.append(("pinned evolution", verify(evolved_manifest), 0))

        controls.append(("unpinned drift", verify(copy.deepcopy(base_manifest)), 1))

        # A card that evolves twice keeps BOTH authorisations, linked by the
        # body each entry replaced.
        second_body = b"Second evolved body.\n"
        card_path.write_bytes(b"# Example\n" + second_body)
        first_pin = pin(evolved_body, original_sha, "first reviewed evolution")
        second_pin = pin(
            second_body,
            first_pin["current_body_sha256"],
            "second reviewed evolution",
            issue=later_issue,
        )
        chain_manifest = copy.deepcopy(base_manifest)
        chain_manifest["cards"][0]["evolution"] = [first_pin, second_pin]
        controls.append(("linked evolution chain", verify(chain_manifest), 0))

        # RED: hashes and links untouched, only the authorisations swapped, so
        # the older issue would be credited with the newer body.
        swapped_manifest = copy.deepcopy(chain_manifest)
        swapped = swapped_manifest["cards"][0]["evolution"]
        for key in ("issue", "issue_node_id"):
            swapped[0][key], swapped[1][key] = swapped[1][key], swapped[0][key]
        controls.append(("swapped evolution attribution", verify(swapped_manifest), 1))

        # RED: the later authorisation overwrites the earlier one in place. The
        # chain keeps its length, its links, and its ordering -- only the
        # replaced authorisation is gone.
        overwritten_manifest = copy.deepcopy(chain_manifest)
        overwritten = overwritten_manifest["cards"][0]["evolution"]
        overwritten[0]["issue"] = overwritten[1]["issue"]
        overwritten[0]["issue_node_id"] = overwritten[1]["issue_node_id"]
        controls.append(("overwritten evolution authorisation", verify(overwritten_manifest), 1))

        undated_manifest = copy.deepcopy(chain_manifest)
        fixture_issues[later_issue_url] = {
            k: v for k, v in later_issue.items() if k != "created_at"
        }
        controls.append(("evolution issue without created_at", verify(undated_manifest), 1))
        fixture_issues[later_issue_url] = later_issue

        # RED: the predecessor is silently dropped. The surviving entry still
        # matches the live body, so only the broken link catches this.
        dropped_manifest = copy.deepcopy(base_manifest)
        dropped_manifest["cards"][0]["evolution"] = [copy.deepcopy(second_pin)]
        controls.append(("dropped history entry", verify(dropped_manifest), 1))

        reordered_manifest = copy.deepcopy(base_manifest)
        reordered_manifest["cards"][0]["evolution"] = [
            copy.deepcopy(second_pin),
            copy.deepcopy(first_pin),
        ]
        controls.append(("reordered evolution chain", verify(reordered_manifest), 1))

        duplicated_manifest = copy.deepcopy(base_manifest)
        duplicated_manifest["cards"][0]["evolution"] = [
            copy.deepcopy(first_pin),
            copy.deepcopy(first_pin),
            copy.deepcopy(second_pin),
        ]
        controls.append(("duplicated evolution entry", verify(duplicated_manifest), 1))

        unrooted_manifest = copy.deepcopy(chain_manifest)
        unrooted_manifest["cards"][0]["evolution"][0]["supersedes_body_sha256"] = "0" * 64
        controls.append(("evolution chain not rooted in the original", verify(unrooted_manifest), 1))

        legacy_shape = copy.deepcopy(base_manifest)
        legacy_shape["cards"][0]["evolution"] = copy.deepcopy(second_pin)
        controls.append(("legacy single-object evolution", verify(legacy_shape), 1))

        empty_chain = copy.deepcopy(base_manifest)
        empty_chain["cards"][0]["evolution"] = []
        controls.append(("empty evolution chain", verify(empty_chain), 1))

        card_path.write_bytes(b"# Example\n" + evolved_body)

        stale_manifest = copy.deepcopy(evolved_manifest)
        stale_manifest["cards"][0]["evolution"][-1]["current_body_sha256"] = "0" * 64
        controls.append(("stale evolution hash", verify(stale_manifest), 1))

        unbound_manifest = copy.deepcopy(evolved_manifest)
        unbound_manifest["cards"][0]["evolution"][-1]["issue"] = "issue 1"
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
        nonexistent_issue["cards"][0]["evolution"][-1]["issue"] = (
            "https://github.com/bonginkan/fairy_tale/issues/999999999"
        )
        controls.append(("nonexistent evolution issue", verify(nonexistent_issue), 1))

        unrelated_issue = copy.deepcopy(evolved_manifest)
        unrelated_issue["cards"][0]["evolution"][-1]["issue_anchor"] = "Unrelated card"
        controls.append(("unrelated evolution issue", verify(unrelated_issue), 1))

        wrong_issue_identity = copy.deepcopy(evolved_manifest)
        wrong_issue_identity["cards"][0]["evolution"][-1]["issue_node_id"] = "I_wrong"
        controls.append(("wrong evolution issue identity", verify(wrong_issue_identity), 1))

        # The chain cannot police its own length: these controls run against a
        # base revision, which is the only record of what the chain held before.
        def append_only(base_cards: list, head_cards: list) -> int:
            found = verify_append_only({"cards": head_cards}, {"cards": base_cards})
            return 1 if found else 0

        base_card = {
            "card_path": "references/cards/example.md",
            "evolution": [copy.deepcopy(first_pin), copy.deepcopy(second_pin)],
        }
        head_same = copy.deepcopy(base_card)
        controls.append(("append-only: unchanged chain", append_only([base_card], [head_same]), 0))

        head_extended = copy.deepcopy(base_card)
        head_extended["evolution"].append(
            pin(b"Third body.\n", second_pin["current_body_sha256"], "third", issue=later_issue)
        )
        controls.append(("append-only: extended chain", append_only([base_card], [head_extended]), 0))

        # H: the entry is dropped AND the survivor is relinked, so the shortened
        # chain verifies on its own. Only the base revision still remembers it.
        head_relinked = {
            "card_path": "references/cards/example.md",
            "evolution": [
                {**copy.deepcopy(second_pin), "supersedes_body_sha256": original_sha}
            ],
        }
        controls.append(("append-only: relinked drop", append_only([base_card], [head_relinked]), 1))

        head_reordered = copy.deepcopy(base_card)
        head_reordered["evolution"].reverse()
        controls.append(("append-only: reordered chain", append_only([base_card], [head_reordered]), 1))

        # An entry recovered from history may be inserted BEFORE a recorded one:
        # that is how #103 came back, and it drops nothing.
        head_recovered = {
            "card_path": "references/cards/example.md",
            "evolution": [copy.deepcopy(first_pin), copy.deepcopy(second_pin)],
        }
        legacy_base = {
            "card_path": "references/cards/example.md",
            "evolution": copy.deepcopy(second_pin),
        }
        controls.append(
            ("append-only: legacy singleton base accepts recovery", append_only([legacy_base], [head_recovered]), 0)
        )

        controls.append(("append-only: card removed", append_only([base_card], []), 1))

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
    parser.add_argument(
        "--append-only-base",
        metavar="REV",
        help=(
            "compare the manifest against the same file at REV (an immutable "
            "revision such as the PR base SHA or a merge-base, never HEAD) and "
            "fail if a recorded authorisation was dropped or reordered"
        ),
    )
    args = parser.parse_args()

    if args.selftest:
        return run_selftest()
    if args.append_only_base:
        return do_verify_append_only(
            args.manifest,
            args.append_only_base,
            str(args.manifest.resolve().relative_to(ROOT)),
        )
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
