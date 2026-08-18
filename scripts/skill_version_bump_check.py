#!/usr/bin/env python3
"""Fail a change that edits the shipped payload without bumping the plugin version.

The distributed plugin is served from a version-keyed cache, so a host that
already holds `0.2.38` keeps serving `0.2.38` no matter what the source says:
`claude plugin update` reports "already at the latest version" and re-fetches
nothing. Three merged PRs edited the skills under one version, and every host's
plugin copy stayed three revisions behind while the user-skill copy moved on.

The rule was already understood -- bump when the skills change -- and nothing
enforced it, so forgetting produced no signal anywhere. This is that signal.

Checks, against an immutable base revision (a PR base SHA or merge base, never
HEAD, which in a checkout IS the tree under test):

- any change under a shipped path requires a different plugin version;
- the plugin manifest and the marketplace entry must agree on that version;
- a version that moves backwards is refused.

Usage:
  python3 scripts/skill_version_bump_check.py --base REV
  python3 scripts/skill_version_bump_check.py --selftest
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST = "plugins/fairy-tale/.claude-plugin/plugin.json"
MARKETPLACE_MANIFEST = ".claude-plugin/marketplace.json"
PLUGIN_NAME = "fairy-tale"
# Every tree whose bytes reach an installed copy, measured against what a host
# actually holds rather than chosen by name: the plugin payload is the whole
# `plugins/fairy-tale/` tree (197 files, of which 110 are skills -- the other 87
# are scripts, schemas, docs, adapters, examples, hooks, fixtures and resources,
# and a hook ships executable behaviour), and `skills/` is the canonical tree the
# tarball installer copies. Naming only the skills paths left 44% of the payload
# outside the gate.
SHIPPED_PREFIXES = ("skills/", "plugins/fairy-tale/")
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = SEMVER_RE.match(value.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def marketplace_version(document: object, plugin_name: str = PLUGIN_NAME) -> str | None:
    """The marketplace lists plugins; read the entry this repository ships."""
    if not isinstance(document, dict):
        return None
    entries = document.get("plugins")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == plugin_name:
            version = entry.get("version")
            return version if isinstance(version, str) else None
    return None


def evaluate(
    changed_paths: list[str],
    base_version: str | None,
    head_version: str | None,
    head_marketplace_version: str | None,
) -> list[str]:
    """The whole rule, free of git so the controls can exercise it directly."""
    failures: list[str] = []
    head_parsed = parse_version(head_version)
    if head_parsed is None:
        failures.append(f"plugin version is not semver: {head_version!r}")
    if head_marketplace_version != head_version:
        failures.append(
            f"plugin manifest says {head_version!r} but the marketplace entry says "
            f"{head_marketplace_version!r}; an installed copy keys on one of them"
        )
    # A version that moves backwards is wrong whatever else the change touched:
    # a host holding the higher version will not come back down, so the lower
    # one is unreachable. Checked before the shipped-file question, because
    # checking it after made a manifest-only downgrade pass.
    base_parsed = parse_version(base_version)
    if head_parsed is not None and base_parsed is not None and head_parsed < base_parsed:
        failures.append(
            f"plugin version moved backwards: {base_version} -> {head_version}"
        )
    shipped = sorted(
        path for path in changed_paths if path.startswith(SHIPPED_PREFIXES)
    )
    if not shipped:
        return failures
    if base_version is None:
        failures.append("cannot read the plugin version at the base revision")
        return failures
    if head_version == base_version:
        failures.append(
            f"{len(shipped)} shipped file(s) changed while the plugin version "
            f"stayed {base_version!r} -- a version-keyed cache will keep serving the "
            f"old copy; first: {shipped[0]}"
        )
    return failures


def git(*args: str) -> tuple[int, str]:
    try:
        done = subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True
        )
    except FileNotFoundError:
        return 1, ""
    return done.returncode, done.stdout


def read_at(rev: str, relative: str) -> object | None:
    code, out = git("show", f"{rev}:{relative}")
    if code != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def do_check(base_rev: str) -> int:
    code, resolved = git("rev-parse", "--verify", f"{base_rev}^{{commit}}")
    resolved = resolved.strip()
    if code != 0 or not resolved:
        print(f"[VERSION-BUMP RED] cannot resolve {base_rev} to a commit")
        return 1
    head_code, head_sha = git("rev-parse", "--verify", "HEAD^{commit}")
    head_sha = head_sha.strip()
    if head_code != 0 or not head_sha:
        print("[VERSION-BUMP RED] cannot resolve HEAD")
        return 1
    if resolved == head_sha:
        print(
            f"[VERSION-BUMP RED] {base_rev} resolves to HEAD ({head_sha[:12]}): a tree "
            f"compared against itself reports no change -- pass a PR base SHA or merge base"
        )
        return 1
    diff_code, diff_out = git("diff", "--name-only", resolved)
    if diff_code != 0:
        print(f"[VERSION-BUMP RED] cannot diff against {base_rev}")
        return 1
    changed = [line.strip() for line in diff_out.splitlines() if line.strip()]

    base_manifest = read_at(resolved, PLUGIN_MANIFEST)
    base_version = (
        base_manifest.get("version") if isinstance(base_manifest, dict) else None
    )
    try:
        head_manifest = json.loads((ROOT / PLUGIN_MANIFEST).read_text(encoding="utf-8"))
        head_marketplace = json.loads(
            (ROOT / MARKETPLACE_MANIFEST).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[VERSION-BUMP RED] cannot read a manifest in the working tree: {exc}")
        return 1

    failures = evaluate(
        changed,
        base_version if isinstance(base_version, str) else None,
        head_manifest.get("version"),
        marketplace_version(head_marketplace),
    )
    if failures:
        for failure in failures:
            print(f"[VERSION-BUMP RED] {failure}")
        return 1
    shipped = [p for p in changed if p.startswith(SHIPPED_PREFIXES)]
    if shipped:
        print(
            f"[VERSION-BUMP GREEN] {len(shipped)} shipped file(s) changed since "
            f"{base_rev}; plugin version {base_version} -> {head_manifest.get('version')}"
        )
    else:
        print(
            f"[VERSION-BUMP GREEN] no shipped file changed since {base_rev}; "
            f"version {head_manifest.get('version')} held"
        )
    return 0


def run_selftest() -> int:
    controls = [
        ("skills changed, version bumped", evaluate(["skills/fairy-tale/SKILL.md"], "0.2.38", "0.2.39", "0.2.39"), 0),
        ("skills changed, version held", evaluate(["skills/fairy-tale/SKILL.md"], "0.2.38", "0.2.38", "0.2.38"), 1),
        ("mirrored skills changed, version held", evaluate(["plugins/fairy-tale/skills/fairy-tale/SKILL.md"], "0.2.38", "0.2.38", "0.2.38"), 1),
        ("nothing shipped changed, version held", evaluate(["docs/notes.md", "scripts/x.py"], "0.2.38", "0.2.38", "0.2.38"), 0),
        ("manifests disagree", evaluate([], "0.2.38", "0.2.39", "0.2.38"), 1),
        ("version moved backwards", evaluate(["skills/fairy-tale/SKILL.md"], "0.2.38", "0.2.37", "0.2.37"), 1),
        ("version moved backwards with nothing shipped changed", evaluate(["docs/notes.md"], "0.2.39", "0.2.38", "0.2.38"), 1),
        ("version moved backwards with no change at all", evaluate([], "0.2.39", "0.2.38", "0.2.38"), 1),
        ("shipped payload outside skills, version held", evaluate(["plugins/fairy-tale/hooks/hooks.json"], "0.2.38", "0.2.38", "0.2.38"), 1),
        ("shipped payload outside skills, version bumped", evaluate(["plugins/fairy-tale/scripts/x.py"], "0.2.38", "0.2.39", "0.2.39"), 0),
        ("version not semver", evaluate([], "0.2.38", "latest", "latest"), 1),
        ("base version unreadable", evaluate(["skills/fairy-tale/SKILL.md"], None, "0.2.39", "0.2.39"), 1),
        ("marketplace entry read", 0 if marketplace_version({"plugins": [{"name": "fairy-tale", "version": "0.2.39"}]}) == "0.2.39" else 1, 0),
        ("marketplace entry missing", 0 if marketplace_version({"plugins": [{"name": "other", "version": "1.0.0"}]}) is None else 1, 0),
    ]
    # The rule above is pure; the entry point is not. Without these, the base
    # resolution and the HEAD refusal could be deleted and every control would
    # stay green -- the shape #117 closed by requiring a control of its own.
    import contextlib
    import io

    def quiet(rev: str) -> int:
        with contextlib.redirect_stdout(io.StringIO()):
            return do_check(rev)

    controls.append(("do_check: HEAD refused as base", quiet("HEAD"), 1))
    controls.append(("do_check: @ refused as base", quiet("@"), 1))
    # The refusal is about the commit the ref resolves to, not the word used to
    # name it. Without this, a comparison weakened to raw strings would still
    # reject "HEAD" and "@" while the exact SHA slipped through as a tautology.
    _, head_sha = git("rev-parse", "--verify", "HEAD^{commit}")
    head_sha = head_sha.strip()
    if head_sha:
        controls.append(("do_check: exact HEAD sha refused as base", quiet(head_sha), 1))
    controls.append(("do_check: unresolvable base refused", quiet("definitely-not-a-ref"), 1))
    # The positive for do_check is deliberately NOT here: its verdict depends on
    # what the branch has changed, so a control asserting green would pass or
    # fail on repository state rather than on this code. CI runs the real check
    # against the merge base in the same step, which is that positive.
    normalised = [
        (name, (1 if isinstance(result, list) and result else 0) if isinstance(result, list) else result, expected)
        for name, result, expected in controls
    ]
    failures = [name for name, actual, expected in normalised if actual != expected]
    if failures:
        for name in failures:
            print(f"[SELFTEST RED] unexpected version-bump result: {name}")
        return 1
    print(f"[SELFTEST GREEN] {len(normalised)} version-bump controls")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", metavar="REV", help="immutable base revision to compare against")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return run_selftest()
    if not args.base:
        parser.error("--base REV is required unless --selftest is given")
    return do_check(args.base)


if __name__ == "__main__":
    sys.exit(main())
