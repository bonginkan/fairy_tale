#!/usr/bin/env python3
"""Session-constant listing-overhead checks for the Fairy Tale skills (#58).

Every Claude Code session pays for each installed skill's frontmatter
description in the shared skill-listing budget (1% of the context window;
the combined description + when_to_use is truncated at 1,536 characters per
entry -- code.claude.com/docs/en/skills, fetched 2026-07-02). This checker
keeps that overhead bounded WITHOUT losing routing recall:

- C1 description_budget: per-skill description (+ when_to_use) stays within
  its recorded character budget.
- C2 trigger_recall_floor: slimming may never drop the representative trigger
  vocabulary (review gate: recall beats brevity; a missing trigger is RED).
- C3 duplicate_registration (--agent-home): the SAME agent home must not
  register a skill twice (local ~/.claude-style skills dir AND a plugin
  install). Classification is explicit -- stale-duplicate (byte-identical:
  remove the local copy), diverged-duplicate (must be reconciled), or
  intentional-override (allowed, requires a `.local-override` marker file in
  the local skill dir). Only the homes passed on the command line are
  scanned, so the 3-host .claude/.codex/.agents coexistence on one machine is
  never a false positive.
- C4 hook_floor: the SessionStart standing instruction keeps its essential
  safety/routing markers (budget, defensive-only, validation, skill trigger).

Usage:
  python3 scripts/skill_listing_overhead_check.py                # measure + gates
  python3 scripts/skill_listing_overhead_check.py --enforce
  python3 scripts/skill_listing_overhead_check.py --agent-home ~/.claude --enforce
  python3 scripts/skill_listing_overhead_check.py --selftest
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / "skills"
BYTES_PER_TOKEN = 4.0

# Recorded character budgets (description + when_to_use combined). Raising a
# budget is a reviewed change, not a local edit.
DESCRIPTION_BUDGETS = {
    "fairy-tale": 700,
    "fairy-tale-benchmark-feedback": 320,
    "fairy-tale-legal-feedback": 250,
    "japanese-wordplay-humor-detection": 420,
}

# Recall floor: representative trigger vocabulary that must survive any
# slimming (review gate, Increment 3). Checked case-insensitively.
REQUIRED_TRIGGERS = {
    "fairy-tale": (
        "loop",
        "spiral",
        "double-helix",
        "evolutionary",
        "e2e",
        "gui dogfood",
        "wwcd",
        "usage-aware",
        "closure",
        "negative-space",
        "excess",
        "migration",
        "research",
        "benchmark",
        "legal",
        "defensive security",
    ),
    "fairy-tale-benchmark-feedback": ("swe-bench pro", "hle", "exploitbench"),
    "fairy-tale-legal-feedback": ("legal", "closure sweep", "fairy fusion"),
    "japanese-wordplay-humor-detection": ("縦読み", "ダジャレ", "回文", "ユーモア", "verbatim"),
}

# Essential SessionStart standing-instruction markers (safety floor +
# routing trigger). Losing any of these is RED (review gate: hook slimming
# must keep residency/safety/routing information).
ESSENTIAL_HOOK_MARKERS = (
    "Residency active",
    "budget",
    "evidence-driven",
    "defensive-only",
    "Validate before claiming completion",
    "`fairy-tale` skill",
)

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def frontmatter_field(skill_md_text: str, field: str) -> str:
    match = FRONTMATTER_RE.match(skill_md_text)
    if not match:
        return ""
    block = match.group(1)
    lines = block.split("\n")
    value_lines: list[str] = []
    capturing = False
    for line in lines:
        if capturing:
            if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", line):
                break
            value_lines.append(line.strip())
            continue
        if line.startswith(f"{field}:"):
            capturing = True
            value_lines.append(line[len(field) + 1 :].strip())
    value = " ".join(v for v in value_lines if v).strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    return value


def listing_text(skill_dir: Path) -> str:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    description = frontmatter_field(text, "description")
    when = frontmatter_field(text, "when_to_use")
    return (description + (" " + when if when else "")).strip()


def check_descriptions(skills_root: Path, results: list[tuple[str, str, str]]) -> None:
    for skill, budget in DESCRIPTION_BUDGETS.items():
        skill_dir = skills_root / skill
        if not (skill_dir / "SKILL.md").exists():
            results.append(("description_budget", "red", f"{skill}: SKILL.md missing"))
            continue
        combined = listing_text(skill_dir)
        chars = len(combined)
        est_tokens = round(len(combined.encode("utf-8")) / BYTES_PER_TOKEN)
        if chars > budget:
            results.append(
                (
                    "description_budget",
                    "red",
                    f"{skill}: {chars} chars > budget {budget} (~{est_tokens} est tokens)",
                )
            )
        else:
            results.append(
                (
                    "description_budget",
                    "green",
                    f"{skill}: {chars} chars <= {budget} (~{est_tokens} est tokens)",
                )
            )
        lowered = combined.lower()
        missing = [t for t in REQUIRED_TRIGGERS.get(skill, ()) if t.lower() not in lowered]
        if missing:
            results.append(
                (
                    "trigger_recall_floor",
                    "red",
                    f"{skill}: missing required trigger(s): {', '.join(missing)}",
                )
            )
        else:
            results.append(
                (
                    "trigger_recall_floor",
                    "green",
                    f"{skill}: all {len(REQUIRED_TRIGGERS.get(skill, ()))} triggers present",
                )
            )


def classify_duplicate(local_dir: Path, plugin_dir: Path) -> tuple[str, str]:
    """Returns (classification, detail). Never 'unclassified': any state that
    does not match a known classification is itself RED."""
    if (local_dir / ".local-override").exists():
        return (
            "intentional-override",
            f"{local_dir} marked .local-override (allowed; plugin copy shadowed deliberately)",
        )
    local_skill = local_dir / "SKILL.md"
    plugin_skill = plugin_dir / "SKILL.md"
    if not local_skill.exists() or not plugin_skill.exists():
        return ("broken-duplicate", f"{local_dir} vs {plugin_dir}: SKILL.md missing on one side")
    if local_skill.read_bytes() == plugin_skill.read_bytes():
        return (
            "stale-duplicate",
            f"{local_dir} byte-identical to plugin copy {plugin_dir}: keep exactly ONE "
            "registration (remove whichever install is not maintained on this host); the "
            "duplicate double-pays the skill-listing budget",
        )
    return (
        "diverged-duplicate",
        f"{local_dir} differs from plugin copy {plugin_dir}: reconcile -- align both to the "
        "current release and keep exactly one registration, or mark the local dir with "
        ".local-override if the divergence is deliberate",
    )


def check_duplicates(agent_homes: list[Path], results: list[tuple[str, str, str]]) -> None:
    if not agent_homes:
        results.append(("duplicate_registration", "skipped", "no --agent-home given"))
        return
    found_any = False
    for home in agent_homes:
        for skill in DESCRIPTION_BUDGETS:
            local_dir = home / "skills" / skill
            plugin_dirs = sorted(home.glob(f"plugins/**/skills/{skill}"))
            if local_dir.is_dir() and plugin_dirs:
                found_any = True
                # Only the newest cached plugin version can be the live
                # registration; older version dirs in the cache are not
                # loaded and would only produce noise.
                plugin_dir = plugin_dirs[-1]
                classification, detail = classify_duplicate(local_dir, plugin_dir)
                status = "green" if classification == "intentional-override" else "red"
                results.append(
                    ("duplicate_registration", status, f"[{classification}] {detail}")
                )
    if not found_any:
        results.append(
            (
                "duplicate_registration",
                "green",
                f"no local+plugin double registration in: "
                + ", ".join(str(h) for h in agent_homes),
            )
        )


def check_hook_floor(results: list[tuple[str, str, str]], instruction: str | None = None) -> None:
    if instruction is None:
        sys.path.insert(0, str(ROOT / "scripts"))
        from fairy_tale_residency_check import STANDING_INSTRUCTION  # type: ignore

        instruction = STANDING_INSTRUCTION
    size = len(instruction.encode("utf-8"))
    missing = [m for m in ESSENTIAL_HOOK_MARKERS if m not in instruction]
    if missing:
        results.append(
            ("hook_floor", "red", f"standing instruction missing: {', '.join(missing)}")
        )
    else:
        results.append(
            (
                "hook_floor",
                "green",
                f"standing instruction {size} bytes; all {len(ESSENTIAL_HOOK_MARKERS)} "
                "essential markers present",
            )
        )


def run_checks(skills_root: Path, agent_homes: list[Path]) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []
    check_descriptions(skills_root, results)
    check_duplicates(agent_homes, results)
    check_hook_floor(results)
    return results


def selftest() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)

        def make_skill(root: Path, name: str, description: str) -> Path:
            d = root / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {description}\n---\n\n# X\n", encoding="utf-8"
            )
            return d

        # RED 1: over-budget description
        skills = tmp_root / "over" / "skills"
        make_skill(
            skills,
            "fairy-tale-legal-feedback",
            "legal closure sweep Fairy Fusion " + ("pad " * 120),
        )
        r: list[tuple[str, str, str]] = []
        check_descriptions(skills, r)
        if not any(c == "description_budget" and s == "red" for c, s, _ in r):
            failures.append("over-budget description did not go red")

        # RED 2: missing required trigger (over-slimmed)
        skills2 = tmp_root / "slim" / "skills"
        make_skill(skills2, "fairy-tale-legal-feedback", "short legal helper")
        r2: list[tuple[str, str, str]] = []
        check_descriptions(skills2, r2)
        red2 = [d for c, s, d in r2 if c == "trigger_recall_floor" and s == "red"]
        if not red2 or "closure sweep" not in red2[0]:
            failures.append("over-slimmed description did not trip the recall floor")

        # duplicate fixtures: same agent home with local + plugin copies
        home = tmp_root / "home"
        make_skill(home / "skills", "fairy-tale", "x")
        local = home / "skills" / "fairy-tale"
        plugin = home / "plugins" / "cache" / "ft" / "skills" / "fairy-tale"
        plugin.mkdir(parents=True)
        (plugin / "SKILL.md").write_bytes((local / "SKILL.md").read_bytes())

        # RED 3: stale duplicate (byte-identical)
        r3: list[tuple[str, str, str]] = []
        check_duplicates([home], r3)
        d3 = [d for c, s, d in r3 if s == "red"]
        if not d3 or "stale-duplicate" not in d3[0]:
            failures.append("stale duplicate not detected/classified")

        # RED 4: diverged duplicate
        (local / "SKILL.md").write_text("---\nname: fairy-tale\ndescription: y\n---\n", encoding="utf-8")
        r4: list[tuple[str, str, str]] = []
        check_duplicates([home], r4)
        d4 = [d for c, s, d in r4 if s == "red"]
        if not d4 or "diverged-duplicate" not in d4[0]:
            failures.append("diverged duplicate not detected/classified")

        # control: intentional override is allowed (green, still classified)
        (local / ".local-override").touch()
        r5: list[tuple[str, str, str]] = []
        check_duplicates([home], r5)
        d5 = [d for c, s, d in r5 if c == "duplicate_registration"]
        if not d5 or "intentional-override" not in d5[0] or any(
            s == "red" for c, s, _ in r5 if c == "duplicate_registration"
        ):
            failures.append("intentional override not classified as allowed")

        # control: unrelated agent home is NOT scanned (no 3-host false positive)
        other_home = tmp_root / "other-home"
        (other_home / "skills" / "fairy-tale").mkdir(parents=True)
        r6: list[tuple[str, str, str]] = []
        check_duplicates([tmp_root / "empty-home"], r6)
        if any(s == "red" for _, s, _ in r6):
            failures.append("unscanned home produced a false positive")

        # RED 5: hook essential marker loss
        r7: list[tuple[str, str, str]] = []
        check_hook_floor(r7, instruction="[fairy-tale] Residency active: trimmed away")
        if not any(c == "hook_floor" and s == "red" for c, s, _ in r7):
            failures.append("hook marker loss did not go red")

        # control: real repo state is green end-to-end
        r8 = run_checks(SKILLS_ROOT, [])
        for check, status, detail in r8:
            if status == "red":
                failures.append(f"repo control red: {check}: {detail}")

    if failures:
        for failure in failures:
            print(f"[SELFTEST RED] {failure}")
        return 1
    print(
        "[SELFTEST GREEN] budgets/recall-floor/duplicate-classification/hook-floor "
        "gates all trip; repo control green"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--agent-home",
        action="append",
        type=Path,
        default=None,
        help="agent home dir(s) to audit for local+plugin double registration; "
        "only the homes given are scanned (no cross-agent false positives)",
    )
    parser.add_argument("--enforce", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    results = run_checks(SKILLS_ROOT, args.agent_home or [])
    reds = 0
    for check, status, detail in results:
        print(f"[{status.upper():7}] {check}: {detail}")
        reds += status == "red"
    if args.enforce and reds:
        print(f"ENFORCE: {reds} red check(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
